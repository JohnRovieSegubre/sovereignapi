‰import sys
import os

sys.path.append(os.path.join(os.getcwd(), 'src'))

from clipper.processing.analyze import AnalyzerFactory

def test_vision():
    # 1. Check Describer Loading
    print("Initializing ImageDescriber...")
    describer = AnalyzerFactory.get_image_describer()
    if not describer:
        print("Failed to get describer.")
        return

    # 2. Test Describe (Mock image or real if exists)
    # We will use the extract_frame from previous steps to make a real image
    video_source = "videoplayback.1769409807272.publer.com.mp4"
    if not os.path.exists(video_source):
        print(f"Video source {video_source} not found.")
        return
        
    from clipper.processing.ffmpeg_utils import extract_frame
    test_frame = "temp/vision_test_frame.jpg"
    try:
        print(f"Extracting frame from {video_source}...")
        extract_frame(video_source, 5.0, test_frame)
        if os.path.exists(test_frame):
            print(f"Frame extracted to {test_frame}")
            
            print("Running Vision Model (this may take time to download weights)...")
            caption = describer.describe(test_frame)
            print(f"\n[VISION OUTPUT]: {caption}\n")
        else:
            print("Frame extraction failed silent.")
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    test_vision()
‰*cascade08"(26a4b9c5f8760e16bc6e710453f074193ee56b0c2Afile:///c:/Users/rovie%20segubre/clipper/scripts/verify_vision.py:(file:///c:/Users/rovie%20segubre/clipper