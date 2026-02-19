import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import logging

from ..config import PipelineConfig, default_config

logger = logging.getLogger(__name__)

@dataclass
class TransformMetadata:
    """Metadata required to reverse the normalization."""
    original_size: Tuple[int, int]  # (width, height)
    target_size: Tuple[int, int]    # (width, height)
    scale: float
    pad_top: int
    pad_left: int
    pad_bottom: int
    pad_right: int

class ImageNormalizer:
    def __init__(self, config: PipelineConfig = default_config):
        self.config = config

    def normalize(self, img: np.ndarray) -> Tuple[np.ndarray, TransformMetadata]:
        """
        Takes an image (numpy array), resizes it to fit within target_resolution while preserving aspect ratio,
        and pads it to be square if configured.
        """
        if img is None:
            raise ValueError("Input image to normalize is None.")
            
        h, w = img.shape[:2]
        target_w, target_h = self.config.target_resolution
        
        # Calculate scale to fit within target box
        scale = min(target_w / w, target_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        # Calculate padding
        pad_top, pad_bottom = 0, 0
        pad_left, pad_right = 0, 0
        
        if self.config.pad_to_square:
            # Pad to match target dimension exactly (usually square)
            delta_w = target_w - new_w
            delta_h = target_h - new_h
            pad_top = delta_h // 2
            pad_bottom = delta_h - pad_top
            pad_left = delta_w // 2
            pad_right = delta_w - pad_left
        
        # Apply padding
        padded = cv2.copyMakeBorder(
            resized, 
            pad_top, pad_bottom, pad_left, pad_right, 
            cv2.BORDER_CONSTANT, 
            value=[0, 0, 0] # Black padding
        )
        
        metadata = TransformMetadata(
            original_size=(w, h),
            target_size=(padded.shape[1], padded.shape[0]),
            scale=scale,
            pad_top=pad_top,
            pad_left=pad_left,
            pad_bottom=pad_bottom,
            pad_right=pad_right
        )
        
        return padded, metadata

    def denormalize(self, image: np.ndarray, metadata: TransformMetadata) -> np.ndarray:
        """
        Reverses the normalization process to get back the original size image (or close to it).
        Notes: 
        - This crops the padding and resizes back up.
        - Result might have slight resampling artifacts.
        """
        # Crop padding
        h, w = image.shape[:2]
        cropped = image[
            metadata.pad_top : h - metadata.pad_bottom,
            metadata.pad_left : w - metadata.pad_right
        ]
        
        # Resize back to original
        original_w, original_h = metadata.original_size
        restored = cv2.resize(cropped, (original_w, original_h), interpolation=cv2.INTER_LINEAR)
        
        return restored

class PanelDetector:
    """
    Helper to extract panels from a full comic page.
    MVP: Uses simple contour detection.
    """
    def detect(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Returns list of bounding boxes (x, y, w, h).
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # Threshold to find white gutters or black frames? 
        # Variable based on style. Assuming standard black frame on white/transparent.
        
        # Invert -> Threshold
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        boxes = []
        min_area = (image.shape[0] * image.shape[1]) * 0.05 # 5% of page
        
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w * h > min_area:
                boxes.append((x, y, w, h))
                
        return sorted(boxes, key=lambda b: (b[1], b[0])) # Sort by Y then X
