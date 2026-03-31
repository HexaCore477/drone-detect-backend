"""
Asynchronous tracking pipeline with three parallel threads:
  Thread 1: Grab frames continuously -> Shared Buffer
  Thread 2: Run detection on frames from buffer -> shared_target_position
  Thread 3: Position-step PTU controller using H52 (move_relative)
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional

import cv2
from app.services.camera import _create_capture, _release_capture

logger = logging.getLogger(__name__)

# --- GLOBAL SHARED STATE ---
_frame_lock = threading.Lock()
_current_frame: Optional[cv2.Mat] = None
_pipeline_stop = threading.Event()

# Thread control
_capture_thread: Optional[threading.Thread] = None
_detection_thread: Optional[threading.Thread] = None
_ptu_thread: Optional[threading.Thread] = None

# Shared state for WebSocket consumers
_result_lock = threading.Lock()
_latest_result: Optional[Dict[str, Any]] = None

PTU_INVERT_PAN  = True
PTU_INVERT_TILT = False

LASER_OFFSET_X = -10  
LASER_OFFSET_Y = 40   

PTU_HFOV_DEG = 60.0

PTU_GAIN        = 0.15          # Proportional gain (was 0.2)
PTU_DERIVATIVE_GAIN = 0.04      # NEW: Derivative gain for damping
PTU_MAX_STEP_DEG = 4.0          # was 8.0
PTU_MIN_STEP_DEG = 0.05
PTU_STEP_SPEED  = 18000         # kept for fallback, used dynamically now
PTU_DEADBAND_PX = 5             # can now be lower because of D-term
PTU_LOOP_SEC    = 0.033         # 30 Hz instead of 20 Hz
SMOOTH_ALPHA    = 0.4           # exponential smoothing factor (0=no smooth, 1=no memory)


def _capture_loop() -> None:
    """Thread 1: Drain the RTSP buffer at maximum speed."""
    global _current_frame
    cap = _create_capture()
    if cap is None:
        logger.error("Pipeline: failed to create capture, capture thread exiting")
        return
    try:
        while not _pipeline_stop.is_set():
            if cap.grab():
                ret, frame = cap.retrieve()
                if ret and frame is not None:
                    with _frame_lock:
                        _current_frame = frame
            else:
                logger.warning("Stream lost, attempting reconnect...")
                _release_capture(cap)
                cap = None
                time.sleep(1.0)
                cap = _create_capture()
                if cap is None:
                    logger.error("Reconnect failed, will retry in 1s")
    except Exception as e:
        logger.error("Pipeline capture thread error: %s", e, exc_info=True)
    finally:
        if cap is not None:
            _release_capture(cap)


def _detection_loop() -> None:
    """Thread 2: Run YOLO detection on the latest frame."""
    from app.api.routes.tracking import _run_detection_on_frame

    global _latest_result
    tracks: Dict = {}
    next_track_id = 0
    last_frame_id = None

    try:
        while not _pipeline_stop.is_set():
            with _frame_lock:
                frame = _current_frame

            if frame is None:
                time.sleep(0.005)
                continue

            frame_id = id(frame)
            if frame_id == last_frame_id:
                time.sleep(0.002)
                continue
            last_frame_id = frame_id

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


def _ptu_control_loop() -> None:
    """
    Thread 3: PD + exponential-smoothed PTU controller at ~30Hz.
    Uses dynamic step speed proportional to step magnitude.
    Replaces the original pure-P fixed-speed stop-and-go controller.

    --- TUNING GUIDE ---
    PTU_GAIN:            Start at 0.15. Increase if PTU is too slow to follow. Decrease if oscillation returns.
    PTU_DERIVATIVE_GAIN: Start at 0.04. Increase if still overshooting. Decrease if motion feels sluggish.
    PTU_DEADBAND_PX:     Can now go as low as 3-5px safely with D-term damping.
    SMOOTH_ALPHA:        0.3 = very smooth/sluggish. 0.5 = snappier. Start at 0.4.
    dynamic_speed range: Currently 2000–16000. Raise floor (2000) if micro-steps feel weak.
    PREDICTION_LEAD_SEC: 0.15 compensates for ~150ms total pipeline latency (YOLO + serial + mechanical).
    """
    from app.services import config as config_service
    from app.services import ptu as ptu_service

    no_detection_count: int = 0

    # PD state
    prev_error_x: float = 0.0
    prev_error_y: float = 0.0

    # Exponential smoothing state
    smoothed_step_x: float = 0.0
    smoothed_step_y: float = 0.0

    try:
        while not _pipeline_stop.is_set():
            loop_start = time.monotonic()

            if not config_service.get_auto_tracking() or not ptu_service.is_connected():
                no_detection_count = 0
                prev_error_x = 0.0
                prev_error_y = 0.0
                smoothed_step_x = 0.0
                smoothed_step_y = 0.0
                time.sleep(PTU_LOOP_SEC)
                continue

            pred = _get_last_prediction_from_pipeline()

            if pred is None:
                no_detection_count += 1
                prev_error_x = 0.0
                prev_error_y = 0.0
                time.sleep(PTU_LOOP_SEC)
                continue

            no_detection_count = 0

            pre_pan, pre_tilt = ptu_service.get_position()

            pred_x = pred["x"]
            pred_y = pred["y"]
            width  = pred["width"]
            height = pred["height"]

            aim_x = (width  / 2.0) + LASER_OFFSET_X
            aim_y = (height / 2.0) - LASER_OFFSET_Y

            error_x = pred_x - aim_x
            error_y = aim_y - pred_y
            error_px = (error_x ** 2 + error_y ** 2) ** 0.5

            if error_px < PTU_DEADBAND_PX:
                # Reset derivative state so there's no jerk when tracking resumes
                prev_error_x = error_x
                prev_error_y = error_y
                # Let smoothed state decay toward zero
                smoothed_step_x *= (1 - SMOOTH_ALPHA)
                smoothed_step_y *= (1 - SMOOTH_ALPHA)
                elapsed = time.monotonic() - loop_start
                time.sleep(max(0.0, PTU_LOOP_SEC - elapsed))
                continue

            deg_per_px_x = PTU_HFOV_DEG / width
            deg_per_px_y = PTU_HFOV_DEG * (height / width) / height

            error_deg_x = error_x * deg_per_px_x
            error_deg_y = error_y * deg_per_px_y

            # --- PD Controller ---
            d_error_x = (error_deg_x - prev_error_x) / PTU_LOOP_SEC
            d_error_y = (error_deg_y - prev_error_y) / PTU_LOOP_SEC
            prev_error_x = error_deg_x
            prev_error_y = error_deg_y

            raw_step_x = (error_deg_x * PTU_GAIN) + (d_error_x * PTU_DERIVATIVE_GAIN)
            raw_step_y = (error_deg_y * PTU_GAIN) + (d_error_y * PTU_DERIVATIVE_GAIN)

            # Clamp before smoothing
            raw_step_x = max(-PTU_MAX_STEP_DEG, min(PTU_MAX_STEP_DEG, raw_step_x))
            raw_step_y = max(-PTU_MAX_STEP_DEG, min(PTU_MAX_STEP_DEG, raw_step_y))

            # --- Exponential smoothing ---
            smoothed_step_x = SMOOTH_ALPHA * raw_step_x + (1 - SMOOTH_ALPHA) * smoothed_step_x
            smoothed_step_y = SMOOTH_ALPHA * raw_step_y + (1 - SMOOTH_ALPHA) * smoothed_step_y

            step_x = smoothed_step_x
            step_y = smoothed_step_y

            if abs(step_x) < PTU_MIN_STEP_DEG and abs(step_y) < PTU_MIN_STEP_DEG:
                elapsed = time.monotonic() - loop_start
                time.sleep(max(0.0, PTU_LOOP_SEC - elapsed))
                continue

            if PTU_INVERT_PAN:
                step_x = -step_x
            if PTU_INVERT_TILT:
                step_y = -step_y

            # --- Dynamic speed: small steps move slowly, large steps move fast ---
            step_magnitude = (step_x ** 2 + step_y ** 2) ** 0.5
            speed_factor = min(1.0, step_magnitude / PTU_MAX_STEP_DEG)
            dynamic_speed = int(2000 + speed_factor * 14000)  # range: 2000–16000

            ptu_service.move_relative(step_x, step_y, dynamic_speed)

            print(
                f"[PTU] pre=({pre_pan:+.3f}°,{pre_tilt:+.3f}°) "
                f"err=({error_x:+.1f},{error_y:+.1f})px "
                f"aim=({aim_x:.0f},{aim_y:.0f}) "
                f"step=({step_x:+.3f},{step_y:+.3f})deg "
                f"spd={dynamic_speed} total={error_px:.1f}px"
            )

            elapsed = time.monotonic() - loop_start
            time.sleep(max(0.0, PTU_LOOP_SEC - elapsed))

    except Exception as e:
        logger.error("Pipeline PTU control thread error: %s", e, exc_info=True)


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
    logger.info("Tracking pipeline started (Shared Buffer mode)")


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