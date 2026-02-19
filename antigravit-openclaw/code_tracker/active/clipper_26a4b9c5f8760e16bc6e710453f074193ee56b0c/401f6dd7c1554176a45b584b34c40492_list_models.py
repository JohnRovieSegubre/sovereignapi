±
import open_clip

print("Available CoCa models:")
for model, pretrained in open_clip.list_pretrained():
    if "coca" in model:
        print(f"{model} ({pretrained})")
±*cascade08"(26a4b9c5f8760e16bc6e710453f074193ee56b0c2?file:///c:/Users/rovie%20segubre/clipper/scripts/list_models.py:(file:///c:/Users/rovie%20segubre/clipper