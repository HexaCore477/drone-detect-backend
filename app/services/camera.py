"""Camera streaming service - RTSP capture and MJPEG frame generation."""
import logging
from typing import Optional

import cv2
import time

from app.core.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()
RTSP_URL = _settings.rtsp_url


def _create_capture() -> Optional[cv2.VideoCapture]:
    """Create a new VideoCapture. One per stream connection to avoid FFmpeg threading issues."""
    logger.info("Opening RTSP stream: %s", RTSP_URL)
    try:
        cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_FPS, 15)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)

        if not cap.isOpened():
            logger.error("Failed to open RTSP stream: %s", RTSP_URL)
            if cap:
                cap.release()
            return None
        return cap
    except Exception as e:
        logger.error("Exception while opening RTSP stream: %s", e)
        return None


def _release_capture(cap: Optional[cv2.VideoCapture]) -> None:
    """Safely release a VideoCapture."""
    if cap is not None:
        try:
            cap.release()
        except Exception as e:
            logger.error("Error releasing capture: %s", e)


def get_resolution() -> Optional[tuple[int, int]]:
    """
    Get frame width and height from the camera stream.
    Returns (width, height) or None if the stream cannot be opened.
    """
    cap = _create_capture()
    if cap is None:
        return None
    try:
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if width <= 0 or height <= 0:
            return None
        return (width, height)
    finally:
        _release_capture(cap)


def get_frame(cap: Optional[cv2.VideoCapture]) -> tuple[Optional[cv2.VideoCapture], Optional["cv2.Mat"]]:
    """
    Read a single frame. Returns (cap, frame).
    If cap becomes invalid, returns (None, None); caller should create a new capture.
    """
    if cap is None or not cap.isOpened():
        return None, None

    try:
        # Always skip to latest frame
        for _ in range(3):  # Skip 5 frames
            cap.grab()

        ret, frame = cap.read()
        if not ret or frame is None:
            logger.warning("Failed to read frame, capture will be recreated")
            _release_capture(cap)
            return None, None
        return cap, frame
    except cv2.error as e:
        logger.error("OpenCV error while reading frame: %s", e)
        _release_capture(cap)
        return None, None
    except Exception as e:
        logger.error("Unexpected error while reading frame: %s", e)
        _release_capture(cap)
        return None, None


def generate_mjpeg_frames():
    """
    Yield MJPEG frames for StreamingResponse.
    Uses a per-connection VideoCapture to avoid FFmpeg async_lock assertion.
    """
    cap: Optional[cv2.VideoCapture] = None
    consecutive_failures = 0
    max_failures = 15
    reconnect_delay = 2.0

    try:
        while True:
            try:
                if cap is None or not cap.isOpened():
                    cap = _create_capture()
                    if cap is None:
                        time.sleep(reconnect_delay)
                        continue
                    consecutive_failures = 0

                cap, frame = get_frame(cap)
                if frame is None:
                    cap = None
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures:
                        logger.warning(
                            "Too many failures (%d), waiting %.1fs before reconnect",
                            max_failures,
                            reconnect_delay,
                        )
                        time.sleep(reconnect_delay)
                        consecutive_failures = 0
                    else:
                        time.sleep(0.05)
                    continue

                consecutive_failures = 0

                ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if not ok:
                    logger.warning("Failed to encode frame as JPEG")
                    continue

                frame_bytes = buffer.tobytes()
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
                )

            except GeneratorExit:
                logger.info("Client disconnected from stream")
                break
            except cv2.error as e:
                logger.error("OpenCV error in stream: %s", e)
                _release_capture(cap)
                cap = None
                time.sleep(0.5)
            except Exception as e:
                logger.error("Error in generate_mjpeg_frames: %s", e)
                cap = None
                time.sleep(0.5)
    finally:
        _release_capture(cap)
