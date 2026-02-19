ΩWimport os
import subprocess
import sys
import re
from typing import Any, Dict, List

try:
    from faster_whisper import WhisperModel
    HAS_FASTER_WHISPER = True
except ImportError:
    HAS_FASTER_WHISPER = False

try:
    from yt_dlp import YoutubeDL
    HAS_YTDLP = True
except ImportError:
    HAS_YTDLP = False


def fetch_youtube_subtitles(video_id: str, output_dir: str = "temp") -> Dict[str, Any]:
    """
    Fetch YouTube auto-generated or manual subtitles using yt-dlp.
    Much faster than running Whisper (seconds vs hours).
    Returns dict with 'text' and 'cues'.
    """
    if not HAS_YTDLP:
        print("yt-dlp not available for subtitle download.")
        return None
    
    os.makedirs(output_dir, exist_ok=True)
    srt_path = os.path.join(output_dir, f"{video_id}.srt")
    
    # Check if SRT already exists
    if os.path.exists(srt_path) and not os.getenv("WHISPER_FORCE"):
        print(f"Subtitles found at {srt_path}, using cached version.")
        from .srt_parser import parse_srt
        with open(srt_path, "r", encoding="utf-8") as f:
            content = f.read()
        cues = parse_srt(content)
        text = " ".join([c.text for c in cues])
        return {"text": text, "cues": cues}
    
    print(f"Fetching YouTube subtitles for {video_id}...")
    
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'writeautomaticsub': True,
        'writesubtitles': True,
        'subtitleslangs': ['en', 'en-orig', 'en-US'],
        'subtitlesformat': 'srt',
        'outtmpl': os.path.join(output_dir, '%(id)s'),
    }
    
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
        # Find the downloaded SRT file (yt-dlp adds language suffix)
        possible_paths = [
            os.path.join(output_dir, f"{video_id}.en.srt"),
            os.path.join(output_dir, f"{video_id}.en-orig.srt"),
            os.path.join(output_dir, f"{video_id}.en-US.srt"),
        ]
        
        actual_srt = None
        for p in possible_paths:
            if os.path.exists(p):
                actual_srt = p
                break
        
        if not actual_srt:
            # Try finding any .srt file with video_id
            for f in os.listdir(output_dir):
                if f.startswith(video_id) and f.endswith(".srt"):
                    actual_srt = os.path.join(output_dir, f)
                    break
        
        if actual_srt:
            # Rename to standard name
            if actual_srt != srt_path:
                os.rename(actual_srt, srt_path)
            
            from .srt_parser import parse_srt
            with open(srt_path, "r", encoding="utf-8") as f:
                content = f.read()
            cues = parse_srt(content)
            text = " ".join([c.text for c in cues])
            print(f"Subtitles downloaded successfully! ({len(cues)} cues)")
            return {"text": text, "cues": cues}
        else:
            print("No English subtitles available for this video.")
            return None
            
    except Exception as e:
        print(f"Subtitle fetch error: {e}")
        return None


def _maybe_prepend_ffmpeg_to_path(env: dict[str, str]) -> dict[str, str]:
    override = os.getenv("FFMPEG_LOCATION") or os.getenv("FFMPEG_PATH")
    candidates: list[str] = []

    if override and os.path.exists(override):
        candidates.append(override)

    home = os.path.expanduser("~")
    vscode_video_binaries = os.path.join(home, ".vscode", "extensions", "video-binaries")
    ffmpeg_exe = os.path.join(vscode_video_binaries, "ffmpeg.exe")
    if os.path.exists(ffmpeg_exe):
        candidates.append(vscode_video_binaries)

    for c in candidates:
        ffmpeg_dir = c if os.path.isdir(c) else os.path.dirname(c)
        if ffmpeg_dir and os.path.isdir(ffmpeg_dir):
            path_val = env.get("PATH") or ""
            parts = path_val.split(os.pathsep) if path_val else []
            if ffmpeg_dir not in parts:
                env = dict(env)
                env["PATH"] = ffmpeg_dir + os.pathsep + path_val
                return env

    return env



def transcribe_with_faster_whisper(video_path: str, model_size: str = "tiny") -> Dict[str, Any]:
    print(f"Using Faster-Whisper (Model: {model_size}) on CPU...")
    # SrtPath check
    output_dir = os.path.dirname(os.path.abspath(video_path)) or os.getcwd()
    base = os.path.splitext(os.path.basename(video_path))[0]
    srt_path = os.path.join(output_dir, base + ".srt")
    
    if os.path.exists(srt_path) and not os.getenv("WHISPER_FORCE"):
        print(f"SRT file found at {srt_path}, skipping transcription.")
        from .srt_parser import parse_srt
        with open(srt_path, "r", encoding="utf-8") as f:
            content = f.read()
        cues = parse_srt(content)
        text = " ".join([c.text for c in cues])
        return {"text": text, "cues": cues}

    try:
        # 1. Initialize Model
        # int8 quantization is default and fast on CPU
        model = WhisperModel(model_size, device="cpu", compute_type="int8")

        # 2. Transcribe
        segments, info = model.transcribe(video_path, beam_size=5)
        
        # 3. Collect & format results
        cues = []
        text_parts = []
        
        print("Transcribing segments...")
        with open(srt_path, "w", encoding="utf-8") as srt_file:
            for i, segment in enumerate(segments):
                start = segment.start
                end = segment.end
                text = segment.text.strip()
                
                # SrtCue format
                # We need a simple class or dict that mimics SrtCue
                class SimpleCue:
                    def __init__(self, idx, s, e, t):
                        self.index = idx
                        self.start = s
                        self.end = e
                        self.text = t
                        
                cues.append(SimpleCue(i+1, start, end, text))
                text_parts.append(text)
                
                def fmt_time(t):
                    hours = int(t // 3600)
                    minutes = int((t % 3600) // 60)
                    seconds = int(t % 60)
                    millis = int((t - int(t)) * 1000)
                    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"
                
                srt_file.write(f"{i+1}\n")
                srt_file.write(f"{fmt_time(start)} --> {fmt_time(end)}\n")
                srt_file.write(f"{text}\n\n")
                
                # Progress indicator
                if (i+1) % 10 == 0:
                    sys.stdout.write(f"Processed {i+1} segments...     \r")
                    sys.stdout.flush()

        print(f"\nTranscription complete! SRT saved to {srt_path}")
        return {"text": " ".join(text_parts), "cues": cues}

    except Exception as e:
        print(f"Faster-Whisper error: {e}")
        return {"text": "", "cues": []}


def transcribe_with_whisper_cli(video_path: str, model: str = "tiny") -> Dict[str, Any]:
    """Call whisper CLI (if available) and return a dict with 'text' and 'segments' (best-effort)."""
    try:
        clip_seconds = int(os.getenv("WHISPER_CLIP_SECONDS", "180"))
        verbose = os.getenv("WHISPER_VERBOSE", "false").lower() in ("1", "true", "yes")
        timeout_seconds = int(os.getenv("WHISPER_TIMEOUT_SECONDS", "900"))

        # Important: whisper writes outputs into the current working directory by default.
        # We want the transcript next to the downloaded video so we can reliably read it.
        output_dir = os.path.dirname(os.path.abspath(video_path)) or os.getcwd()
        base = os.path.splitext(os.path.basename(video_path))[0]

        # Prefer the console script if present; otherwise fall back to module execution.
        # (Windows environments sometimes miss the 'whisper' entrypoint script.)
        cmd = [
            "whisper",
            video_path,
            "--model",
            model,
            "--output_format",
            "srt",
            "--output_dir",
            output_dir,
            "--language",
            "en",
        ]

        srt_path = os.path.join(output_dir, base + ".srt")
        print(f"DEBUG: Checking for SRT at: {srt_path}")
        if os.path.exists(srt_path) and not os.getenv("WHISPER_FORCE"):
            print(f"SRT file found at {srt_path}, skipping transcription.")
        else:
            # Speed up verification: only transcribe the first N seconds.
            if clip_seconds > 0:
                cmd.extend(["--clip_timestamps", f"0,{clip_seconds}"])

            if not verbose:
                cmd.extend(["--verbose", "False"])

            env = _maybe_prepend_ffmpeg_to_path(dict(os.environ))
            try:
                t_val = timeout_seconds if timeout_seconds > 0 else None
                subprocess.run(cmd, check=True, timeout=t_val, env=env)
            except FileNotFoundError:
                # Fallback module execution
                cmd[0] = sys.executable
                cmd.insert(1, "-m")
                cmd.insert(2, "whisper")
                 # Re-align arguments since we shifted
                t_val = timeout_seconds if timeout_seconds > 0 else None
                subprocess.run(cmd, check=True, timeout=t_val, env=env)

        srt_path = os.path.join(output_dir, base + ".srt")
        text = ""
        cues = []
        
        if os.path.exists(srt_path):
            from .srt_parser import parse_srt
            with open(srt_path, "r", encoding="utf-8") as f:
                content = f.read()
            cues = parse_srt(content)
            # Reconstruct full text from cues
            text = " ".join([c.text for c in cues])

        return {"text": text, "cues": cues}
    except Exception as e:
        print(f"Transcription error: {e}")
        return {"text": "", "cues": []}



def transcribe(video_path: str, model: str = "tiny") -> Dict[str, Any]:
    """Transcribe a video/audio file.

    Env:
    - WHISPER_MODEL: overrides model parameter
    - WHISPER_CLIP_SECONDS: transcribe only first N seconds (default 180)
    - WHISPER_VERBOSE: set true to show whisper progress
    - WHISPER_TIMEOUT_SECONDS: kill whisper if it runs too long (default 900)
    """

    try:
        effective_model = os.getenv("WHISPER_MODEL", model)
        
        if HAS_FASTER_WHISPER and not os.getenv("WHISPER_FORCE_CLI"):
            return transcribe_with_faster_whisper(video_path, model_size=effective_model)

        env = _maybe_prepend_ffmpeg_to_path(dict(os.environ))
        try:
            subprocess.run(["whisper", "--help"], capture_output=True, env=env)
        except FileNotFoundError:
            subprocess.run([sys.executable, "-m", "whisper", "--help"], capture_output=True, env=env)
        effective_model = os.getenv("WHISPER_MODEL", model)
        return transcribe_with_whisper_cli(video_path, model=effective_model)
    except Exception:
        raise RuntimeError("Whisper CLI not available. Install openai-whisper or whisper.cpp for transcription.")
' *cascade08'1*cascade081M *cascade08M’ *cascade08’¨*cascade08¨≠ *cascade08≠Å! *cascade08Å!°7*cascade08°7‡7 *cascade08‡7‰7*cascade08‰7“@ *cascade08“@çA *cascade08çA∆A*cascade08∆AÏB *cascade08ÏB≤C *cascade08≤C∆E *cascade08∆EèF*cascade08èFπF *cascade08πFºF*cascade08ºF…H *cascade08…H’H *cascade08’HûI*cascade08ûI»I *cascade08»IÀI*cascade08ÀI∆N *cascade08∆N N*cascade08 N´Q *cascade08´QëS *cascade08ëSΩW *cascade08"(26a4b9c5f8760e16bc6e710453f074193ee56b0c2Mfile:///c:/Users/rovie%20segubre/clipper/src/clipper/processing/transcribe.py:(file:///c:/Users/rovie%20segubre/clipper