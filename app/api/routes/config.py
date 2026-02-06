"""Config API routes."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.services import config as config_service

router = APIRouter(prefix="/config", tags=["config"])


class AutoTrackingBody(BaseModel):
    is_auto_tracking: bool


@router.get("/auto-tracking")
def get_auto_tracking():
    """Get is_auto_tracking config value."""
    value = config_service.get_auto_tracking()
    return {"is_auto_tracking": value}


@router.post("/auto-tracking")
def set_auto_tracking(body: AutoTrackingBody):
    """Set is_auto_tracking config value."""
    config_service.set_auto_tracking(body.is_auto_tracking)
    return {"is_auto_tracking": body.is_auto_tracking}
