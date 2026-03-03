"""Tracking WebSocket: stream balloon detections with tracking and 500ms prediction."""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple
import threading

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.services.alert_mail import process_balloon_detection
from app.services.camera import _create_capture, _release_capture, get_frame
from app.services.detection import detect_objects
from app.services import view_subscription

router = APIRouter(prefix="/tracking", tags=["tracking"])

# Tracking configuration
MAX_TRACK_AGE_SEC = 2.0  # Remove tracks older than this
PREDICTION_LEAD_SEC = 0  # 10ms ahead
SEND_INTERVAL_SEC = 0.05  # 50ms between sends

# Shared last prediction for backend PTU auto-tracking (primary target only)
_last_prediction_lock = threading.Lock()
_last_prediction: Optional[Dict[str, float]] = None


def set_last_prediction(x: float, y: float, width: int, height: int, timestamp: float) -> None:
    """Store last predicted point and frame size for backend auto-tracking."""
    global _last_prediction
    with _last_prediction_lock:
        _last_prediction = {
            "x": float(x),
            "y": float(y),
            "width": float(width),
            "height": float(height),
            "timestamp": float(timestamp),
        }


def get_last_prediction() -> Optional[Dict[str, float]]:
    """Return a copy of the last prediction for backend auto-tracking."""
    with _last_prediction_lock:
        if _last_prediction is None:
            return None
        return dict(_last_prediction)


# Minimum |omega| to use turning model; below this use straight-line (avoids div by zero)
_OMEGA_EPS = 1e-6


class ExtendedKalmanFilter2D:
    """
    Extended Kalman Filter with Constant Turn Rate and Velocity (CTRV) model.
    State: [x, y, psi, v, omega]
    - x, y: position (pixels)
    - psi: heading (radians), direction of velocity
    - v: speed (pixels/sec)
    - omega: turn rate (radians/sec)
    """

    def __init__(
        self,
        x: float,
        y: float,
        dt: float = 0.05,
        process_noise: float = 50.0,
        measurement_noise: float = 10.0,
    ):
        # State: [x, y, psi, v, omega]
        self.state = np.array([[x], [y], [0.0], [0.0], [0.0]], dtype=float)
        self.dt = dt

        # Measurement: we observe [x, y] only
        self.H = np.array([
            [1, 0, 0, 0, 0],
            [0, 1, 0, 0, 0],
        ], dtype=float)

        # Process noise (tuned for pixel coordinates)
        q_pos = process_noise * dt**2
        q_psi = 0.1 * dt
        q_v = 10.0 * dt
        q_omega = 0.5 * dt
        self.Q = np.diag([q_pos, q_pos, q_psi, q_v, q_omega]).astype(float)

        # Measurement noise
        r = measurement_noise
        self.R = np.array([[r, 0], [0, r]], dtype=float)

        # State covariance
        self.P = np.eye(5, dtype=float) * 100.0

    def _predict_state(self, dt: float) -> None:
        """Apply CTRV motion model to state (in-place)."""
        x, y, psi, v, omega = self.state[:, 0]
        abs_omega = abs(omega)
        if abs_omega < _OMEGA_EPS:
            # Straight-line motion
            self.state[0, 0] = x + v * np.cos(psi) * dt
            self.state[1, 0] = y + v * np.sin(psi) * dt
            self.state[2, 0] = psi
            self.state[3, 0] = v
            self.state[4, 0] = omega
        else:
            # Turning motion
            self.state[0, 0] = x + (v / omega) * (np.sin(psi + omega * dt) - np.sin(psi))
            self.state[1, 0] = y + (v / omega) * (-np.cos(psi + omega * dt) + np.cos(psi))
            self.state[2, 0] = (psi + omega * dt + np.pi) % (2.0 * np.pi) - np.pi
            self.state[3, 0] = v
            self.state[4, 0] = omega

    def _compute_jacobian_f(self, dt: float) -> np.ndarray:
        """Jacobian of state transition w.r.t. state."""
        x, y, psi, v, omega = self.state[:, 0]
        abs_omega = abs(omega)
        if abs_omega < _OMEGA_EPS:
            # Straight-line: F is constant
            return np.array([
                [1, 0, -v * np.sin(psi) * dt, np.cos(psi) * dt, 0],
                [0, 1, v * np.cos(psi) * dt, np.sin(psi) * dt, 0],
                [0, 0, 1, 0, 0],
                [0, 0, 0, 1, 0],
                [0, 0, 0, 0, 1],
            ], dtype=float)
        # Turning: Jacobian of CTRV
        a13 = (v / omega) * (np.cos(psi + omega * dt) - np.cos(psi))
        a14 = (1.0 / omega) * (np.sin(psi + omega * dt) - np.sin(psi))
        a15 = (dt * v / omega) * np.cos(psi + omega * dt) - (v / omega**2) * (
            np.sin(psi + omega * dt) - np.sin(psi)
        )
        a23 = (v / omega) * (np.sin(psi + omega * dt) - np.sin(psi))
        a24 = (1.0 / omega) * (-np.cos(psi + omega * dt) + np.cos(psi))
        a25 = (dt * v / omega) * np.sin(psi + omega * dt) - (v / omega**2) * (
            -np.cos(psi + omega * dt) + np.cos(psi)
        )
        return np.array([
            [1, 0, a13, a14, a15],
            [0, 1, a23, a24, a25],
            [0, 0, 1, 0, dt],
            [0, 0, 0, 1, 0],
            [0, 0, 0, 0, 1],
        ], dtype=float)

    def predict(self, dt: Optional[float] = None) -> Tuple[float, float]:
        """Predict state ahead. Returns (x, y)."""
        dt_use = dt if dt is not None else self.dt
        self._predict_state(dt_use)
        F = self._compute_jacobian_f(dt_use)
        self.P = F @ self.P @ F.T + self.Q
        return float(self.state[0, 0]), float(self.state[1, 0])

    def update(self, x: float, y: float) -> Tuple[float, float]:
        """Update with measurement. Returns (x, y)."""
        z = np.array([[x], [y]], dtype=float)
        y_res = z - self.H @ self.state
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.state = self.state + K @ y_res
        self.P = (np.eye(5) - K @ self.H) @ self.P
        return float(self.state[0, 0]), float(self.state[1, 0])

    def predict_ahead(self, lead_seconds: float) -> Tuple[float, float]:
        """Predict position lead_seconds into the future (does not modify state)."""
        x, y, psi, v, omega = self.state[:, 0]
        abs_omega = abs(omega)
        if abs_omega < _OMEGA_EPS:
            pred_x = x + v * np.cos(psi) * lead_seconds
            pred_y = y + v * np.sin(psi) * lead_seconds
        else:
            pred_x = x + (v / omega) * (np.sin(psi + omega * lead_seconds) - np.sin(psi))
            pred_y = y + (v / omega) * (-np.cos(psi + omega * lead_seconds) + np.cos(psi))
        return float(pred_x), float(pred_y)


# Alias for backward compatibility
KalmanFilter2D = ExtendedKalmanFilter2D


class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class DetectedBalloon(BaseModel):
    id: str
    color: str
    size: str
    centerX: float
    centerY: float
    boundingBox: BoundingBox
    isTarget: bool
    predictedCenterX: float | None = None
    predictedCenterY: float | None = None
    confidence: float = 0.0


class Track:
    """Represents a tracked balloon with Kalman-filtered position and prediction."""

    def __init__(self, track_id: str, detection: Dict, timestamp: float):
        self.id = track_id
        self.last_seen = timestamp
        # Color from pixel-based detection (red, blue, green, yellow, other)
        self.color = detection.get("color", "other")
        self.size = "medium"
        self.is_target = False

        cx = detection["centerX"]
        cy = detection["centerY"]
        self.kalman = KalmanFilter2D(cx, cy, dt=SEND_INTERVAL_SEC)
        self.kalman.update(cx, cy)
        self._last_measurement = (float(cx), float(cy))

        # Store bbox from last detection (Kalman only tracks center)
        self._bbox = {
            "bbox_x": detection["bbox_x"],
            "bbox_y": detection["bbox_y"],
            "bbox_w": detection["bbox_w"],
            "bbox_h": detection["bbox_h"],
        }

    def update(self, detection: Dict, timestamp: float):
        """Update track with new detection; Kalman filter smooths and estimates velocity."""
        cx = detection["centerX"]
        cy = detection["centerY"]
        self.kalman.predict(dt=timestamp - self.last_seen)
        self.kalman.update(cx, cy)
        self.last_seen = timestamp
        self._last_measurement = (float(cx), float(cy))
        self.color = detection.get("color", self.color)
        self._bbox = {
            "bbox_x": detection["bbox_x"],
            "bbox_y": detection["bbox_y"],
            "bbox_w": detection["bbox_w"],
            "bbox_h": detection["bbox_h"],
        }

    def predict(self, lead_seconds: float) -> Tuple[float, float]:
        """Predict position lead_seconds ahead using Kalman filter."""
        return self.kalman.predict_ahead(lead_seconds)

    def get_current_position(self) -> Tuple[float, float]:
        """Get Kalman-filtered current position."""
        x, y = self.kalman.state[0, 0], self.kalman.state[1, 0]
        return float(x), float(y)

    def get_current_bbox(self) -> Dict:
        """Get most recent bounding box from last detection."""
        return dict(self._bbox)


def calculate_iou(bbox1: Dict, bbox2: Dict) -> float:
    """
    Calculate Intersection over Union (IoU) between two bounding boxes.
    
    Args:
        bbox1, bbox2: Dicts with keys: bbox_x, bbox_y, bbox_w, bbox_h
    
    Returns:
        IoU value between 0 and 1
    """
    x1_1, y1_1 = bbox1["bbox_x"], bbox1["bbox_y"]
    x2_1, y2_1 = x1_1 + bbox1["bbox_w"], y1_1 + bbox1["bbox_h"]
    
    x1_2, y1_2 = bbox2["bbox_x"], bbox2["bbox_y"]
    x2_2, y2_2 = x1_2 + bbox2["bbox_w"], y1_2 + bbox2["bbox_h"]
    
    # Intersection
    xi1 = max(x1_1, x1_2)
    yi1 = max(y1_1, y1_2)
    xi2 = min(x2_1, x2_2)
    yi2 = min(y2_1, y2_2)
    
    if xi2 <= xi1 or yi2 <= yi1:
        return 0.0
    
    inter_area = (xi2 - xi1) * (yi2 - yi1)
    
    # Union
    area1 = bbox1["bbox_w"] * bbox1["bbox_h"]
    area2 = bbox2["bbox_w"] * bbox2["bbox_h"]
    union_area = area1 + area2 - inter_area
    
    if union_area <= 0:
        return 0.0
    
    return inter_area / union_area


def associate_detections_to_tracks(
    detections: List[Dict], tracks: Dict[str, Track], timestamp: float, iou_threshold: float = 0.3
) -> Tuple[List[Dict], Dict[str, Track]]:
    """
    Associate new detections with existing tracks using IoU matching.
    
    Returns:
        Tuple of (unmatched_detections, updated_tracks)
    """
    unmatched_detections = []
    matched_track_ids = set()
    
    # For each detection, find best matching track
    for det in detections:
        best_iou = 0.0
        best_track_id: Optional[str] = None
        
        for track_id, track in tracks.items():
            if track_id in matched_track_ids:
                continue
            
            # Get track's last bounding box
            track_bbox = track.get_current_bbox()
            
            iou = calculate_iou(det, track_bbox)
            if iou > best_iou and iou >= iou_threshold:
                best_iou = iou
                best_track_id = track_id
        
        if best_track_id:
            # Update existing track
            tracks[best_track_id].update(det, timestamp)
            matched_track_ids.add(best_track_id)
        else:
            # New detection, will create new track
            unmatched_detections.append(det)
    
    # Remove old tracks
    current_time = timestamp
    tracks_to_remove = [
        tid for tid, track in tracks.items()
        if current_time - track.last_seen > MAX_TRACK_AGE_SEC
    ]
    for tid in tracks_to_remove:
        del tracks[tid]
    
    return unmatched_detections, tracks


def _run_detection_on_frame(
    frame: Any,
    tracks: Dict[str, Track],
    next_track_id: int,
) -> Tuple[Dict[str, Track], int, List[Dict[str, Any]]]:
    """
    Run YOLO detection and tracking on a given frame.
    Used by the async pipeline (Thread 2). Caller provides the frame.

    Returns (tracks, next_track_id, payload_dict).
    """
    timestamp = time.time()
    frame_height, frame_width = frame.shape[:2]

    # Run YOLO detection (balloon or drone based on DRONE_DETECTION_ENABLED)
    raw_detections = detect_objects(frame)

    if raw_detections:
        # Update existing tracks using IoU association
        unmatched_detections, tracks = associate_detections_to_tracks(
            raw_detections, tracks, timestamp
        )

        # Create new tracks for unmatched detections
        for det in unmatched_detections:
            track_id = f"balloon-{next_track_id}"
            next_track_id += 1
            tracks[track_id] = Track(track_id, det, timestamp)
    else:
        # No detections this frame: age out stale tracks so we don't send fixed/stale positions
        current_time = timestamp
        tracks_to_remove = [
            tid for tid, track in tracks.items()
            if current_time - track.last_seen > MAX_TRACK_AGE_SEC
        ]
        for tid in tracks_to_remove:
            del tracks[tid]

    # Build per-track data only when we have detections this frame (avoid sending stale positions)
    track_items: List[Dict[str, Any]] = []
    if raw_detections:
        for track in tracks.values():
            cx, cy = track.get_current_position()
            pred_cx, pred_cy = track.predict(PREDICTION_LEAD_SEC)
            bbox = track.get_current_bbox()
            area = bbox["bbox_w"] * bbox["bbox_h"]
            track_items.append(
                {
                    "track": track,
                    "cx": cx,
                    "cy": cy,
                    "pred_cx": pred_cx,
                    "pred_cy": pred_cy,
                    "bbox": bbox,
                    "area": area,
                }
            )

    balloons: List[DetectedBalloon] = []
    primary_pred: Optional[Dict[str, float]] = None
    primary_item: Optional[Dict[str, Any]] = None

    if track_items:
        # Rule:
        # 1. If red balloons exist -> show only the largest red balloon.
        # 2. If no red balloons    -> show only the largest balloon (any color).
        red_items = [item for item in track_items if item["track"].color == "red"]
        primary_item = max(red_items, key=lambda it: it["area"]) if red_items else max(track_items, key=lambda it: it["area"])
        t = primary_item["track"]
        cx = primary_item["cx"]
        cy = primary_item["cy"]
        pred_cx = primary_item["pred_cx"]
        pred_cy = primary_item["pred_cy"]
        bbox = primary_item["bbox"]

        t.is_target = True
        primary_pred = {
            "x": pred_cx,
            "y": pred_cy,
            "width": float(frame_width),
            "height": float(frame_height),
        }

        balloons.append(
            DetectedBalloon(
                id=t.id,
                color=t.color,
                size=t.size,
                centerX=cx,
                centerY=cy,
                boundingBox=BoundingBox(
                    x=bbox["bbox_x"],
                    y=bbox["bbox_y"],
                    width=bbox["bbox_w"],
                    height=bbox["bbox_h"],
                ),
                isTarget=t.is_target,
                predictedCenterX=pred_cx,
                predictedCenterY=pred_cy,
                confidence=0.85,
            )
        )

    # Update shared prediction for backend PTU auto-tracking (primary track only)
    if primary_pred is not None:
        set_last_prediction(
            primary_pred["x"],
            primary_pred["y"],
            int(primary_pred["width"]),
            int(primary_pred["height"]),
            timestamp,
        )

    # Alert email: send when balloon count/color state changes and is stable for 5 frames
    process_balloon_detection(timestamp, track_items)

    # Kalman filter state for primary track (for Waterfall Kalman log)
    kalman_data: Optional[Dict[str, Any]] = None
    if track_items and primary_item:
        t = primary_item["track"]
        k = t.kalman
        x, y = float(k.state[0, 0]), float(k.state[1, 0])
        psi, v = float(k.state[2, 0]), float(k.state[3, 0])
        vx = v * np.cos(psi)
        vy = v * np.sin(psi)
        pred_cx, pred_cy = primary_item["pred_cx"], primary_item["pred_cy"]
        last_meas = getattr(t, "_last_measurement", (x, y))
        kalman_data = {
            "trackId": t.id,
            "x": x,
            "y": y,
            "vx": vx,
            "vy": vy,
            "predX": float(pred_cx),
            "predY": float(pred_cy),
            "measurementX": float(last_meas[0]),
            "measurementY": float(last_meas[1]),
        }

    payload = {
        "timestamp": int(timestamp * 1000),
        "balloons": [b.model_dump() for b in balloons],
        "kalman": kalman_data,
    }
    return tracks, next_track_id, payload


def _run_detection_and_tracking(
    cap: Any,
    tracks: Dict[str, Track],
    next_track_id: int,
) -> Tuple[Any, Dict[str, Track], int, List[Dict[str, Any]]]:
    """
    Run frame capture, then detection and tracking. Used when pipeline is disabled.
    Returns (cap, tracks, next_track_id, payload_dict).
    """
    cap, frame = get_frame(cap)
    if frame is None:
        return cap, tracks, next_track_id, {"timestamp": 0, "balloons": []}
    tracks, next_track_id, payload = _run_detection_on_frame(frame, tracks, next_track_id)
    return cap, tracks, next_track_id, payload


@router.websocket("/ws")
async def tracking_ws(websocket: WebSocket) -> None:
    """
    Stream detections with tracking and predictions.
    Uses async pipeline (Thread 1: capture, Thread 2: detection, Thread 3: PTU).
    Sends updates every 50ms from shared result. Falls back to blocking mode if pipeline not running.
    """
    from app.services import tracking_pipeline

    await websocket.accept()

    # Fallback when pipeline not running: use blocking detection
    cap = None
    tracks: Dict[str, Track] = {}
    next_track_id = 0

    try:
        while True:
            loop_start = time.time()

            if tracking_pipeline.is_pipeline_running():
                payload = tracking_pipeline.get_latest_result()
            else:
                cap = _create_capture() if cap is None else cap
                if cap is not None:
                    cap, tracks, next_track_id, payload = await asyncio.to_thread(
                        _run_detection_and_tracking, cap, tracks, next_track_id
                    )
                    if cap is None:
                        cap = _create_capture()
                else:
                    payload = {"timestamp": 0, "balloons": []}

            if payload and view_subscription.should_send_tracking() and (
                payload.get("balloons") or payload.get("timestamp", 0) > 0
            ):
                await websocket.send_json(payload)

            elapsed = time.time() - loop_start
            sleep_time = max(0, SEND_INTERVAL_SEC - elapsed)
            await asyncio.sleep(sleep_time)

    except WebSocketDisconnect:
        pass
    finally:
        if not tracking_pipeline.is_pipeline_running() and cap is not None:
            _release_capture(cap)
