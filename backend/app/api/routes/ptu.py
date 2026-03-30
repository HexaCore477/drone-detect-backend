"""PTU API routes."""
import asyncio
import os
import queue

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.services import ptu as ptu_service
from app.services import view_subscription

router = APIRouter(prefix="/ptu", tags=["ptu"])

VALID_DIRECTIONS = frozenset(
    {"left", "right", "up", "down", "pause", "left-up", "left-down", "right-up", "right-down"}
)


def _default_baud() -> int:
    """Read PTU_BAUD from env (set after running scripts/change_ptu_baud.py)."""
    try:
        return int(os.getenv("PTU_BAUD", "9600"))
    except (TypeError, ValueError):
        return 9600


class MoveBody(BaseModel):
    pan: float = 0
    tilt: float = 0
    speed: int | None = None


class ConnectBody(BaseModel):
    port: str
    baud: int | None = None


@router.get("/getports")
def get_ports():
    """Return available serial port names."""
    return {"ports": ptu_service.get_available_ports()}


@router.get("/connect-status")
def connect_status():
    """Return whether PTU is currently connected and the active baud rate."""
    return {
        "connected": ptu_service.is_connected(),
        "baud": ptu_service._connected_baud,   # None when disconnected
        "env_baud": _default_baud(),
    }


@router.get("/position/cached")
def get_cached_position():
    """Return cached (pan, tilt) position in degrees."""
    pan, tilt = ptu_service.get_position()
    return {"pan": pan, "tilt": tilt}


@router.get("/position/query")
def query_position():
    """
    Method 1 — On-demand position query.
    Sends H10E (azimuth / A1) and H20E (pitch / A2) to the PTU.
    Returns pulse counts and converted angles:
      angle (°) = pulse_count × resolution  (read from H99E on connect).
    """
    success, pan, tilt, az_pulse, pt_pulse = ptu_service.query_position()
    if not success:
        raise HTTPException(status_code=503, detail="PTU position query failed or timed out")
    return {
        "pan": pan,
        "tilt": tilt,
        "az_pulse": az_pulse,
        "pt_pulse": pt_pulse,
        "resolution": ptu_service.get_resolution(),
    }


@router.get("/resolution")
def get_resolution():
    """
    Return the cached pulse-to-degree resolution (°/pulse).
    Updated automatically on connect via H99E, or manually via POST /resolution/refresh.
    """
    return {"resolution": ptu_service.get_resolution()}


@router.post("/resolution/refresh")
def refresh_resolution():
    """
    Send H99E to the PTU and refresh the pulse-to-degree resolution.
    Parses the 'pulse-> degree = <value>' line from the PTU response.
    """
    success, resolution = ptu_service.read_resolution()
    if not success:
        raise HTTPException(
            status_code=503,
            detail="PTU resolution query (H99E) failed or timed out",
        )
    return {"ok": True, "resolution": resolution}


@router.post("/connect")
def ptu_connect(body: ConnectBody):
    """
    Connect to PTU on the given serial port.

    - `baud` is optional. When omitted the service uses PTU_BAUD from .env
      (default 9600).
    - To change the device baud rate, run scripts/change_ptu_baud.py while
      the app is stopped, then update PTU_BAUD in .env and restart.
    """
    baud = body.baud if body.baud is not None else _default_baud()
    success, message = ptu_service.connect(body.port, baud)
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return {"ok": True, "message": message, "baud": baud}


@router.post("/move/absolute")
def move_absolute(body: MoveBody):
    """Move PTU to absolute position (degrees). Sends H51,azimuth_pulse,pitch_pulse,speedE."""
    speed = body.speed if body.speed is not None else ptu_service.get_default_speed_ptu()
    success, message = ptu_service.move_absolute(body.pan, body.tilt, speed)
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return {"ok": True, "message": message}


@router.post("/move/relative")
def move_relative(body: MoveBody):
    """Move PTU relative to current position (degrees). Sends H52,delta_az,delta_pt,speedE."""
    speed = body.speed if body.speed is not None else ptu_service.get_default_speed_ptu()
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


@router.websocket("/ws/commands")
async def ptu_commands_ws(websocket: WebSocket) -> None:
    """
    Stream PTU movement commands (H51, H52, H61, H62, etc.) when they are sent.
    Use for Waterfall PTU COMMANDS log.
    """
    await websocket.accept()
    cmd_queue = ptu_service.get_command_broadcast_queue()
    try:
        while True:
            try:
                if view_subscription.should_send_ptu_commands():
                    cmd = cmd_queue.get_nowait()
                    await websocket.send_json({"command": cmd})
            except queue.Empty:
                pass
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        pass