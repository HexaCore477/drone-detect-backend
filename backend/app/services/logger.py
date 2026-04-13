"""Logging service - logs target states, PTU reactions, tracking errors, and errors."""

import logging
import os
import queue
import threading
from typing import Any, Optional

PTU_EVENT_LOG = logging.getLogger("ptu.event")
TRACKING_LOG = logging.getLogger("tracking")
PTU_ERROR_LOG = logging.getLogger("ptu.error")

_logs_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
os.makedirs(_logs_dir, exist_ok=True)

_tracking_handler = logging.FileHandler(os.path.join(_logs_dir, "tracking.log"))
_tracking_handler.setLevel(logging.DEBUG)
_tracking_handler.setFormatter(
    logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
TRACKING_LOG.addHandler(_tracking_handler)
TRACKING_LOG.setLevel(logging.DEBUG)
TRACKING_LOG.propagate = False

_ptu_handler = logging.FileHandler(os.path.join(_logs_dir, "ptu.log"))
_ptu_handler.setLevel(logging.DEBUG)
_ptu_handler.setFormatter(
    logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
PTU_EVENT_LOG.addHandler(_ptu_handler)
PTU_EVENT_LOG.setLevel(logging.DEBUG)
PTU_EVENT_LOG.propagate = False

_error_handler = logging.FileHandler(os.path.join(_logs_dir, "ptu_error.log"))
_error_handler.setLevel(logging.ERROR)
_error_handler.setFormatter(
    logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
PTU_ERROR_LOG.addHandler(_error_handler)
PTU_ERROR_LOG.setLevel(logging.ERROR)
PTU_ERROR_LOG.propagate = False


def log_target_state(pan: float, tilt: float, speed: Optional[int] = None) -> None:
    """Log target position (requested)."""
    msg = f"target pan={pan:.4f} tilt={tilt:.4f}"
    if speed is not None:
        msg += f" speed={speed}"
    PTU_EVENT_LOG.info(msg)


def log_ptu_reaction(
    cmd_type: str,
    cmd_data: str,
    pan: float,
    tilt: float,
    speed: Optional[int] = None,
) -> None:
    """Log PTU reaction (command sent to serial)."""
    msg = f"reaction {cmd_type}: {cmd_data} -> pan={pan:.4f} tilt={tilt:.4f}"
    if speed is not None:
        msg += f" speed={speed}"
    PTU_EVENT_LOG.info(msg)


def log_tracking_error(
    err_px_x: float,
    err_px_y: float,
    err_px_mag: float,
    vx_deg: float,
    vy_deg: float,
    speed: int,
) -> None:
    """Log tracking error (target) vs PTU reaction (command in degrees)."""
    TRACKING_LOG.info(
        f"error: px_x={err_px_x:.1f} px_y={err_px_y:.1f} px_mag={err_px_mag:.1f} "
        f"cmd_deg: vx={vx_deg:.4f} vy={vy_deg:.4f} speed={speed}"
    )


def log_error(source: str, error: Exception) -> None:
    """Log PTU error."""
    PTU_ERROR_LOG.error(f"[{source}] {type(error).__name__}: {error}")


def log_connection(port: str, baud: int, success: bool) -> None:
    """Log PTU connection attempt."""
    if success:
        PTU_EVENT_LOG.info(f"connected: {port} @ {baud} baud")
    else:
        PTU_ERROR_LOG.error(f"connect failed: {port} @ {baud} baud")


def log_disconnection(port: Optional[str]) -> None:
    """Log PTU disconnection."""
    PTU_EVENT_LOG.info(f"disconnected: {port}")


def log_position_query(
    pan: float, tilt: float, az_pulse: Optional[int], pt_pulse: Optional[int]
) -> None:
    """Log position query result."""
    PTU_EVENT_LOG.info(
        f"position: pan={pan:.4f} tilt={tilt:.4f} pulse_az={az_pulse} pulse_pt={pt_pulse}"
    )


def log_direction(direction: str, speed: int, cmd_data: str) -> None:
    """Log direction command."""
    PTU_EVENT_LOG.info(f"direction: {direction} speed={speed} cmd={cmd_data}")


def log_resolution(resolution: float) -> None:
    """Log resolution read from PTU."""
    PTU_EVENT_LOG.info(f"resolution: {resolution:.9f} deg/pulse")
