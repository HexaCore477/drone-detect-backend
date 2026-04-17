"""Tracking WebSocket: stream balloon/drone detections with Kalman tracking."""
from __future__ import annotations

import asyncio
import time
import threading
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.services.alert_mail import process_balloon_detection
from app.services import view_subscription

router = APIRouter(prefix="/tracking", tags=["tracking"])

# ---------------------------------------------------------------------------
# Tracking constants
# ---------------------------------------------------------------------------
MAX_TRACK_AGE_SEC   = 2.0
PREDICTION_LEAD_SEC = 0.25  # updated: matches pipeline constant
WARMUP_FRAMES       = 4
SEND_INTERVAL_SEC   = 0.05

# ---------------------------------------------------------------------------
# Shared last-prediction (written by detection thread, read by PTU thread)
# ---------------------------------------------------------------------------
_last_prediction_lock = threading.Lock()
_last_prediction: Optional[Dict[str, float]] = None


def set_last_prediction(
    x: float,
    y: float,
    width: int,
    height: int,
    timestamp: float,
    vx: float = 0.0,
    vy: float = 0.0,
) -> None:
    """
    Store the latest Kalman-predicted target position for the PTU controller.
    vx/vy are Kalman velocity components (px/s) used for feedforward.
    """
    global _last_prediction
    with _last_prediction_lock:
        _last_prediction = {
            "x":         float(x),
            "y":         float(y),
            "width":     float(width),
            "height":    float(height),
            "timestamp": float(timestamp),
            "vx":        float(vx),
            "vy":        float(vy),
        }


def clear_last_prediction() -> None:
    global _last_prediction
    with _last_prediction_lock:
        _last_prediction = None


def get_last_prediction() -> Optional[Dict[str, float]]:
    with _last_prediction_lock:
        return dict(_last_prediction) if _last_prediction else None


# ---------------------------------------------------------------------------
# Extended Kalman Filter (CTRV model)
# ---------------------------------------------------------------------------
_OMEGA_EPS = 1e-6


class ExtendedKalmanFilter2D:
    """
    EKF with Constant Turn Rate and Velocity (CTRV) model.
    State: [x, y, psi, v, omega]
    """

    def __init__(self, x: float, y: float, dt: float = 0.05,
                 process_noise: float = 50.0, measurement_noise: float = 10.0):
        self.state = np.array([[x], [y], [0.0], [0.0], [0.0]], dtype=float)
        self.dt = dt
        self.H = np.array([[1,0,0,0,0],[0,1,0,0,0]], dtype=float)
        q_pos = process_noise * dt**2
        self.Q = np.diag([q_pos, q_pos, 0.1*dt, 10.0*dt, 0.5*dt]).astype(float)
        self.R = np.eye(2, dtype=float) * measurement_noise
        self.P = np.eye(5, dtype=float) * 100.0

    def _predict_state(self, dt: float) -> None:
        x, y, psi, v, omega = self.state[:, 0]
        if abs(omega) < _OMEGA_EPS:
            self.state[0, 0] = x + v * np.cos(psi) * dt
            self.state[1, 0] = y + v * np.sin(psi) * dt
        else:
            self.state[0, 0] = x + (v/omega)*(np.sin(psi + omega*dt) - np.sin(psi))
            self.state[1, 0] = y + (v/omega)*(-np.cos(psi + omega*dt) + np.cos(psi))
            self.state[2, 0] = (psi + omega*dt + np.pi) % (2*np.pi) - np.pi
        self.state[3, 0] = v
        self.state[4, 0] = omega

    def _jacobian_f(self, dt: float) -> np.ndarray:
        x, y, psi, v, omega = self.state[:, 0]
        if abs(omega) < _OMEGA_EPS:
            return np.array([
                [1,0,-v*np.sin(psi)*dt, np.cos(psi)*dt,0],
                [0,1, v*np.cos(psi)*dt, np.sin(psi)*dt,0],
                [0,0,1,0,0],[0,0,0,1,0],[0,0,0,0,1],
            ], dtype=float)
        a13 = (v/omega)*(np.cos(psi+omega*dt)-np.cos(psi))
        a14 = (1/omega)*(np.sin(psi+omega*dt)-np.sin(psi))
        a15 = (dt*v/omega)*np.cos(psi+omega*dt)-(v/omega**2)*(np.sin(psi+omega*dt)-np.sin(psi))
        a23 = (v/omega)*(np.sin(psi+omega*dt)-np.sin(psi))
        a24 = (1/omega)*(-np.cos(psi+omega*dt)+np.cos(psi))
        a25 = (dt*v/omega)*np.sin(psi+omega*dt)-(v/omega**2)*(-np.cos(psi+omega*dt)+np.cos(psi))
        return np.array([
            [1,0,a13,a14,a15],[0,1,a23,a24,a25],
            [0,0,1,0,dt],[0,0,0,1,0],[0,0,0,0,1],
        ], dtype=float)

    def predict(self, dt: Optional[float] = None) -> Tuple[float, float]:
        dt_use = dt if dt is not None else self.dt
        self._predict_state(dt_use)
        F = self._jacobian_f(dt_use)
        self.P = F @ self.P @ F.T + self.Q
        return float(self.state[0,0]), float(self.state[1,0])

    def update(self, x: float, y: float) -> Tuple[float, float]:
        z = np.array([[x],[y]], dtype=float)
        y_res = z - self.H @ self.state
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.state = self.state + K @ y_res
        self.P = (np.eye(5) - K @ self.H) @ self.P
        return float(self.state[0,0]), float(self.state[1,0])

    def predict_ahead(self, lead: float) -> Tuple[float, float]:
        x, y, psi, v, omega = self.state[:, 0]
        if abs(omega) < _OMEGA_EPS:
            return float(x + v*np.cos(psi)*lead), float(y + v*np.sin(psi)*lead)
        return (
            float(x + (v/omega)*(np.sin(psi+omega*lead)-np.sin(psi))),
            float(y + (v/omega)*(-np.cos(psi+omega*lead)+np.cos(psi))),
        )


# Backward-compat alias
KalmanFilter2D = ExtendedKalmanFilter2D


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class BoundingBox(BaseModel):
    x: float; y: float; width: float; height: float


class DetectedBalloon(BaseModel):
    id: str; color: str; size: str
    centerX: float; centerY: float
    boundingBox: BoundingBox
    isTarget: bool
    predictedCenterX: float | None = None
    predictedCenterY: float | None = None
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# Track
# ---------------------------------------------------------------------------
class Track:
    def __init__(self, track_id: str, det: Dict, timestamp: float):
        self.id = track_id
        self.last_seen = timestamp
        self.color = det.get("color", "other")
        self.size = "medium"
        self.is_target = False
        cx, cy = det["centerX"], det["centerY"]
        self.kalman = KalmanFilter2D(cx, cy, dt=SEND_INTERVAL_SEC)
        self.kalman.update(cx, cy)
        self._last_measurement = (float(cx), float(cy))
        self._update_count = 1
        self._bbox = {k: det[k] for k in ("bbox_x","bbox_y","bbox_w","bbox_h")}

    def update(self, det: Dict, timestamp: float) -> None:
        cx, cy = det["centerX"], det["centerY"]
        self.kalman.predict(dt=timestamp - self.last_seen)
        self.kalman.update(cx, cy)
        self.last_seen = timestamp
        self._last_measurement = (float(cx), float(cy))
        self._update_count += 1
        self.color = det.get("color", self.color)
        self._bbox = {k: det[k] for k in ("bbox_x","bbox_y","bbox_w","bbox_h")}

    def predict(self, lead: float) -> Tuple[float, float]:
        if self._update_count < WARMUP_FRAMES:
            return self.get_current_position()
        return self.kalman.predict_ahead(lead)

    def get_current_position(self) -> Tuple[float, float]:
        return float(self.kalman.state[0,0]), float(self.kalman.state[1,0])

    def get_current_bbox(self) -> Dict:
        return dict(self._bbox)

    def get_velocity(self) -> Tuple[float, float]:
        """Return (vx, vy) in px/s derived from Kalman CTRV state."""
        psi = float(self.kalman.state[2, 0])
        v   = float(self.kalman.state[3, 0])
        return v * float(np.cos(psi)), v * float(np.sin(psi))


# ---------------------------------------------------------------------------
# IoU association
# ---------------------------------------------------------------------------
def _iou(a: Dict, b: Dict) -> float:
    ax2, ay2 = a["bbox_x"]+a["bbox_w"], a["bbox_y"]+a["bbox_h"]
    bx2, by2 = b["bbox_x"]+b["bbox_w"], b["bbox_y"]+b["bbox_h"]
    ix1, iy1 = max(a["bbox_x"],b["bbox_x"]), max(a["bbox_y"],b["bbox_y"])
    ix2, iy2 = min(ax2,bx2), min(ay2,by2)
    if ix2<=ix1 or iy2<=iy1: return 0.0
    inter = (ix2-ix1)*(iy2-iy1)
    union = a["bbox_w"]*a["bbox_h"] + b["bbox_w"]*b["bbox_h"] - inter
    return inter/union if union>0 else 0.0


def _associate(detections: List[Dict], tracks: Dict[str, Track],
               timestamp: float, iou_thresh: float = 0.3
               ) -> Tuple[List[Dict], Dict[str, Track]]:
    unmatched = []
    matched: set = set()
    for det in detections:
        best_iou, best_id = 0.0, None
        for tid, track in tracks.items():
            if tid in matched: continue
            iou = _iou(det, track.get_current_bbox())
            if iou > best_iou and iou >= iou_thresh:
                best_iou, best_id = iou, tid
        if best_id:
            tracks[best_id].update(det, timestamp)
            matched.add(best_id)
        else:
            unmatched.append(det)
    # Age out stale tracks
    for tid in [t for t,tr in tracks.items() if timestamp-tr.last_seen > MAX_TRACK_AGE_SEC]:
        del tracks[tid]
    return unmatched, tracks


# ---------------------------------------------------------------------------
# Core detection + tracking (called by detection thread)
# ---------------------------------------------------------------------------
def _run_detection_on_frame(
    frame: Any,
    tracks: Dict[str, Track],
    next_track_id: int,
) -> Tuple[Dict[str, Track], int, Dict[str, Any]]:
    """
    Run YOLO + Kalman on one frame.  Returns (tracks, next_id, payload).
    Single source of truth — no duplicate path in the WebSocket handler.
    """
    from app.services.detection import detect_objects

    timestamp = time.time()
    h, w = frame.shape[:2]

    raw = detect_objects(frame)

    if raw:
        unmatched, tracks = _associate(raw, tracks, timestamp)
        for det in unmatched:
            tid = f"balloon-{next_track_id}"
            next_track_id += 1
            tracks[tid] = Track(tid, det, timestamp)
    else:
        for tid in [t for t,tr in tracks.items() if timestamp-tr.last_seen > MAX_TRACK_AGE_SEC]:
            del tracks[tid]

    # Build track items only when we have fresh detections
    items: List[Dict[str, Any]] = []
    if raw:
        for track in tracks.values():
            cx, cy = track.get_current_position()
            pcx, pcy = track.predict(PREDICTION_LEAD_SEC)
            bbox = track.get_current_bbox()
            items.append({
                "track": track, "cx": cx, "cy": cy,
                "pred_cx": pcx, "pred_cy": pcy,
                "bbox": bbox, "area": bbox["bbox_w"]*bbox["bbox_h"],
            })

    balloons: List[DetectedBalloon] = []
    primary_pred: Optional[Dict] = None
    primary_item: Optional[Dict] = None

    if items:
        red = [it for it in items if it["track"].color == "red"]
        primary_item = max(red or items, key=lambda it: it["area"])
        t = primary_item["track"]
        t.is_target = True
        primary_pred = {
            "x": primary_item["pred_cx"], "y": primary_item["pred_cy"],
            "width": float(w), "height": float(h),
        }
        bbox = primary_item["bbox"]
        balloons.append(DetectedBalloon(
            id=t.id, color=t.color, size=t.size,
            centerX=primary_item["cx"], centerY=primary_item["cy"],
            boundingBox=BoundingBox(
                x=bbox["bbox_x"], y=bbox["bbox_y"],
                width=bbox["bbox_w"], height=bbox["bbox_h"],
            ),
            isTarget=True,
            predictedCenterX=primary_item["pred_cx"],
            predictedCenterY=primary_item["pred_cy"],
            confidence=0.85,
        ))

    if primary_pred and primary_item:
        # Extract Kalman velocity (px/s) for PTU feedforward
        kf_vx, kf_vy = primary_item["track"].get_velocity()
        set_last_prediction(
            primary_item["cx"], primary_item["cy"],  # v8: send CURRENT pos, not predicted
            int(primary_pred["width"]), int(primary_pred["height"]),
            timestamp,
            vx=kf_vx,
            vy=kf_vy,
        )
    else:
        clear_last_prediction()

    process_balloon_detection(timestamp, items)

    # Kalman debug data for Waterfall log
    kalman_data = None
    if primary_item:
        t = primary_item["track"]
        k = t.kalman
        px, py = float(k.state[0,0]), float(k.state[1,0])
        psi, v = float(k.state[2,0]), float(k.state[3,0])
        kf_vx, kf_vy = t.get_velocity()
        kalman_data = {
            "trackId": t.id,
            "x": px, "y": py,
            "vx": kf_vx, "vy": kf_vy,
            "predX": primary_item["pred_cx"], "predY": primary_item["pred_cy"],
            "measurementX": float(t._last_measurement[0]),
            "measurementY": float(t._last_measurement[1]),
            "updateCount": t._update_count,
            "warmedUp": t._update_count >= WARMUP_FRAMES,
        }

    return tracks, next_track_id, {
        "timestamp": int(timestamp * 1000),
        "balloons": [b.model_dump() for b in balloons],
        "kalman": kalman_data,
    }


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------
@router.websocket("/ws")
async def tracking_ws(websocket: WebSocket) -> None:
    """
    Stream detection + tracking results at 50 ms cadence.
    Always uses the shared pipeline result.
    """
    from app.services import tracking_pipeline

    await websocket.accept()
    try:
        while True:
            t0 = time.time()
            payload = tracking_pipeline.get_latest_result()
            if payload and view_subscription.should_send_tracking() and (
                payload.get("balloons") or payload.get("timestamp", 0) > 0
            ):
                await websocket.send_json(payload)
            await asyncio.sleep(max(0, SEND_INTERVAL_SEC - (time.time() - t0)))
    except WebSocketDisconnect:
        pass