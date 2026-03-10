"""PTU (Pan-Tilt Unit) service - serial port listing and move commands."""
import logging
import os
import queue
import re
import threading
import time
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no cover
    import serial  # type: ignore

logger = logging.getLogger(__name__)

# Pulse <-> degree conversion: angle = pulse × 0.0009375
PULSE_TO_DEG = 0.0009375
DEG_TO_PULSE = 1.0 / PULSE_TO_DEG


def _get_default_speed_ptu() -> int:
    """PTU speed for move_absolute/move_relative. From DEFAULT_SPEED_PTU in .env."""
    try:
        return int(os.getenv("DEFAULT_SPEED_PTU", "10000"))
    except (TypeError, ValueError):
        return 10000


def _get_direction_speed_default() -> int:
    """PTU speed for direction commands. From DIRECTION_SPEED_DEFAULT in .env."""
    try:
        return int(os.getenv("DIRECTION_SPEED_DEFAULT", "2000"))
    except (TypeError, ValueError):
        return 2000


def get_default_speed_ptu() -> int:
    """Public accessor for API routes."""
    return _get_default_speed_ptu()


# move_absolute: H51,<azimuth_pulse>,<pitch_pulse>,<speed_ptu>E
# move_relative: H52,<delta_azimuth_pulse>,<delta_pitch_pulse>,<speed_ptu>E
# H10E → get azimuth (A1) in pulses
# H20E → get pitch (A2) in pulses

# Direction command templates: H61/H62/H63/H64 use speed; H60 uses az_dir,pitch_dir,speed; H65 is pause
DIRECTION_COMMANDS: dict[str, bytes] = {
    "left": b"H61,2000E",
    "right": b"H62,2000E",
    "up": b"H63,2000E",
    "down": b"H64,2000E",
    "right-up": b"H60,-1,1,2000E",
    "left-down": b"H60,1,-1,2000E",
    "right-down": b"H60,-1,-1,2000E",
    "left-up": b"H60,1,1,2000E",
    "pause": b"H65E",
}


def _build_direction_payload(direction_name: str, speed: int) -> bytes:
    """Build PTU direction command bytes with given speed. Pause ignores speed."""
    if direction_name == "pause":
        return b"H65E"
    if direction_name in ("left", "right", "up", "down"):
        cmd_map = {"left": "H61", "right": "H62", "up": "H63", "down": "H64"}
        return f"{cmd_map[direction_name]},{speed}E".encode("ascii")
    # Diagonals: H60,az_dir,pitch_dir,speed
    diag_map = {
        "right-up": (-1, 1),
        "left-down": (1, -1),
        "right-down": (-1, -1),
        "left-up": (1, 1),
    }
    az_dir, pitch_dir = diag_map.get(direction_name, (0, 0))
    return f"H60,{az_dir},{pitch_dir},{speed}E".encode("ascii")

# Sentinel to stop worker thread
_STOP = object()

# Queue for broadcasting PTU movement commands (H51, H52, H61, etc.) to WebSocket clients.
# maxsize=1 so we keep only the newest; old data is dropped when full.
_command_broadcast_queue: queue.Queue = queue.Queue(maxsize=1)

# Serial connection state
_current_pan = 0.0
_current_tilt = 0.0
_serial: Optional["serial.Serial"] = None
_connected_port: Optional[str] = None
_connected_baud: Optional[int] = None
_worker_thread: Optional[threading.Thread] = None
_serial_lock = threading.Lock()
_command_queue: queue.Queue = queue.Queue()
_worker_stop = threading.Event()


def get_available_ports() -> list[str]:
    """Return list of available serial port names."""
    try:
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        return sorted([p.device for p in ports])
    except ImportError:
        logger.warning("pyserial not installed, returning empty port list")
        return []
    except Exception as e:
        logger.error("Error listing serial ports: %s", e)
        return []


def _degrees_to_pulse(deg: float) -> int:
    """Convert degrees to pulse count."""
    return int(round(deg * DEG_TO_PULSE))


def _pulse_to_degrees(pulse: int) -> float:
    """Convert pulse count to degrees."""
    return pulse * PULSE_TO_DEG


def _send_and_flush(payload: bytes) -> None:
    """Send bytes and flush. Caller must hold serial and ensure it is open."""
    if _serial is None or not _serial.is_open:
        return
    _serial.write(payload)
    try:
        _serial.flush()
    except Exception:
        pass


def _query_pulse(cmd: bytes) -> Optional[int]:
    """Send query command, read response, parse pulse value. Returns None on failure."""
    if _serial is None or not _serial.is_open:
        return None
    try:
        _serial.reset_input_buffer()
        _serial.write(cmd)
        _serial.flush()
        line = _serial.readline()
        if not line:
            return None
        text = line.decode("ascii", errors="ignore").strip()
        # Try to extract integer (e.g. *12345, A1=12345, 12345)
        m = re.search(r"[-]?\d+", text)
        if m:
            return int(m.group(0))
    except Exception as e:
        logger.warning("PTU query failed: %s", e)
    return None

def _serial_worker() -> None:
    """Worker thread: processes commands from queue and performs serial I/O."""
    global _current_pan, _current_tilt
    while not _worker_stop.is_set():
        try:
            cmd = _command_queue.get(timeout=0.2)
            if cmd is _STOP:
                break
            try:
                if _serial is not None and _serial.is_open:
                    if cmd[0] == "move_absolute":
                        _, pan_deg, tilt_deg, speed = cmd
                        az_pulse = _degrees_to_pulse(pan_deg)
                        pt_pulse = _degrees_to_pulse(tilt_deg)
                        payload = f"H51,{az_pulse},{pt_pulse},{speed}E".encode("ascii")
                        _send_and_flush(payload)
                        try:
                            _command_broadcast_queue.put_nowait(payload.decode("ascii"))
                        except queue.Full:
                            _command_broadcast_queue.get_nowait()
                            _command_broadcast_queue.put_nowait(payload.decode("ascii"))
                        logger.debug("PTU move absolute: pan=%.2f°, tilt=%.2f° (%d, %d pulses)", pan_deg, tilt_deg, az_pulse, pt_pulse)
                    elif cmd[0] == "move_relative":
                        _, pan_delta, tilt_delta, speed = cmd
                        d_az = _degrees_to_pulse(pan_delta)
                        d_pt = _degrees_to_pulse(tilt_delta)
                        payload = f"H52,{d_az},{d_pt},{speed}E".encode("ascii")
                        _send_and_flush(payload)
                        try:
                            _command_broadcast_queue.put_nowait(payload.decode("ascii"))
                        except queue.Full:
                            _command_broadcast_queue.get_nowait()
                            _command_broadcast_queue.put_nowait(payload.decode("ascii"))
                    elif cmd[0] == "query_position":
                        result_queue = cmd[1]
                        az_pulse = _query_pulse(b"H10E")
                        pt_pulse = _query_pulse(b"H20E")
                        if az_pulse is not None and pt_pulse is not None:
                            _current_pan = _pulse_to_degrees(az_pulse)
                            _current_tilt = _pulse_to_degrees(pt_pulse)
                        try:
                            result_queue.put((_current_pan, _current_tilt), block=False)
                        except queue.Full:
                            pass
                    elif cmd[0] == "direction":
                        direction_name = cmd[1]
                        speed = cmd[2] if len(cmd) >= 3 else _get_direction_speed_default()
                        #print(f"direction_name: {direction_name}, speed: {speed}")
                        if direction_name not in DIRECTION_COMMANDS:
                            raise ValueError(f"Unknown direction: {direction_name}")
                        payload = _build_direction_payload(direction_name, speed)

                        _serial.write(payload)
                        try:
                            _serial.flush()
                        except Exception:
                            # Some backends may not support flush reliably; ignore.
                            pass
                        try:
                            _command_broadcast_queue.put_nowait(payload.decode("ascii"))
                        except queue.Full:
                            _command_broadcast_queue.get_nowait()
                            _command_broadcast_queue.put_nowait(payload.decode("ascii"))
                        logger.debug("PTU direction sent: %s (%r)", direction_name, payload)
                    elif cmd[0] == "write":
                        _, data = cmd
                        _serial.write(data)
            except Exception as e:
                logger.error("PTU worker command failed: %s", e)
            finally:
                _command_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            logger.error("PTU worker error: %s", e)


def _enqueue(cmd: tuple) -> bool:
    """Enqueue command for worker. Returns True if queued, False if not connected."""
    if _serial is None:
        return False
    # For move commands: drop older move commands, keep only newest
    cmd_type = cmd[0] if cmd else None
    if cmd_type in ("move_absolute", "move_relative", "direction"):
        _drop_old_move_commands()
    _command_queue.put(cmd)
    return True


def _drop_old_move_commands() -> None:
    """Drain move commands from queue, keep non-move items (query_position, _STOP)."""
    kept: list = []
    try:
        while True:
            item = _command_queue.get_nowait()
            if item is _STOP:
                kept.append(item)
            elif isinstance(item, tuple) and item[0] == "query_position":
                kept.append(item)
            else:
                # move_absolute, move_relative, direction - drop
                pass
    except queue.Empty:
        pass
    for item in kept:
        _command_queue.put(item)


def move_absolute(pan: float, tilt: float, speed: int | None = None) -> tuple[bool, str]:
    """
    Move PTU to absolute position (degrees).
    Sends H51,<azimuth_pulse>,<pitch_pulse>,<speed_ptu>E
    Returns (success, message). Command is queued for worker thread.
    """
    speed = speed if speed is not None else _get_default_speed_ptu()
    try:
        if _connected_port:
            _enqueue(("move_absolute", pan, tilt, speed))
        return True, "OK"
    except Exception as e:
        logger.error("PTU move absolute failed: %s", e)
        return False, str(e)


def move_relative(pan_delta: float, tilt_delta: float, speed: int | None = None) -> tuple[bool, str]:
    """
    Move PTU relative to current position (degrees).
    Sends H52,<delta_azimuth_pulse>,<delta_pitch_pulse>,<speed_ptu>E
    Returns (success, message). Command is queued for worker thread.
    """
    speed = speed if speed is not None else _get_default_speed_ptu()
    try:
        if _connected_port:
            _enqueue(("move_relative", pan_delta, tilt_delta, speed))
        return True, "OK"
    except Exception as e:
        logger.error("PTU move relative failed: %s", e)
        return False, str(e)

def get_position() -> tuple[float, float]:
    """Return cached (pan, tilt) position in degrees."""
    return _current_pan, _current_tilt

def query_position() -> tuple[bool, float, float]:
    """
    Query PTU for actual position via H10E (azimuth) and H20E (pitch).
    Returns (success, pan_deg, tilt_deg). Blocks until response or timeout.
    Updates _current_pan and _current_tilt with the returned values.
    """
    global _current_pan, _current_tilt
    if not _connected_port or _serial is None or not _serial.is_open:
        return False, _current_pan, _current_tilt
    result_queue: queue.Queue = queue.Queue(maxsize=1)
    _command_queue.put(("query_position", result_queue))
    try:
        pan, tilt = result_queue.get(timeout=2.0)
        _current_pan = pan
        _current_tilt = tilt
        return True, pan, tilt
    except queue.Empty:
        logger.warning("PTU query_position timeout")
        return False, _current_pan, _current_tilt


def direction(direction_name: str, speed: int | None = None) -> tuple[bool, str]:
    """
    Move PTU in the given direction.
    direction_name: left, right, up, down, pause, left-up, left-down, right-up, right-down
    speed: optional PTU speed (40, 50, 60, etc.); default 50. Ignored for pause.
    Returns (success, message). Command is queued for worker thread.
    """
    if direction_name not in DIRECTION_COMMANDS:
        return False, f"Unknown direction: {direction_name}"
    try:
        if _connected_port:
            cmd: tuple = ("direction", direction_name)
            if speed is not None:
                cmd = ("direction", direction_name, speed)
            _enqueue(cmd)
        return True, "OK"
    except Exception as e:
        logger.error("PTU direction failed: %s", e)
        return False, str(e)


def connect(port: str, baud: int = 9600) -> tuple[bool, str]:
    """Connect to PTU on the given serial port. Starts worker thread. Returns (success, message)."""
    global _serial, _connected_port, _connected_baud, _worker_thread
    with _serial_lock:
        try:
            # Disconnect existing connection first
            if _serial is not None:
                _disconnect_internal()

            import serial
            _serial = serial.Serial(
                port=port,
                baudrate=baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.5,
                write_timeout=0.5,
            )
            _connected_port = port
            _connected_baud = baud

            # Start worker thread
            _worker_stop.clear()
            _worker_thread = threading.Thread(target=_serial_worker, daemon=True)
            _worker_thread.start()

            logger.info("PTU connected: %s @ %d (worker thread started)", port, baud)
            return True, "OK"
        except ImportError as e:
            logger.error("PTU connect failed (pyserial not installed): %s", e)
            _serial = None
            _connected_port = None
            _connected_baud = None
            return False, "pyserial not installed"
        except serial.SerialException as e:
            logger.error("PTU connect failed: %s", e)
            _serial = None
            _connected_port = None
            _connected_baud = None
            return False, str(e)
        except Exception as e:
            logger.error("PTU connect failed: %s", e)
            _serial = None
            _connected_port = None
            _connected_baud = None
            return False, str(e)


def _disconnect_internal() -> None:
    """Internal: stop worker, close serial. Caller must hold _serial_lock."""
    global _serial, _connected_port, _connected_baud, _worker_thread
    if _serial is not None:
        # Signal worker to stop and wait for it
        _worker_stop.set()
        _command_queue.put(_STOP)
        if _worker_thread is not None and _worker_thread.is_alive():
            _worker_thread.join(timeout=2.0)
            if _worker_thread.is_alive():
                logger.warning("PTU worker thread did not stop in time")
        _worker_thread = None
        try:
            _serial.close()
            logger.info("PTU disconnected: %s", _connected_port)
        except Exception as e:
            logger.warning("Error closing serial port: %s", e)
        finally:
            _serial = None
            _connected_port = None
            _connected_baud = None


def disconnect() -> tuple[bool, str]:
    """Disconnect from PTU. Returns (success, message)."""
    with _serial_lock:
        try:
            _disconnect_internal()
            return True, "OK"
        except Exception as e:
            logger.error("PTU disconnect failed: %s", e)
            return False, str(e)


def is_connected() -> bool:
    """Return whether PTU is connected."""
    return _connected_port is not None


def get_command_broadcast_queue() -> queue.Queue:
    """Return the queue of PTU movement commands for WebSocket broadcast."""
    return _command_broadcast_queue
