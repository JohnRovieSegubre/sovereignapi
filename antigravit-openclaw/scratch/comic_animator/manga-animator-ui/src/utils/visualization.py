import cv2
import numpy as np
from typing import List, Optional, Tuple, Dict

def draw_skeleton(image: np.ndarray, keypoints: List[Dict[str, float]], color: Tuple[int, int, int] = (0, 255, 0), thickness: int = 2) -> np.ndarray:
    """
    Draws pose skeleton on the image.
    Expects keypoints as list of dicts with 'x', 'y' (normalized or pixel).
    This is a placeholder for the actual MediaPipe topology drawing.
    """
    img_copy = image.copy()
    h, w = img_copy.shape[:2]
    
    # Basic drawing of points for now
    for kp in keypoints:
        x = int(kp.get('x', 0))
        y = int(kp.get('y', 0))
        # If normalized (<1.0), scale up. Crude heuristic, precise handling in Pipeline needed.
        if 0 <= x <= 1 and 0 <= y <= 1: 
             x = int(x * w)
             y = int(y * h)
             
        cv2.circle(img_copy, (x, y), thickness * 2, color, -1)
    
    return img_copy

def create_grid(images: List[np.ndarray], cols: int = 2) -> np.ndarray:
    """Concatenates images into a grid."""
    if not images:
        return np.zeros((100, 100, 3), dtype=np.uint8)
    
    # Ensure all same size
    h, w = images[0].shape[:2]
    resized = [cv2.resize(img, (w, h)) for img in images]
    
    rows = (len(resized) + cols - 1) // cols
    
    # fill with blank if not multiple of cols
    while len(resized) < rows * cols:
        resized.append(np.zeros_like(resized[0]))
        
    grid_rows = []
    for i in range(rows):
        row_imgs = resized[i*cols : (i+1)*cols]
        grid_rows.append(np.hstack(row_imgs))
        
    return np.vstack(grid_rows)
