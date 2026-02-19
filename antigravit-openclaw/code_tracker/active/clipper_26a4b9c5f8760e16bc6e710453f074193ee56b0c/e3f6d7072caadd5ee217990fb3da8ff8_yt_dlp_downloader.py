Ýimport os
from yt_dlp import YoutubeDL


def _detect_ffmpeg_location() -> str | None:
    """Return a directory or file path usable as yt-dlp 'ffmpeg_location'."""
    override = os.getenv("FFMPEG_LOCATION") or os.getenv("FFMPEG_PATH")
    if override and os.path.exists(override):
        return override

    # Common local location (VS Code extension) used on this machine.
    home = os.path.expanduser("~")
    vscode_video_binaries = os.path.join(home, ".vscode", "extensions", "video-binaries")
    if os.path.isdir(vscode_video_binaries):
        ffmpeg_exe = os.path.join(vscode_video_binaries, "ffmpeg.exe")
        if os.path.exists(ffmpeg_exe):
            return vscode_video_binaries

    return None


def get_channel_videos_ytdlp(channel_url: str, max_results: int = 10, query: str = None) -> list[dict]:
    """
    Fetch recent videos from a channel using yt-dlp (no API key needed).
    Returns list of dicts with: id, title, duration_seconds, description.
    """
    # yt-dlp can fetch channel/playlist info directly
    ydl_opts = {
        'quiet': True,
        'extract_flat': 'in_playlist',  # Don't download, just get metadata
        'playlist_items': f'1-{max_results}',
        'ignoreerrors': True,
    }
    
    ffmpeg_location = _detect_ffmpeg_location()
    if ffmpeg_location:
        ydl_opts['ffmpeg_location'] = ffmpeg_location
    
    # For channels, yt-dlp needs /videos suffix for uploads tab
    fetch_url = channel_url
    if not fetch_url.endswith('/videos'):
        fetch_url = fetch_url.rstrip('/') + '/videos'
    
    videos = []
    with YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(fetch_url, download=False)
            if info and 'entries' in info:
                for entry in info['entries'][:max_results]:
                    if entry is None:
                        continue
                    vid = {
                        'id': entry.get('id', ''),
                        'title': entry.get('title', 'Unknown'),
                        'duration_seconds': entry.get('duration', 0) or 0,
                        'description': entry.get('description', '') or '',
                        'url': entry.get('url', f"https://www.youtube.com/watch?v={entry.get('id', '')}")
                    }
                    # Filter by query if provided
                    if query:
                        if query.lower() not in vid['title'].lower():
                            continue
                    videos.append(vid)
        except Exception as e:
            print(f"yt-dlp channel fetch error: {e}")
    
    return videos


def download_video(video_url: str, out_dir: str = 'temp') -> str:
    """Download a video via yt-dlp and return the path to the mp4 file."""
    os.makedirs(out_dir, exist_ok=True)
    out_template = os.path.join(out_dir, '%(id)s.%(ext)s')
    ydl_opts = {
        # Try multiple formats in order of preference
        'format': 'best[height<=720]/bestvideo[height<=720]+bestaudio/best',
        'outtmpl': out_template,
        'merge_output_format': 'mp4',
        'quiet': False,
        'no_warnings': False,
        # Use android client which may bypass some restrictions
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
    }

    ffmpeg_location = _detect_ffmpeg_location()
    if ffmpeg_location:
        ydl_opts['ffmpeg_location'] = ffmpeg_location

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        if info is None:
            raise RuntimeError(f"Failed to download video: {video_url}")
        filename = ydl.prepare_filename(info)
        # ensure .mp4 extension
        if not filename.endswith('.mp4'):
            base = os.path.splitext(filename)[0]
            filename = base + '.mp4'
    return filename

– *cascade08–—*cascade08—˜ *cascade08˜™*cascade08™› *cascade08›*cascade08ž*cascade08žŸ *cascade08Ÿ *cascade08 ¡ *cascade08¡¤ *cascade08¤¦*cascade08¦§ *cascade08§© *cascade08©ª*cascade08ª« *cascade08«­*cascade08­¯ *cascade08¯°*cascade08°± *cascade08±² *cascade08²³ *cascade08³´*cascade08´µ *cascade08µ¼*cascade08¼½ *cascade08½Á*cascade08ÁÛ *cascade08ÛÜ*cascade08ÜÝ *cascade08Ýà*cascade08àá *cascade08áâ*cascade08âã *cascade08ãæ*cascade08æç *cascade08çˆ*cascade08ˆ‰*cascade08‰¼ *cascade08¼ã*cascade08ãæ*cascade08æç *cascade08ç*cascade08‚ *cascade08‚…*cascade08…† *cascade08†Ž*cascade08Ž *cascade08œ *cascade08œ  *cascade08 §*cascade08§© *cascade08©ª*cascade08ª¬ *cascade08¬®*cascade08®¯ *cascade08¯° *cascade08°´*cascade08´µ *cascade08µ¶*cascade08¶· *cascade08·Á*cascade08ÁÂ *cascade08ÂÄ*cascade08ÄÅ *cascade08ÅÇ*cascade08ÇÈ *cascade08ÈÊ*cascade08ÊÍ*cascade08ÍÎ *cascade08ÎÏ*cascade08ÏÐ *cascade08ÐÑ*cascade08ÑÜ *cascade08Üá*cascade08áâ *cascade08âã*cascade08ãå *cascade08åç*cascade08çè *cascade08èé*cascade08éê *cascade08êí *cascade08íî*cascade08îï *cascade08ïð*cascade08ðñ *cascade08ñõ*cascade08õö*cascade08ö÷ *cascade08÷ø*cascade08øù *cascade08ùü*cascade08üþ *cascade08þ‚*cascade08‚ƒ *cascade08ƒ„*cascade08„† *cascade08†‡ *cascade08‡ˆ*cascade08ˆ‹ *cascade08‹Œ *cascade08Œ—*cascade08—™ *cascade08™š *cascade08šŸ*cascade08ŸŒ *cascade08Œð*cascade08ðÝ *cascade08"(26a4b9c5f8760e16bc6e710453f074193ee56b0c2Tfile:///c:/Users/rovie%20segubre/clipper/src/clipper/downloader/yt_dlp_downloader.py:(file:///c:/Users/rovie%20segubre/clipper