import pytest
import numpy as np
import cv2
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.pipeline.preprocessing import ImageNormalizer, PanelDetector
from src.pipeline.keypoints import Keypoint
from src.pipeline.warping import Warper
from src.config import PipelineConfig, default_config

def run_manual_tests():
    print("Running Manual Checks...")
    
    # 1. Preprocessing
    print("Test: Preprocessing...", end="")
    try:
        cfg = PipelineConfig(target_resolution=(1024, 1024), pad_to_square=True)
        normalizer = ImageNormalizer(cfg)
        img = np.zeros((600, 800, 3), dtype=np.uint8)
        cv2.imwrite("temp_test.png", img)
        padded, meta = normalizer.normalize(Path("temp_test.png"))
        assert padded.shape == (1024, 1024, 3)
        assert meta.original_size == (800, 600)
        os.remove("temp_test.png")
        print("PASS")
    except Exception as e:
        print(f"FAIL: {e}")

    # 2. Keypoints Logic (Mocked Detector)
    print("Test: Keypoints Logic...", end="")
    try:
        # We manually test the array conversion logic without instantiating the heavy MediaPipe model
        # which seems to be failing in this specific CLI env.
        from src.pipeline.keypoints import PoseDetector
        
        # Mock the __init__ to avoid loading MP
        with patch.object(PoseDetector, '__init__', return_value=None):
            detector = PoseDetector()
            # Manually set config since we skipped init
            detector.config = default_config
            
            kps = [Keypoint(0, "nose", 0.5, 0.5, 0.0, 1.0, 1.0)]
            arr = detector.keypoints_to_array(kps, (100, 100))
            assert arr.shape == (1, 2)
            assert arr[0][0] == 50
            assert arr[0][1] == 50
            print("PASS")
            
    except Exception as e:
        print(f"FAIL: {e}")
        import traceback
        traceback.print_exc()

    # 3. Warping Geometry
    print("Test: Warping Geometry...", end="")
    try:
        warper = Warper(default_config)
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        src_pts = np.array([[10, 10], [90, 10], [50, 90]], dtype=float)
        dst_pts = np.array([[10, 20], [90, 20], [50, 80]], dtype=float) 
        out = warper.warp_frame(img, src_pts, dst_pts)
        assert out.shape == img.shape
        print("PASS")
    except Exception as e:
        print(f"FAIL: {e}")

if __name__ == "__main__":
    run_manual_tests()
