"""PTU (Pan-Tilt Unit) service - serial port listing and move commands."""
import logging
import queue
import threading
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no cover
    import serial  # type: ignore

logger = logging.getLogger(__name__)

#
# PTU protocol direction commands (ASCII) as provided.
# We send these bytes exactly over the serial port.
#
# LEFT:        H61,10000E
# RIGHT:       H62,10000E
# TOP:         H63,10000E
# DOWN:        H64,10000E
# TOP-RIGHT:   H60,-1,1,50E
# DOWN-LEFT:   H60,1,-1,50E
# DOWN-RIGHT:  H60,-1,-1,50E
# TOP-LEFT:    H60,1,1,50E
# STOP:        H65E
#
DIRECTION_COMMANDS: dict[str, bytes] = {
    "left": b"H61,10000E",
    "right": b"H62,10000E",
    "up": b"H63,10000E",
    "down": b"H64,10000E",
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
                        _, pan, tilt = cmd
                        _current_pan = pan
                        _current_tilt = tilt
                        # TODO: Send PTU protocol bytes over _serial.write()
                        logger.debug("PTU move absolute: pan=%.2f, tilt=%.2f", pan, tilt)
                    elif cmd[0] == "move_relative":
                        _, pan_delta, tilt_delta = cmd
                        _current_pan += pan_delta
                        _current_tilt += tilt_delta
                        # TODO: Send PTU protocol bytes over _serial.write()
                        logger.debug(
                            "PTU move relative: pan_delta=%.2f, tilt_delta=%.2f -> pan=%.2f, tilt=%.2f",
                            pan_delta, tilt_delta, _current_pan, _current_tilt,
                        )
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


def move_absolute(pan: float, tilt: float) -> tuple[bool, str]:
    """
    Move PTU to absolute position (degrees).
    Returns (success, message). Command is queued for worker thread.
    """
    try:
        if _connected_port:
            _enqueue(("move_absolute", pan, tilt))
        else:
            global _current_pan, _current_tilt
            _current_pan = pan
            _current_tilt = tilt
        return True, "OK"
    except Exception as e:
        logger.error("PTU move absolute failed: %s", e)
        return False, str(e)


def move_relative(pan_delta: float, tilt_delta: float) -> tuple[bool, str]:
    """
    Move PTU relative to current position (degrees).
    Returns (success, message). Command is queued for worker thread.
    """
    try:
        if _connected_port:
            _enqueue(("move_relative", pan_delta, tilt_delta))
        else:
            global _current_pan, _current_tilt
            _current_pan += pan_delta
            _current_tilt += tilt_delta
        return True, "OK"
    except Exception as e:
        logger.error("PTU move relative failed: %s", e)
        return False, str(e)


def get_position() -> tuple[float, float]:
    """Return current (pan, tilt) position in degrees."""
    return _current_pan, _current_tilt


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
