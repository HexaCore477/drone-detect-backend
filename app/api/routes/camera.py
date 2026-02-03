"""Camera API routes."""
from fastapi import APIRouter, HTTPException

from app.services.camera import get_resolution

router = APIRouter(prefix="/camera", tags=["camera"])


@router.get("/resolution")
def camera_resolution():
    """Return the camera frame size (width, height)."""
    result = get_resolution()
    if result is None:
        raise HTTPException(status_code=503, detail="Unable to get camera resolution")
    width, height = result
    return {"width": width, "height": height}
