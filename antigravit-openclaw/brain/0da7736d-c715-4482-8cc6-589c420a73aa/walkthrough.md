## Walkthrough - Manga Animation Pipeline

The **Manga Animation Pipeline** is now a full-stack application capable of transforming static manga panels into interpolated animations. It supports both **Face Focus** and **Full Body** modes, handling the unique challenges of stylized manga art through robust preprocessing and manual override capabilities.

## 🚀 Key Features
- **Dual Mode Detection**: `FaceLandmarker` for expression animation and `PoseLandmarker` for full-body action.
- **Raw-to-Norm Transformation**: Custom coordinate mapping ensures reliable detection on high-res manga pages before normalizing for the animation engine.
- **Production UI**: A modern **Next.js 14** web interface with real-time configuration (FPS, Duration, Mode) and file uploads.
- **API-First Architecture**: The python engine runs as an isolated worker service (`worker.py`) compliant with a strict JSON Error Contract.

## 📂 Artifacts
- **Source Code**: `manga-animator-ui/` (Frontend + Backend Worker)
- **Engine**: `src/` (Core Computer Vision Pipeline)
- **Output**: `output/` (Generated MP4s and Debug frames)

## 🎥 Results

### 1. The Interface
The new "Comic Animator" dashboard allows Directors to upload panels and fine-tune generation settings.
*(UI Screenshot placeholder - see `app/page.tsx`)*

### 2. Animation Logic
The pipeline successfully interpolated the test samples, managing the aspect ratio considerations and stylized features of the manga characters.

### 3. Landmark Verification
Debug outputs confirm that the **Raw-to-Norm** fix correctly maps detection points to the animation logic, solving the initial "Pose Mismatch" errors.
![Normalized Mesh](output/debug/normalized_start.png)

## 🔧 Usage
1. **Start Backend**: `.\setup_backend.ps1`
2. **Start Frontend**: `npm run dev`
3. **Generate**: Upload inputs at `localhost:3000` and click "Generate".

**Status**: MISSION ACCOMPLISHED. Ready for User Testing.
