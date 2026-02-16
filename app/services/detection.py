"""YOLO-based balloon detection service."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Literal

import cv2
import numpy as np
import torch

try:
    from ultralytics import YOLO  # type: ignore[import]
except ImportError:  # pragma: no cover - runtime dependency
    YOLO = None  # type: ignore[assignment]

_MODEL: "YOLO | None" = None


def _get_model() -> "YOLO":
    """
    Lazily load the YOLO model from app/yolo_models/best_balloon_nano.pt.
    
    The model is kept in a module-level singleton so we only pay the load cost once.
    """
    global _MODEL
    if _MODEL is not None:
        return _MODEL

    if YOLO is None:
        raise RuntimeError(
            "ultralytics is not installed. Install with `pip install ultralytics` "
            "and ensure PyTorch is available."
        )
    
    # Path: backend/app/services/detection.py -> backend/app/yolo_models/
    # Go up one level from services/ to app/, then into yolo_models/
    model_path = Path(__file__).resolve().parent.parent / "yolo_models" / "best_balloon_nano.pt"
    if not model_path.is_file():
        raise FileNotFoundError(f"YOLO model not found at: {model_path}")

    # PyTorch 2.6+ uses weights_only=True by default; Ultralytics checkpoints
    # contain custom classes that trigger UnpicklingError. We trust our model
    # file, so temporarily use weights_only=False for loading.
    _original_torch_load = torch.load
    try:
        def _patched_load(*args, **kwargs):
            kwargs.setdefault("weights_only", False)
            return _original_torch_load(*args, **kwargs)

        torch.load = _patched_load
        _MODEL = YOLO(str(model_path))
    finally:
        torch.load = _original_torch_load

    return _MODEL


# Class names that count as "red" (case-insensitive) - used only if model has color classes
RED_CLASS_NAMES = frozenset({"red", "red_balloon", "balloon_red"})

# Use inner region (60% of bbox) to avoid edges and background
ROI_INNER_SCALE = 0.6  # Use center 60% of bbox

# Minimum match percentage (0–1) to accept a color classification
MIN_COLOR_MATCH = 0.1

# Color ranges in HSV (OpenCV: H 0-180, S 0-255, V 0-255)
# Red wraps around 0/180, so it uses two ranges
COLOR_RANGES: Dict[str, Any] = {
    "white": ([0, 0, 200], [180, 30, 255]),
    "red": ([0, 100, 100], [10, 255, 255], [170, 100, 100], [180, 255, 255]),
    "green": ([40, 50, 50], [80, 255, 255]),
    "blue": ([100, 50, 50], [130, 255, 255]),
    "black": ([0, 0, 0], [180, 255, 30]),
    "orange": ([10, 100, 100], [25, 255, 255]),
    "yellow": ([25, 100, 100], [35, 255, 255]),
}

# Map classifier output to API-supported colors
SUPPORTED_COLORS = frozenset({"red", "blue", "green", "yellow"})


def _classify_color_from_roi(roi: np.ndarray) -> str | None:
    """
    Classify color from an ROI using HSV ranges and grid-based pixel sampling.

    Samples pixels in a grid pattern, checks each color range, and returns
    the color with the highest match percentage (min 10% match).
    """
    if roi.size == 0:
        return None

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    sample_step = max(2, min(roi.shape[0] // 20, roi.shape[1] // 20))
    sampled_pixels = hsv[::sample_step, ::sample_step]
    total_pixels = sampled_pixels.shape[0] * sampled_pixels.shape[1]

    if total_pixels == 0:
        return None

    color_scores: Dict[str, float] = {}

    for color_name, ranges in COLOR_RANGES.items():
        if len(ranges) == 2:
            lower = np.array(ranges[0])
            upper = np.array(ranges[1])
            mask = np.all(
                (sampled_pixels >= lower) & (sampled_pixels <= upper), axis=2
            )
        else:
            # Multiple ranges (e.g. red wraps at 0 and 180)
            lower1, upper1 = np.array(ranges[0]), np.array(ranges[1])
            lower2, upper2 = np.array(ranges[2]), np.array(ranges[3])
            mask1 = np.all(
                (sampled_pixels >= lower1) & (sampled_pixels <= upper1), axis=2
            )
            mask2 = np.all(
                (sampled_pixels >= lower2) & (sampled_pixels <= upper2), axis=2
            )
            mask = mask1 | mask2

        match_percentage = float(np.sum(mask)) / total_pixels
        color_scores[color_name] = match_percentage

    best_color = max(color_scores, key=color_scores.get)
    if color_scores[best_color] < MIN_COLOR_MATCH:
        return None

    return best_color


def detect_color_from_roi(
    frame: "cv2.Mat",
    bbox_x: float,
    bbox_y: float,
    bbox_w: float,
    bbox_h: float,
) -> Literal["red", "blue", "green", "yellow", "other"]:
    """
    Detect balloon color from the bounding box region using HSV color analysis.

    Crops the center region of the bbox, samples pixels in a grid, and
    classifies by matching against HSV color ranges (red uses two ranges
    since it wraps at 0/180).

    Returns one of: red, blue, green, yellow, other
    """
    h_img, w_img = frame.shape[:2]
    cx = bbox_x + bbox_w / 2
    cy = bbox_y + bbox_h / 2
    inner_w = max(4, bbox_w * ROI_INNER_SCALE)
    inner_h = max(4, bbox_h * ROI_INNER_SCALE)
    x1 = int(max(0, cx - inner_w / 2))
    y1 = int(max(0, cy - inner_h / 2))
    x2 = int(min(w_img, x1 + inner_w))
    y2 = int(min(h_img, y1 + inner_h))

    if x2 <= x1 or y2 <= y1:
        return "other"

    roi = frame[y1:y2, x1:x2]
    result = _classify_color_from_roi(roi)

    if result is None:
        return "other"
    if result in SUPPORTED_COLORS:
        return result  # type: ignore[return-value]
    return "other"


def detect_balloons(frame: "cv2.Mat") -> List[Dict[str, Any]]:
    """
    Run YOLO detection and return **all** detected balloons.
    
    Each detection dict contains:
      - bbox_x, bbox_y, bbox_w, bbox_h
      - centerX, centerY
      - confidence
    
    Tracking logic is responsible for associating detections to tracks and
    deciding which object to follow.
    """
    model = _get_model()
    results = model(frame, verbose=False, conf=0.45, iou=0.5)
    boxes = results[0].boxes
    names = model.names  # class_id -> class_name

    detections: List[Dict[str, Any]] = []

    for box in boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        w = x2 - x1
        h = y2 - y1
        if w <= 0 or h <= 0:
            continue

        cls_id = int(box.cls[0].item())
        if isinstance(names, dict):
            class_name = names.get(cls_id, "")
        else:
            class_name = names[cls_id] if 0 <= cls_id < len(names) else ""

        # Pixel-based color detection (model not trained for color classes)
        color = detect_color_from_roi(frame, float(x1), float(y1), float(w), float(h))

        detections.append(
            {
                "bbox_x": float(x1),
                "bbox_y": float(y1),
                "bbox_w": float(w),
                "bbox_h": float(h),
                "centerX": float(x1 + w / 2.0),
                "centerY": float(y1 + h / 2.0),
                "confidence": float(box.conf[0].item()),
                "class_name": class_name,
                "color": color,
                "is_red": color == "red",
            }
        )

    return detections
