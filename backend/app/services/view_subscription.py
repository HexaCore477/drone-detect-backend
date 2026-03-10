"""View subscription state - controls when backend sends detection/PTU data to frontend."""
import threading

_operational_active = False
_waterfall_active = False
_lock = threading.Lock()


def set_operational_active(active: bool) -> None:
    """Set operational view subscription state."""
    global _operational_active
    with _lock:
        _operational_active = active


def set_waterfall_active(active: bool) -> None:
    """Set waterfall view subscription state."""
    global _waterfall_active
    with _lock:
        _waterfall_active = active


def should_send_tracking() -> bool:
    """Return True if detection/tracking data should be sent (operational or waterfall active)."""
    with _lock:
        return _operational_active or _waterfall_active


def should_send_ptu_commands() -> bool:
    """Return True if PTU commands should be sent (waterfall active only)."""
    with _lock:
        return _waterfall_active
