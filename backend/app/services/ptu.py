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

# Pulse <-> degree conversion: angle = pulse × 0.0009375 (PTU42 default)
PULSE_TO_DEG = 0.0009375
DEG_TO_PULSE = 1.0 / PULSE_TO_DEG

_resolution: float = PULSE_TO_DEG

def _calc_query_delay(baud: int) -> float:
    """Return the H10E/H20E read delay in seconds for the given baud rate."""
    if baud >= 115200:
        return 0.030
    if baud >= 38400:
        return 0.080
    if baud >= 19200:
        return 0.120
    # Default / 9600
    return 0.200


def _calc_h99_delay(baud: int) -> float:
    """Return the H99E read delay in seconds for the given baud rate."""
    if baud >= 115200:
        return 0.060
    if baud >= 38400:
        return 0.180
    if baud >= 19200:
        return 0.280
    # Default / 9600
    return 0.500

_query_delay: float = _calc_query_delay(9600)
_h99_delay: float   = _calc_h99_delay(9600)


def _update_delays(baud: int) -> None:
    """Recompute read delays for the current baud rate."""
    global _query_delay, _h99_delay
    _query_delay = _calc_query_delay(baud)
    _h99_delay   = _calc_h99_delay(baud)
    logger.info(
        "PTU read delays updated for %d baud: query=%.3fs, h99=%.3fs",
        baud, _query_delay, _h99_delay,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    """Send query command, read response, parse pulse value. Returns None on failure.
    """
    if _serial is None or not _serial.is_open:
        return None
    try:
        _serial.write(cmd)
        _serial.flush()
        time.sleep(_query_delay)
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
    """
    Send H99E and parse the 'pulse-> degree = <value>' line from the response.
    Returns the resolution float on success, None on failure.
    """
    if _serial is None or not _serial.is_open:
        return None
    try:
        _serial.write(b"H99E")
        _serial.flush()
        time.sleep(_h99_delay)
        raw = _serial.read(512)  # ReadFile — safe on Windows
        if not raw:
            return None
        text = raw.decode("ascii", errors="ignore")
        m = re.search(r"pulse\s*->\s*degree\s*=\s*([\d.]+)", text, re.IGNORECASE)
        if m:
            return float(m.group(1))
    except Exception as e:
        logger.warning("PTU H99E resolution query failed: %s", e)
    return None


def _change_baud_on_device(new_baud: int) -> bool:
    """
    Send H93 to the PTU to change its serial baud rate, then reopen the host
    port at the new baud rate.
    """
    global _serial, _connected_port, _connected_baud

    if _serial is None or not _serial.is_open:
        logger.warning("_change_baud_on_device: serial not open")
        return False

    # Only 9600 and 115200 are supported by the device.
    baud_param_map = {9600: 1, 115200: 2}
    baud_param = baud_param_map.get(new_baud)
    if baud_param is None:
        logger.error(
            "_change_baud_on_device: unsupported baud rate %d (must be 9600 or 115200)",
            new_baud,
        )
        return False

    # Use a conservative max_speed default; H93 third parameter is the speed
    # percent/pulse mapping — preserve the device default (20000).
    max_speed = 20000
    cmd = f"H93,{baud_param},1,{max_speed}E".encode("ascii")

    logger.info(
        "Sending baud-rate change command to PTU: %s  (new baud: %d)",
        cmd.decode("ascii"), new_baud,
    )

    try:
        _serial.write(cmd)
        _serial.flush()
    except Exception as e:
        logger.error("Failed to send H93 baud change: %s", e)
        return False

    # H93 saves the setting and restarts the device immediately.
    # Give it 1.5 s to restart before reopening.
    time.sleep(1.5)

    # Reopen the serial port at the new baud rate.
    port = _connected_port
    try:
        _serial.close()
    except Exception:
        pass

    try:
        import serial as _serial_mod
        _serial = _serial_mod.Serial(
            port=port,
            baudrate=new_baud,
            bytesize=_serial_mod.EIGHTBITS,
            parity=_serial_mod.PARITY_NONE,
            stopbits=_serial_mod.STOPBITS_ONE,
            timeout=0.5,
            write_timeout=0.5,
        )
        _connected_baud = new_baud
        _update_delays(new_baud)
        logger.info("PTU port %s reopened at %d baud", port, new_baud)
        return True
    except Exception as e:
        logger.error("Failed to reopen serial port at %d baud: %s", new_baud, e)
        _serial = None
        _connected_port = None
        _connected_baud = None
        return False


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
                            _current_pan = _pulse_to_degrees(az_pulse)
                            _current_tilt = _pulse_to_degrees(pt_pulse)
                            logger.debug(
                                "PTU position: az=%d pulses → %.4f°, pt=%d pulses → %.4f° (res=%.9f °/pulse)",
                                az_pulse, _current_pan, pt_pulse, _current_tilt, _resolution,
                            )
                        try:
                            result_queue.put(
                                (_current_pan, _current_tilt, az_pulse, pt_pulse), block=False
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

                    elif cmd[0] == "change_baud":
                        # change_baud must acquire _serial_lock; do it here in the worker
                        # to avoid deadlock (worker is the only thread that does serial I/O).
                        new_baud = cmd[1]
                        result_queue = cmd[2]
                        with _serial_lock:
                            ok = _change_baud_on_device(new_baud)
                        try:
                            result_queue.put(ok, block=False)
                        except queue.Full:
                            pass

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
            if item is _STOP:
                kept.append(item)
            elif isinstance(item, tuple) and item[0] == "query_position":
                kept.append(item)
            else:
                pass  # move_absolute, move_relative, direction — drop
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


def change_baud_rate(new_baud: int) -> tuple[bool, str]:
    """
    Change the PTU serial baud rate at runtime.
    """
    if new_baud not in (9600, 115200):
        return False, f"Unsupported baud rate {new_baud}. Must be 9600 or 115200."

    if not _connected_port or _serial is None or not _serial.is_open:
        return False, "PTU not connected"

    if _connected_baud == new_baud:
        return True, f"Already at {new_baud} baud — no change needed"

    result_queue: queue.Queue = queue.Queue(maxsize=1)
    _command_queue.put(("change_baud", new_baud, result_queue))
    try:
        # Allow up to 5 s: 1.5 s restart sleep + reopen overhead
        ok = result_queue.get(timeout=5.0)
        if ok:
            logger.info("PTU baud rate changed to %d", new_baud)
            return True, "OK"
        return False, f"Failed to change baud rate to {new_baud}"
    except queue.Empty:
        logger.warning("PTU change_baud_rate timeout")
        return False, "Baud rate change timed out"


def connect(port: str, baud: int = 9600) -> tuple[bool, str]:
    """Connect to PTU on the given serial port. Starts worker thread."""
    global _serial, _connected_port, _connected_baud, _worker_thread
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