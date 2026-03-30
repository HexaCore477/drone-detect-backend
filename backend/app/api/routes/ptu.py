"""PTU API routes."""
import asyncio
import queue

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.services import ptu as ptu_service
from app.services import view_subscription

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


class ChangeBaudBody(BaseModel):
    baud: int
    """New baud rate. Supported values: 9600, 115200."""


@router.get("/getports")
def get_ports():
    """Return available serial port names."""
    ports = ptu_service.get_available_ports()
    return {"ports": ports}


@router.get("/connect-status")
def connect_status():
    """Return whether PTU is currently connected."""
    return {"connected": ptu_service.is_connected()}


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
    """Connect to PTU on the given serial port."""
    success, message = ptu_service.connect(body.port, body.baud)
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return {"ok": True, "message": message}


@router.post("/baud")
def change_baud(body: ChangeBaudBody):
    """
    Change the PTU baud rate at runtime.
    """
    if body.baud not in (9600, 115200):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported baud rate {body.baud}. Must be 9600 or 115200.",
        )
    success, message = ptu_service.change_baud_rate(body.baud)
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return {"ok": True, "baud": body.baud, "message": message}


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