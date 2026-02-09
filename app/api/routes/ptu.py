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
    speed: int | None = None  # PTU speed (default 4000)


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


@router.get("/position")
def get_position():
    """Return cached (pan, tilt) position in degrees."""
    pan, tilt = ptu_service.get_position()
    return {"pan": pan, "tilt": tilt}


@router.get("/position/query")
def query_position():
    """Query PTU for actual position via H10E/H20E. Returns (pan, tilt) in degrees."""
    success, pan, tilt = ptu_service.query_position()
    if not success:
        raise HTTPException(status_code=503, detail="PTU position query failed or timed out")
    return {"pan": pan, "tilt": tilt}


@router.post("/connect")
def ptu_connect(body: ConnectBody):
    """Connect to PTU on the given serial port."""
    success, message = ptu_service.connect(body.port, body.baud)
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return {"ok": True, "message": message}


@router.post("/move/absolute")
def move_absolute(body: MoveBody):
    """Move PTU to absolute position (degrees). Sends H51,azimuth_pulse,pitch_pulse,speedE."""
    speed = body.speed if body.speed is not None else ptu_service.DEFAULT_SPEED_PTU
    success, message = ptu_service.move_absolute(body.pan, body.tilt, speed)
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return {"ok": True, "message": message}


@router.post("/move/relative")
def move_relative(body: MoveBody):
    """Move PTU relative to current position (degrees). Sends H52,delta_az,delta_pt,speedE."""
    speed = body.speed if body.speed is not None else ptu_service.DEFAULT_SPEED_PTU
    success, message = ptu_service.move_relative(body.pan, body.tilt, speed)
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
