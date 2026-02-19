„ """
TTS Engine for generating persona voiceovers.
Uses pyttsx3 with Windows SAPI5 voices.
"""

import os
import pyttsx3
from typing import Optional


# Voice configuration per persona
PERSONA_VOICES = {
    'chatgpt': {
        'voice_name': 'David',  # Male, professional
        'rate': 150,            # Words per minute
    },
    'grok': {
        'voice_name': 'Zira',   # Female, quick wit
        'rate': 180,            # Faster = snappy
    },
    'claude': {
        'voice_name': 'David',  # Male, thoughtful
        'rate': 130,            # Slower = deliberate
    },
}

# Fallback for unknown personas
DEFAULT_VOICE = {
    'voice_name': 'David',
    'rate': 150,
}


def _find_voice(engine, name_fragment: str):
    """Find a voice by partial name match."""
    voices = engine.getProperty('voices')
    for voice in voices:
        if name_fragment.lower() in voice.name.lower():
            return voice.id
    # Return first voice as fallback
    return voices[0].id if voices else None


def generate_persona_audio(
    text: str,
    persona_name: str,
    output_path: str,
    engine: Optional[pyttsx3.Engine] = None
) -> str:
    """
    Generate a WAV audio file for a persona's speech.
    
    Args:
        text: The text to speak
        persona_name: Name of the persona (chatgpt, grok, claude)
        output_path: Path to save the WAV file
        engine: Optional pre-initialized pyttsx3 engine
        
    Returns:
        Path to the generated audio file
    """
    # Normalize persona name
    persona_key = persona_name.lower().strip()
    config = PERSONA_VOICES.get(persona_key, DEFAULT_VOICE)
    
    # Initialize engine if not provided
    own_engine = engine is None
    if own_engine:
        engine = pyttsx3.init()
    
    try:
        # Set voice
        voice_id = _find_voice(engine, config['voice_name'])
        if voice_id:
            engine.setProperty('voice', voice_id)
        
        # Set speech rate
        engine.setProperty('rate', config['rate'])
        
        # Set volume (0.0 to 1.0)
        engine.setProperty('volume', 0.9)
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        
        # Generate audio file
        engine.save_to_file(text, output_path)
        engine.runAndWait()
        
        return output_path
        
    finally:
        if own_engine:
            engine.stop()


def generate_all_persona_audio(
    personas: list,
    work_dir: str,
) -> list:
    """
    Generate audio files for all personas.
    
    Args:
        personas: List of persona dicts with 'model' and 'text' keys
        work_dir: Directory to save audio files
        
    Returns:
        List of paths to generated audio files
    """
    audio_paths = []
    
    for i, persona in enumerate(personas):
        model_name = persona.get('model', f'Model{i}')
        text = persona.get('text', '')
        
        if not text:
            audio_paths.append(None)
            continue
        
        output_path = os.path.join(work_dir, f"persona_{i}_{model_name.lower()}.wav")
        
        print(f"Generating TTS for {model_name}: '{text[:50]}...'")
        
        # Create fresh engine for each file to avoid hang issues
        try:
            generate_persona_audio(text, model_name, output_path, engine=None)
            audio_paths.append(output_path)
        except Exception as e:
            print(f"TTS failed for {model_name}: {e}")
            audio_paths.append(None)
    
    return audio_paths


if __name__ == "__main__":
    # Test
    test_personas = [
        {'model': 'ChatGPT', 'text': 'I believe the answer is quite straightforward when you analyze the details.'},
        {'model': 'Grok', 'text': 'Easy! Sarah did it. Classic misdirection.'},
        {'model': 'Claude', 'text': 'Perhaps we should consider the videographer, as they had access.'},
    ]
    
    paths = generate_all_persona_audio(test_personas, "temp/tts_test")
    print(f"Generated: {paths}")
ç *cascade08çÁ*cascade08Áß *cascade08ß¨*cascade08¨‰ *cascade08‰Í*cascade08ÍÎ *cascade08ÎÙ*cascade08Ùı *cascade08ı˜*cascade08˜¯ *cascade08¯˙*cascade08˙Ä *cascade08Ää*cascade08äå *cascade08åï*cascade08ïñ *cascade08ñó*cascade08óò *cascade08ò§*cascade08§• *cascade08•´*cascade08´¨ *cascade08¨≤*cascade08≤º *cascade08º√*cascade08√ƒ *cascade08ƒÀ*cascade08ÀÃ *cascade08ÃŒ*cascade08Œœ *cascade08œ“*cascade08“” *cascade08”◊*cascade08◊„  *cascade08"(26a4b9c5f8760e16bc6e710453f074193ee56b0c2Mfile:///c:/Users/rovie%20segubre/clipper/src/clipper/processing/tts_engine.py:(file:///c:/Users/rovie%20segubre/clipper