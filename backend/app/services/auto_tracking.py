"""Automatic tracking service"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

MAX_PTU_SPEED       = 10000
MIN_PTU_SPEED       = 100
DEFAULT_HFOV_DEG    = 60.0
DEADBAND_PX         = 5.0
MAX_STEP_DEG        = 15.0
MIN_STEP_DEG        = 0.0
UPDATE_INTERVAL_SEC = 0.1
PREDICTION_LEAD_SEC = 0.0
INVERT_PAN          = True
INVERT_PITCH        = False


def _get_speed_from_distance(distance_px: float, width: float) -> int:
    if width <= 0:
        return MAX_PTU_SPEED
    norm = min(distance_px / (width / 3), 1.0)
    return int(MIN_PTU_SPEED + norm * (MAX_PTU_SPEED - MIN_PTU_SPEED))


def _get_step_from_distance(distance_px: float, width: float) -> float:
    if width <= 0:
        return MAX_STEP_DEG
    norm = min(distance_px / (width / 3), 1.0)
    return MIN_STEP_DEG + norm * (MAX_STEP_DEG - MIN_STEP_DEG)


async def start_auto_tracking() -> None:
    """
    Called by config route when frontend enables auto-tracking.
    The actual PTU control is handled by tracking_pipeline._ptu_control_loop
    which reads config_service.get_auto_tracking() every cycle.
    """
    logger.info("Auto-tracking enabled (PTU control via tracking_pipeline)")


async def stop_auto_tracking() -> None:
    """
    Called by config route when frontend disables auto-tracking.
    tracking_pipeline._ptu_control_loop stops sending commands automatically
    on the next cycle because get_auto_tracking() will return False.
    """
    logger.info("Auto-tracking disabled")