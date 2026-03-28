"""Camera streaming service - Shared MJPEG frame generation."""
import logging
import os
import cv2
import time
from typing import Optional
from app.core.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()
RTSP_URL = _settings.rtsp_url

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
    "rtsp_transport;udp|"
    "fflags;nobuffer|"
    "flags;low_delay|"
    "framedrop;1|"
    "strict;experimental|"
    "analyzeduration;0|"
    "probesize;32|"
    "max_delay;0|"
    "reorder_queue_size;0"
)


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
    if cap:
        cap.release()


def get_resolution() -> Optional[tuple[int, int]]:
    cap = _create_capture()
    if not cap:
        return None
    res = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    cap.release()
    return res


def generate_mjpeg_frames():
    """
    Yield MJPEG frames from the GLOBAL pipeline shared buffer.
    Zero new RTSP connections = zero extra camera-side latency.
    Pushes every new frame immediately — no artificial sleep.
    """
    from app.services import tracking_pipeline

    last_frame_id = None

    while True:
        frame = tracking_pipeline.get_current_frame_for_stream()

        if frame is None:
            time.sleep(0.005)
            continue

        frame_id = id(frame)
        if frame_id == last_frame_id:
            time.sleep(0.002) 
            continue
        last_frame_id = frame_id

        ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
        )