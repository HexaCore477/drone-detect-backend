"""Tracking WebSocket: stream balloon detections with tracking and 500ms prediction."""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.services.camera import _create_capture, _release_capture, get_frame
from app.services.detection import detect_balloons

router = APIRouter(prefix="/tracking", tags=["tracking"])

# Tracking configuration
MAX_TRACK_AGE_SEC = 2.0  # Remove tracks older than this
PREDICTION_LEAD_SEC = 0.5  # 500ms ahead
SEND_INTERVAL_SEC = 0.05  # 50ms between sends


class KalmanFilter2D:
    """
    Constant-velocity Kalman filter for 2D position tracking.
    State: [x, y, vx, vy]
    """

    def __init__(
        self,
        x: float,
        y: float,
        dt: float = 0.05,
        process_noise: float = 50.0,
        measurement_noise: float = 10.0,
    ):
        # State: [x, y, vx, vy]
        self.state = np.array([[x], [y], [0.0], [0.0]], dtype=float)
        self.dt = dt

        # State transition: x' = x + vx*dt, y' = y + vy*dt, vx' = vx, vy' = vy
        self.F = np.array([
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ], dtype=float)

        # Measurement: we observe [x, y]
        self.H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0],
        ], dtype=float)

        # Process noise covariance (acceleration uncertainty)
        q = process_noise
        self.Q = np.array([
            [q * dt**4 / 4, 0, q * dt**3 / 2, 0],
            [0, q * dt**4 / 4, 0, q * dt**3 / 2],
            [q * dt**3 / 2, 0, q * dt**2, 0],
            [0, q * dt**3 / 2, 0, q * dt**2],
        ], dtype=float)

        # Measurement noise covariance
        r = measurement_noise
        self.R = np.array([[r, 0], [0, r]], dtype=float)

        # State covariance
        self.P = np.eye(4, dtype=float) * 100.0

    def predict(self, dt: Optional[float] = None) -> Tuple[float, float]:
        """Predict state ahead. Returns (x, y)."""
        dt_use = dt if dt is not None else self.dt
        F = np.array([
            [1, 0, dt_use, 0],
            [0, 1, 0, dt_use],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ], dtype=float)
        self.state = F @ self.state
        self.P = F @ self.P @ F.T + self.Q
        return float(self.state[0, 0]), float(self.state[1, 0])

    def update(self, x: float, y: float) -> Tuple[float, float]:
        """Update with measurement. Returns (x, y)."""
        z = np.array([[x], [y]], dtype=float)
        y_res = z - self.H @ self.state
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.state = self.state + K @ y_res
        self.P = (np.eye(4) - K @ self.H) @ self.P
        return float(self.state[0, 0]), float(self.state[1, 0])

    def predict_ahead(self, lead_seconds: float) -> Tuple[float, float]:
        """Predict position lead_seconds into the future (does not modify state)."""
        x, y, vx, vy = self.state[:, 0]
        return float(x + vx * lead_seconds), float(y + vy * lead_seconds)


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
        self.color = "red"
        self.size = "medium"
        self.is_target = False

        cx = detection["centerX"]
        cy = detection["centerY"]
        self.kalman = KalmanFilter2D(cx, cy, dt=SEND_INTERVAL_SEC)
        self.kalman.update(cx, cy)

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


def _run_detection_and_tracking(
    cap: Any,
    tracks: Dict[str, Track],
    next_track_id: int,
) -> Tuple[Any, Dict[str, Track], int, List[Dict[str, Any]]]:
    """
    Run frame capture, YOLO detection, and tracking in a thread.
    Single-target mode: detection returns at most 1 balloon. We always use the
    current detection directly (no IoU association) so tracking stays correct
    after PTU movement when the view shifts.
    Returns (cap, tracks, next_track_id, payload_dict).
    """
    cap, frame = get_frame(cap)
    if frame is None:
        return cap, tracks, next_track_id, {"timestamp": 0, "balloons": []}

    timestamp = time.time()

    # Run YOLO detection (returns 0 or 1 target)
    raw_detections = detect_balloons(frame)

    # Single-target mode: always use current detection for the single track.
    # No IoU association - always update with latest detection. This avoids
    # mismatch after PTU movement when the view shifts and IoU would fail.
    if raw_detections:
        det = raw_detections[0]
        if len(tracks) == 1:
            track = next(iter(tracks.values()))
            track.update(det, timestamp)
        else:
            tracks.clear()
            track_id = f"balloon-{next_track_id}"
            next_track_id += 1
            track = Track(track_id, det, timestamp)
            tracks[track_id] = track
        track.is_target = True
    else:
        tracks.clear()

    # Convert tracks to payload
    balloons: List[DetectedBalloon] = []
    for track in tracks.values():
        cx, cy = track.get_current_position()
        pred_cx, pred_cy = track.predict(PREDICTION_LEAD_SEC)
        bbox = track.get_current_bbox()

        balloons.append(
            DetectedBalloon(
                id=track.id,
                color=track.color,
                size=track.size,
                centerX=cx,
                centerY=cy,
                boundingBox=BoundingBox(
                    x=bbox["bbox_x"],
                    y=bbox["bbox_y"],
                    width=bbox["bbox_w"],
                    height=bbox["bbox_h"],
                ),
                isTarget=track.is_target,
                predictedCenterX=pred_cx,
                predictedCenterY=pred_cy,
                confidence=0.85,
            )
        )

    payload = {
        "timestamp": int(timestamp * 1000),
        "balloons": [b.model_dump() for b in balloons],
    }
    return cap, tracks, next_track_id, payload


@router.websocket("/ws")
async def tracking_ws(websocket: WebSocket) -> None:
    """
    Stream detections with tracking and 500ms-ahead predictions.
    Sends updates every 50ms for low latency.
    Detection/tracking runs in a thread pool to avoid blocking the event loop.
    """
    await websocket.accept()

    cap = _create_capture()
    tracks: Dict[str, Track] = {}
    next_track_id = 0

    try:
        while True:
            loop_start = time.time()

            # Run detection + tracking in thread pool to protect event loop
            cap, tracks, next_track_id, payload = await asyncio.to_thread(
                _run_detection_and_tracking,
                cap,
                tracks,
                next_track_id,
            )

            if payload["balloons"] or payload["timestamp"] > 0:
                await websocket.send_json(payload)

            # Recreate capture if lost
            if cap is None:
                cap = _create_capture()
                await asyncio.sleep(0.05)
                continue

            # Maintain 50ms send interval
            elapsed = time.time() - loop_start
            sleep_time = max(0, SEND_INTERVAL_SEC - elapsed)
            await asyncio.sleep(sleep_time)

    except WebSocketDisconnect:
        pass
    finally:
        _release_capture(cap)
