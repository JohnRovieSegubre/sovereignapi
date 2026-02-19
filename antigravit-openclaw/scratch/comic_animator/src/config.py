import os
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

@dataclass
class PipelineConfig:
    # General
    seed: int = 42
    output_dir: Path = Path("output")
    
    # Preprocessing
    target_resolution: Tuple[int, int] = (1024, 1024)
    pad_to_square: bool = True
    
    # Segmentation (SAM)
    sam_checkpoint_path: Path = Path("models/sam_vit_b_01ec64.pth")
    sam_model_type: str = "vit_b" # vit_h, vit_l, vit_b
    mask_strategy: str = "largest_center" # largest_center, manual, union
    
    # Keypoints (MediaPipe)
    detection_mode: str = "pose" # pose, face
    min_detection_confidence: float = 0.2
    min_tracking_confidence: float = 0.5
    
    # Motion Planning
    fps: int = 24
    duration_sec: float = 2.0
    interpolation_method: str = "cubic_ease_in_out" # linear, cubic_ease_in_out
    
    # Rendering
    feather_radius: int = 5
    
    def __post_init__(self):
        # Convert string paths to Path objects if needed
        if isinstance(self.output_dir, str):
            self.output_dir = Path(self.output_dir)
        if isinstance(self.sam_checkpoint_path, str):
            self.sam_checkpoint_path = Path(self.sam_checkpoint_path)

    @property
    def num_frames(self) -> int:
        return int(self.fps * self.duration_sec)

# Default configuration instance
default_config = PipelineConfig()
