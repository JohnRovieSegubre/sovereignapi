“
import os
import sys
from gpt4all import GPT4All

def test_prompts():
    model_path = os.path.abspath("models/mistral-7b-v0.1.Q2_K.gguf")
    model_dir = os.path.dirname(model_path)
    model_name = os.path.basename(model_path)
    
    print(f"Loading model: {model_name}...")
    # Use CPU/suppression logic manually here if needed, or just normal load for test
    model = GPT4All(model_name, model_path=model_dir, allow_download=False, device='cpu')

    riddle_text = "I speak without a mouth and hear without ears. I have no body, but I come alive with wind. What am I?"
    
    # 1. The "Strict" Prompt (Current Implementation)
    prompt_strict = (
        f"Riddle: {riddle_text}\n\n"
        "Instructions: Provide 3 different short answers (under 10 words) to this riddle from the perspective of different AI assistants.\n"
        "Format:\n"
        "ChatGPT: [Scanning database... Answer]\n"
        "Grok: [Roasting you... Answer]\n"
        "Claude: [Thoughtful analysis... Answer]\n\n"
        "Responses:"
    )
    
    print("\n--- Testing STRICT Prompt ---")
    resp_strict = model.generate(prompt_strict, max_tokens=128)
    print(f"RAW RESPOSNE:\n{resp_strict}\n-----------------------------")

    # 2. The "Completion" Prompt
    prompt_simple = (
        f"Riddle: {riddle_text}\n\n"
        "Here are 3 short guesses from AI assistants:\n\n"
        "1. ChatGPT: \""
    )
    
    print("\n--- Testing SIMPLE Prompt ---")
    resp_simple = model.generate(prompt_simple, max_tokens=128)
    print(f"RAW RESPOSNE:\n{resp_simple}\n-----------------------------")

if __name__ == "__main__":
    test_prompts()
ó	 *cascade08ó	õ	*cascade08õ	ù	 *cascade08ù	ý	*cascade08ý	Í
 *cascade08Í
Ô
*cascade08Ô
æ
 *cascade08æ
é
*cascade08é
ë
 *cascade08ë
í
*cascade08í
î
 *cascade08î
ï
*cascade08ï
ð
 *cascade08ð
ô
*cascade08ô
õ
 *cascade08õ
ö
*cascade08ö
ù
 *cascade08ù
û
*cascade08û
“ *cascade08"(26a4b9c5f8760e16bc6e710453f074193ee56b0c2=file:///c:/Users/rovie%20segubre/clipper/tests/test_prompt.py:(file:///c:/Users/rovie%20segubre/clipper