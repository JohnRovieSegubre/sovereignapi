# Task: Improved Typography & Overlays

## Typography Engine Upgrade
- [x] Research available tools for typography (MoviePy, Pillow, FFmpeg, HTML/CSS) <!-- id: 0 -->
- [x] Create Implementation Plan for Pillow-based Text Rendering <!-- id: 1 -->
- [x] Implemenet dependencies and `TextRenderer` class using Pillow <!-- id: 3 -->
    - [x] Install Requirements
    - [x] `TextOverlayGenerator` implementation
- [x] Refactor `shorts_render.py` <!-- id: 4 -->
    - [x] Replace `drawtext` filter with `overlay` filter
    - [x] Integrate `TextRenderer` to generate assets before FFmpeg call
- [x] Verify changes with a test render <!-- id: 5 -->
    - [x] Create `test_render_manual.py`
    - [x] Run test and check for errors

## Refinement: TikTok Style
- [x] Update `TextOverlayGenerator` for TikTok "Classic" aesthetic <!-- id: 6 -->
    - [x] Switch to Bold fonts
    - [x] Add black stroke/outline
    - [x] Tighten padding
- [x] Verify TikTok style render (manual) <!-- id: 7 -->

## Maintenance
- [x] Fix GPT4All CUDA DLL error (Force CPU) <!-- id: 8 -->
- [x] Suppress noisy GPT4All DLL warnings <!-- id: 10 -->
    - [x] Fixed syntax error introduced during suppression <!-- id: 11 -->
    - [x] Fixed UnboundLocalError (os/sys shadowing) <!-- id: 12 -->
- [x] Verify fix by running `riddle_bot.py` <!-- id: 9 -->
- [x] Debug LLM response quality (Hallucinating lists) <!-- id: 14 -->
    - [x] Analyze prompt in `riddle_segment.py`
    - [x] Improve prompt engineering for Q2 Mistral
    - [x] Verify fix with `riddle_bot.py`
- [x] Debug Audio Cutoff & Overlap <!-- id: 15 -->
    - [x] Inspect `shorts_render.py` timing logic
    - [x] Fix audio cutoff (Increased clamp from 8s to 20s)
    - [x] Reduce default answer duration to avoid overlap
- [x] Debug "Bad Response" Issue <!-- id: 16 -->
    - [x] Create `tests/test_prompt.py` to reproduce failure
    - [x] Revert to "Completion Style" prompt logic
    - [x] Verify with standalone test
    - [x] Apply fix to `riddle_segment.py`
    - [ ] Notify user and request final confirmation
