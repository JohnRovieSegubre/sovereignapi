import sys
import logging
import cv2
import numpy as np
import json
import traceback
from pathlib import Path
from dataclasses import asdict

# Add src to path
sys.path.append(str(Path(__file__).parent))

from src.config import default_config, PipelineConfig
from src.pipeline.preprocessing import ImageNormalizer
# from src.pipeline.segmentation import SegmentationEngine # DEPRECATED
from src.pipeline.keypoints import PoseDetector
from src.pipeline.motion_planner import MotionPlanner
from src.pipeline.warping import Warper
from src.pipeline.rendering import VideoExporter
from src.utils.io import RunManifest
from src.utils.visualization import draw_skeleton

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("worker")

# Error Contract Constants
ERR_ASSET_MISSING = "ASSET_MISSING"
ERR_ASPECT_MISMATCH = "ASPECT_MISMATCH"
ERR_POSE_MISMATCH = "POSE_MISMATCH"
ERR_FACE_LOW_CONFIDENCE = "FACE_CONFIDENCE_LOW"
ERR_INTERNAL = "INTERNAL_ERROR"

class AnimationError(Exception):
    """Custom exception for structured API errors."""
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)

def load_image_from_url(url: str) -> np.ndarray:
    path = Path(url)
    if not path.exists():
        raise AnimationError(ERR_ASSET_MISSING, f"Asset not found: {path}")
    return cv2.imread(str(path))

def run_job(job_payload: dict):
    job_id = f"job_{job_payload.get('seed', 0)}"
    output_dir = Path("output") / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    video_path = output_dir / "animation.mp4"
    manifest_path = output_dir / "run_manifest.json"
    
    try:
        # 1. Validation & Config
        if "start_panel" not in job_payload or "end_panel" not in job_payload:
            raise AnimationError(ERR_ASSET_MISSING, "Missing start_panel or end_panel")

        config = PipelineConfig()
        
        # Timing
        timing = job_payload.get("timing", {})
        config.fps = timing.get("fps", 24)
        num_frames = timing.get("frames", 12)
        config.duration_sec = num_frames / config.fps
        
        # Seed
        config.seed = job_payload.get("seed", 42)
        np.random.seed(config.seed)
        
        # Overrides
        overrides = job_payload.get("overrides", {})
        config.detection_mode = "face" if overrides.get("face") else "pose"

        logger.info(f"Starting Job {job_id} | Mode: {config.detection_mode}")
        
        # 2. Asset Loading & Validation
        start_img_raw = load_image_from_url(job_payload["start_panel"])
        end_img_raw = load_image_from_url(job_payload["end_panel"])

        # Check Aspect Ratio Tolerance (e.g. 5%)
        h1, w1 = start_img_raw.shape[:2]
        h2, w2 = end_img_raw.shape[:2]
        ratio1 = w1 / h1
        ratio2 = w2 / h2
        if abs(ratio1 - ratio2) > 0.05:
            raise AnimationError(ERR_ASPECT_MISMATCH, f"Aspect ratio mismatch: {ratio1:.2f} vs {ratio2:.2f}")

        # 3. Pipeline Initialization
        # VISION PIVOT: SAM Removed for "Maskless v1.0"
        normalizer = ImageNormalizer(config)
        # segmenter = SegmentationEngine(config) # DEPRECATED
        pose_detector = PoseDetector(config)
        planner = MotionPlanner(config)
        warper = Warper(config)
        exporter = VideoExporter(config)
        
        # Normalize
        start_img, meta_start = normalizer.normalize(start_img_raw)
        end_img, meta_end = normalizer.normalize(end_img_raw)
        
        # Segmentation (Masking) - REMOVED
        # The new vision relies on pure mesh warping and potential latent refinement.
        start_mask = None 
        end_mask = None
        
        # Pose Extraction
        start_kps_raw = pose_detector.detect(start_img_raw, label="start")
        end_kps_raw = pose_detector.detect(end_img_raw, label="end")
        
        if not start_kps_raw or not end_kps_raw:
            code = ERR_FACE_LOW_CONFIDENCE if config.detection_mode == "face" else ERR_POSE_MISMATCH
            raise AnimationError(code, f"Landmark detection failed for mode: {config.detection_mode}")

        # Transform landmarks
        def transform_kps(kps, meta, target_shape):
            h_target, w_target = target_shape[:2]
            for kp in kps:
                raw_px = kp.x * meta.original_size[0]
                raw_py = kp.y * meta.original_size[1]
                norm_px = (raw_px * meta.scale) + meta.pad_left
                norm_py = (raw_py * meta.scale) + meta.pad_top
                kp.x = norm_px / w_target
                kp.y = norm_py / h_target
            return kps

        start_kps_obj = transform_kps(start_kps_raw, meta_start, start_img.shape)
        end_kps_obj = transform_kps(end_kps_raw, meta_end, end_img.shape)
        
        # Interpolation
        interpolated_kps = planner.interpolate(start_kps_obj, end_kps_obj)
        
        # Rendering Loop
        frames = []
        # Start hold
        for _ in range(int(config.fps * 0.5)):
            frames.append(start_img)
            
        for i, frame_kps in enumerate(interpolated_kps):
            # Warping logic (simplified from main.py)
            frame_map = {k['index']: k for k in frame_kps}
            src_pts = []
            dst_pts = []
            
            for kp_start in start_kps_obj:
                kp_target = frame_map.get(kp_start.index)
                if kp_target:
                    # Target pixel
                    tx = min(int(kp_target['x'] * start_img.shape[1]), start_img.shape[1]-1)
                    ty = min(int(kp_target['y'] * start_img.shape[0]), start_img.shape[0]-1)
                    dst_pts.append([tx, ty])
                    
                    # Source pixel
                    sx = min(int(kp_start.x * start_img.shape[1]), start_img.shape[1]-1)
                    sy = min(int(kp_start.y * start_img.shape[0]), start_img.shape[0]-1)
                    src_pts.append([sx, sy])
            
            if len(dst_pts) < 3:
                frames.append(start_img)
                continue
                
            warped = warper.warp_frame(start_img, np.array(src_pts), np.array(dst_pts))
            frames.append(warped)
            
        # End hold
        for _ in range(int(config.fps * 0.5)):
            frames.append(end_img)
            
        # Export
        exporter.export_video(frames, video_path)
        
        # 4. Result/Manifest Construction
        result = {
            "job_id": job_id,
            "status": "completed",
            "output": {
                "video": str(video_path),
                "thumbnail": str(output_dir / "thumb.jpg") # TODO: Generating thumb
            },
            "meta": {
                "frames": len(frames),
                "fps": config.fps,
                "engine_version": "maskless_v1.0",
                "seed": config.seed
            }
        }
        
        # Write Manifest
        with open(manifest_path, "w") as f:
            json.dump(result, f, indent=2)
            
        print(json.dumps(result, indent=2))
        return result

    except AnimationError as e:
        logger.warning(f"Job Rejected: {e.code} - {e.message}")
        error_result = {
            "job_id": job_id,
            "status": "error",
            "error_code": e.code,
            "error_message": e.message
        }
        print(json.dumps(error_result, indent=2))
        return error_result

    except Exception as e:
        logger.error(f"Job Failed (Internal): {e}")
        traceback.print_exc()
        error_result = {
            "job_id": job_id,
            "status": "error",
            "error_code": ERR_INTERNAL,
            "error_message": str(e)
        }
        print(json.dumps(error_result, indent=2))
        return error_result

if __name__ == "__main__":
    # Example Payload (Simulation of API Request)
    # in production, this would come from sys.argv or a queue listener
    
    # Check if a payload file path is provided arg
    if len(sys.argv) > 1:
        payload_path = sys.argv[1]
        with open(payload_path, "r") as f:
            payload = json.load(f)
        run_job(payload)
    else:
        # Default test payload
        test_payload = {
            "start_panel": "debug_start.png",
            "end_panel": "debug_end.png",
            "mode": "final",
            "overrides": {"face": True},
            "timing": {"fps": 24, "frames": 24},
            "seed": 999
        }
        logger.info("Running with default test payload...")
        run_job(test_payload)
