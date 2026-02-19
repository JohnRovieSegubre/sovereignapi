import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from ..config import PipelineConfig, default_config
from .keypoints import Keypoint

@dataclass
class InterpolatedFrame:
    frame_index: int
    keypoints: List[Dict[str, float]] # list of {'x': val, 'y': val}

class MotionPlanner:
    def __init__(self, config: PipelineConfig = default_config):
        self.config = config

    def interpolate(self, start_kps: List[Keypoint], end_kps: List[Keypoint]) -> List[List[Dict[str, float]]]:
        """
        Generates N intermediate sets of keypoints between start and end.
        Returns list of keypoint lists (frames).
        """
        num_frames = self.config.num_frames
        frames = []
        
        # Identify common keypoints by index (MediaPipe indices are consistent)
        # We assume start_kps and end_kps are sorted by index or we map them.
        # MediaPipe always returns fixed 33 points, but visibility varies.
        
        # Create a dict for easier lookup
        start_map = {kp.index: kp for kp in start_kps}
        end_map = {kp.index: kp for kp in end_kps}
        
        # Union of indices
        all_indices = set(start_map.keys()) | set(end_map.keys())
        
        for i in range(num_frames):
            t = (i + 1) / (num_frames + 1) # t in (0, 1) excluding 0 and 1
            
            # Apply easing
            t_eased = self._ease_in_out(t) if self.config.interpolation_method == "cubic_ease_in_out" else t
            
            frame_kps = []
            
            for idx in sorted(list(all_indices)):
                start = start_map.get(idx)
                end = end_map.get(idx)
                
                # If point exists in both, interpolate
                if start and end:
                    x = (1 - t_eased) * start.x + t_eased * end.x
                    y = (1 - t_eased) * start.y + t_eased * end.y
                    # Simple z interpolation
                    z = (1 - t_eased) * start.z + t_eased * end.z
                    
                    frame_kps.append({'x': x, 'y': y, 'index': idx, 'present': True})
                
                # If only in start, fade out? For now, we just hold it or ignore.
                # MVP: If missing in one, we linearly interpolate to the other's position if it wasn't visible?
                # Actually, if it's missing, we probably shouldn't warp it.
                # Let's keep it if present in EITHER, using the other as target.
                elif start and not end:
                    # Decay to... let's stay at start
                    frame_kps.append({'x': start.x, 'y': start.y, 'index': idx, 'present': True})
                elif end and not start:
                     # Appear at end
                    frame_kps.append({'x': end.x, 'y': end.y, 'index': idx, 'present': True})
            
            frames.append(frame_kps)
            
        return frames

    def _ease_in_out(self, t: float) -> float:
        # Cubic ease in/out
        return 3 * t**2 - 2 * t**3
