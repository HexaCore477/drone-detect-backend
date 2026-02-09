"""YOLO-based balloon detection service."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import cv2
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


# Class names that count as "red" (case-insensitive)
RED_CLASS_NAMES = frozenset({"red", "red_balloon", "balloon_red"})


def _is_red_class(class_name: str) -> bool:
    """Return True if the class represents a red balloon."""
    return class_name.lower().strip() in RED_CLASS_NAMES


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
        is_red = _is_red_class(class_name)

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
                "is_red": is_red,
            }
        )

    return detections
