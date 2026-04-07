"""
Asynchronous tracking pipeline with three parallel threads:
  Thread 1: Grab frames continuously -> Shared Buffer
  Thread 2: Run detection on frames from buffer -> shared_target_position
  Thread 3: PID + feedforward velocity-mode PTU controller (H60)

Controller design:
  - Full PID (P + I + D) on pixel error
  - Velocity feedforward from Kalman state (vx, vy)
  - Integral anti-windup (clamp + conditional integration)
  - Derivative on measurement (not on error) to avoid derivative kick
  - Reduced EMA alpha for faster response
  - Staleness guard: skips predictions older than 150 ms
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional

import cv2
from app.services.camera import _create_capture, _release_capture

logger = logging.getLogger(__name__)

# --- GLOBAL SHARED STATE ---
_frame_lock = threading.Lock()
_current_frame: Optional[cv2.Mat] = None
_pipeline_stop = threading.Event()

# Thread handles
_capture_thread:   Optional[threading.Thread] = None
_detection_thread: Optional[threading.Thread] = None
_ptu_thread:       Optional[threading.Thread] = None

# Shared result for WebSocket consumers
_result_lock = threading.Lock()
_latest_result: Optional[Dict[str, Any]] = None

# ---------------------------------------------------------------------------
# PTU controller constants
# ---------------------------------------------------------------------------
PTU_INVERT_PAN  = True
PTU_INVERT_TILT = False

LASER_OFFSET_X = -10
LASER_OFFSET_Y =  40

PTU_HFOV_DEG = 60.0

# ── PID gains (pan axis) ────────────────────────────────────────────────────
# Kp: proportional — main driving force toward center
# Ki: integral     — eliminates steady-state offset (target never reaches center)
# Kd: derivative   — damps oscillation / overshoot
PAN_KP  = 1.20
PAN_KI  = 0.08   # small: we don't want slow windup to fight fast motion
PAN_KD  = 0.30

# ── PID gains (tilt axis) ───────────────────────────────────────────────────
TILT_KP = 0.80
TILT_KI = 0.05
TILT_KD = 0.20

# ── Velocity feedforward gains ──────────────────────────────────────────────
# Applied to Kalman vx/vy (px/s) to anticipate target motion before error builds
PTU_GAIN_VX = 0.55  # pan  feedforward
PTU_GAIN_VY = 0.35  # tilt feedforward

# ── Integral anti-windup clamp (in degree-equivalent units) ─────────────────
# Prevents integral from accumulating when target is far out of frame
PAN_INTEGRAL_CLAMP  = 15.0
TILT_INTEGRAL_CLAMP = 10.0

# ── Integral conditional: only integrate when error is small enough ──────────
# Avoids integral windup during large slews
INTEGRAL_ENABLE_THRESHOLD_PX = 80

# H60 speed range (pulse/s)
PTU_MAX_SPEED = 10000
PTU_MIN_SPEED = 300

PTU_LOOP_SEC = 0.02  # 50 Hz — must match dt used in integral/derivative

# Deadband: inside this radius (px) PTU stops and holds
# Reduced from 6 → 2 for better centering
PTU_DEADBAND_PX = 2

# EMA alpha on raw error before PID (anti-jitter, not anti-response)
# Reduced from 0.15 → 0.08 — faster response with less smoothing
PTU_ERROR_EMA_ALPHA = 0.08

# Normalised H60 vector magnitude cap
PTU_MAX_VECTOR = 100

# Prediction lead: how far ahead (seconds) to place the aim point
# Reduced from 0.35 → 0.25 for tighter tracking response
PREDICTION_LEAD_SEC = 0.25

# Staleness guard: ignore predictions older than this
PREDICTION_MAX_AGE_SEC = 0.15


# ---------------------------------------------------------------------------
# Thread 1 — continuous frame capture
# ---------------------------------------------------------------------------
def _capture_loop() -> None:
    global _current_frame
    cap = _create_capture()
    if cap is None:
        logger.error("Pipeline: failed to create capture, capture thread exiting")
        return
    try:
        while not _pipeline_stop.is_set():
            if cap.grab():
                ret, frame = cap.retrieve()
                if ret and frame is not None:
                    with _frame_lock:
                        _current_frame = frame
            else:
                logger.warning("Stream lost, attempting reconnect…")
                _release_capture(cap)
                cap = None
                time.sleep(1.0)
                cap = _create_capture()
                if cap is None:
                    logger.error("Reconnect failed, will retry in 1 s")
    except Exception as e:
        logger.error("Pipeline capture thread error: %s", e, exc_info=True)
    finally:
        if cap is not None:
            _release_capture(cap)


# ---------------------------------------------------------------------------
# Thread 2 — YOLO detection + Kalman tracking
# ---------------------------------------------------------------------------
def _detection_loop() -> None:
    from app.api.routes.tracking import _run_detection_on_frame

    global _latest_result
    tracks: Dict = {}
    next_track_id = 0
    last_frame_id = None

    try:
        while not _pipeline_stop.is_set():
            with _frame_lock:
                frame = _current_frame

            if frame is None:
                time.sleep(0.005)
                continue

            frame_id = id(frame)
            if frame_id == last_frame_id:
                time.sleep(0.002)
                continue
            last_frame_id = frame_id

            try:
                tracks, next_track_id, payload = _run_detection_on_frame(
                    frame, tracks, next_track_id
                )
                with _result_lock:
                    _latest_result = payload
            except Exception as e:
                logger.error("Pipeline detection error: %s", e, exc_info=True)
    except Exception as e:
        logger.error("Pipeline detection thread error: %s", e, exc_info=True)


# ---------------------------------------------------------------------------
# PID state container
# ---------------------------------------------------------------------------
class _PIDAxis:
    """Single-axis PID with anti-windup and derivative-on-measurement."""

    def __init__(self, kp: float, ki: float, kd: float, integral_clamp: float, dt: float):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.integral_clamp = integral_clamp
        self.dt = dt
        # state
        self.integral: float = 0.0
        self.prev_measurement: float = 0.0   # derivative on measurement
        self._initialised: bool = False

    def reset(self) -> None:
        self.integral = 0.0
        self.prev_measurement = 0.0
        self._initialised = False

    def compute(
        self,
        error: float,
        measurement: float,
        enable_integral: bool = True,
    ) -> float:
        """
        Compute PID output for one time step.

        Args:
            error:            current smoothed error (setpoint − measurement)
            measurement:      raw measurement (used for derivative to avoid kick)
            enable_integral:  False during large slews to prevent windup
        Returns:
            PID output in the same units as error (pixels × gain = deg-equivalent)
        """
        # ── Proportional ────────────────────────────────────────────────────
        p_term = self.kp * error

        # ── Integral with conditional anti-windup ───────────────────────────
        if enable_integral:
            self.integral += error * self.dt
            # Hard clamp
            self.integral = max(-self.integral_clamp,
                                min(self.integral_clamp, self.integral))
        i_term = self.ki * self.integral

        # ── Derivative on measurement (avoids derivative kick on setpoint jump) ─
        if not self._initialised:
            self.prev_measurement = measurement
            self._initialised = True
        d_meas = (measurement - self.prev_measurement) / self.dt
        self.prev_measurement = measurement
        # Negate: if measurement is increasing in direction of error, d_term brakes
        d_term = -self.kd * d_meas

        return p_term + i_term + d_term


# ---------------------------------------------------------------------------
# Thread 3 — PID + feedforward PTU controller (H60)
# ---------------------------------------------------------------------------
def _ptu_control_loop() -> None:
    """
    20 Hz PID + velocity-feedforward controller using H60 continuous joystick mode.

    Output pipeline:
      raw_error → EMA smooth → PID(P+I+D) → + feedforward(vx,vy) → H60 vector + speed
    """
    from app.services import config as config_service
    from app.services import ptu as ptu_service

    dt = PTU_LOOP_SEC

    # Independent PID instances per axis
    pid_pan  = _PIDAxis(PAN_KP,  PAN_KI,  PAN_KD,  PAN_INTEGRAL_CLAMP,  dt)
    pid_tilt = _PIDAxis(TILT_KP, TILT_KI, TILT_KD, TILT_INTEGRAL_CLAMP, dt)

    # EMA state
    smooth_err_x: float = 0.0
    smooth_err_y: float = 0.0
    alpha = PTU_ERROR_EMA_ALPHA

    was_stopped = True

    def _stop_ptu() -> None:
        nonlocal was_stopped
        if not was_stopped:
            ptu_service.direction("pause")
            was_stopped = True

    def _reset_all() -> None:
        nonlocal smooth_err_x, smooth_err_y
        pid_pan.reset()
        pid_tilt.reset()
        smooth_err_x = 0.0
        smooth_err_y = 0.0

    try:
        while not _pipeline_stop.is_set():
            time.sleep(dt)

            # ── Guard: auto-tracking must be on and PTU connected ────────────
            if not config_service.get_auto_tracking() or not ptu_service.is_connected():
                _stop_ptu()
                _reset_all()
                continue

            pred = _get_last_prediction_from_pipeline()

            # ── Guard: no active prediction ──────────────────────────────────
            if pred is None:
                _stop_ptu()
                # Decay smoothed error toward zero instead of hard reset
                smooth_err_x *= (1.0 - alpha)
                smooth_err_y *= (1.0 - alpha)
                # Decay integral too (target lost → unwind slowly)
                pid_pan.integral  *= 0.90
                pid_tilt.integral *= 0.90
                continue

            # ── Guard: stale prediction ──────────────────────────────────────
            pred_age = time.time() - pred.get("timestamp", time.time())
            if pred_age > PREDICTION_MAX_AGE_SEC:
                _stop_ptu()
                smooth_err_x *= (1.0 - alpha)
                smooth_err_y *= (1.0 - alpha)
                pid_pan.integral  *= 0.90
                pid_tilt.integral *= 0.90
                continue

            # ── Compute pixel errors ─────────────────────────────────────────
            pred_x = pred["x"]
            pred_y = pred["y"]
            width  = pred["width"]
            height = pred["height"]

            aim_x = (width  / 2.0) + LASER_OFFSET_X
            aim_y = (height / 2.0) - LASER_OFFSET_Y

            raw_err_x = pred_x - aim_x
            raw_err_y = aim_y  - pred_y   # positive = target above aim → tilt up

            # ── EMA smoothing (anti-jitter, low alpha = fast response) ───────
            smooth_err_x = alpha * raw_err_x + (1.0 - alpha) * smooth_err_x
            smooth_err_y = alpha * raw_err_y + (1.0 - alpha) * smooth_err_y

            error_px = (smooth_err_x ** 2 + smooth_err_y ** 2) ** 0.5

            # ── Deadband: inside this radius hold still ──────────────────────
            if error_px < PTU_DEADBAND_PX:
                _stop_ptu()
                # Don't reset integral — let it hold the steady-state correction
                continue

            # ── Angle scaling (auto-corrects for zoom via frame width) ───────
            # PTU_HFOV_DEG is nominal at native resolution.
            # At higher zoom the physical FOV shrinks proportionally → same formula
            # still works because detection reports pixel coords in the actual
            # captured frame, and width reflects the resolution being processed.
            deg_per_px = PTU_HFOV_DEG / max(width, 1.0)

            # ── Conditional integral: only accumulate when close ─────────────
            enable_int = error_px < INTEGRAL_ENABLE_THRESHOLD_PX

            # ── PID output (in degree-equivalent units) ──────────────────────
            out_x = pid_pan.compute(
                smooth_err_x * deg_per_px,
                raw_err_x    * deg_per_px,
                enable_integral=enable_int,
            )
            out_y = pid_tilt.compute(
                smooth_err_y * deg_per_px,
                raw_err_y    * deg_per_px,
                enable_integral=enable_int,
            )

            # ── Velocity feedforward from Kalman state ───────────────────────
            ff_vx = pred.get("vx", 0.0) * deg_per_px * PTU_GAIN_VX
            ff_vy = pred.get("vy", 0.0) * deg_per_px * PTU_GAIN_VY

            vx = out_x + ff_vx
            vy = out_y - ff_vy   # vy: downward motion → push down

            # ── Normalise to H60 vector space ────────────────────────────────
            max_v = max(abs(vx), abs(vy), 1e-6)
            scale = min(PTU_MAX_VECTOR / max_v, PTU_MAX_VECTOR)
            a1 = int(round(vx * scale))   # pan  (A1)
            a2 = int(round(vy * scale))   # tilt (A2)

            if PTU_INVERT_PAN:
                a1 = -a1
            if PTU_INVERT_TILT:
                a2 = -a2

            # ── Speed: proportional to normalised error magnitude ────────────
            norm_err = min(error_px / (width / 4.0), 1.0)
            speed = int(PTU_MIN_SPEED + norm_err * (PTU_MAX_SPEED - PTU_MIN_SPEED))

            # ── Send H60 directly through the serial write queue ─────────────
            cmd_bytes = f"H60,{a1},{a2},{speed}E".encode("ascii")
            try:
                from app.services.ptu import _command_queue, _drop_old_move_commands
                _drop_old_move_commands()
                _command_queue.put(("write", cmd_bytes))
            except Exception as _e:
                logger.warning("H60 enqueue failed: %s", _e)

            was_stopped = False

            logger.debug(
                "[PID-H60] err=(%.1f,%.1f)px smooth=(%.1f,%.1f)px "
                "pid=(%.2f,%.2f) ff=(%.2f,%.2f) int=(%.3f,%.3f) "
                "vec=(%d,%d) speed=%d age=%.3fs",
                raw_err_x, raw_err_y,
                smooth_err_x, smooth_err_y,
                out_x, out_y,
                ff_vx, ff_vy,
                pid_pan.integral, pid_tilt.integral,
                a1, a2, speed, pred_age,
            )

    except Exception as e:
        logger.error("Pipeline PTU control thread error: %s", e, exc_info=True)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------
def get_current_frame_for_stream() -> Optional[cv2.Mat]:
    with _frame_lock:
        return _current_frame


def _get_last_prediction_from_pipeline() -> Optional[Dict[str, float]]:
    from app.api.routes.tracking import get_last_prediction
    return get_last_prediction()


def start_pipeline() -> None:
    global _capture_thread, _detection_thread, _ptu_thread
    if _capture_thread is not None and _capture_thread.is_alive():
        logger.warning("Pipeline already running")
        return
    _pipeline_stop.clear()
    _capture_thread   = threading.Thread(target=_capture_loop,     daemon=True, name="capture")
    _detection_thread = threading.Thread(target=_detection_loop,   daemon=True, name="detection")
    _ptu_thread       = threading.Thread(target=_ptu_control_loop, daemon=True, name="ptu")
    _capture_thread.start()
    _detection_thread.start()
    _ptu_thread.start()
    logger.info("Tracking pipeline started (PID + feedforward controller)")


def stop_pipeline() -> None:
    global _capture_thread, _detection_thread, _ptu_thread
    _pipeline_stop.set()
    for t in (_capture_thread, _detection_thread, _ptu_thread):
        if t is not None and t.is_alive():
            t.join(timeout=2.0)
    _capture_thread = _detection_thread = _ptu_thread = None
    logger.info("Tracking pipeline stopped")


def get_latest_result() -> Optional[Dict[str, Any]]:
    with _result_lock:
        return dict(_latest_result) if _latest_result else None


def is_pipeline_running() -> bool:
    return _capture_thread is not None and _capture_thread.is_alive()