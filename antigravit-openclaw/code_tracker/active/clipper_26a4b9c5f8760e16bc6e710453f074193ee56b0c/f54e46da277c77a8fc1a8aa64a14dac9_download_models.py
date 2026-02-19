³import os
import sys

def download_vision_model():
    print("Downloading Vision Model (OpenCLIP CoCa)...")
    try:
        import open_clip
        # This will trigger download to cache
        model, _, _ = open_clip.create_model_and_transforms(
            model_name="coca_ViT-B-32",
            pretrained="mscoco_finetuned_laion2b_s13b_b90k"
        )
        print("Vision Model Downloaded Successfully!")
    except Exception as e:
        print(f"Vision Model Download Failed: {e}")

def download_whisper_model():
    print("Downloading Whisper Model (Faster-Whisper)...")
    try:
        from faster_whisper import WhisperModel
        # This triggers download
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        print("Whisper Model Downloaded Successfully!")
    except Exception as e:
        print(f"Whisper Model Download Failed: {e}")

if __name__ == "__main__":
    print("Starting Model Downloads...")
    download_whisper_model()
    download_vision_model()
    print("All downloads complete.")
³*cascade08"(26a4b9c5f8760e16bc6e710453f074193ee56b0c2Cfile:///c:/Users/rovie%20segubre/clipper/scripts/download_models.py:(file:///c:/Users/rovie%20segubre/clipper