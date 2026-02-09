"""PTU (Pan-Tilt Unit) service - serial port listing and move commands."""
import logging
import queue
import re
import threading
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no cover
    import serial  # type: ignore

logger = logging.getLogger(__name__)

# Pulse <-> degree conversion: angle = pulse × 0.0009375
PULSE_TO_DEG = 0.0009375
DEG_TO_PULSE = 1.0 / PULSE_TO_DEG
DEFAULT_SPEED_PTU = 4000

# move_absolute: H51,<azimuth_pulse>,<pitch_pulse>,<speed_ptu>E
# move_relative: H52,<delta_azimuth_pulse>,<delta_pitch_pulse>,<speed_ptu>E
# H10E → get azimuth (A1) in pulses
# H20E → get pitch (A2) in pulses

DIRECTION_COMMANDS: dict[str, bytes] = {
    "left": b"H61,50E",
    "right": b"H62,50E",
    "up": b"H63,50E",
    "down": b"H64,50E",
    "right-up": b"H60,-1,1,50E",
    "left-down": b"H60,1,-1,50E",
    "right-down": b"H60,-1,-1,50E",
    "left-up": b"H60,1,1,50E",
    "pause": b"H65E",
}

# Sentinel to stop worker thread
_STOP = object()


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
                        _current_pan = pan_deg
                        _current_tilt = tilt_deg
                        logger.debug("PTU move absolute: pan=%.2f°, tilt=%.2f° (%d, %d pulses)", pan_deg, tilt_deg, az_pulse, pt_pulse)
                    elif cmd[0] == "move_relative":
                        _, pan_delta, tilt_delta, speed = cmd
                        d_az = _degrees_to_pulse(pan_delta)
                        d_pt = _degrees_to_pulse(tilt_delta)
                        payload = f"H52,{d_az},{d_pt},{speed}E".encode("ascii")
                        _send_and_flush(payload)
                        _current_pan += pan_delta
                        _current_tilt += tilt_delta
                        logger.debug(
                            "PTU move relative: Δpan=%.2f°, Δtilt=%.2f° (%d, %d pulses) -> pan=%.2f°, tilt=%.2f°",
                            pan_delta, tilt_delta, d_az, d_pt, _current_pan, _current_tilt,
                        )
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
                        _, direction_name = cmd
                        payload = DIRECTION_COMMANDS.get(direction_name)
                        if payload is None:
                            raise ValueError(f"Unknown direction: {direction_name}")

                        # Send ASCII command as-is
                        _serial.write(payload)
                        try:
                            _serial.flush()
                        except Exception:
                            # Some backends may not support flush reliably; ignore.
                            pass

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
    _command_queue.put(cmd)
    return True


def move_absolute(pan: float, tilt: float, speed: int = DEFAULT_SPEED_PTU) -> tuple[bool, str]:
    """
    Move PTU to absolute position (degrees).
    Sends H51,<azimuth_pulse>,<pitch_pulse>,<speed_ptu>E
    Returns (success, message). Command is queued for worker thread.
    """
    try:
        if _connected_port:
            _enqueue(("move_absolute", pan, tilt, speed))
        else:
            global _current_pan, _current_tilt
            _current_pan = pan
            _current_tilt = tilt
        return True, "OK"
    except Exception as e:
        logger.error("PTU move absolute failed: %s", e)
        return False, str(e)


def move_relative(pan_delta: float, tilt_delta: float, speed: int = DEFAULT_SPEED_PTU) -> tuple[bool, str]:
    """
    Move PTU relative to current position (degrees).
    Sends H52,<delta_azimuth_pulse>,<delta_pitch_pulse>,<speed_ptu>E
    Returns (success, message). Command is queued for worker thread.
    """
    try:
        if _connected_port:
            _enqueue(("move_relative", pan_delta, tilt_delta, speed))
        else:
            global _current_pan, _current_tilt
            _current_pan += pan_delta
            _current_tilt += tilt_delta
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
    """
    if not _connected_port or _serial is None or not _serial.is_open:
        return False, _current_pan, _current_tilt
    result_queue: queue.Queue = queue.Queue(maxsize=1)
    _command_queue.put(("query_position", result_queue))
    try:
        pan, tilt = result_queue.get(timeout=2.0)
        return True, pan, tilt
    except queue.Empty:
        logger.warning("PTU query_position timeout")
        return False, _current_pan, _current_tilt


def direction(direction_name: str) -> tuple[bool, str]:
    """
    Move PTU in the given direction.
    direction_name: left, right, up, down, pause, left-up, left-down, right-up, right-down
    Returns (success, message). Command is queued for worker thread.
    """
    if direction_name not in DIRECTION_COMMANDS:
        return False, f"Unknown direction: {direction_name}"
    try:
        if _connected_port:
            _enqueue(("direction", direction_name))
        # If not connected, we don't have hardware to move. Treat as no-op success.
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
