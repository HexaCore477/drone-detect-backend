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

PULSE_TO_DEG = 0.0009375
DEG_TO_PULSE = 1.0 / PULSE_TO_DEG

_resolution: float = PULSE_TO_DEG


def _get_ptu_baud() -> int:
    try:
        return int(os.getenv("PTU_BAUD", "9600"))
    except (TypeError, ValueError):
        return 9600

def _calc_query_delay(baud: int) -> float:
    if baud >= 115200: return 0.030
    if baud >= 38400:  return 0.080
    if baud >= 19200:  return 0.120
    return 0.200  # 9600 default


def _calc_h99_delay(baud: int) -> float:
    if baud >= 115200: return 0.060
    if baud >= 38400:  return 0.180
    if baud >= 19200:  return 0.280
    return 0.500  # 9600 default

_baud       = _get_ptu_baud()
_query_delay = _calc_query_delay(_baud)
_h99_delay   = _calc_h99_delay(_baud)


def _update_delays(baud: int) -> None:
    """Recompute read delays whenever the active baud rate changes."""
    global _query_delay, _h99_delay
    _query_delay = _calc_query_delay(baud)
    _h99_delay   = _calc_h99_delay(baud)
    logger.info("PTU read delays: query=%.3fs  h99=%.3fs  @%d baud",
                _query_delay, _h99_delay, baud)


# ---------------------------------------------------------------------------
# Speed helpers
# ---------------------------------------------------------------------------
def _get_default_speed_ptu() -> int:
    try:
        return int(os.getenv("DEFAULT_SPEED_PTU", "10000"))
    except (TypeError, ValueError):
        return 10000


def _get_direction_speed_default() -> int:
    try:
        return int(os.getenv("DIRECTION_SPEED_DEFAULT", "2000"))
    except (TypeError, ValueError):
        return 2000


def get_default_speed_ptu() -> int:
    return _get_default_speed_ptu()


# ---------------------------------------------------------------------------
# Direction helpers
# ---------------------------------------------------------------------------
DIRECTION_COMMANDS: dict[str, bytes] = {
    "left":       b"H61,2000E",
    "right":      b"H62,2000E",
    "up":         b"H63,2000E",
    "down":       b"H64,2000E",
    "right-up":   b"H60,-1,1,2000E",
    "left-down":  b"H60,1,-1,2000E",
    "right-down": b"H60,-1,-1,2000E",
    "left-up":    b"H60,1,1,2000E",
    "pause":      b"H65E",
}


def _build_direction_payload(direction_name: str, speed: int) -> bytes:
    if direction_name == "pause":
        return b"H65E"
    if direction_name in ("left", "right", "up", "down"):
        cmd_map = {"left": "H61", "right": "H62", "up": "H63", "down": "H64"}
        return f"{cmd_map[direction_name]},{speed}E".encode("ascii")
    diag_map = {
        "right-up":   (-1,  1),
        "left-down":  ( 1, -1),
        "right-down": (-1, -1),
        "left-up":    ( 1,  1),
    }
    az_dir, pitch_dir = diag_map.get(direction_name, (0, 0))
    return f"H60,{az_dir},{pitch_dir},{speed}E".encode("ascii")


# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
_STOP = object()

_command_broadcast_queue: queue.Queue = queue.Queue(maxsize=1)

_current_pan:  float = 0.0
_current_tilt: float = 0.0
_serial:         Optional["serial.Serial"] = None
_connected_port: Optional[str]             = None
_connected_baud: Optional[int]             = None
_worker_thread:  Optional[threading.Thread] = None
_serial_lock   = threading.Lock()
_command_queue: queue.Queue = queue.Queue()
_worker_stop   = threading.Event()


# ---------------------------------------------------------------------------
# Internal serial helpers  (worker thread only)
# ---------------------------------------------------------------------------
def _degrees_to_pulse(deg: float) -> int:
    """Convert degrees to pulse count."""
    return int(round(deg * DEG_TO_PULSE))


def _pulse_to_degrees(pulse: int) -> float:
    """Convert pulse count to degrees using current dynamic resolution."""
    return pulse * _resolution


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
    """Send H10E/H20E, wait baud-scaled delay, parse pulse reply."""
    if _serial is None or not _serial.is_open:
        return None
    try:
        _serial.write(cmd)
        _serial.flush()
        time.sleep(_query_delay)   # scaled to PTU_BAUD
        raw = _serial.read(32)
        if not raw:
            return None
        text = raw.decode("ascii", errors="ignore").strip()
        m = re.search(r"[-]?\d+", text)
        if m:
            return int(m.group(0))
    except Exception as e:
        logger.warning("PTU query failed: %s", e)
    return None


def _query_resolution_from_h99() -> Optional[float]:
    """Send H99E, wait baud-scaled delay, parse resolution."""
    if _serial is None or not _serial.is_open:
        return None
    try:
        _serial.write(b"H99E")
        _serial.flush()
        time.sleep(_h99_delay)   # scaled to PTU_BAUD
        raw = _serial.read(512)
        if not raw:
            return None
        text = raw.decode("ascii", errors="ignore")
        m = re.search(r"pulse\s*->\s*degree\s*=\s*([\d.]+)", text, re.IGNORECASE)
        if m:
            return float(m.group(1))
    except Exception as e:
        logger.warning("PTU H99E resolution query failed: %s", e)
    return None


# ---------------------------------------------------------------------------
# Worker thread
# ---------------------------------------------------------------------------
def _serial_worker() -> None:
    """Worker thread: processes commands from queue and performs serial I/O."""
    global _current_pan, _current_tilt, _resolution
    global _serial, _connected_port, _connected_baud
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
                            _current_pan  = _pulse_to_degrees(az_pulse)
                            _current_tilt = _pulse_to_degrees(pt_pulse)
                            logger.debug(
                                "PTU position: az=%d pulses → %.4f°, pt=%d pulses → %.4f° (res=%.9f °/pulse)",
                                az_pulse, _current_pan, pt_pulse, _current_tilt, _resolution,
                            )
                        try:
                            result_queue.put(
                                (_current_pan, _current_tilt, az_pulse, pt_pulse),
                                block=False,
                            )
                        except queue.Full:
                            pass

                    elif cmd[0] == "read_resolution":
                        result_queue = cmd[1]
                        res = _query_resolution_from_h99()
                        if res is not None:
                            _resolution = res
                            logger.info("PTU resolution updated via H99E: %.9f °/pulse", _resolution)
                        else:
                            logger.warning(
                                "PTU H99E query returned no resolution; keeping %.9f °/pulse",
                                _resolution,
                            )
                        try:
                            result_queue.put(_resolution, block=False)
                        except queue.Full:
                            pass

                    elif cmd[0] == "direction":
                        direction_name = cmd[1]
                        speed = cmd[2] if len(cmd) >= 3 else _get_direction_speed_default()
                        if direction_name not in DIRECTION_COMMANDS:
                            raise ValueError(f"Unknown direction: {direction_name}")
                        payload = _build_direction_payload(direction_name, speed)
                        _serial.write(payload)
                        try:
                            _serial.flush()
                        except Exception:
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
                err_str = str(e)
                _is_fatal = (
                    isinstance(e, PermissionError)
                    or (isinstance(e, OSError) and getattr(e, "errno", None) == 13)
                    or "PermissionError(13" in err_str
                    or "Access is denied" in err_str
                )
                if _is_fatal:
                    logger.error("PTU serial port access denied — auto-disconnecting")
                    try:
                        if _serial is not None:
                            _serial.close()
                    except Exception:
                        pass
                    _serial = None
                    _connected_port = None
                    _connected_baud = None
                    break
            finally:
                _command_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            logger.error("PTU worker error: %s", e)


# ---------------------------------------------------------------------------
# Queue helpers
# ---------------------------------------------------------------------------
def _enqueue(cmd: tuple) -> bool:
    """Enqueue command for worker. Returns True if queued, False if not connected."""
    if _serial is None:
        return False
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
            if item is _STOP or (isinstance(item, tuple) and item[0] == "query_position"):
                kept.append(item)
    except queue.Empty:
        pass
    for item in kept:
        _command_queue.put(item)


def _drop_old_position_queries() -> None:
    """Drain all pending query_position items; keep everything else."""
    kept: list = []
    try:
        while True:
            item = _command_queue.get_nowait()
            if item is _STOP or not (isinstance(item, tuple) and item[0] == "query_position"):
                kept.append(item)
    except queue.Empty:
        pass
    for item in kept:
        _command_queue.put(item)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_available_ports() -> list[str]:
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


def move_absolute(pan: float, tilt: float, speed: int | None = None) -> tuple[bool, str]:
    """
    Move PTU to absolute position (degrees).
    Sends H51,<azimuth_pulse>,<pitch_pulse>,<speed_ptu>E
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


def enqueue_position_query() -> bool:
    """
    Fire-and-forget positional refresh (Method 1).
    Enqueues H10E + H20E queries without blocking the caller.
    """
    if not _connected_port or _serial is None or not _serial.is_open:
        return False
    _drop_old_position_queries()
    result_queue: queue.Queue = queue.Queue(maxsize=1)
    _command_queue.put(("query_position", result_queue))
    return True


def query_position() -> tuple[bool, float, float, Optional[int], Optional[int]]:
    """
    Query PTU for actual position via H10E (azimuth) and H20E (pitch).
    Blocks until response or 2 s timeout. Updates internal position cache.
    Returns (success, pan_deg, tilt_deg, az_pulse, pt_pulse).
    """
    global _current_pan, _current_tilt
    if not _connected_port or _serial is None or not _serial.is_open:
        return False, _current_pan, _current_tilt, None, None
    result_queue: queue.Queue = queue.Queue(maxsize=1)
    _command_queue.put(("query_position", result_queue))
    try:
        pan, tilt, az_pulse, pt_pulse = result_queue.get(timeout=2.0)
        _current_pan = pan
        _current_tilt = tilt
        return True, pan, tilt, az_pulse, pt_pulse
    except queue.Empty:
        logger.warning("PTU query_position timeout")
        return False, _current_pan, _current_tilt, None, None


def read_resolution() -> tuple[bool, float]:
    """
    Query PTU resolution via H99E.
    Returns (success, resolution_degrees_per_pulse).
    Blocks up to 3 s.
    """
    global _resolution
    if not _connected_port or _serial is None or not _serial.is_open:
        return False, _resolution
    result_queue: queue.Queue = queue.Queue(maxsize=1)
    _command_queue.put(("read_resolution", result_queue))
    try:
        res = result_queue.get(timeout=3.0)
        _resolution = res
        return True, res
    except queue.Empty:
        logger.warning("PTU read_resolution timeout")
        return False, _resolution


def get_resolution() -> float:
    """Return the cached pulse-to-degree resolution (°/pulse)."""
    return _resolution


def direction(direction_name: str, speed: int | None = None) -> tuple[bool, str]:
    """
    Move PTU in the given direction.
    direction_name: left, right, up, down, pause, left-up, left-down, right-up, right-down
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


def connect(port: str, baud: int | None = None) -> tuple[bool, str]:
    """
    Connect to PTU on the given serial port.
    Baud rate is taken from PTU_BAUD env var (default 9600) unless explicitly passed.
    To change baud rate: run scripts/change_ptu_baud.py, then update PTU_BAUD in .env.
    """
    global _serial, _connected_port, _connected_baud, _worker_thread

    # Use env baud if caller did not supply one explicitly
    if baud is None:
        baud = _get_ptu_baud()

    with _serial_lock:
        try:
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
            _update_delays(baud)

            _worker_stop.clear()
            _worker_thread = threading.Thread(target=_serial_worker, daemon=True)
            _worker_thread.start()

            logger.info("PTU connected: %s @ %d baud (worker thread started)", port, baud)
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
    """Disconnect from PTU."""
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