"""
Asynchronous tracking pipeline with three parallel threads:
  Thread 1: Grab frames continuously -> Shared Buffer
  Thread 2: Run detection on frames from buffer -> shared_target_position
  Thread 3: H60 velocity-mode PTU controller
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

# Thread handles
_capture_thread:   Optional[threading.Thread] = None
_detection_thread: Optional[threading.Thread] = None
_ptu_thread:       Optional[threading.Thread] = None

# Shared result for WebSocket consumers
_result_lock = threading.Lock()
_latest_result: Optional[Dict[str, Any]] = None

# ---------------------------------------------------------------------------
# PTU controller constants
# ---------------------------------------------------------------------------
PTU_INVERT_PAN  = True
PTU_INVERT_TILT = False

LASER_OFFSET_X = -10
LASER_OFFSET_Y =  45

PTU_HFOV_DEG = 60.0

PTU_GAIN_H = 0.60
PTU_GAIN_V = 0.35

# H60 speed range (pulse/s)
PTU_MAX_SPEED = 8000
PTU_MIN_SPEED = 300

PTU_LOOP_SEC    = 0.05   # 20 Hz
PTU_DEADBAND_PX = 6      # smoothed error below this → send H65E stop

# Error-space EMA alpha (0 = no smoothing, 1 = frozen)
PTU_ERROR_EMA_ALPHA = 0.35

PTU_MAX_VECTOR = 100   # normalised vector magnitude cap fed into H60


# ---------------------------------------------------------------------------
# Thread 1 — continuous frame capture
# ---------------------------------------------------------------------------
def _capture_loop() -> None:
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


# ---------------------------------------------------------------------------
# Thread 3 — H60 velocity-mode PTU controller
# ---------------------------------------------------------------------------
def _ptu_control_loop() -> None:
    """
    20 Hz proportional velocity controller using H60 (continuous joystick mode).

    Tracking target: the Kalman-predicted position (blue dot on frontend).
    set_last_prediction() in tracking.py stores pred_cx/pred_cy — the EKF
    look-ahead point — NOT the raw bbox centre.  This function drives that
    blue dot onto the laser aim point (green circle on frontend).

    Aim point in pixel coords:
        aim_x = width/2  + LASER_OFFSET_X
        aim_y = height/2 - LASER_OFFSET_Y   ← note sign: offset moves aim UP

    Error = (predicted_x - aim_x,  aim_y - predicted_y)
        • positive pan  error → target is RIGHT  of aim → pan right
        • positive tilt error → target is ABOVE  aim   → tilt up

    PTU_INVERT_PAN/TILT flip the sign to match your PTU's motor direction.
    """
    from app.services import config as config_service
    from app.services import ptu as ptu_service

    smooth_err_x: float = 0.0
    smooth_err_y: float = 0.0
    alpha = PTU_ERROR_EMA_ALPHA
    was_stopped = True

    try:
        while not _pipeline_stop.is_set():
            time.sleep(PTU_LOOP_SEC)

            if not config_service.get_auto_tracking() or not ptu_service.is_connected():
                if not was_stopped:
                    ptu_service.direction("pause")
                    was_stopped = True
                smooth_err_x = smooth_err_y = 0.0
                continue

            pred = _get_last_prediction_from_pipeline()

            if pred is None:
                if not was_stopped:
                    ptu_service.direction("pause")
                    was_stopped = True
                smooth_err_x *= (1.0 - alpha)
                smooth_err_y *= (1.0 - alpha)
                continue


            pred_x = pred.get("raw_x", pred["x"])
            pred_y = pred.get("raw_y", pred["y"])

            FF_GAIN = 0.3
            pred_x += FF_GAIN * (pred["x"] - pred_x)
            pred_y += FF_GAIN * (pred["y"] - pred_y)

            width  = pred["width"]
            height = pred["height"]

            aim_x = (width  / 2.0) + LASER_OFFSET_X
            aim_y = (height / 2.0) - LASER_OFFSET_Y

            raw_err_x = pred_x - aim_x
            raw_err_y = aim_y  - pred_y  # flip: positive → target is above aim → tilt up

            # EMA smoothing in error-space suppresses jitter at the deadband
            smooth_err_x = alpha * raw_err_x + (1.0 - alpha) * smooth_err_x
            smooth_err_y = alpha * raw_err_y + (1.0 - alpha) * smooth_err_y

            error_px = (smooth_err_x ** 2 + smooth_err_y ** 2) ** 0.5

            logger.debug(
                "[PTU] blue_dot=(%.1f,%.1f) aim=(%.1f,%.1f) "
                "raw_err=(%.1f,%.1f) smooth_err=(%.1f,%.1f) total=%.1fpx",
                pred_x, pred_y, aim_x, aim_y,
                raw_err_x, raw_err_y,
                smooth_err_x, smooth_err_y,
                error_px,
            )

            # ── Inside deadband: blue dot is on aim point → hold ────────────
            if error_px < PTU_DEADBAND_PX:
                if not was_stopped:
                    ptu_service.direction("pause")
                    was_stopped = True
                continue

            # ── Outside deadband: issue H60 velocity command ─────────────────
            deg_per_px = PTU_HFOV_DEG / width

            vx = smooth_err_x * deg_per_px * PTU_GAIN_H
            vy = smooth_err_y * deg_per_px * PTU_GAIN_V

            # Normalise so the dominant axis saturates at PTU_MAX_VECTOR
            max_v = max(abs(vx), abs(vy), 1e-6)
            scale = min(PTU_MAX_VECTOR / max_v, PTU_MAX_VECTOR)
            a1 = int(round(vx * scale))   # pan  (A1)
            a2 = int(round(vy * scale))   # tilt (A2)

            if PTU_INVERT_PAN:
                a1 = -a1
            if PTU_INVERT_TILT:
                a2 = -a2

            # Proportional speed: larger pixel error → faster slew
            norm_err = min(error_px / (width / 4.0), 1.0)
            speed = int(PTU_MIN_SPEED + norm_err * (PTU_MAX_SPEED - PTU_MIN_SPEED))

            cmd_bytes = f"H60,{a1},{a2},{speed}E".encode("ascii")
            try:
                from app.services.ptu import _command_queue, _drop_old_move_commands
                _drop_old_move_commands()
                _command_queue.put(("write", cmd_bytes))
            except Exception as _e:
                logger.warning("H60 enqueue failed: %s", _e)

            was_stopped = False

            logger.debug(
                "[PTU-H60] vec=(%d,%d) speed=%d",
                a1, a2, speed,
            )

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
    logger.info("Tracking pipeline started")


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