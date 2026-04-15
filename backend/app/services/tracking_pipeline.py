"""
Asynchronous tracking pipeline with three parallel threads:
  Thread 1: Grab frames continuously -> Shared Buffer
  Thread 2: Run detection on frames from buffer -> shared_target_position
  Thread 3: Position-mode PTU controller using H52 (relative move)

v10 — STRUCTURAL REWRITE: switches from H60 velocity-mode to H52 position-mode.

  The PTU manual states H60 is "for manual control only and not suitable for
  programming area control."  H60 commands instant velocity changes with zero
  acceleration, causing all the jitter and overshoot problems we've been
  fighting for 9 versions.

  H52 (relative position with trapezoidal acceleration) is the firmware's
  intended command for automated control.  Benefits:
    - Firmware handles acceleration/deceleration internally (no jitter)
    - Positional commands are self-limiting (no velocity overshoot)
    - Zero-crossing is smooth (increment passes through zero naturally)
    - No PID integral needed (each move is a fresh positional correction)
    - No speed cap, rate limiter, or command gate needed

  The control loop is now:
    1. pixel_error → degree_error (via HFOV/frame_width)
    2. feedforward_deg = kalman_velocity * deg_per_px * lead_time
    3. move_deg = (error_deg * GAIN) + feedforward_deg
    4. ptu_service.move_relative(pan_deg, tilt_deg, MOVE_SPEED)
    5. Sleep ~100ms (H52 completes small moves in 30-80ms)

  Runs at ~10 Hz (vs 30 Hz for H60). This matches the detection rate (~25fps)
  and gives H52 time to execute each move.
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

# ── Position-mode tuning ──────────────────────────────────────────────────
# GAIN: fraction of pixel error corrected per cycle.
#   0.5 = correct half the error each step (stable, smooth)
#   0.7 = correct 70% (faster, but may oscillate if detection is noisy)
#   1.0 = correct full error (aggressive — only if detection is rock-solid)
PAN_GAIN  = 0.75
TILT_GAIN = 0.5

# Feedforward: anticipate drone motion by this many seconds
FF_LEAD_SEC = 0.05       # conservative — only 100ms of look-ahead
FF_PAN_GAIN  = 0.5       # scale factor on pan feedforward
FF_TILT_GAIN = 0.4       # scale factor on tilt feedforward

# H52 speed parameter: how fast the PTU executes each relative move
# Higher = more responsive. Unit: pulses/second.
# Manual says max 20000-40000 depending on settings.
# At 15000 p/s with resolution 0.0009375 deg/pulse = 14.06 deg/s max
MOVE_SPEED = 15000

# Loop timing
PTU_LOOP_SEC = 0.080     # ~12.5 Hz — gives H52 time to complete each move

# Error thresholds
PTU_DEADBAND_PX  = 5     # ignore errors smaller than this (px)
PREDICTION_MAX_AGE_SEC = 0.15  # reject predictions older than this

# Coast/stop behavior
PTU_COAST_CYCLES      = 8   # how many no-prediction cycles before stopping
DRONE_STOP_VEL_THRESHOLD = 4.0
DRONE_SPEED_EMA_ALPHA = 0.50

# Stale prediction detection
STALE_REPEAT_WARN  = 2    # at 10Hz, stale=2 means 200ms of no new data
STALE_REPEAT_COAST = 6
STALE_MOVE_DECAY   = 0.80


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


# ---------------------------------------------------------------------------
# Thread 3 — Position-mode PTU controller (H52 relative moves)
# ---------------------------------------------------------------------------
def _ptu_control_loop() -> None:
    from app.services import config as config_service
    from app.services import ptu   as ptu_service
    from app.services import logger as ptu_logger

    dt = PTU_LOOP_SEC

    coast_cycles = 0
    smooth_drone_speed = 0.0

    _last_pred_key: Optional[tuple] = None
    _stale_repeat_count = 0

    # Track last move for stale-frame decay
    _last_move_pan  = 0.0
    _last_move_tilt = 0.0

    def _stop_ptu():
        ptu_service.write_raw(b"H65E")
        ptu_logger.PTU_EVENT_LOG.info("ptu_stop: cmd=H65E")

    def _send_move(pan_deg: float, tilt_deg: float, speed: int):
        """Send H52 relative move via the existing ptu_service.move_relative."""
        if PTU_INVERT_PAN:
            pan_deg = -pan_deg
        if PTU_INVERT_TILT:
            tilt_deg = -tilt_deg
        ptu_service.move_relative(pan_deg, tilt_deg, speed)

    try:
        while not _pipeline_stop.is_set():
            loop_start = time.monotonic()

            # ── Check tracking enabled ───────────────────────────────────
            if not config_service.get_auto_tracking() or not ptu_service.is_connected():
                coast_cycles = 0
                smooth_drone_speed = 0.0
                _last_pred_key = None
                _stale_repeat_count = 0
                _last_move_pan = _last_move_tilt = 0.0
                time.sleep(max(0, dt - (time.monotonic() - loop_start)))
                continue

            pred = _get_last_prediction_from_pipeline()

            # ── No prediction ────────────────────────────────────────────
            if pred is None:
                coast_cycles += 1
                if coast_cycles > PTU_COAST_CYCLES:
                    _stop_ptu()
                time.sleep(max(0, dt - (time.monotonic() - loop_start)))
                continue

            # ── Stale by age ─────────────────────────────────────────────
            pred_age = time.time() - pred.get("timestamp", time.time())
            if pred_age > PREDICTION_MAX_AGE_SEC:
                coast_cycles += 1
                if coast_cycles > PTU_COAST_CYCLES:
                    _stop_ptu()
                time.sleep(max(0, dt - (time.monotonic() - loop_start)))
                continue

            # ── Valid prediction ──────────────────────────────────────────
            coast_cycles = 0
            pred_x  = pred["x"]
            pred_y  = pred["y"]
            width   = pred["width"]
            height  = pred["height"]
            vx_kal  = pred.get("vx", 0.0)
            vy_kal  = pred.get("vy", 0.0)

            # ── Stale detection (same prediction repeated) ───────────────
            pred_key = (round(pred_x, 1), round(pred_y, 1),
                        round(vx_kal, 1), round(vy_kal, 1))
            if pred_key == _last_pred_key:
                _stale_repeat_count += 1
            else:
                _stale_repeat_count = 0
            _last_pred_key = pred_key

            if _stale_repeat_count >= STALE_REPEAT_COAST:
                _stop_ptu()
                time.sleep(max(0, dt - (time.monotonic() - loop_start)))
                continue

            # ── On stale frame: send decayed version of last move ────────
            if _stale_repeat_count > 0 and _stale_repeat_count < STALE_REPEAT_COAST:
                _last_move_pan  *= STALE_MOVE_DECAY
                _last_move_tilt *= STALE_MOVE_DECAY
                if abs(_last_move_pan) > 0.001 or abs(_last_move_tilt) > 0.001:
                    _send_move(_last_move_pan, _last_move_tilt, MOVE_SPEED)
                _tracking_logger.info(
                    "target=(%.1f,%.1f) move=(%.4f,%.4f)deg spd=%d stale=%d HOLD",
                    pred_x, pred_y, _last_move_pan, _last_move_tilt,
                    MOVE_SPEED, _stale_repeat_count)
                time.sleep(max(0, dt - (time.monotonic() - loop_start)))
                continue

            # ── Fresh prediction — compute position correction ───────────
            aim_x = (width  / 2.0) + LASER_OFFSET_X
            aim_y = (height / 2.0) - LASER_OFFSET_Y

            raw_err_x = pred_x - aim_x       # positive = target is right of center
            raw_err_y = aim_y  - pred_y       # positive = target is above center

            error_px = math.hypot(raw_err_x, raw_err_y)

            # Deadband — don't move for sub-pixel noise
            if error_px < PTU_DEADBAND_PX:
                _last_move_pan = _last_move_tilt = 0.0
                time.sleep(max(0, dt - (time.monotonic() - loop_start)))
                continue

            # ── Drone speed tracking ─────────────────────────────────────
            drone_speed_raw = math.hypot(vx_kal, vy_kal)
            smooth_drone_speed = (
                DRONE_SPEED_EMA_ALPHA * drone_speed_raw
                + (1.0 - DRONE_SPEED_EMA_ALPHA) * smooth_drone_speed
            )

            # ── Convert pixel error to degrees ───────────────────────────
            deg_per_px = PTU_HFOV_DEG / max(width, 1.0)

            err_deg_x = raw_err_x * deg_per_px
            err_deg_y = raw_err_y * deg_per_px

            # ── Feedforward: anticipate drone motion ─────────────────────
            ff_deg_x = vx_kal * deg_per_px * FF_LEAD_SEC * FF_PAN_GAIN
            ff_deg_y = vy_kal * deg_per_px * FF_LEAD_SEC * FF_TILT_GAIN

            # ── Compute move command ─────────────────────────────────────
            # Position mode: move by a fraction of the error + feedforward
            move_pan  = err_deg_x * PAN_GAIN  + ff_deg_x
            move_tilt = err_deg_y * TILT_GAIN + ff_deg_y

            # Store for stale-frame decay
            _last_move_pan  = move_pan
            _last_move_tilt = move_tilt

            # ── Send H52 relative move ───────────────────────────────────
            _send_move(move_pan, move_tilt, MOVE_SPEED)

            # ── Logging ──────────────────────────────────────────────────
            _tracking_logger.info(
                "target=(%.1f,%.1f) aim=(%.1f,%.1f) "
                "vel=(%.1f,%.1f)px/s drone_spd=%.1f(smooth=%.1f) "
                "err=(%.1f,%.1f)px err_deg=(%.4f,%.4f) "
                "ff_deg=(%.4f,%.4f) move=(%.4f,%.4f)deg spd=%d "
                "stale=%d",
                pred_x, pred_y, aim_x, aim_y,
                vx_kal, vy_kal,
                drone_speed_raw, smooth_drone_speed,
                raw_err_x, raw_err_y,
                err_deg_x, err_deg_y,
                ff_deg_x, ff_deg_y,
                move_pan, move_tilt, MOVE_SPEED,
                _stale_repeat_count)

            time.sleep(max(0, dt - (time.monotonic() - loop_start)))

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
    logger.info("Tracking pipeline started (v10 — H52 position mode)")

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