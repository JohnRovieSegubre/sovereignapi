£import os

# Runtime options: 'stub' (default), 'llama_cpp', 'ollama', 'gpt4all', 'hf_bnb'
RUNTIME = os.getenv('RUNTIME', 'gpt4all')  # Using GPT4All with local GGUF model
MODEL_PATH = os.getenv('MODEL_PATH', 'models/mistral-7b-v0.1.Q2_K.gguf')  # Fixed path
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3.2')
LLAMA_CPP_BIN = os.getenv('LLAMA_CPP_BIN', '')  # path to llama.cpp binary if used

# AI analyzer settings
DEFAULT_CLIP_LENGTH = int(os.getenv('DEFAULT_CLIP_LENGTH', '30'))
TARGET_CLIPS = int(os.getenv('TARGET_CLIPS', '5'))
~ *cascade08~ƒ*cascade08ƒ‹ *cascade08‹Ž*cascade08Ž‘ *cascade08‘—*cascade08—™ *cascade08™›*cascade08›œ *cascade08œ*cascade08Ÿ *cascade08Ÿ¢*cascade08¢£ *cascade08£©*cascade08©ª *cascade08ª®*cascade08®£ *cascade08"(26a4b9c5f8760e16bc6e710453f074193ee56b0c2>file:///c:/Users/rovie%20segubre/clipper/src/clipper/config.py:(file:///c:/Users/rovie%20segubre/clipper