"""
Asynchronous tracking pipeline with three parallel threads.

v11 — Returns to H60 velocity mode with sign-change lockout.

  H52 position mode (v10) was a dead end: each H52 command restarts
  acceleration from zero, so the PTU never builds continuous speed.
  At 35000 p/s with accel=15000, the accel phase alone is 40833 pulses —
  but each cycle's move is only ~17000 pulses. The PTU spent every cycle
  accelerating from standstill, making it slower than H60 velocity mode.

  H60 is the right command for continuous tracking — it maintains momentum.
  The problem with H60 was never the command itself, it was the control
  logic causing sign-flips at zero crossings (PTU reverses direction when
  the drone flies through center).

  This version combines ALL proven fixes from v2-v9 with a new sign-change
  lockout that prevents the zero-crossing reversal:

  FROM v8: tracking.py sends current position (not predicted) — eliminates
           double prediction.  No change needed to tracking.py.
  FROM v9: PAN_KP=2.0, PAN_KD=0.12, FF uses raw error for attenuation.
  FROM v6: 30Hz loop, command gate, stale-frame hold.
  FROM v7: Speed cap proportional to command magnitude.

  NEW — Sign-change lockout:
    When the pan command wants to reverse direction, don't send the reversal
    immediately. Instead, hold the previous direction (decaying) for up to
    LOCKOUT_FRAMES cycles. Only reverse if the new direction persists for
    that many frames. This prevents the D-term/EMA lag from causing a
    momentary false reversal at zero crossings, while still allowing genuine
    direction changes (when the error truly crosses and stays crossed).
"""

from __future__ import annotations

import logging
import math
import os
import threading
import time
from typing import Any, Dict, Optional

import cv2
from app.services.camera import _create_capture, _release_capture

logger = logging.getLogger(__name__)

_log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
os.makedirs(_log_dir, exist_ok=True)
_tracking_handler = logging.FileHandler(os.path.join(_log_dir, "tracking.log"))
_tracking_handler.setLevel(logging.DEBUG)
_tracking_handler.setFormatter(
    logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
_tracking_logger = logging.getLogger("tracking_pipeline")
_tracking_logger.addHandler(_tracking_handler)
_tracking_logger.setLevel(logging.DEBUG)
_tracking_logger.propagate = False

_frame_lock = threading.Lock()
_current_frame: Optional[cv2.Mat] = None
_current_frame_time: float = 0.0
_pipeline_stop = threading.Event()

_capture_thread: Optional[threading.Thread] = None
_detection_thread: Optional[threading.Thread] = None
_ptu_thread: Optional[threading.Thread] = None

_result_lock = threading.Lock()
_latest_result: Optional[Dict[str, Any]] = None

# ---------------------------------------------------------------------------
# PTU controller constants
# ---------------------------------------------------------------------------
PTU_INVERT_PAN  = True
PTU_INVERT_TILT = False

LASER_OFFSET_X = -10
LASER_OFFSET_Y = 40
PTU_HFOV_DEG = 60.0

# ── PID gains (from v9) ──────────────────────────────────────────────────
PAN_KP  = 2.80
PAN_KI  = 0.005
PAN_KD  = 0.12

TILT_KP = 0.90
TILT_KI = 0.005
TILT_KD = 0.06

PTU_GAIN_VX = 1.5
PTU_GAIN_VY = 0.8

PAN_INTEGRAL_CLAMP  = 35.0
TILT_INTEGRAL_CLAMP = 32.0
INTEGRAL_ENABLE_THRESHOLD_PX = 20

PTU_MAX_SPEED = 11000
PTU_MIN_SPEED = 350

PTU_LOOP_SEC = 0.033      # 30 Hz

PTU_DEADBAND_PX  = 4
PTU_VEL_DEADBAND = 9

PAN_ERROR_EMA_ALPHA  = 0.50
TILT_ERROR_EMA_ALPHA = 0.60

PTU_MAX_VECTOR = 100

# FF (from v9 — uses raw error for attenuation)
PREDICTION_LEAD_SEC = 0.15
FF_GAIN_MULTIPLIER  = 2.0
FF_ATTEN_ERROR_PX   = 800.0
FF_MIN_GAIN         = 0.02

PREDICTION_MAX_AGE_SEC = 0.10
PTU_COAST_CYCLES       = 10
PTU_STOP_COAST_FRAMES  = 5

SPEED_VEL_MAX_CONTRIBUTION = 7000
SPEED_ERR_STOPPED_MAX      = 4000
SPEED_ERR_MAX_CONTRIBUTION = 5000
DRONE_MAX_VEL_PX_S         = 750.0
DRONE_STOP_VEL_THRESHOLD   = 4.0
DRONE_SPEED_EMA_ALPHA      = 0.80

STALE_REPEAT_WARN  = 3
STALE_REPEAT_COAST = 10
STALE_SPEED_DECAY  = 0.85
STALE_CMD_DECAY    = 0.90

CMD_RATE_LIMIT    = 50
CMD_GATE_DA       = 3
CMD_GATE_DSPD     = 100
CMD_GATE_MAX_SKIP = 5
SPEED_CAP_BASE = 800
SPEED_PER_CMD     = 250

# ── Sign-change lockout ──────────────────────────────────────────────────
# When pan command reverses sign, don't send the reversal immediately.
# Hold previous direction (decaying) for up to LOCKOUT_FRAMES.
# Only allow the reversal if it persists for that many consecutive frames
# OR if the raw error has clearly crossed (error confirms the reversal).
LOCKOUT_FRAMES         = 20     # ~100ms at 30Hz
LOCKOUT_ERROR_OVERRIDE = 40    # if |raw_err_x| > this in the NEW direction, skip lockout


# ---------------------------------------------------------------------------
def _capture_loop() -> None:
    global _current_frame, _current_frame_time
    cap = _create_capture()
    if cap is None:
        logger.error("Pipeline: failed to create capture, capture thread exiting")
        return
    try:
        while not _pipeline_stop.is_set():
            if cap.grab():
                ret, frame = cap.retrieve()
                if ret and frame is not None:
                    now = time.time()
                    with _frame_lock:
                        _current_frame      = frame
                        _current_frame_time = now
            else:
                logger.warning("Stream lost, attempting reconnect…")
                _release_capture(cap)
                cap = None
                time.sleep(1.0)
                cap = _create_capture()
                if cap is None:
                    logger.error("Reconnect failed, will retry in 1 s")
    except Exception as e:
        logger.error("Pipeline capture thread error: %s", e, exc_info=True)
    finally:
        if cap is not None:
            _release_capture(cap)


def _detection_loop() -> None:
    from app.api.routes.tracking import _run_detection_on_frame
    global _latest_result
    tracks: Dict = {}
    next_track_id = 0
    last_frame_time = 0.0
    try:
        while not _pipeline_stop.is_set():
            with _frame_lock:
                frame = _current_frame
                frame_time = _current_frame_time
            if frame is None or frame_time <= last_frame_time:
                time.sleep(0.002)
                continue
            last_frame_time = frame_time
            try:
                tracks, next_track_id, payload = _run_detection_on_frame(
                    frame, tracks, next_track_id)
                with _result_lock:
                    _latest_result = payload
            except Exception as e:
                logger.error("Pipeline detection error: %s", e, exc_info=True)
    except Exception as e:
        logger.error("Pipeline detection thread error: %s", e, exc_info=True)


class _PIDAxis:
    def __init__(self, kp, ki, kd, integral_clamp, dt):
        self.kp, self.ki, self.kd = kp, ki, kd
        self.integral_clamp, self.dt = integral_clamp, dt
        self.integral = self.prev_measurement = 0.0
        self._init = False

    def reset(self):
        self.integral = self.prev_measurement = 0.0
        self._init = False

    def compute(self, error, measurement, enable_integral=True):
        p = self.kp * error
        if enable_integral:
            self.integral += error * self.dt
            self.integral = max(-self.integral_clamp, min(self.integral_clamp, self.integral))
        i = self.ki * self.integral
        if not self._init:
            self.prev_measurement = measurement
            self._init = True
        d_meas = (measurement - self.prev_measurement) / self.dt
        self.prev_measurement = measurement
        return p + i + (-self.kd * d_meas)


def _scale_axes(vx, vy):
    S = 3.5
    cx, cy = vx * S, vy * S
    mx = max(abs(cx), abs(cy), 1e-9)
    if mx > PTU_MAX_VECTOR:
        r = PTU_MAX_VECTOR / mx
        cx, cy = cx * r, cy * r
    return int(round(cx)), int(round(cy))


def _cap_speed(a1, a2, speed):
    return min(speed, SPEED_CAP_BASE + max(abs(a1), abs(a2)) * SPEED_PER_CMD)

# ---------------------------------------------------------------------------
def _ptu_control_loop() -> None:
    from app.services import config as config_service
    from app.services import ptu   as ptu_service
    from app.services import logger as ptu_logger

    dt = PTU_LOOP_SEC
    pid_pan  = _PIDAxis(PAN_KP,  PAN_KI,  PAN_KD,  PAN_INTEGRAL_CLAMP,  dt)
    pid_tilt = _PIDAxis(TILT_KP, TILT_KI, TILT_KD, TILT_INTEGRAL_CLAMP, dt)

    smooth_err_x = smooth_err_y = 0.0
    was_stopped = True
    coast_cycles = 0
    last_width, last_height = 1920.0, 1080.0
    last_deg_per_px = PTU_HFOV_DEG / 1920.0
    smooth_drone_speed = 0.0
    _coast_stop_count = 0

    _last_pred_key: Optional[tuple] = None
    _stale_repeat_count = 0
    _stale_speed_factor = 1.0

    _prev_a1 = _prev_a2 = 0
    _sent_a1 = _sent_a2 = _sent_spd = 0
    _skip_count = 0

    _last_a1 = _last_a2 = 0
    _last_speed = PTU_MIN_SPEED

    # Sign-change lockout state
    _last_pan_sign = 0       # +1 or -1
    _reversal_count = 0      # how many frames the new sign has persisted

    def _stop_ptu():
        nonlocal was_stopped, _sent_a1, _sent_a2, _sent_spd
        if not was_stopped:
            ptu_service.write_raw(b"H65E")
            ptu_logger.PTU_EVENT_LOG.info("h60_stop: cmd=H65E")
            was_stopped = True
            _sent_a1 = _sent_a2 = _sent_spd = 0

    def _reset_all():
        nonlocal smooth_err_x, smooth_err_y, coast_cycles, smooth_drone_speed
        nonlocal _coast_stop_count, _last_pred_key, _stale_repeat_count, _stale_speed_factor
        nonlocal _prev_a1, _prev_a2, _sent_a1, _sent_a2, _sent_spd, _skip_count
        nonlocal _last_a1, _last_a2, _last_speed, _last_pan_sign, _reversal_count
        pid_pan.reset(); pid_tilt.reset()
        smooth_err_x = smooth_err_y = 0.0
        coast_cycles = 0; smooth_drone_speed = 0.0; _coast_stop_count = 0
        _last_pred_key = None; _stale_repeat_count = 0; _stale_speed_factor = 1.0
        _prev_a1 = _prev_a2 = 0; _sent_a1 = _sent_a2 = _sent_spd = 0; _skip_count = 0
        _last_a1 = _last_a2 = 0; _last_speed = PTU_MIN_SPEED
        _last_pan_sign = 0; _reversal_count = 0

    def _send_h60(a1, a2, speed):
        nonlocal was_stopped, _sent_a1, _sent_a2, _sent_spd, _skip_count
        cmd = f"H60,{a1},{a2},{speed}E".encode("ascii")
        if ptu_service.write_raw(cmd):
            was_stopped = False
            _sent_a1, _sent_a2, _sent_spd = a1, a2, speed
            _skip_count = 0
            ptu_logger.PTU_EVENT_LOG.debug(
                "h60_velocity: cmd=%s a1=%d a2=%d speed=%d",
                cmd.decode("ascii"), a1, a2, speed)
            try:
                import queue as _q
                ptu_service._command_broadcast_queue.put_nowait(cmd.decode("ascii"))
            except Exception:
                try:
                    ptu_service._command_broadcast_queue.get_nowait()
                    ptu_service._command_broadcast_queue.put_nowait(cmd.decode("ascii"))
                except Exception:
                    pass

    def _should_send(a1, a2, speed):
        nonlocal _skip_count
        da = max(abs(a1 - _sent_a1), abs(a2 - _sent_a2))
        ds = abs(speed - _sent_spd)
        if da >= CMD_GATE_DA or ds >= CMD_GATE_DSPD:
            return True
        _skip_count += 1
        return _skip_count >= CMD_GATE_MAX_SKIP

    try:
        while not _pipeline_stop.is_set():
            loop_start = time.monotonic()

            if not config_service.get_auto_tracking() or not ptu_service.is_connected():
                _stop_ptu(); _reset_all()
                time.sleep(max(0, dt - (time.monotonic() - loop_start)))
                continue

            pred = _get_last_prediction_from_pipeline()

            if pred is None:
                coast_cycles += 1
                if coast_cycles > PTU_COAST_CYCLES:
                    _stop_ptu()
                    pid_pan.integral *= 0.9; pid_tilt.integral *= 0.9
                    smooth_err_x *= 0.9; smooth_err_y *= 0.9
                time.sleep(max(0, dt - (time.monotonic() - loop_start)))
                continue

            pred_age = time.time() - pred.get("timestamp", time.time())
            if pred_age > PREDICTION_MAX_AGE_SEC:
                coast_cycles += 1
                if coast_cycles > PTU_COAST_CYCLES:
                    _stop_ptu()
                time.sleep(max(0, dt - (time.monotonic() - loop_start)))
                continue

            coast_cycles = 0
            pred_x, pred_y = pred["x"], pred["y"]
            width, height = pred["width"], pred["height"]
            vx_kal, vy_kal = pred.get("vx", 0.0), pred.get("vy", 0.0)
            last_width, last_height = width, height

            # ── Stale detection ──────────────────────────────────────────
            pred_key = (round(pred_x, 1), round(pred_y, 1),
                        round(vx_kal, 1), round(vy_kal, 1))
            if pred_key == _last_pred_key:
                _stale_repeat_count += 1
            else:
                _stale_repeat_count = 0
                _stale_speed_factor = 1.0
            _last_pred_key = pred_key

            if _stale_repeat_count >= STALE_REPEAT_COAST:
                _stop_ptu()
                _stale_speed_factor *= STALE_SPEED_DECAY
                time.sleep(max(0, dt - (time.monotonic() - loop_start)))
                continue
            elif _stale_repeat_count >= STALE_REPEAT_WARN:
                _stale_speed_factor = max(_stale_speed_factor * STALE_SPEED_DECAY, 0.3)

            # ── Stale frame: hold with decay ─────────────────────────────
            if _stale_repeat_count > 0:
                a1 = int(round(_last_a1 * STALE_CMD_DECAY))
                a2 = int(round(_last_a2 * STALE_CMD_DECAY))
                spd = max(int(_last_speed * STALE_CMD_DECAY), PTU_MIN_SPEED)
                _prev_a1, _prev_a2 = a1, a2
                if _should_send(a1, a2, spd):
                    _send_h60(a1, a2, spd)
                _tracking_logger.info(
                    "target=(%.1f,%.1f) spd=%d cmd=(%d,%d) stale=%d HOLD",
                    pred_x, pred_y, spd, a1, a2, _stale_repeat_count)
                time.sleep(max(0, dt - (time.monotonic() - loop_start)))
                continue

            # ── Fresh: full PID ──────────────────────────────────────────
            aim_x = (width / 2.0) + LASER_OFFSET_X
            aim_y = (height / 2.0) - LASER_OFFSET_Y
            raw_err_x = pred_x - aim_x
            raw_err_y = aim_y - pred_y

            smooth_err_x = PAN_ERROR_EMA_ALPHA * raw_err_x + (1.0 - PAN_ERROR_EMA_ALPHA) * smooth_err_x
            smooth_err_y = TILT_ERROR_EMA_ALPHA * raw_err_y + (1.0 - TILT_ERROR_EMA_ALPHA) * smooth_err_y
            error_px = math.hypot(smooth_err_x, smooth_err_y)
            raw_error_px = math.hypot(raw_err_x, raw_err_y)

            drone_speed_raw = math.hypot(vx_kal, vy_kal)
            smooth_drone_speed = (DRONE_SPEED_EMA_ALPHA * drone_speed_raw
                                  + (1.0 - DRONE_SPEED_EMA_ALPHA) * smooth_drone_speed)
            drone_stopped = smooth_drone_speed < DRONE_STOP_VEL_THRESHOLD

            # Speed
            if drone_stopped:
                er = min(error_px / (width / 4.0), 1.0)
                speed_base = int(PTU_MIN_SPEED + er * SPEED_ERR_STOPPED_MAX)
            else:
                vr = min(smooth_drone_speed / DRONE_MAX_VEL_PX_S, 1.0)
                speed_base = int(PTU_MIN_SPEED + vr * SPEED_VEL_MAX_CONTRIBUTION)
            ne = min(error_px / (width / 4.0), 1.0)
            speed = min(speed_base + int(ne * SPEED_ERR_MAX_CONTRIBUTION), PTU_MAX_SPEED)
            speed = max(int(speed * _stale_speed_factor), PTU_MIN_SPEED)

            # PID
            deg_per_px = PTU_HFOV_DEG / max(width, 1.0)
            last_deg_per_px = deg_per_px
            enable_int = error_px < INTEGRAL_ENABLE_THRESHOLD_PX

            out_x = pid_pan.compute(smooth_err_x * deg_per_px,
                                    raw_err_x * deg_per_px, enable_int)

            # if abs(raw_err_x) < 150:
            #     out_x *= 0.6fv

            out_y = pid_tilt.compute(smooth_err_y * deg_per_px,
                                     raw_err_y * deg_per_px, enable_int)

            # if abs(raw_err_y) < 150:
            #     out_y *= 0.5

            # FF with raw-error attenuation (v9)
            ff_raw = 1.0 - min(raw_error_px / FF_ATTEN_ERROR_PX, 1.0)
            ff_atten = max(FF_MIN_GAIN, ff_raw * ff_raw)
            ff_vx = vx_kal * deg_per_px * PTU_GAIN_VX * PREDICTION_LEAD_SEC * FF_GAIN_MULTIPLIER * ff_atten
            ff_vy = vy_kal * deg_per_px * PTU_GAIN_VY * PREDICTION_LEAD_SEC * FF_GAIN_MULTIPLIER * ff_atten

            vx = out_x + ff_vx
            vy = out_y - ff_vy

            a1, a2 = _scale_axes(vx, vy)
            if PTU_INVERT_PAN:  a1 = -a1
            if PTU_INVERT_TILT: a2 = -a2

            # Rate limit
            a1 = int(round(_prev_a1 + max(-CMD_RATE_LIMIT, min(CMD_RATE_LIMIT, a1 - _prev_a1))))
            a2 = int(round(_prev_a2 + max(-CMD_RATE_LIMIT, min(CMD_RATE_LIMIT, a2 - _prev_a2))))

            # ── Sign-change lockout (prevents zero-crossing reversal) ────
            # If pan command wants to reverse, check if it's a genuine
            # direction change or just a momentary D-term/EMA artifact.
            new_sign = 1 if a1 > 0 else (-1 if a1 < 0 else 0)
            if new_sign != 0 and _last_pan_sign != 0 and new_sign != _last_pan_sign:
                # Command wants to reverse
                _reversal_count += 1
                # Allow reversal if:
                # 1) raw error clearly confirms the new direction, OR
                # 2) reversal has persisted for LOCKOUT_FRAMES
                err_confirms = (raw_err_x > LOCKOUT_ERROR_OVERRIDE and new_sign < 0) or \
                               (raw_err_x < -LOCKOUT_ERROR_OVERRIDE and new_sign > 0)
                               # Note: inverted because PTU_INVERT_PAN
                if not err_confirms and _reversal_count < LOCKOUT_FRAMES:
                    # Suppress reversal — decay previous command instead
                    a1 = int(round(_prev_a1 * 0.5))
                    _tracking_logger.debug("LOCKOUT: suppressed pan reversal, holding a1=%d", a1)
                else:
                    # Genuine reversal — allow it
                    _last_pan_sign = new_sign
                    _reversal_count = 0
            else:
                if new_sign != 0:
                    _last_pan_sign = new_sign
                _reversal_count = 0

            _prev_a1, _prev_a2 = a1, a2

            speed = _cap_speed(a1, a2, speed)
            _last_a1, _last_a2, _last_speed = a1, a2, speed

            # Stop decision
            cmd_small = abs(a1) < PTU_VEL_DEADBAND and abs(a2) < PTU_VEL_DEADBAND
            err_small = abs(raw_err_x) < PTU_DEADBAND_PX * 2 and abs(raw_err_y) < PTU_DEADBAND_PX * 2
            if cmd_small and err_small and drone_stopped:
                _coast_stop_count += 1
            else:
                _coast_stop_count = 0
            if _coast_stop_count >= PTU_STOP_COAST_FRAMES:
                _stop_ptu()
            else:
                if _should_send(a1, a2, speed):
                    _send_h60(a1, a2, speed)

            _tracking_logger.info(
                "target=(%.1f,%.1f) aim=(%.1f,%.1f) "
                "vel=(%.1f,%.1f)px/s drone_spd=%.1f(smooth=%.1f) stopped=%s "
                "spd=%d err=(%.1f,%.1f)px cmd=(%d,%d) "
                "stale=%d sf=%.2f rev=%d",
                pred_x, pred_y, aim_x, aim_y,
                vx_kal, vy_kal, drone_speed_raw, smooth_drone_speed, drone_stopped,
                speed, raw_err_x, raw_err_y, a1, a2,
                _stale_repeat_count, _stale_speed_factor, _reversal_count)

            _tracking_logger.debug(
                "err=(%.1f,%.1f)px smooth=(%.1f,%.1f)px "
                "pid=(%.2f,%.2f) ff=(%.2f,%.2f) ff_atten=%.2f int=(%.3f,%.3f) "
                "cmd=(%d,%d) speed=%d age=%.3fs",
                raw_err_x, raw_err_y, smooth_err_x, smooth_err_y,
                out_x, out_y, ff_vx, ff_vy, ff_atten,
                pid_pan.integral, pid_tilt.integral,
                a1, a2, speed, pred_age)

            time.sleep(max(0, dt - (time.monotonic() - loop_start)))

    except Exception as e:
        logger.error("Pipeline PTU control thread error: %s", e, exc_info=True)


# ---------------------------------------------------------------------------
def get_current_frame_for_stream() -> Optional[cv2.Mat]:
    with _frame_lock:
        return _current_frame

def _get_last_prediction_from_pipeline():
    from app.api.routes.tracking import get_last_prediction
    return get_last_prediction()

def start_pipeline():
    global _capture_thread, _detection_thread, _ptu_thread
    if _capture_thread is not None and _capture_thread.is_alive():
        logger.warning("Pipeline already running"); return
    _pipeline_stop.clear()
    _capture_thread   = threading.Thread(target=_capture_loop,     daemon=True, name="capture")
    _detection_thread = threading.Thread(target=_detection_loop,   daemon=True, name="detection")
    _ptu_thread       = threading.Thread(target=_ptu_control_loop, daemon=True, name="ptu")
    _capture_thread.start(); _detection_thread.start(); _ptu_thread.start()
    logger.info("Tracking pipeline started (v11 — H60 with sign-change lockout)")

def stop_pipeline():
    global _capture_thread, _detection_thread, _ptu_thread
    _pipeline_stop.set()
    for t in (_capture_thread, _detection_thread, _ptu_thread):
        if t is not None and t.is_alive(): t.join(timeout=2.0)
    _capture_thread = _detection_thread = _ptu_thread = None
    logger.info("Tracking pipeline stopped")

def get_latest_result():
    with _result_lock:
        return dict(_latest_result) if _latest_result else None

def is_pipeline_running():
    return _capture_thread is not None and _capture_thread.is_alive()