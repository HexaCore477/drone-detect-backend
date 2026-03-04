"""
Asynchronous tracking pipeline with three parallel threads:
  Thread 1: Grab frames continuously -> frame_queue
  Thread 2: Run detection on frames from queue -> shared_target_position
  Thread 3: PTU control loop at fixed rate (reads shared_target_position)

Reduces pipeline delay by decoupling capture, detection, and PTU control.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any, Dict, List, Optional

from app.services.camera import _create_capture, _release_capture, get_frame
from app.api.routes.tracking import (
    set_last_prediction,
    _run_detection_on_frame,
)

logger = logging.getLogger(__name__)

# Pipeline configuration
FRAME_QUEUE_MAXSIZE = 1  # Keep only latest frame to minimize latency
PTU_LOOP_INTERVAL_SEC = 0.1  # 100ms fixed rate for PTU control

# Thread control
_pipeline_stop = threading.Event()
_capture_thread: Optional[threading.Thread] = None
_detection_thread: Optional[threading.Thread] = None
_ptu_thread: Optional[threading.Thread] = None

# Shared state for WebSocket consumers
_result_lock = threading.Lock()
_latest_result: Optional[Dict[str, Any]] = None


def _capture_loop() -> None:
    """Thread 1: Grab frames continuously and put in queue."""
    cap = _create_capture()
    if cap is None:
        logger.error("Pipeline: failed to create capture, capture thread exiting")
        return
    try:
        while not _pipeline_stop.is_set():
            cap, frame = get_frame(cap)
            if frame is not None:
                try:
                    # maxsize=1: replace if full, always have latest
                    _frame_queue.put_nowait(frame.copy())
                except queue.Full:
                    _frame_queue.get_nowait()
                    _frame_queue.put_nowait(frame.copy())
            if cap is None:
                cap = _create_capture()
                if cap is None:
                    time.sleep(0.5)
    except Exception as e:
        logger.error("Pipeline capture thread error: %s", e, exc_info=True)
    finally:
        _release_capture(cap)
        logger.info("Pipeline capture thread stopped")


def _detection_loop() -> None:
    """Thread 2: Run detection on frames from queue, update shared target position."""
    global _latest_result
    tracks: Dict = {}
    next_track_id = 0
    try:
        while not _pipeline_stop.is_set():
            try:
                frame = _frame_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if frame is None:
                continue
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
    finally:
        logger.info("Pipeline detection thread stopped")


def _ptu_control_loop() -> None:
    """Thread 3: PTU control at fixed rate, reads shared target position."""
    from app.services import config as config_service
    from app.services import ptu as ptu_service
    from app.services import auto_tracking as auto_tracking_service

    loop_count = 0
    try:
        while not _pipeline_stop.is_set():
            loop_count += 1
            time.sleep(PTU_LOOP_INTERVAL_SEC)

            if not config_service.get_auto_tracking():
                continue
            if not ptu_service.is_connected():
                continue

            pred = _get_last_prediction_from_pipeline()
            if pred is None:
                # No target detected - stop PTU movement
                ptu_service.direction("pause")
                continue

            pred_x = pred["x"]
            pred_y = pred["y"]
            width = pred["width"]
            height = pred["height"]
            center_x = width / 2.0
            center_y = height / 2.0
            error_x = pred_x - center_x
            error_y = center_y - pred_y
            error_px = (error_x**2 + error_y**2) ** 0.5

            if error_px < auto_tracking_service.DEADBAND_PX:
                continue

            deg_per_px_x = auto_tracking_service.DEFAULT_HFOV_DEG / width
            deg_per_px_y = (
                auto_tracking_service.DEFAULT_HFOV_DEG * (height / width)
            ) / height
            delta_pan = error_x * deg_per_px_x
            delta_pitch = error_y * deg_per_px_y

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
    finally:
        logger.info("Pipeline PTU control thread stopped")


def _get_last_prediction_from_pipeline() -> Optional[Dict[str, float]]:
    """Get last prediction (used by PTU thread)."""
    from app.api.routes.tracking import get_last_prediction
    return get_last_prediction()


# Module-level frame queue (initialized when pipeline starts)
_frame_queue: queue.Queue = queue.Queue(maxsize=FRAME_QUEUE_MAXSIZE)


def start_pipeline() -> None:
    """Start the three pipeline threads."""
    global _capture_thread, _detection_thread, _ptu_thread, _frame_queue
    if _capture_thread is not None and _capture_thread.is_alive():
        logger.warning("Pipeline already running")
        return
    _pipeline_stop.clear()
    _frame_queue = queue.Queue(maxsize=FRAME_QUEUE_MAXSIZE)
    _capture_thread = threading.Thread(target=_capture_loop, daemon=True)
    _detection_thread = threading.Thread(target=_detection_loop, daemon=True)
    _ptu_thread = threading.Thread(target=_ptu_control_loop, daemon=True)
    _capture_thread.start()
    _detection_thread.start()
    _ptu_thread.start()
    logger.info("Tracking pipeline started (3 threads: capture, detection, PTU)")


def stop_pipeline() -> None:
    """Stop the pipeline threads."""
    global _capture_thread, _detection_thread, _ptu_thread
    _pipeline_stop.set()
    for t in (_capture_thread, _detection_thread, _ptu_thread):
        if t is not None and t.is_alive():
            t.join(timeout=2.0)
            if t.is_alive():
                logger.warning("Pipeline thread did not stop in time")
    _capture_thread = None
    _detection_thread = None
    _ptu_thread = None
    logger.info("Tracking pipeline stopped")


def get_latest_result() -> Optional[Dict[str, Any]]:
    """Get latest detection/tracking result for WebSocket consumers."""
    with _result_lock:
        if _latest_result is None:
            return None
        return dict(_latest_result)


def is_pipeline_running() -> bool:
    """Return True if pipeline threads are running."""
    return (
        _capture_thread is not None
        and _capture_thread.is_alive()
    )
