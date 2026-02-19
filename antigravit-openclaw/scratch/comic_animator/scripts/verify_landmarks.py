import cv2
import numpy as np
import argparse
from pathlib import Path
import logging

from src.pipeline.keypoints import PoseDetector
from src.config import PipelineConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_landmarks")

def main():
    parser = argparse.ArgumentParser(description="Quickly verify landmark detection on an image.")
    parser.add_argument("image", type=str, help="Path to the image file")
    parser.add_argument("--mode", type=str, choices=["face", "pose"], default="face", help="Detection mode")
    parser.add_argument("--output", type=str, default="debug_landmarks.png", help="Output path")
    parser.add_argument("--label", type=str, help="Label for manual override check (start/end)")
    args = parser.parse_args()

    # Load config
    config = PipelineConfig()
    config.detection_mode = args.mode
    
    # Initialize detector
    detector = PoseDetector(config)
    
    # Load image
    img = cv2.imread(args.image)
    if img is None:
        logger.error(f"Could not load image: {args.image}")
        return

    # Detect
    logger.info(f"Running {args.mode} detection on {args.image}...")
    kps = detector.detect(img, label=args.label)
    
    if not kps:
        logger.error("No landmarks detected!")
        # Create a red 'X' image to show failure
        cv2.putText(img, "DETECTION FAILED", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    else:
        logger.info(f"Detected {len(kps)} landmarks.")
        # Draw landmarks
        for kp in kps:
            px = int(kp.x * img.shape[1])
            py = int(kp.y * img.shape[0])
            cv2.circle(img, (px, py), 2, (0, 255, 0), -1)
            
        cv2.putText(img, f"{args.mode.upper()} MODE: {len(kps)} pts", (20, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    # Save
    cv2.imwrite(args.output, img)
    logger.info(f"Debug image saved to {args.output}")

if __name__ == "__main__":
    main()
