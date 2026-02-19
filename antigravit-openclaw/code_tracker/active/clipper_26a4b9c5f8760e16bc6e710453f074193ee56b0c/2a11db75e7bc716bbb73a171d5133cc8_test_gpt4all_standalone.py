¶

import os
import sys
import time
from gpt4all import GPT4All

def test_gpt4all():
    model_path = os.path.abspath("models/mistral-7b-v0.1.Q2_K.gguf")
    model_dir = os.path.dirname(model_path)
    model_name = os.path.basename(model_path)
    
    print(f"Testing GPT4All with:")
    print(f"  Path: {model_path}")
    print(f"  Dir: {model_dir}")
    print(f"  Name: {model_name}")

    if not os.path.exists(model_path):
        print("ERROR: Model file not found!")
        return

    print("\nInitializing GPT4All (device='cpu')...")
    start_t = time.time()
    try:
        # Explicitly setting device='cpu' to avoid CUDA search
        model = GPT4All(model_name, model_path=model_dir, allow_download=False, device='cpu')
        print(f"Initialization took {time.time() - start_t:.2f}s")
        
        print("\nGenerating text...")
        gen_start = time.time()
        # Use a short prompt and small token count for speed
        response = model.generate("The capital of France is", max_tokens=10)
        print(f"Response: {response}")
        print(f"Generation took {time.time() - gen_start:.2f}s")
        
    except Exception as e:
        print(f"\nCRASHED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_gpt4all()
¶
*cascade08"(26a4b9c5f8760e16bc6e710453f074193ee56b0c2Ifile:///c:/Users/rovie%20segubre/clipper/tests/test_gpt4all_standalone.py:(file:///c:/Users/rovie%20segubre/clipper