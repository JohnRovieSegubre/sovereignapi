import argparse
import sys
import logging
import cv2
import numpy as np
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config import default_config, PipelineConfig
from src.pipeline.preprocessing import ImageNormalizer, PanelDetector
from src.pipeline.segmentation import SegmentationEngine
from src.pipeline.keypoints import PoseDetector
from src.pipeline.motion_planner import MotionPlanner
from src.pipeline.warping import Warper
from src.pipeline.rendering import VideoExporter
from src.utils.io import RunManifest
from src.utils.visualization import draw_skeleton

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

def load_image(path: Path) -> np.ndarray:
    if not path.exists():
        logger.error(f"File not found: {path}")
        sys.exit(1)
    return cv2.imread(str(path))

def main():
    parser = argparse.ArgumentParser(description="Comic Panel Animator")
    parser.add_argument("--start", required=True, help="Path to start frame image")
    parser.add_argument("--end", required=True, help="Path to end frame image")
    parser.add_argument("--output", default="output/anim.mp4", help="Path to output video")
    parser.add_argument("--fps", type=int, default=24, help="Frames per second")
    parser.add_argument("--duration", type=float, default=2.0, help="Duration in seconds")
    parser.add_argument("--debug", action="store_true", help="Enable debug outputs")
    
    args = parser.parse_args()
    
    # 0. Setup
    config = default_config
    config.fps = args.fps
    config.duration_sec = args.duration
    
    output_path = Path(args.output)
    manifest = RunManifest(f"run_{output_path.stem}", output_path.parent)
    
    logger.info("Initializing modules...")
    normalizer = ImageNormalizer(config)
    segmenter = SegmentationEngine(config) # Loads SAM
    pose_detector = PoseDetector(config) # Loads MediaPipe
    planner = MotionPlanner(config)
    warper = Warper(config)
    exporter = VideoExporter(config)
    
    # 1. Load & Preprocess
    start_img_raw = load_image(Path(args.start))
    end_img_raw = load_image(Path(args.end))
    
    # Normalize (resize/pad)
    start_img, meta_start = normalizer.normalize(start_img_raw)
    end_img, meta_end = normalizer.normalize(end_img_raw)
    
    # Save normalized images for debug
    debug_dir = config.output_dir / "debug"
    debug_dir.mkdir(exist_ok=True, parents=True)
    cv2.imwrite(str(debug_dir / "normalized_start.png"), start_img)
    cv2.imwrite(str(debug_dir / "normalized_end.png"), end_img)

    # 2. Segmentation (Masks) with Caching
    mask_dir = config.output_dir / "masks"
    mask_dir.mkdir(exist_ok=True, parents=True)
    start_mask_path = mask_dir / f"{Path(args.start).stem}_mask.png"
    end_mask_path = mask_dir / f"{Path(args.end).stem}_mask.png"

    if start_mask_path.exists() and end_mask_path.exists():
        logger.info("Loading cached masks from disk...")
        start_mask = cv2.imread(str(start_mask_path), cv2.IMREAD_GRAYSCALE)
        end_mask = cv2.imread(str(end_mask_path), cv2.IMREAD_GRAYSCALE)
    else:
        logger.info("Generating ID masks (this may take a while)...")
        start_mask = segmenter.generate_mask(start_img)
        end_mask = segmenter.generate_mask(end_img)
        cv2.imwrite(str(start_mask_path), start_mask)
        cv2.imwrite(str(end_mask_path), end_mask)
    
    # 3. Keypoints (Detect on RAW for better reliability, then transform)
    logger.info("Detecting landmarks on raw images...")
    start_kps_raw = pose_detector.detect(start_img_raw, label="start")
    end_kps_raw = pose_detector.detect(end_img_raw, label="end")
    
    if not start_kps_raw or not end_kps_raw:
        logger.error("Could not detect landmarks in one of the images. Aborting.")
        sys.exit(1)

    # Transform landmarks to normalized space
    def transform_kps(kps, meta, target_shape):
        h_target, w_target = target_shape[:2]
        for kp in kps:
            # First convert normalized raw to raw pixels
            raw_px = kp.x * meta.original_size[0]
            raw_py = kp.y * meta.original_size[1]
            # Transform to normalized space
            norm_px = (raw_px * meta.scale) + meta.pad_left
            norm_py = (raw_py * meta.scale) + meta.pad_top
            # Convert back to 0-1 normalized space relative to target_shape
            kp.x = norm_px / w_target
            kp.y = norm_py / h_target
        return kps

    start_kps_obj = transform_kps(start_kps_raw, meta_start, start_img.shape)
    end_kps_obj = transform_kps(end_kps_raw, meta_end, end_img.shape)
    
    # 4. Motion Planning
    logger.info("Planning motion...")
    interpolated_frames_kps = planner.interpolate(start_kps_obj, end_kps_obj)
    
    # 5. Generation loop
    generated_frames = []
    
    # Add start hold
    for _ in range(int(config.fps * 0.5)):
        generated_frames.append(start_img)
        
    logger.info(f"Rendering {len(interpolated_frames_kps)} in-between frames...")
    for idx, frame_kps_list in enumerate(interpolated_frames_kps):
        # Construct target array ordered like our detection points
        frame_map = {k['index']: k for k in frame_kps_list}
        
        target_pts = []
        source_pts = [] 
        
        for kp_start in start_kps_obj:
            kp_target = frame_map.get(kp_start.index)
            if kp_target:
                # Convert normalized to pixel
                tx = min(int(kp_target['x'] * start_img.shape[1]), start_img.shape[1]-1)
                ty = min(int(kp_target['y'] * start_img.shape[0]), start_img.shape[0]-1)
                target_pts.append([tx, ty])
                
                # Corresponding source point
                sx = min(int(kp_start.x * start_img.shape[1]), start_img.shape[1]-1)
                sy = min(int(kp_start.y * start_img.shape[0]), start_img.shape[0]-1)
                source_pts.append([sx, sy])
                
        if len(target_pts) < 3:
            logger.warning(f"Frame {idx}: Not enough points to warp. Skipping.")
            generated_frames.append(start_img) 
            continue
            
        # Warp
        warped = warper.warp_frame(
            start_img, 
            np.array(source_pts), 
            np.array(target_pts)
        )
        
        if args.debug:
            # Draw skeleton for debug
            warped = draw_skeleton(warped, frame_kps_list)
            
        generated_frames.append(warped)
        
    # Add end hold
    for _ in range(int(config.fps * 0.5)):
        generated_frames.append(end_img)
        
    # 6. Export
    logger.info("Exporting...")
    exporter.export_video(generated_frames, output_path)
    
    # Also save GIF for quick preview
    exporter.export_gif(generated_frames, output_path.with_suffix(".gif"))
    
    manifest.add_artifact("video", output_path)
    manifest.update("status", "success")
    logger.info("Done!")

if __name__ == "__main__":
    main()
