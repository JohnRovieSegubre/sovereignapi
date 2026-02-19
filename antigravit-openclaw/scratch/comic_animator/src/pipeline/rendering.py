import cv2
import numpy as np
import subprocess
import logging
from pathlib import Path
from typing import List, Optional

from ..config import PipelineConfig, default_config

logger = logging.getLogger(__name__)

class VideoExporter:
    def __init__(self, config: PipelineConfig = default_config):
        self.config = config

    def composite_frame(self, 
                        background: np.ndarray, 
                        foreground: np.ndarray, 
                        mask: np.ndarray) -> np.ndarray:
        """
        Composites foreground onto background using the mask.
        Assumes all are same size.
        """
        # Ensure mask is 0-1 float or 0-255 uint8 single channel
        if len(mask.shape) == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
            
        # Normalize mask to 0.0 - 1.0
        alpha = mask.astype(float) / 255.0
        
        # Expand alpha to 3 channels
        alpha = cv2.merge([alpha, alpha, alpha])
        
        # Blend
        foreground = foreground.astype(float)
        background = background.astype(float)
        
        # Out = F * alpha + B * (1 - alpha)
        out = cv2.multiply(alpha, foreground) + cv2.multiply(1.0 - alpha, background)
        
        return out.astype(np.uint8)

    def export_video(self, frames: List[np.ndarray], output_path: Path):
        """
        Writes a sequence of frames to MP4 using FFmpeg (via pipe) or OpenCV VideoWriter.
        Using OpenCV for simplicity and portability in MVP.
        """
        if not frames:
            logger.warning("No frames to export.")
            return

        h, w = frames[0].shape[:2]
        fps = self.config.fps
        
        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Codec: 'mp4v' for .mp4 usually works on Windows/Linux
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (w, h))
        
        if not out.isOpened():
            logger.error(f"Failed to open video writer for {output_path}")
            # Fallback to MJPG/avi?
            return

        logger.info(f"Exporting video to {output_path} ({len(frames)} frames)")
        for frame in frames:
            out.write(frame)
            
        out.release()
        logger.info("Export complete.")

    def export_gif(self, frames: List[np.ndarray], output_path: Path):
         """Export as GIF using Pillow."""
         from PIL import Image
         
         if not frames:
             return
             
         pil_frames = [Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB)) for f in frames]
         duration_ms = 1000 / self.config.fps
         
         pil_frames[0].save(
            output_path,
            save_all=True,
            append_images=pil_frames[1:],
            optimize=False,
            duration=duration_ms,
            loop=0
         )
         logger.info(f"Exported GIF to {output_path}")
