"""Stream API routes — MJPEG HTTP stream + low-latency WebSocket stream."""
import asyncio
import time

import cv2
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from app.services.camera import generate_mjpeg_frames

router = APIRouter(prefix="/stream", tags=["stream"])


@router.get("")
def video_stream():
    """
    MJPEG stream endpoint.
    Frontend uses: <img src="/api/stream" />
    """
    return StreamingResponse(
        generate_mjpeg_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.websocket("/ws")
async def stream_ws(websocket: WebSocket):
    """
    WebSocket stream endpoint — lower latency than MJPEG over HTTP.

    Sends raw JPEG bytes as binary WebSocket frames.
    Frontend: useCameraStream hook (ws://host:8000/api/stream/ws)

    Why this is faster than the MJPEG <img> approach:
    - No HTTP chunked-transfer framing overhead
    - Browser does not buffer WebSocket binary messages the way it buffers
      multipart HTTP responses
    - We control exactly when each frame is pushed
    """
    from app.services import tracking_pipeline

    await websocket.accept()
    last_frame_id = None

    try:
        while True:
            frame = tracking_pipeline.get_current_frame_for_stream()

            if frame is None:
                await asyncio.sleep(0.005)
                continue

            frame_id = id(frame)
            if frame_id == last_frame_id:
                await asyncio.sleep(0.002)
                continue
            last_frame_id = frame_id

            ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ok:
                continue

            await websocket.send_bytes(buffer.tobytes())

    except WebSocketDisconnect:
        pass
    except Exception as e:
        pass