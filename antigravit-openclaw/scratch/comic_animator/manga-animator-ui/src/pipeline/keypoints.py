import cv2
import numpy as np
import mediapipe as mp
import logging
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass

from ..config import PipelineConfig, default_config

logger = logging.getLogger(__name__)

@dataclass
class Keypoint:
    index: int
    name: str
    x: float  # Normalized 0-1
    y: float  # Normalized 0-1
    z: float  # Normalized (depth)
    visibility: float
    presence: float

class PoseDetector:
    def __init__(self, config: PipelineConfig = default_config):
        self.config = config
        
        # MediaPipe Tasks API
        BaseOptions = mp.tasks.BaseOptions
        VisionRunningMode = mp.tasks.vision.RunningMode
        
        self.detector = None
        self.mode = config.detection_mode

        if self.mode == "face":
            FaceLandmarker = mp.tasks.vision.FaceLandmarker
            FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
            model_path = "models/face_landmarker.task"
            try:
                options = FaceLandmarkerOptions(
                    base_options=BaseOptions(model_asset_path=model_path),
                    running_mode=VisionRunningMode.IMAGE,
                    min_face_detection_confidence=config.min_detection_confidence
                )
                self.detector = FaceLandmarker.create_from_options(options)
                logger.info(f"Loaded MediaPipe Face Landmarker from {model_path}")
            except Exception as e:
                logger.error(f"Failed to load FaceLandmarker (Mode: {self.mode}): {e}")
        else: # pose
            PoseLandmarker = mp.tasks.vision.PoseLandmarker
            PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
            model_path = "models/pose_landmarker_heavy.task"
            try:
                options = PoseLandmarkerOptions(
                    base_options=BaseOptions(model_asset_path=model_path),
                    running_mode=VisionRunningMode.IMAGE,
                    min_pose_detection_confidence=config.min_detection_confidence
                )
                self.detector = PoseLandmarker.create_from_options(options)
                logger.info(f"Loaded MediaPipe Pose Landmarker from {model_path}")
            except Exception as e:
                logger.error(f"Failed to load PoseLandmarker (Mode: {self.mode}): {e}")

    def detect(self, image: np.ndarray, label: str = None) -> Optional[List[Keypoint]]:
        """
        Detects landmarks in the given image.
        Supports manual override if 'landmarks_override.json' exists in output_dir.
        """
        # --- MANUAL OVERRIDE LOGIC ---
        override_path = self.config.output_dir / "landmarks_override.json"
        if override_path.exists() and label:
            try:
                import json
                with open(override_path, "r") as f:
                    overrides = json.load(f)
                
                if label in overrides:
                    logger.info(f"Using manual landmark overrides for {label}")
                    keypoints = []
                    for idx, (px, py) in enumerate(overrides[label]):
                        # Normalize back to 0-1 for internal processing
                        h, w = image.shape[:2]
                        keypoints.append(Keypoint(
                            index=idx,
                            name=f"manual_{idx}",
                            x=px / w,
                            y=py / h,
                            z=0.0,
                            visibility=1.0,
                            presence=1.0
                        ))
                    return keypoints
            except Exception as e:
                logger.error(f"Failed to load manual overrides: {e}")
        # -----------------------------

        if self.detector is None:
            return None

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)
        
        detection_result = self.detector.detect(mp_image)
        
        # Result attribute depends on the model
        landmarks_list = getattr(detection_result, "face_landmarks", None) or \
                         getattr(detection_result, "pose_landmarks", None)
        
        if not landmarks_list:
            logger.warning(f"No {self.mode} landmarks detected for {label or 'image'}.")
            return None
            
        # Use first detection
        landmarks = landmarks_list[0]
        
        keypoints = []
        for idx, landmark in enumerate(landmarks):
            # For face mode, we use indices 0-477
            name = f"point_{idx}"
            if self.mode == "pose":
                # Only use name mapping for pose
                name = getattr(self, "landmark_names", {}).get(idx, name)
                
            kp = Keypoint(
                index=idx,
                name=name,
                x=landmark.x,
                y=landmark.y,
                z=landmark.z,
                visibility=getattr(landmark, 'visibility', 1.0),
                presence=getattr(landmark, 'presence', 1.0)
            )
            keypoints.append(kp)
            
        return keypoints

    def keypoints_to_array(self, keypoints: List[Keypoint], image_shape: Tuple[int, int]) -> np.ndarray:
        """
        Converts normalized keypoints to pixel coordinates (N, 2).
        """
        h, w = image_shape[:2]
        coords = []
        for kp in keypoints:
            px = min(int(kp.x * w), w - 1)
            py = min(int(kp.y * h), h - 1)
            coords.append([px, py])
        return np.array(coords)
