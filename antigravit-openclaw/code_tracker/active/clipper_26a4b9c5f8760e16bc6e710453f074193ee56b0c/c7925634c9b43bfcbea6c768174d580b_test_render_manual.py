îimport os
import sys
from clipper.processing.shorts_render import render_multi_model_short

def test_render():
    # Use the existing video file found in root
    source_video = os.path.abspath("videoplayback.1769409807272.publer.com.mp4")
    output_video = os.path.abspath("output/test_tiktok_style.mp4")
    work_dir = os.path.abspath("temp/test_pillow_work")
    
    if not os.path.exists(source_video):
        print(f"Error: Source video not found at {source_video}")
        return

    # Dummy Persona Data
    personas = [
        {
            "model": "ChatGPT",
            "text": "This is a test of the new Pillow typography engine! It should look cleaner.",
            "color": "#10a37f"
        },
        {
            "model": "Claude",
            "text": "I agree. The text wrapping and background boxes should be much better now.",
            "color": "#d97757"
        },
        {
            "model": "Grok",
            "text": "I'm just here for the memes, but the font rendering does look premium.",
            "color": "#000000"
        }
    ]

    print("Starting render test...")
    try:
        render_multi_model_short(
            source_video=source_video,
            output_video=output_video,
            question_start=0,
            question_end=5,   # Use first 5s as "Question"
            official_start=10,
            official_end=15,  # Use 10-15s as "Official Answer"
            personas=personas,
            work_dir=work_dir
        )
        print(f"Test Complete! Checked output at: {output_video}")
    except Exception as e:
        print(f"Test Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_render()
§ *cascade08§¨*cascade08¨© *cascade08©«*cascade08«¬ *cascade08¬­*cascade08­® *cascade08®²*cascade08²î *cascade08"(26a4b9c5f8760e16bc6e710453f074193ee56b0c2Dfile:///c:/Users/rovie%20segubre/clipper/tests/test_render_manual.py:(file:///c:/Users/rovie%20segubre/clipper