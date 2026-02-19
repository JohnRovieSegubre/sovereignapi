import cv2
import numpy as np
import torch
import logging
from pathlib import Path
from typing import Optional, List, Union, Tuple
from segment_anything import sam_model_registry, SamAutomaticMaskGenerator, SamPredictor

from ..config import PipelineConfig, default_config

logger = logging.getLogger(__name__)

class SegmentationEngine:
    def __init__(self, config: PipelineConfig = default_config):
        self.config = config
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.sam = None
        self.mask_generator = None
        
        self._load_model()

    def _load_model(self):
        checkpoint = self.config.sam_checkpoint_path
        model_type = self.config.sam_model_type
        
        if not checkpoint.exists():
            logger.warning(f"SAM checkpoint not found at {checkpoint}. Segmentation will fail unless fallback is used.")
            return

        try:
            logger.info(f"Loading SAM ({model_type}) from {checkpoint} on {self.device}...")
            self.sam = sam_model_registry[model_type](checkpoint=str(checkpoint))
            self.sam.to(device=self.device)
            self.mask_generator = SamAutomaticMaskGenerator(
                model=self.sam,
                points_per_side=32,
                pred_iou_thresh=0.86,
                stability_score_thresh=0.92,
                crop_n_layers=1,
                crop_n_points_downscale_factor=2,
                min_mask_region_area=100,
            )
            logger.info("SAM loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load SAM: {e}")
            self.sam = None

    def generate_mask(self, image: np.ndarray, strategy: str = "largest_center") -> np.ndarray:
        """
        Generates a binary mask (0 or 255) for the foreground character.
        If SAM is not loaded, returns a simple center-crop mask as fallback (for testing).
        """
        if self.sam is None:
            logger.warning("SAM not loaded. Using fallback rectangle mask.")
            return self._fallback_mask(image.shape)
            
        # Convert BGR to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        logger.info("Running SAM mask generation...")
        masks = self.mask_generator.generate(image_rgb)
        
        if not masks:
            logger.warning("SAM found no masks. Using fallback.")
            return self._fallback_mask(image.shape)
            
        selected_mask = self._select_mask(masks, strategy, image.shape)
        
        # Post-process (optional cleanup)
        binary_mask = (selected_mask * 255).astype(np.uint8)
        return binary_mask

    def _select_mask(self, masks: List[dict], strategy: str, shape: Tuple[int, int, int]) -> np.ndarray:
        """
        Selects the best mask based on strategy.
        """
        h, w = shape[:2]
        center_x, center_y = w // 2, h // 2
        
        if strategy == "largest_center":
            # Filter masks that overlap with the center region
            candidates = []
            for m in masks:
                segmentation = m['segmentation']
                # Check center overlap
                if segmentation[center_y, center_x]:
                    candidates.append(m)
            
            if not candidates:
                # If no center overlap, just take largest
                candidates = masks
                
            # Sort by area (descending)
            best = max(candidates, key=lambda x: x['area'])
            return best['segmentation']
            
        elif strategy == "union":
            # Combine all masks that are likely relevant? 
            # For now, just union all large masks.
            total_mask = np.zeros((h, w), dtype=bool)
            for m in masks:
                 if m['area'] > (h*w * 0.05): # >5% of screen
                     total_mask = np.logical_or(total_mask, m['segmentation'])
            return total_mask
            
        else:
            # Default to largest
            best = max(masks, key=lambda x: x['area'])
            return best['segmentation']

    def _fallback_mask(self, shape: Tuple[int, int, int]) -> np.ndarray:
        """Returns a generic oval mask in the center."""
        h, w = shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        center = (w // 2, h // 2)
        axes = (w // 4, h // 3)
        cv2.ellipse(mask, center, axes, 0, 0, 360, 255, -1)
        return mask
