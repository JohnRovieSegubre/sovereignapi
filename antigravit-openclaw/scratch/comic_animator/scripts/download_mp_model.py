import requests
from pathlib import Path
from tqdm import tqdm

def download_file(url: str, dest_path: Path):
    if dest_path.exists():
        print(f"File already exists at {dest_path}, skipping download.")
        return

    print(f"Downloading {dest_path.name} from {url}...")
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        
        with open(dest_path, 'wb') as f, tqdm(
            desc=dest_path.name,
            total=total_size,
            unit='iB',
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for data in response.iter_content(chunk_size=1024):
                size = f.write(data)
                bar.update(size)
        print("Download complete.")
    except Exception as e:
        print(f"Failed to download: {e}")
        if dest_path.exists():
            dest_path.unlink() # Delete partial file

if __name__ == "__main__":
    # URL for the heavy (most accurate) pose landmarker task
    # Source: Google MediaPipe Developers Guide
    # https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task
    
    url = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task"
    dest = Path("models/pose_landmarker_heavy.task")
    
    download_file(url, dest)
