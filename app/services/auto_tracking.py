"""Automatic tracking service - moves PTU to align predicted point with frame center."""
import asyncio
import logging
import threading
import time
from typing import Optional, Tuple

from app.services import config as config_service
from app.services import ptu as ptu_service
from app.api.routes import tracking as tracking_routes
from app.services.camera import get_resolution

logger = logging.getLogger(__name__)

# Auto-tracking configuration
DEFAULT_HFOV_DEG = 60.0  # Horizontal field of view in degrees
DEADBAND_PX = 5.0  # Don't move if error is smaller than this (pixels)
MAX_STEP_DEG = 2.0  # Maximum step per update in degrees
AUTO_TRACKING_SPEED = 50  # PTU speed for auto-tracking moves
UPDATE_INTERVAL_SEC = 0.1  # Check every 100ms
PREDICTION_LEAD_SEC = 0.5  # 500ms ahead prediction
# PTU axis inversion
# Horizontal movement is correct; vertical is inverted.
INVERT_PAN = True    # keep horizontal inversion
INVERT_PITCH = False # disable vertical inversion so tilt matches image

async def _run_auto_tracking_loop() -> None:
    """Main auto-tracking loop - runs continuously."""
    loop_count = 0
    
    logger.info("Auto-tracking loop started")
    
    while True:
        try:
            loop_count += 1
            
            # Check if auto-tracking is enabled
            is_enabled = config_service.get_auto_tracking()
            if not is_enabled:
                if loop_count % 50 == 0:  # Log every 5 seconds when disabled
                    logger.debug("Auto-tracking: disabled (loop running)")
                await asyncio.sleep(UPDATE_INTERVAL_SEC)
                continue
            
            # Check if PTU is connected
            is_ptu_connected = ptu_service.is_connected()
            if not is_ptu_connected:
                logger.debug("Auto-tracking: PTU not connected, waiting...")
                await asyncio.sleep(UPDATE_INTERVAL_SEC)
                continue
            
            # Use latest predicted point from tracking WebSocket pipeline
            pred = tracking_routes.get_last_prediction()
            if not pred:
                if loop_count % 10 == 0:
                    logger.debug("Auto-tracking: no shared prediction yet")
                await asyncio.sleep(UPDATE_INTERVAL_SEC)
                continue

            pred_x = pred["x"]
            pred_y = pred["y"]
            width = pred["width"]
            height = pred["height"]

            center_x = width / 2.0
            center_y = height / 2.0
            
            # Calculate error (predicted point relative to center)
            error_x = pred_x - center_x  # Positive = predicted is RIGHT of center
            error_y = center_y - pred_y  # Positive = predicted is ABOVE center (y increases down)
            
            error_px = (error_x**2 + error_y**2) ** 0.5
            if error_px < DEADBAND_PX:
                logger.debug("Auto-tracking: error too small (%.1f px), skipping", error_px)
                await asyncio.sleep(UPDATE_INTERVAL_SEC)
                continue
            
            # Convert pixels to degrees
            deg_per_px_x = DEFAULT_HFOV_DEG / width
            deg_per_px_y = (DEFAULT_HFOV_DEG * (height / width)) / height
            
            # To move center toward predicted point (quadrant logic):
            # - Predicted in upper-right  -> pan right (+), tilt up   (+)
            # - Predicted in lower-right  -> pan right (+), tilt down (-)
            # - Predicted in upper-left   -> pan left  (-), tilt up   (+)
            # - Predicted in lower-left   -> pan left  (-), tilt down (-)
            delta_pan = error_x * deg_per_px_x
            delta_pitch = error_y * deg_per_px_y
            
            # Limit step size
            mag = (delta_pan**2 + delta_pitch**2) ** 0.5
            if mag > MAX_STEP_DEG:
                scale = MAX_STEP_DEG / mag
                delta_pan *= scale
                delta_pitch *= scale
            
            # PTU H52: positive azimuth = right, positive pitch = up.
            # Hardware is inverted relative to this math, so match
            # the calibrated frontend behavior by flipping both axes.
            if INVERT_PAN:
                delta_pan = -delta_pan
            if INVERT_PITCH:
                delta_pitch = -delta_pitch
            
            logger.info(
                "Auto-tracking: pred=(%.1f, %.1f), center=(%.1f, %.1f), error=(%.1f, %.1f) px, "
                "move=(%.3f°, %.3f°)",
                pred_x, pred_y, center_x, center_y, error_x, error_y, delta_pan, delta_pitch
            )
            
            # Move PTU
            success, msg = ptu_service.move_relative(delta_pan, delta_pitch, AUTO_TRACKING_SPEED)
            if not success:
                logger.warning("Auto-tracking move failed: %s", msg)
            else:
                logger.debug("Auto-tracking move sent: pan=%.3f°, pitch=%.3f°, speed=%d", 
                           delta_pan, delta_pitch, AUTO_TRACKING_SPEED)
            
            await asyncio.sleep(UPDATE_INTERVAL_SEC)
            
        except Exception as e:
            logger.error("Error in auto-tracking loop: %s", e, exc_info=True)
            await asyncio.sleep(UPDATE_INTERVAL_SEC)


_auto_tracking_task: Optional[asyncio.Task] = None


async def start_auto_tracking() -> None:
    """Start the auto-tracking background task."""
    global _auto_tracking_task
    if _auto_tracking_task is None or _auto_tracking_task.done():
        try:
            _auto_tracking_task = asyncio.create_task(_run_auto_tracking_loop())
            logger.info("Auto-tracking task started successfully")
        except Exception as e:
            logger.error("Failed to start auto-tracking task: %s", e, exc_info=True)


async def stop_auto_tracking() -> None:
    """Stop the auto-tracking background task."""
    global _auto_tracking_task
    if _auto_tracking_task is not None and not _auto_tracking_task.done():
        _auto_tracking_task.cancel()
        try:
            await _auto_tracking_task
        except asyncio.CancelledError:
            pass
        _auto_tracking_task = None
        logger.info("Auto-tracking task stopped")
