­import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from clipper.processing.shorts_render import render_multi_model_short

def test_render():
    source = "videoplayback.1769409807272.publer.com.mp4"
    if not os.path.exists(source):
        print(f"File {source} not found.")
        return
    source = os.path.abspath(source)
    output = os.path.abspath("output/verify_riddle.mp4")

    
    # Fake detected segments
    # Assuming video has enough length. Let's pick 0-5s as question, 10-15s as official.
    personas = [
        {'model': 'ChatGPT', 'text': 'The answer is likely a shadow, because it follows you but has no mass.', 'color': '#10a37f'},
        {'model': 'Grok', 'text': 'It is obviously a shadow. Lol.', 'color': '#ffffff'},
        {'model': 'Claude', 'text': 'I believe the riddle describes a shadow, a phenomenon characterizing light obstruction.', 'color': '#d97757'}
    ]
    
    try:
        render_multi_model_short(
            source_video=source,
            output_video=output,
            question_start=0.0,
            question_end=5.0,
            official_start=10.0,
            official_end=15.0,
            personas=personas,
            work_dir="temp/riddle_test"
        )
        print(f"Success! Output at {output}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_render()
Ù *cascade08Ùý*cascade08ýŒ *cascade08Œœ*cascade08œ¶ *cascade08¶¹*cascade08¹­ *cascade08"(26a4b9c5f8760e16bc6e710453f074193ee56b0c2Afile:///c:/Users/rovie%20segubre/clipper/scripts/verify_riddle.py:(file:///c:/Users/rovie%20segubre/clipper