"""Config API routes."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.services import auto_tracking, config as config_service

router = APIRouter(prefix="/config", tags=["config"])


class AutoTrackingBody(BaseModel):
    is_auto_tracking: bool


@router.get("/auto-tracking")
def get_auto_tracking():
    """Get is_auto_tracking config value."""
    value = config_service.get_auto_tracking()
    return {"is_auto_tracking": value}


@router.post("/auto-tracking")
async def set_auto_tracking(body: AutoTrackingBody):
    """
    Set is_auto_tracking config value and start/stop backend auto-tracking.
    When set to true, the PTU auto-tracking loop is started.
    When set to false, the loop is stopped.
    """
    config_service.set_auto_tracking(body.is_auto_tracking)
    if body.is_auto_tracking:
        await auto_tracking.start_auto_tracking()
    else:
        await auto_tracking.stop_auto_tracking()
    return {"is_auto_tracking": body.is_auto_tracking}
