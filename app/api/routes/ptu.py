"""PTU API routes."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import ptu as ptu_service

router = APIRouter(prefix="/ptu", tags=["ptu"])

VALID_DIRECTIONS = frozenset(
    {"left", "right", "up", "down", "pause", "left-up", "left-down", "right-up", "right-down"}
)


class MoveBody(BaseModel):
    pan: float = 0
    tilt: float = 0


class ConnectBody(BaseModel):
    port: str
    baud: int = 9600


@router.get("/getports")
def get_ports():
    """Return available serial port names."""
    ports = ptu_service.get_available_ports()
    return {"ports": ports}


@router.get("/connect-status")
def connect_status():
    """Return whether PTU is currently connected."""
    return {"connected": ptu_service.is_connected()}


@router.post("/connect")
def ptu_connect(body: ConnectBody):
    """Connect to PTU on the given serial port."""
    success, message = ptu_service.connect(body.port, body.baud)
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return {"ok": True, "message": message}


@router.post("/move/absolute")
def move_absolute(body: MoveBody):
    """Move PTU to absolute position (degrees)."""
    success, message = ptu_service.move_absolute(body.pan, body.tilt)
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return {"ok": True, "message": message}


@router.post("/move/relative")
def move_relative(body: MoveBody):
    """Move PTU relative to current position (degrees)."""
    success, message = ptu_service.move_relative(body.pan, body.tilt)
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return {"ok": True, "message": message}


@router.post("/direction/{direction_name}")
def direction(direction_name: str):
    """Move PTU in direction: left, right, up, down, pause, left-up, left-down, right-up, right-down."""
    if direction_name not in VALID_DIRECTIONS:
        raise HTTPException(status_code=400, detail=f"Invalid direction: {direction_name}")
    success, message = ptu_service.direction(direction_name)
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return {"ok": True, "message": message}


@router.post("/disconnect")
def ptu_disconnect():
    """Disconnect from PTU."""
    success, message = ptu_service.disconnect()
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return {"ok": True, "message": message}
