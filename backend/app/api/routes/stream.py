"""Stream API routes."""
from fastapi import APIRouter
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
        },
    )
