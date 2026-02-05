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


def detect_balloons(frame: "cv2.Mat") -> List[Dict[str, Any]]:
    """
    Run YOLO detection on a single BGR frame and return a list of balloon detections.
    
    Args:
        frame: OpenCV BGR image (numpy array)
    
    Returns:
        List of detection dicts with structure:
        {
            "bbox_x": float,      # left edge
            "bbox_y": float,      # top edge
            "bbox_w": float,      # width
            "bbox_h": float,      # height
            "centerX": float,     # center X coordinate
            "centerY": float,     # center Y coordinate
            "confidence": float,  # detection confidence score
        }
    """
    model = _get_model()
    
    # YOLO from ultralytics accepts numpy arrays (BGR is fine)
    results = model(frame, verbose=False, conf=0.25)  # confidence threshold
    boxes = results[0].boxes
    
    detections: List[Dict[str, Any]] = []
    
    for box in boxes:
        # xyxy format: [x1, y1, x2, y2]
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        w = x2 - x1
        h = y2 - y1
        cx = x1 + w / 2.0
        cy = y1 + h / 2.0
        conf = float(box.conf[0].item())
        
        detections.append({
            "bbox_x": float(x1),
            "bbox_y": float(y1),
            "bbox_w": float(w),
            "bbox_h": float(h),
            "centerX": float(cx),
            "centerY": float(cy),
            "confidence": conf,
        })
    
    return detections
