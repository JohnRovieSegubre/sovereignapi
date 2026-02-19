
"""
ModelAdapter Interface
----------------------
Defines the contract for Generative Video providers (Runway, Kling, Luma).
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional

class ModelAdapter(ABC):
    @abstractmethod
    def submit_job(self, start_img_path: str, end_img_path: str, prompt: str, seed: int) -> str:
        """
        Submits a job to the external API.
        Returns: job_id (str)
        """
        pass

    @abstractmethod
    def poll_status(self, job_id: str) -> Dict:
        """
        Checks job status.
        Returns: {
            "status": "pending" | "processing" | "completed" | "failed",
            "video_url": str (optional),
            "progress": float (0.0 to 1.0)
        }
        """
        pass

class MockAdapter(ModelAdapter):
    """
    Mock adapter for local development without burning API credits.
    Returns the last generated local video essentially instantly.
    """
    def submit_job(self, start_img_path: str, end_img_path: str, prompt: str, seed: int) -> str:
        import time
        return f"mock_job_{int(time.time())}"

    def poll_status(self, job_id: str) -> Dict:
        return {
            "status": "completed",
            "video_url": "output/manga_face_v2.mp4", # Placeholder
            "progress": 1.0
        }
