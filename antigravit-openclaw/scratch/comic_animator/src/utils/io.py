import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional
import logging

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("comic_animator")

def ensure_dir(path: Path) -> Path:
    """Ensures a directory exists."""
    path = Path(path)
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    return path

def save_json(data: Any, path: Path, indent: int = 2):
    """Saves data to a JSON file safely."""
    path = Path(path)
    ensure_dir(path.parent)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, default=str)
    logger.debug(f"Saved JSON to {path}")

def load_json(path: Path) -> Any:
    """Loads data from a JSON file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

class RunManifest:
    """Tracks metadata for a specific execution run."""
    def __init__(self, run_id: str, output_dir: Path):
        self.run_id = run_id
        self.output_dir = ensure_dir(output_dir)
        self.manifest_path = self.output_dir / "manifest.json"
        
        self.metadata = {
            "run_id": run_id,
            "timestamp": time.time(),
            "status": "started",
            "artifacts": {}
        }
        self._save()

    def update(self, key: str, value: Any):
        self.metadata[key] = value
        self._save()
        
    def add_artifact(self, name: str, path: Path):
        self.metadata["artifacts"][name] = str(path)
        self._save()

    def _save(self):
        save_json(self.metadata, self.manifest_path)
