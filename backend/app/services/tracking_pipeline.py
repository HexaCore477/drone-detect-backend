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

PTU_GAIN = 0.2

PTU_MAX_STEP_DEG = 8.0
PTU_MIN_STEP_DEG = 0.05

PTU_STEP_SPEED = 18000
PTU_STEP_ACCEL = 20000

PTU_DEADBAND_PX = 10

PTU_LOOP_SEC = 0.05  


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
    Thread 3: Position-step PTU controller at 20Hz.
    """
    from app.services import config as config_service
    from app.services import ptu as ptu_service

    no_detection_count: int = 0

    try:
        while not _pipeline_stop.is_set():
            time.sleep(PTU_LOOP_SEC)

            if not config_service.get_auto_tracking() or not ptu_service.is_connected():
                no_detection_count = 0
                continue

            pred = _get_last_prediction_from_pipeline()

            if pred is None:
                no_detection_count += 1
                continue

            no_detection_count = 0

            pre_pan, pre_tilt = ptu_service.get_position()

            pred_x  = pred["x"]
            pred_y  = pred["y"]
            width   = pred["width"]
            height  = pred["height"]

            aim_x = (width  / 2.0) + LASER_OFFSET_X
            aim_y = (height / 2.0) - LASER_OFFSET_Y

            error_x = pred_x - aim_x
            error_y = aim_y - pred_y
            error_px = (error_x ** 2 + error_y ** 2) ** 0.5

            if error_px < PTU_DEADBAND_PX:
                continue

            deg_per_px_x = PTU_HFOV_DEG / width
            deg_per_px_y = PTU_HFOV_DEG * (height / width) / height

            error_deg_x = error_x * deg_per_px_x
            error_deg_y = error_y * deg_per_px_y

            step_x = error_deg_x * PTU_GAIN
            step_y = error_deg_y * PTU_GAIN

            step_x = max(-PTU_MAX_STEP_DEG, min(PTU_MAX_STEP_DEG, step_x))
            step_y = max(-PTU_MAX_STEP_DEG, min(PTU_MAX_STEP_DEG, step_y))

            if abs(step_x) < PTU_MIN_STEP_DEG and abs(step_y) < PTU_MIN_STEP_DEG:
                continue

            if PTU_INVERT_PAN:
                step_x = -step_x
            if PTU_INVERT_TILT:
                step_y = -step_y

            ptu_service.move_relative(step_x, step_y, PTU_STEP_SPEED)

            print(
                f"[PTU] pre=({pre_pan:+.3f}°,{pre_tilt:+.3f}°) "
                f"err=({error_x:+.1f},{error_y:+.1f})px "
                f"aim=({aim_x:.0f},{aim_y:.0f}) "
                f"step=({step_x:+.3f},{step_y:+.3f})deg "
                f"total={error_px:.1f}px"
            )

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