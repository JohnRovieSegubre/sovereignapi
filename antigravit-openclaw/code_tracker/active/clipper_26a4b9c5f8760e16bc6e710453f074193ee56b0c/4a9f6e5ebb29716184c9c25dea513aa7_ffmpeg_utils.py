êimport os
import shutil
import subprocess

def build_ffmpeg_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    """Return an env dict with a working ffmpeg on PATH (best-effort).

    We prefer explicit env overrides, then fall back to a local ffmpeg bundled in a VS Code extension
    that exists on this machine.
    """

    env = dict(base_env or os.environ)

    # Some environments (e.g., spawned shells) may omit critical Windows vars.
    # CreateProcess may fail to locate executables without them.
    if not env.get("SystemRoot"):
        env["SystemRoot"] = env.get("WINDIR") or "C:\\Windows"
    if not env.get("WINDIR"):
        env["WINDIR"] = env.get("SystemRoot") or "C:\\Windows"
    if not env.get("ComSpec"):
        env["ComSpec"] = os.path.join(env["SystemRoot"], "System32", "cmd.exe")

    override = env.get("FFMPEG_LOCATION") or env.get("FFMPEG_PATH")
    candidates: list[str] = []
    if override and os.path.exists(override):
        candidates.append(override)

    home = os.path.expanduser("~")
    vscode_video_binaries = os.path.join(home, ".vscode", "extensions", "video-binaries")
    if os.path.isdir(vscode_video_binaries) and os.path.exists(os.path.join(vscode_video_binaries, "ffmpeg.exe")):
        candidates.append(vscode_video_binaries)

    for c in candidates:
        ffmpeg_dir = c if os.path.isdir(c) else os.path.dirname(c)
        if not ffmpeg_dir or not os.path.isdir(ffmpeg_dir):
            continue
        path_val = env.get("PATH") or ""
        parts = path_val.split(os.pathsep) if path_val else []
        if ffmpeg_dir not in parts:
            env["PATH"] = ffmpeg_dir + os.pathsep + path_val
        break

    return env


def find_ffmpeg_exe(env: dict[str, str] | None = None) -> str | None:
    """Return an absolute path to ffmpeg.exe if we can locate it."""
    e = env or build_ffmpeg_env()

    override = e.get("FFMPEG_EXE")
    if override and os.path.exists(override):
        return override

    # Preferred local VS Code extension location.
    home = os.path.expanduser("~")
    vscode_video_binaries = os.path.join(home, ".vscode", "extensions", "video-binaries")
    candidate = os.path.join(vscode_video_binaries, "ffmpeg.exe")
    if os.path.exists(candidate):
        return candidate

    # Fall back to PATH search if available.
    path_val = e.get("PATH")
    found = shutil.which("ffmpeg", path=path_val)
    return found

def extract_frame(video_path: str, timestamp: float, output_path: str) -> str:
    """Extract a single frame from video at timestamp as a JPEG."""
    env = build_ffmpeg_env()
    ffmpeg = find_ffmpeg_exe(env) or "ffmpeg"
    
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    
    cmd = [
        ffmpeg, "-y",
        "-ss", str(timestamp),
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2", # High quality JPEG
        "-update", "1",
        output_path
    ]
    
    # We suppress output unless error
    try:
        subprocess.run(cmd, check=True, env=env, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Frame extraction failed: {e.stderr}")
        raise e
        
    return output_path
ê*cascade08"(26a4b9c5f8760e16bc6e710453f074193ee56b0c2Ofile:///c:/Users/rovie%20segubre/clipper/src/clipper/processing/ffmpeg_utils.py:(file:///c:/Users/rovie%20segubre/clipper