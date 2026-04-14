"""
Asynchronous tracking pipeline with three parallel threads:
  Thread 1: Grab frames continuously -> Shared Buffer
  Thread 2: Run detection on frames from buffer -> shared_target_position
  Thread 3: PID + feedforward velocity-mode PTU controller (H60)
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

# --- GLOBAL SHARED STATE ---
_frame_lock = threading.Lock()
_current_frame: Optional[cv2.Mat] = None
_current_frame_time: float = 0.0
_pipeline_stop = threading.Event()

# Thread handles
_capture_thread: Optional[threading.Thread] = None
_detection_thread: Optional[threading.Thread] = None
_ptu_thread: Optional[threading.Thread] = None

# Shared result for WebSocket consumers
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

PAN_KP  = 3.50
PAN_KI  = 0.0
PAN_KD  = 0.12 

TILT_KP = 1.00
TILT_KI = 0.0
TILT_KD = 0.0
                 # tilt swings at 13 px error due to jitter/dt amplification)

PTU_GAIN_VX = 1.0   # was 1.0
PTU_GAIN_VY = 0.8

PAN_INTEGRAL_CLAMP  = 35.0
TILT_INTEGRAL_CLAMP = 32.0

INTEGRAL_ENABLE_THRESHOLD_PX = 8    # was 5

PTU_MAX_SPEED = 11000
PTU_MIN_SPEED = 1500
PTU_MIN_DRIVE = 25

PTU_LOOP_SEC = 0.015  # ~67 Hz

PTU_DEADBAND_PX  = 5   # kept for coasting logic only — NOT used to stop PTU
PTU_VEL_DEADBAND = 8   # stop only when final command vector is this small

PAN_ERROR_EMA_ALPHA  = 0.75
TILT_ERROR_EMA_ALPHA = 0.50   # heavier smoothing on noisy tilt axis

PTU_MAX_VECTOR = 100

PREDICTION_LEAD_SEC    = 0.20
PREDICTION_MAX_AGE_SEC = 0.05
PTU_COAST_CYCLES       = 10
PTU_STOP_COAST_FRAMES  = 8      # frames command must stay small before PTU stops (~0.12s)

# ---------------------------------------------------------------------------
# Velocity-based speed model constants
# ---------------------------------------------------------------------------
SPEED_VEL_MAX_CONTRIBUTION = 7000
SPEED_ERR_STOPPED_MAX      = 4000   # speed bonus when drone stopped but error large
SPEED_ERR_MAX_CONTRIBUTION = 5000   # extra speed units for gap-closing
DRONE_MAX_VEL_PX_S         = 350.0  # px/s considered "full speed"
DRONE_STOP_VEL_THRESHOLD   = 8.0
DRONE_SPEED_EMA_ALPHA      = 0.50   # smoothing for drone speed estimate


# ---------------------------------------------------------------------------
# Thread 1 — continuous frame capture
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


# ---------------------------------------------------------------------------
# Thread 2 — YOLO detection + Kalman tracking
# ---------------------------------------------------------------------------
def _detection_loop() -> None:
    from app.api.routes.tracking import _run_detection_on_frame

    global _latest_result
    tracks: Dict    = {}
    next_track_id   = 0
    last_frame_time = 0.0

    try:
        while not _pipeline_stop.is_set():
            with _frame_lock:
                frame      = _current_frame
                frame_time = _current_frame_time

            if frame is None or frame_time <= last_frame_time:
                time.sleep(0.002)
                continue

            last_frame_time = frame_time

            try:
                tracks, next_track_id, payload = _run_detection_on_frame(
                    frame, tracks, next_track_id
                )
                with _result_lock:
                    _latest_result = payload
            except Exception as e:
                logger.error("Pipeline detection error: %s", e, exc_info=True)
    except Exception as e:
        logger.error("Pipeline detection thread error: %s", e, exc_info=True)


# ---------------------------------------------------------------------------
# PID state container
# ---------------------------------------------------------------------------
class _PIDAxis:
    def __init__(
        self, kp: float, ki: float, kd: float, integral_clamp: float, dt: float
    ):
        self.kp             = kp
        self.ki             = ki
        self.kd             = kd
        self.integral_clamp = integral_clamp
        self.dt             = dt
        self.integral: float         = 0.0
        self.prev_measurement: float = 0.0
        self._initialised: bool      = False

    def reset(self) -> None:
        self.integral         = 0.0
        self.prev_measurement = 0.0
        self._initialised     = False

    def compute(
        self, error: float, measurement: float, enable_integral: bool = True
    ) -> float:
        p_term = self.kp * error

        if enable_integral:
            self.integral += error * self.dt
            self.integral  = max(
                -self.integral_clamp, min(self.integral_clamp, self.integral)
            )
        i_term = self.ki * self.integral

        if not self._initialised:
            self.prev_measurement = measurement
            self._initialised     = True
        d_meas = (measurement - self.prev_measurement) / self.dt
        self.prev_measurement = measurement
        d_term = -self.kd * d_meas

        return p_term + i_term + d_term


# ---------------------------------------------------------------------------
# Thread 3 — PID + feedforward PTU controller (H60)
# ---------------------------------------------------------------------------
def _ptu_control_loop() -> None:
    from app.services import config as config_service
    from app.services import ptu   as ptu_service

    dt = PTU_LOOP_SEC

    pid_pan  = _PIDAxis(PAN_KP,  PAN_KI,  PAN_KD,  PAN_INTEGRAL_CLAMP,  dt)
    pid_tilt = _PIDAxis(TILT_KP, TILT_KI, TILT_KD, TILT_INTEGRAL_CLAMP, dt)

    smooth_err_x: float = 0.0
    smooth_err_y: float = 0.0
    # Per-axis alphas — do NOT reassign these inside the loop
    alpha_x = PAN_ERROR_EMA_ALPHA
    alpha_y = TILT_ERROR_EMA_ALPHA

    was_stopped  = True
    coast_cycles = 0

    last_width:  float = 1280.0
    last_height: float = 720.0
    last_deg_per_px: float = PTU_HFOV_DEG / 1280.0

    smooth_drone_speed: float = 0.0
    _coast_stop_count:  int   = 0

    def _stop_ptu() -> None:
        nonlocal was_stopped
        if not was_stopped:
            ptu_service.write_raw(b"H65E")
            was_stopped = True

    def _reset_all() -> None:
        nonlocal smooth_err_x, smooth_err_y, coast_cycles, smooth_drone_speed, _coast_stop_count
        pid_pan.reset()
        pid_tilt.reset()
        smooth_err_x       = 0.0
        smooth_err_y       = 0.0
        coast_cycles       = 0
        smooth_drone_speed = 0.0
        _coast_stop_count  = 0

    def _send_h60(a1: int, a2: int, speed: int) -> None:
        nonlocal was_stopped
        cmd_bytes = f"H60,{a1},{a2},{speed}E".encode("ascii")
        if ptu_service.write_raw(cmd_bytes):
            was_stopped = False
            try:
                import queue as _q
                ptu_service._command_broadcast_queue.put_nowait(
                    cmd_bytes.decode("ascii")
                )
            except (_q.Full, Exception):
                try:
                    ptu_service._command_broadcast_queue.get_nowait()
                    ptu_service._command_broadcast_queue.put_nowait(
                        cmd_bytes.decode("ascii")
                    )
                except Exception:
                    pass

    try:
        while not _pipeline_stop.is_set():
            loop_start = time.monotonic()

            if not config_service.get_auto_tracking() or not ptu_service.is_connected():
                _stop_ptu()
                _reset_all()
                elapsed = time.monotonic() - loop_start
                time.sleep(max(0, dt - elapsed))
                continue

            pred = _get_last_prediction_from_pipeline()

            # ── No prediction: coast or stop ─────────────────────────────────
            if pred is None:
                coast_cycles += 1
                if coast_cycles > PTU_COAST_CYCLES:
                    _stop_ptu()
                    pid_pan.integral  *= 0.90
                    pid_tilt.integral *= 0.90
                    smooth_err_x      *= 0.9
                    smooth_err_y      *= 0.9
                    smooth_drone_speed *= 0.9
                else:
                    error_px = (smooth_err_x**2 + smooth_err_y**2) ** 0.5
                    if error_px >= PTU_DEADBAND_PX:
                        decay        = 0.85
                        smooth_err_x *= decay
                        smooth_err_y *= decay
                        vx = smooth_err_x * last_deg_per_px * PAN_KP  * 0.5
                        vy = smooth_err_y * last_deg_per_px * TILT_KP * 0.5
                        max_v = max(abs(vx), abs(vy), 1e-6)
                        scale = min(PTU_MAX_VECTOR / max_v, PTU_MAX_VECTOR)
                        a1 = int(round(vx * scale))
                        a2 = int(round(vy * scale))
                        if PTU_INVERT_PAN:  a1 = -a1
                        if PTU_INVERT_TILT: a2 = -a2
                        norm_err = min(error_px / (last_width / 4.0), 1.0)
                        speed    = int(PTU_MIN_SPEED + norm_err * (PTU_MAX_SPEED - PTU_MIN_SPEED))
                        _send_h60(a1, a2, speed)
                    else:
                        _stop_ptu()

                elapsed = time.monotonic() - loop_start
                time.sleep(max(0, dt - elapsed))
                continue

            # ── Stale prediction ──────────────────────────────────────────────
            pred_age = time.time() - pred.get("timestamp", time.time())
            if pred_age > PREDICTION_MAX_AGE_SEC:
                coast_cycles += 1
                if coast_cycles > PTU_COAST_CYCLES:
                    _stop_ptu()
                    pid_pan.integral  *= 0.90
                    pid_tilt.integral *= 0.90
                elapsed = time.monotonic() - loop_start
                time.sleep(max(0, dt - elapsed))
                continue

            # ── Valid prediction ──────────────────────────────────────────────
            coast_cycles = 0

            pred_x  = pred["x"]
            pred_y  = pred["y"]
            width   = pred["width"]
            height  = pred["height"]
            vx_kal  = pred.get("vx", 0.0)
            vy_kal  = pred.get("vy", 0.0)

            last_width  = width
            last_height = height

            aim_x = (width  / 2.0) + LASER_OFFSET_X
            aim_y = (height / 2.0) - LASER_OFFSET_Y

            raw_err_x = pred_x - aim_x
            raw_err_y = aim_y  - pred_y

            # Per-axis EMA — tilt smoothed more heavily to suppress jitter
            smooth_err_x = alpha_x * raw_err_x + (1.0 - alpha_x) * smooth_err_x
            smooth_err_y = alpha_y * raw_err_y + (1.0 - alpha_y) * smooth_err_y

            error_px = (smooth_err_x**2 + smooth_err_y**2) ** 0.5

            # ── Drone speed tracking ──────────────────────────────────────────
            drone_speed_raw    = math.hypot(vx_kal, vy_kal)
            smooth_drone_speed = (
                DRONE_SPEED_EMA_ALPHA * drone_speed_raw
                + (1.0 - DRONE_SPEED_EMA_ALPHA) * smooth_drone_speed
            )
            drone_stopped = smooth_drone_speed < DRONE_STOP_VEL_THRESHOLD

            # ── Speed model: velocity base + error correction ─────────────────
            # speed_base stays HIGH while drone moves regardless of pixel error.
            # speed_correction adds extra speed to close a gap faster.
            # Both collapse naturally when drone stops and error is zero.
            if drone_stopped:
                # Drone stopped: still scale speed by error so PTU closes the gap
                err_ratio  = min(error_px / (width / 4.0), 1.0)
                speed_base = int(PTU_MIN_SPEED + err_ratio * SPEED_ERR_STOPPED_MAX)
            else:
                vel_ratio  = min(smooth_drone_speed / DRONE_MAX_VEL_PX_S, 1.0)
                speed_base = int(PTU_MIN_SPEED + vel_ratio * SPEED_VEL_MAX_CONTRIBUTION)

            norm_err         = min(error_px / (width / 4.0), 1.0)
            speed_correction = int(norm_err * SPEED_ERR_MAX_CONTRIBUTION)
            speed            = min(speed_base + speed_correction, PTU_MAX_SPEED)

            # ── PID + feedforward ─────────────────────────────────────────────
            deg_per_px      = PTU_HFOV_DEG / max(width, 1.0)
            last_deg_per_px = deg_per_px

            enable_int = error_px < INTEGRAL_ENABLE_THRESHOLD_PX

            out_x = pid_pan.compute(
                smooth_err_x * deg_per_px,
                raw_err_x    * deg_per_px,
                enable_integral=enable_int,
            )
            out_y = pid_tilt.compute(
                smooth_err_y * deg_per_px,
                raw_err_y    * deg_per_px,
                enable_integral=enable_int,
            )

            ff_vx = vx_kal * deg_per_px * PTU_GAIN_VX * PREDICTION_LEAD_SEC * 10.0
            ff_vy = vy_kal * deg_per_px * PTU_GAIN_VY * PREDICTION_LEAD_SEC * 10.0

            vx = out_x + ff_vx
            vy = out_y - ff_vy

            # ── Scale to PTU command range (−100 … 100) ───────────────────────
            max_v = max(abs(vx), abs(vy), 1e-6)
            scale = min(PTU_MAX_VECTOR / max_v, PTU_MAX_VECTOR)
            a1 = int(round(vx * scale))
            a2 = int(round(vy * scale))

            if PTU_INVERT_PAN:  a1 = -a1
            if PTU_INVERT_TILT: a2 = -a2

            # Minimum drive to overcome stiction
            if abs(a1) < PTU_MIN_DRIVE and abs(raw_err_x) > 1:
                a1 = PTU_MIN_DRIVE if a1 >= 0 else -PTU_MIN_DRIVE
            if abs(a2) < PTU_MIN_DRIVE and abs(raw_err_y) > 1:
                a2 = PTU_MIN_DRIVE if a2 >= 0 else -PTU_MIN_DRIVE

            # ── Stop decision: coast before stopping ──────────────────────
            # Only stop after PTU_STOP_COAST_FRAMES consecutive frames of
            # small command AND small error. Prevents a single Kalman velocity
            # dropout halting the PTU mid-approach to a stationary drone.
            cmd_small = (abs(a1) < PTU_VEL_DEADBAND and abs(a2) < PTU_VEL_DEADBAND)
            err_small = (abs(raw_err_x) < PTU_DEADBAND_PX * 2
                         and abs(raw_err_y) < PTU_DEADBAND_PX * 2)
            if cmd_small and err_small:
                _coast_stop_count += 1
            else:
                _coast_stop_count = 0
            if _coast_stop_count >= PTU_STOP_COAST_FRAMES:
                _stop_ptu()
            else:
                _send_h60(a1, a2, speed)

            _tracking_logger.info(
                "target=(%.1f,%.1f) aim=(%.1f,%.1f) "
                "vel=(%.1f,%.1f)px/s drone_spd=%.1f(smooth=%.1f) stopped=%s "
                "spd_base=%d spd_corr=%d spd=%d err=(%.1f,%.1f)px cmd=(%d,%d)",
                pred_x, pred_y, aim_x, aim_y,
                vx_kal, vy_kal,
                drone_speed_raw, smooth_drone_speed, drone_stopped,
                speed_base, speed_correction, speed,
                raw_err_x, raw_err_y,
                a1, a2,
            )

            _tracking_logger.debug(
                "err=(%.1f,%.1f)px smooth=(%.1f,%.1f)px "
                "pid=(%.2f,%.2f) ff=(%.2f,%.2f) int=(%.3f,%.3f) "
                "vec=(%d,%d) speed=%d age=%.3fs",
                raw_err_x, raw_err_y,
                smooth_err_x, smooth_err_y,
                out_x, out_y,
                ff_vx, ff_vy,
                pid_pan.integral, pid_tilt.integral,
                a1, a2, speed, pred_age,
            )

            elapsed = time.monotonic() - loop_start
            time.sleep(max(0, dt - elapsed))

    except Exception as e:
        logger.error("Pipeline PTU control thread error: %s", e, exc_info=True)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------
def get_current_frame_for_stream() -> Optional[cv2.Mat]:
    with _frame_lock:
        return _current_frame


def _get_last_prediction_from_pipeline() -> Optional[Dict[str, float]]:
    from app.api.routes.tracking import get_last_prediction
    return get_last_prediction()


def start_pipeline() -> None:
    global _capture_thread, _detection_thread, _ptu_thread
    if _capture_thread is not None and _capture_thread.is_alive():
        logger.warning("Pipeline already running")
        return
    _pipeline_stop.clear()
    _capture_thread   = threading.Thread(target=_capture_loop,     daemon=True, name="capture")
    _detection_thread = threading.Thread(target=_detection_loop,   daemon=True, name="detection")
    _ptu_thread       = threading.Thread(target=_ptu_control_loop, daemon=True, name="ptu")
    _capture_thread.start()
    _detection_thread.start()
    _ptu_thread.start()
    logger.info("Tracking pipeline started (PID + feedforward controller)")


def stop_pipeline() -> None:
    global _capture_thread, _detection_thread, _ptu_thread
    _pipeline_stop.set()
    for t in (_capture_thread, _detection_thread, _ptu_thread):
        if t is not None and t.is_alive():
            t.join(timeout=2.0)
    _capture_thread = _detection_thread = _ptu_thread = None
    logger.info("Tracking pipeline stopped")


def get_latest_result() -> Optional[Dict[str, Any]]:
    with _result_lock:
        return dict(_latest_result) if _latest_result else None


def is_pipeline_running() -> bool:
    return _capture_thread is not None and _capture_thread.is_alive()