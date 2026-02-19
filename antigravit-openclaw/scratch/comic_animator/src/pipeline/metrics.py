import cv2
import numpy as np
import logging
from skimage.metrics import structural_similarity as ssim

logger = logging.getLogger(__name__)

class QualityMetrics:
    @staticmethod
    def compute_ssim(img1: np.ndarray, img2: np.ndarray) -> float:
        """
        Computes Structural Similarity Index between two images.
        Images must be same size.
        """
        if img1.shape != img2.shape:
            logger.warning(f"Image shapes do not match for SSIM: {img1.shape} vs {img2.shape}")
            return 0.0
            
        # Convert to grayscale for SSIM
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        
        score, _ = ssim(gray1, gray2, full=True)
        return score

    @staticmethod
    def check_flicker(frames: list[np.ndarray]) -> float:
        """
        Computes average SSIM between consecutive frames. 
        Lower value indicates high change (flicker or fast motion).
        """
        if len(frames) < 2:
            return 1.0
            
        scores = []
        for i in range(len(frames) - 1):
            s = QualityMetrics.compute_ssim(frames[i], frames[i+1])
            scores.append(s)
            
        return np.mean(scores)

    # Placeholder for CLIP
    # def compute_clip_similarity(self, img1, img2): ...
