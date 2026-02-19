# Implementation Plan - Rich Typography & Overlays

## Problem
The current video generation uses FFmpeg's `drawtext` filter. This is performant but limited:
- Hard to do complex word wrapping or precise layout.
- Limited styling (basic colors, hard to do rounded corners or "chat bubble" aesthetics).
- No support for rich text (bolding one word, mixing colors).

## Goal
Improve typography and overlay capabilities by moving text rendering **out** of FFmpeg and into Python (Pillow). We will generate transparent PNG images containing the styled text and overlay them onto the video.

## User Review Required
> [!NOTE]
> This plan utilizes `Pillow` (already in requirements) to minimize new dependencies. If you require **extremely** complex styling (like CSS shadows, gradients, flexbox layouts), we should consider adding `html2image` or `moviepy`, but Pillow is a great significant step up from `drawtext`.

## Proposed Changes

### `src/clipper/processing`

#### [NEW] `text_renderer.py`
Create a helper class `TextOverlayGenerator` that uses `Pillow` (`PIL.Image`, `PIL.ImageDraw`, `PIL.ImageFont`) to:
- Create a transparent RGBA image of video resolution (or specific overlay size).
- Draw text with:
    - Custom fonts (ttf).
    - Word wrapping (better than `textwrap` + ffmpeg).
    - Background boxes with rounded corners (chat bubble style).
    - Drop shadows.
- Save the result as a `.png` file in the temp working directory.

#### [MODIFY] `shorts_render.py`
- Import `TextOverlayGenerator`.
- In the `render_multi_model_short` function:
    - Iterate through `personas`.
    - Instead of creating a `.txt` file for `drawtext`, call `TextOverlayGenerator.generate(...)` to create a `overlay_{i}.png`.
    - Update the FFmpeg filter chain:
        - Remove `drawtext=...`.
        - Add the `.png` as a new input (`-i overlay_i.png`).
        - Use the `overlay` filter to composite the PNG on top of the background color/video.
            - `[bg][overlay_input]overlay=0:0[out]`

## Verification Plan

### Manual Verification
1.  **Render Test**: Run `riddle_bot.py --file local_test_video.mp4` (or similar command used in development).
2.  **Visual Check**: Inspect the output video.
    - Check if text is legible.
    - Check if "Persona" names and text look better (e.g., centered, background box).
    - Check if emoji/special characters render (Pillow handles unicode better if font supports it).

### Automated Tests
None existing for visual output quality. Will rely on manual verification of the generated MP4.
