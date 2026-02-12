"""Camera API routes."""
from fastapi import APIRouter, HTTPException

from app.services.camera import get_resolution
from app.services import camera_zoom as zoom_service

router = APIRouter(prefix="/camera", tags=["camera"])


@router.get("/resolution")
def camera_resolution():
    """Return the camera frame size (width, height)."""
    result = get_resolution()
    if result is None:
        raise HTTPException(status_code=503, detail="Unable to get camera resolution")
    width, height = result
    return {"width": width, "height": height}


# ----- Camera Zoom (Hikvision ISAPI PTZ) -----


@router.post("/zoom/connect")
def camera_zoom_connect():
    """Connect / verify camera for zoom control (ISAPI)."""
    success, message = zoom_service.zoom_connect()
    if not success:
        raise HTTPException(status_code=503, detail=message)
    return {"ok": True, "message": message}


@router.post("/zoom/in")
def camera_zoom_in():
    """Start zoom in (continuous). Send zoom stop to end."""
    success, message = zoom_service.zoom_in()
    if not success:
        raise HTTPException(status_code=503, detail=message)
    return {"ok": True, "message": message}


@router.post("/zoom/out")
def camera_zoom_out():
    """Start zoom out (continuous). Send zoom stop to end."""
    success, message = zoom_service.zoom_out()
    if not success:
        raise HTTPException(status_code=503, detail=message)
    return {"ok": True, "message": message}


@router.post("/zoom/stop")
def camera_zoom_stop():
    """Stop zoom (and pan/tilt) movement."""
    success, message = zoom_service.zoom_stop()
    if not success:
        raise HTTPException(status_code=503, detail=message)
    return {"ok": True, "message": message}
