"""Joystick control service - maps joystick input to PTU direction commands.

When automatic object tracking is disabled, joystick control is active.
Runs in a background thread to avoid blocking the main process.
"""
import logging
import math
import threading
import time
from typing import Optional

from app.services import config as config_service
from app.services import ptu as ptu_service

logger = logging.getLogger(__name__)

# Deadzone: joystick values below this are treated as zero (prevents drift)
JOYSTICK_DEADZONE = 0.1

# Speed tiers based on joystick magnitude (absolute value 0..1)
# |joystick| < 0.1 -> pause
# 0.1 to 0.4 -> speed 40
# 0.4 to 0.7 -> speed 50
# 0.7 to 1.0 -> speed 60
SPEED_TIERS = [
    (0.1, 40),
    (0.4, 50),
    (0.7, 60),
]

# Poll interval (seconds)
POLL_INTERVAL_SEC = 0.05

# Joystick axis indices (typical gamepad layout)
AXIS_X = 0  # Left stick X: negative=left, positive=right
AXIS_Y = 1  # Left stick Y: negative=forward/up, positive=backward/down

_joystick_thread: Optional[threading.Thread] = None
_joystick_stop = threading.Event()
_joystick: Optional[object] = None


def _magnitude_to_speed(mag: float) -> int:
    """Map joystick magnitude (0..1) to PTU speed. Returns 0 for pause."""
    if mag < JOYSTICK_DEADZONE:
        return 0
    for threshold, speed in reversed(SPEED_TIERS):
        if mag >= threshold:
            return speed
    return SPEED_TIERS[0][1]


def _apply_deadzone(value: float) -> float:
    """Apply deadzone: values in [-deadzone, deadzone] become 0."""
    if abs(value) < JOYSTICK_DEADZONE:
        return 0.0
    # Rescale so output goes from 0 to 1 as input goes from deadzone to 1
    sign = 1.0 if value > 0 else -1.0
    return sign * (abs(value) - JOYSTICK_DEADZONE) / (1.0 - JOYSTICK_DEADZONE)


def _direction_from_axes(x: float, y: float) -> str:
    """
    Map joystick (x, y) to PTU direction.
    x: negative=left, positive=right
    y: negative=forward/up, positive=backward/down
    """
    if x == 0 and y == 0:
        return "pause"
    if abs(x) >= abs(y):
        if x > 0:
            return "right"
        return "left"
    if y > 0:
        return "down"
    return "up"


def _direction_from_axes_diagonal(x: float, y: float) -> str:
    """
    Map joystick (x, y) to PTU direction including diagonals.
    Uses angular thresholds: prefer diagonal when both axes are significant.
    """
    if x == 0 and y == 0:
        return "pause"
    # Normalize for direction selection
    mag = math.sqrt(x * x + y * y)
    if mag < 1e-6:
        return "pause"
    nx = x / mag
    ny = y / mag

    # Diagonal thresholds: if |nx| and |ny| are both > ~0.38 (45°), it's diagonal
    thresh = 0.38
    if abs(nx) > thresh and abs(ny) > thresh:
        if nx > 0 and ny < 0:
            return "right-up"
        if nx > 0 and ny > 0:
            return "right-down"
        if nx < 0 and ny > 0:
            return "left-down"
        if nx < 0 and ny < 0:
            return "left-up"

    # Cardinal
    if abs(nx) >= abs(ny):
        return "right" if nx > 0 else "left"
    return "up" if ny < 0 else "down"


def _joystick_loop() -> None:
    """Background thread: poll joystick and send PTU direction commands."""
    global _joystick
    try:
        import pygame

        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() == 0:
            logger.info("Joystick: no device found, control disabled")
            return
        _joystick = pygame.joystick.Joystick(0)
        _joystick.init()
        logger.info("Joystick: %s initialized", _joystick.get_name())
    except ImportError:
        logger.warning("Joystick: pygame not installed, control disabled")
        return
    except Exception as e:
        logger.warning("Joystick init failed: %s", e)
        return

    last_direction: Optional[str] = None
    last_speed = 0

    while not _joystick_stop.is_set():
        try:
            if config_service.get_auto_tracking():
                # Auto-tracking on: joystick disabled, send pause if we were moving
                if last_direction and last_direction != "pause":
                    ptu_service.direction("pause")
                    last_direction = "pause"
                    last_speed = 0
                time.sleep(POLL_INTERVAL_SEC)
                continue

            if not ptu_service.is_connected():
                time.sleep(POLL_INTERVAL_SEC)
                continue

            pygame.event.pump()
            x_raw = _joystick.get_axis(AXIS_X)
            y_raw = _joystick.get_axis(AXIS_Y)
            # Pygame axes: -1 to 1. Invert Y: forward push -> down, backward pull -> up
            x = _apply_deadzone(float(x_raw))
            y = -_apply_deadzone(float(y_raw))

            mag = math.sqrt(x * x + y * y)
            if mag > 1.0:
                mag = 1.0
            speed = _magnitude_to_speed(mag)

            if speed == 0:
                direction = "pause"
            else:
                direction = _direction_from_axes_diagonal(x, y)

            if direction != last_direction or speed != last_speed:
                ptu_service.direction(direction, speed if speed > 0 else None)
                last_direction = direction
                last_speed = speed

        except Exception as e:
            logger.error("Joystick loop error: %s", e, exc_info=True)

        time.sleep(POLL_INTERVAL_SEC)

    try:
        if _joystick is not None:
            _joystick.quit()
    except Exception:
        pass
    logger.info("Joystick control thread stopped")


def start_joystick() -> None:
    """Start the joystick control background thread."""
    global _joystick_thread
    if _joystick_thread is not None and _joystick_thread.is_alive():
        return
    _joystick_stop.clear()
    _joystick_thread = threading.Thread(target=_joystick_loop, daemon=True)
    _joystick_thread.start()
    logger.info("Joystick control thread started")


def stop_joystick() -> None:
    """Stop the joystick control background thread."""
    global _joystick_thread
    _joystick_stop.set()
    if _joystick_thread is not None and _joystick_thread.is_alive():
        _joystick_thread.join(timeout=2.0)
        if _joystick_thread.is_alive():
            logger.warning("Joystick thread did not stop in time")
    _joystick_thread = None
    logger.info("Joystick control stopped")
