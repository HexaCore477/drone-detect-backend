"""View subscription API - start/stop commands for operational and waterfall views."""
from fastapi import APIRouter

from app.services import view_subscription

router = APIRouter(prefix="/view", tags=["view"])


@router.post("/start_operation")
def start_operation() -> dict:
    """Frontend calls when Operational view is fully loaded. Backend will send detection data."""
    view_subscription.set_operational_active(True)
    return {"ok": True, "message": "operational_started"}


@router.post("/stop_operation")
def stop_operation() -> dict:
    """Frontend calls when Operational view unmounts. Backend stops sending detection data."""
    view_subscription.set_operational_active(False)
    return {"ok": True, "message": "operational_stopped"}


@router.post("/start_waterfall")
def start_waterfall() -> dict:
    """Frontend calls when Waterfall view is fully loaded. Backend sends all data (detection + PTU commands)."""
    view_subscription.set_waterfall_active(True)
    return {"ok": True, "message": "waterfall_started"}


@router.post("/stop_waterfall")
def stop_waterfall() -> dict:
    """Frontend calls when Waterfall view unmounts. Backend stops sending all data."""
    view_subscription.set_waterfall_active(False)
    return {"ok": True, "message": "waterfall_stopped"}
