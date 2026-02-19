import os
import sys
import requests
from pathlib import Path
from tqdm import tqdm

# Add src to path to import config
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from src.config import default_config

MODELS = {
    "vit_h": {
        "url": "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth",
        "filename": "sam_vit_h_4b8939.pth"
    },
    "vit_l": {
        "url": "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_l_0b3195.pth",
        "filename": "sam_vit_l_0b3195.pth"
    },
    "vit_b": {
        "url": "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth",
        "filename": "sam_vit_b_01ec64.pth"
    }
}

def download_file(url: str, dest_path: Path):
    if dest_path.exists():
        print(f"File already exists: {dest_path}")
        return

    print(f"Downloading {url} to {dest_path}...")
    response = requests.get(url, stream=True)
    total_size_in_bytes = int(response.headers.get('content-length', 0))
    block_size = 1024 # 1 Kibibyte
    progress_bar = tqdm(total=total_size_in_bytes, unit='iB', unit_scale=True)
    
    with open(dest_path, 'wb') as file:
        for data in response.iter_content(block_size):
            progress_bar.update(len(data))
            file.write(data)
    progress_bar.close()
    
    if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
        print("ERROR, something went wrong")
        if dest_path.exists():
            os.remove(dest_path)

def main():
    # Ensure models directory exists
    models_dir = Path("models")
    if not models_dir.exists():
        models_dir.mkdir(parents=True)
    
    # Get model type from config or default to vit_h
    model_type = default_config.sam_model_type
    if model_type not in MODELS:
        print(f"Unknown model type in config: {model_type}. Defaulting to vit_h.")
        model_type = "vit_h"
        
    info = MODELS[model_type]
    dest_path = models_dir / info["filename"]
    
    print(f"Configured model: {model_type}")
    download_file(info["url"], dest_path)
    print("Done!")

if __name__ == "__main__":
    main()
