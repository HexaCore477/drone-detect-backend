"""
Asynchronous tracking pipeline with three parallel threads:
  Thread 1: Grab frames continuously -> Shared Buffer
  Thread 2: Run detection on frames from buffer -> shared_target_position
  Thread 3: PTU control loop at fixed rate (reads shared_target_position)
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

# Pipeline configuration
PTU_LOOP_INTERVAL_SEC = 0.1  # 100ms fixed rate for PTU control

# Thread control
_capture_thread: Optional[threading.Thread] = None
_detection_thread: Optional[threading.Thread] = None
_ptu_thread: Optional[threading.Thread] = None

# Shared state for WebSocket consumers
_result_lock = threading.Lock()
_latest_result: Optional[Dict[str, Any]] = None


def _capture_loop() -> None:
    """
    Thread 1: Drain the RTSP buffer at maximum speed.

    Key design decisions:
    - grab() only fetches the compressed packet from the network; retrieve()
      does the actual decode. By calling grab() in a tight loop we drain any
      buffered frames so that when we finally retrieve() we always get the
      most-recently-transmitted frame from the camera.
    - We never sleep inside the hot path — the camera's own frame rate acts
      as the natural throttle.
    - On reconnect we back off for 1 second to avoid hammering a dead stream.
    """
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
    """
    Thread 2: Run YOLO detection on the latest frame from the shared buffer.

    The deferred import breaks the circular dependency:
      tracking_pipeline (module load) -> tracking.py (module load) -> tracking_pipeline
    By importing inside the function body both modules are fully initialised first.
    """
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
    """Thread 3: PTU control at fixed rate."""
    from app.services import config as config_service
    from app.services import ptu as ptu_service
    from app.services import auto_tracking as auto_tracking_service

    try:
        while not _pipeline_stop.is_set():
            time.sleep(PTU_LOOP_INTERVAL_SEC)

            if not config_service.get_auto_tracking() or not ptu_service.is_connected():
                continue

            pred = _get_last_prediction_from_pipeline()
            if pred is None:
                ptu_service.direction("pause")
                continue

            pred_x, pred_y = pred["x"], pred["y"]
            width, height = pred["width"], pred["height"]
            center_x, center_y = width / 2.0, height / 2.0
            error_x, error_y = pred_x - center_x, center_y - pred_y
            error_px = (error_x**2 + error_y**2) ** 0.5

            if error_px < auto_tracking_service.DEADBAND_PX:
                continue

            deg_per_px_x = auto_tracking_service.DEFAULT_HFOV_DEG / width
            deg_per_px_y = (auto_tracking_service.DEFAULT_HFOV_DEG * (height / width)) / height
            delta_pan, delta_pitch = error_x * deg_per_px_x, error_y * deg_per_px_y

            max_step = auto_tracking_service._get_step_from_distance(error_px, width)
            mag = (delta_pan**2 + delta_pitch**2) ** 0.5
            if mag > max_step:
                scale = max_step / mag
                delta_pan *= scale
                delta_pitch *= scale

            if auto_tracking_service.INVERT_PAN:
                delta_pan = -delta_pan
            if auto_tracking_service.INVERT_PITCH:
                delta_pitch = -delta_pitch

            speed = auto_tracking_service._get_speed_from_distance(error_px, width)
            ptu_service.move_relative(delta_pan, delta_pitch, speed)
    except Exception as e:
        logger.error("Pipeline PTU control thread error: %s", e, exc_info=True)


def get_current_frame_for_stream() -> Optional[cv2.Mat]:
    """Return the latest captured frame for the MJPEG/WebSocket stream."""
    with _frame_lock:
        return _current_frame


def _get_last_prediction_from_pipeline() -> Optional[Dict[str, float]]:
    from app.api.routes.tracking import get_last_prediction
    return get_last_prediction()


def start_pipeline() -> None:
    """Start the three pipeline threads."""
    global _capture_thread, _detection_thread, _ptu_thread
    if _capture_thread is not None and _capture_thread.is_alive():
        logger.warning("Pipeline already running")
        return
    _pipeline_stop.clear()
    _capture_thread = threading.Thread(target=_capture_loop, daemon=True, name="capture")
    _detection_thread = threading.Thread(target=_detection_loop, daemon=True, name="detection")
    _ptu_thread = threading.Thread(target=_ptu_control_loop, daemon=True, name="ptu")
    _capture_thread.start()
    _detection_thread.start()
    _ptu_thread.start()
    logger.info("Tracking pipeline started (Shared Buffer mode)")


def stop_pipeline() -> None:
    """Stop the pipeline threads."""
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