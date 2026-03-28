"""Camera streaming service - Shared MJPEG frame generation."""
import logging
import cv2
import time
from typing import Optional
from app.core.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()
RTSP_URL = _settings.rtsp_url


def _create_capture() -> Optional[cv2.VideoCapture]:
    """Internal capture creator for the tracking pipeline."""
    try:
        cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap if cap.isOpened() else None
    except Exception as e:
        logger.error("Capture creation error: %s", e)
        return None


def _release_capture(cap: Optional[cv2.VideoCapture]) -> None:
    if cap: cap.release()


def get_resolution() -> Optional[tuple[int, int]]:
    cap = _create_capture()
    if not cap: return None
    res = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    cap.release()
    return res


def generate_mjpeg_frames():
    """
    Yield MJPEG frames from the GLOBAL pipeline.
    Zero new RTSP connections = Zero extra camera-side latency.
    """
    from app.services import tracking_pipeline
    
    while True:
        # Get frame that the Capture Thread already downloaded
        frame = tracking_pipeline.get_current_frame_for_stream()
        
        if frame is None:
            time.sleep(0.01)
            continue

        # Using Quality 70 reduces frame size and "Presentation" delay
        ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if not ok: continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
        )
        # Match roughly 30fps
        time.sleep(0.03)