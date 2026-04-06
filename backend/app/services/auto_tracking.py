"""Auto-tracking service — start/stop hook called by the config route.

All PTU control logic lives in tracking_pipeline._ptu_control_loop.
This module only handles the enable/disable lifecycle signal.
"""
import logging

logger = logging.getLogger(__name__)


async def start_auto_tracking() -> None:
    """
    Called by POST /config/auto-tracking when is_auto_tracking is set to true.
    The PTU control loop in tracking_pipeline reads get_auto_tracking() every
    cycle, so it activates automatically on the next tick.
    """
    logger.info("Auto-tracking enabled")


async def stop_auto_tracking() -> None:
    """
    Called by POST /config/auto-tracking when is_auto_tracking is set to false.
    The PTU control loop stops issuing commands on the next cycle.
    """
    logger.info("Auto-tracking disabled")