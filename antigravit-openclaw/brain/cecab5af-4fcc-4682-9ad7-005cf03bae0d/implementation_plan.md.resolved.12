# Adding Persona Voiceovers

Add distinct text-to-speech voices for each AI persona in the riddle videos.

## Proposed Changes

### [NEW] [tts_engine.py](file:///c:/Users/rovie%20segubre/clipper/src/clipper/processing/tts_engine.py)

Create a TTS utility wrapper using `pyttsx3`:

- `generate_persona_audio(text, persona_name, output_path)` - Generates WAV audio file
- Voice mapping:
  - **ChatGPT** → David voice, 150 wpm, normal pitch (professional)
  - **Grok** → Zira voice, 180 wpm, faster (witty/quick)  
  - **Claude** → David voice, 130 wpm, slower (thoughtful)

---

### [MODIFY] [shorts_render.py](file:///c:/Users/rovie%20segubre/clipper/src/clipper/processing/shorts_render.py)

Replace silent `anullsrc` with TTS audio:

1. Call `generate_persona_audio()` for each persona
2. Add audio files as FFmpeg inputs
3. Replace `anullsrc` filter with `amovie` or direct audio input
4. Adjust persona clip duration to match audio length (min 2.5s, max 6s)

## Verification Plan

### Manual Verification
- Run `riddle_bot.py --force`
- Play output video and confirm each persona has distinct voice

