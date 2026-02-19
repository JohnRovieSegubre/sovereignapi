# Comic Animator

A system for animating panel-to-panel transitions in comics using keypoint interpolation and warping.

## Setup

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   **Important:** You need `mediapipe`, `opencv-python`, `torch`, `segment-anything`.

2. **Download Models:**
   Run the helper script to download SAM weights (approx 2.4GB):
   ```bash
   python scripts/download_models.py
   ```
   This places `sam_vit_h_4b8939.pth` in the `models/` directory.

## Usage

**Basic Animation:**
```bash
python main.py --start inputs/panel1.png --end inputs/panel2.png --output output/result.mp4
```

**Options:**
- `--fps`: Set frame rate (default 24).
- `--duration`: Animation duration in seconds (default 2.0).
- `--debug`: Enable debug visualizations (skeleton overlays).

## Architecture

- **Preprocessing:** Resizes/pads images to 1024x1024 (`src/pipeline/preprocessing.py`).
- **Segmentation:** Uses Segment Anything (SAM) to isolate characters (`src/pipeline/segmentation.py`).
- **Keypoints:** Uses MediaPipe Pose to extract body joints (`src/pipeline/keypoints.py`).
- **Motion Planning:** Interpolates skeletons using cubic easing (`src/pipeline/motion_planner.py`).
- **Warping:** Delaunay triangulation + Affine warp to move pixels (`src/pipeline/warping.py`).
- **Rendering:** Exports logic via OpenCV (`src/pipeline/rendering.py`).

## Testing

Run the test suite:
```bash
python -m pytest tests/
```

## Notes

- If SAM model is missing, the system will use a fallback (center ellipse mask) so you can still debug the pipeline.
