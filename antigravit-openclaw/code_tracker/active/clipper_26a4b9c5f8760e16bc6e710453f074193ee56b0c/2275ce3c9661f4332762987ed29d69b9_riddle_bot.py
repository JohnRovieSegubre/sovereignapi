Ù;import os
import sys
import argparse
from clipper.downloader.yt_dlp_downloader import get_channel_videos_ytdlp, download_video
from clipper.processing.transcribe import transcribe, fetch_youtube_subtitles
from clipper.processing.riddle_segment import RiddleAnalyzer
from clipper.processing.shorts_render import render_multi_model_short
from clipper.uploader import upload_video

# Config
POSTED_FILE = 'posted_riddles.txt'

def load_posted():
    try:
        with open(POSTED_FILE, 'r', encoding='utf-8') as f:
            return set(x.strip() for x in f if x.strip())
    except FileNotFoundError:
        return set()

def mark_posted(video_id: str):
    with open(POSTED_FILE, 'a', encoding='utf-8') as f:
        f.write(video_id + '\n')

def get_next_output_path(vid: str) -> str:
    """Generate output path with auto-incrementing version number."""
    version = 1
    while True:
        path = os.path.abspath(f"output/riddle_{vid}_{version}.mp4")
        if not os.path.exists(path):
            return path
        version += 1

def run_riddle_bot(channel_url, max_videos=10, force=False):
    print(f"Scanning channel: {channel_url} for 'riddle' content...")
    
    # 1. Fetch metadata with query="riddle" to prioritize riddle videos
    #    and ensure we get duration
    videos = get_channel_videos_ytdlp(channel_url, max_results=max_videos, query="riddle")
    posted = load_posted()
    
    analyzer = RiddleAnalyzer()

    for v in videos:
        vid = v['id']
        title = v['title']
        duration = v.get('duration_seconds', 0)
        
        if vid in posted and not force:
            print(f"Skipping already posted: {vid} (use --force to reprocess)")
            continue

        print(f"\nChecking candidate: {title} ({vid}) | Duration: {duration}s")
        
        # FILTER 1: Duration check (Skip Compilations > 20 mins)
        if duration > 1200: # 20 mins
            print(f"Skipping: Too long ({duration}s > 1200s). Likely a compilation.")
            continue
            
        # FILTER 2: AI Relevance Check (Brain Check)
        print("Running AI Relevance Check...")
        is_relevant = analyzer.check_video_relevance(title, v.get('description', ''))
        if not is_relevant:
            print("Skipping: AI says this is NOT a riddle video.")
            continue
            
        print("Passed all filters. Downloading...")
        
        # 2. Download
        video_url = f"https://www.youtube.com/watch?v={vid}"
        try:
            video_path = download_video(video_url)
            video_path = os.path.abspath(video_path)  # Ensure absolute path for FFmpeg
        except Exception as e:
            print(f"Download failed: {e}")
            continue
            
        # 3. Transcribe - Try YouTube subtitles first (fast), then Whisper (slow)
        print("Fetching transcription...")
        try:
            # Try YouTube subtitles first (seconds vs hours)
            trans_result = fetch_youtube_subtitles(vid, output_dir="temp")
            
            # Fall back to Whisper if no subtitles available
            if not trans_result or not trans_result.get('cues'):
                print("No YouTube subtitles available. Falling back to Whisper...")
                trans_result = transcribe(video_path)
            
            cues = trans_result.get('cues', [])
        except Exception as e:
            print(f"Transcription failed: {e}")
            continue

        if not cues:
            print("No cues found in transcript.")
            continue

        # 4. Analyze (Find Riddles + Vision + Personas)
        print("Analyzing for riddles (Vision + Personas)...")
        # Note: We pass video_path so it can extract frames for vision
        riddle_segments = analyzer.find_riddle_segments(cues, video_path=video_path, max_candidates=1)
        
        if not riddle_segments:
            print("No valid riddles segments found in this video.")
            # Maybe mark posted so we don't re-download? Or maybe keep trying if algorithm improves.
            continue
            
        print(f"Found {len(riddle_segments)} valid riddle segments.")

        # 5. Render & Upload
        seg = riddle_segments[0]
        print(f"Rendering Short for riddle: {seg.riddle_text[:50]}...")
        
        out_name = get_next_output_path(vid)
        try:
            render_multi_model_short(
                source_video=video_path,
                output_video=out_name,
                question_start=seg.question_start,
                question_end=seg.question_end,
                official_start=seg.official_start,
                official_end=seg.official_end,
                personas=seg.personas,
                work_dir=f"temp/work_{vid}"
            )
            
            print(f"Success! Video rendered to: {out_name}")
            
            # Optional: Upload
            # res = upload_video(out_name, title=f"Riddle: {seg.riddle_text[:30]}? #shorts", description="Can you solve it?")
            # print('Uploaded:', res.get('id'))
            
            mark_posted(vid)
            break # Stop after one successful video for this run

        except Exception as e:
            print(f"Render failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    default_channel = "https://www.youtube.com/@BRIGHTSIDEOFFICIAL"
    
    parser = argparse.ArgumentParser(description="Auto-Riddle Bot")
    parser.add_argument("channel", nargs="?", default=default_channel, help="Channel URL")
    parser.add_argument("--file", help="Process a local video file instead of downloading")
    parser.add_argument("--force", action="store_true", help="Reprocess already-posted videos")
    
    args = parser.parse_args()
    
    if args.file:
        print(f"Processing local file: {args.file}")
        
        # Mock what the loop does
        analyzer = RiddleAnalyzer()
        video_path = os.path.abspath(args.file)
        vid_id = "local_test"
        
        print("Transcribing video...")
        try:
            trans_result = transcribe(video_path)
            cues = trans_result.get('cues', [])
        except Exception as e:
            print(f"Transcription failed: {e}")
            sys.exit(1)
            
        if not cues:
            print("No cues found.")
            sys.exit(1)

        print("Analyzing for riddles (Vision + Personas)...")
        riddle_segments = analyzer.find_riddle_segments(cues, video_path=video_path, max_candidates=1)
        
        if not riddle_segments:
            print("No valid riddles found.")
            sys.exit(0)
            
        seg = riddle_segments[0]
        print(f"Found riddle: {seg.riddle_text[:50]}...")
        out_name = os.path.abspath(f"output/riddle_{vid_id}_1.mp4")
        
        try:
            render_multi_model_short(
                source_video=video_path,
                output_video=out_name,
                question_start=seg.question_start,
                question_end=seg.question_end,
                official_start=seg.official_start,
                official_end=seg.official_end,
                personas=seg.personas,
                work_dir=f"temp/work_{vid_id}"
            )
            print(f"Success! Video rendered to: {out_name}")
        except Exception as e:
            print(f"Render failed: {e}")
            
    else:
        run_riddle_bot(args.channel, force=args.force)

5 *cascade085∑ *cascade08∑–*cascade08–é *cascade08éÉ *cascade08Éµ*cascade08µ‹ *cascade08‹ﬁ*cascade08ﬁÎ*cascade08Îö	 *cascade08ö	≤	*cascade08≤	∫	 *cascade08∫	Æ
*cascade08Æ
…
 *cascade08…
œ
*cascade08œ
Û
 *cascade08Û
É*cascade08É¢ *cascade08¢…*cascade08…Ä *cascade08Ä◊*cascade08◊Á *cascade08Áı*cascade08ı™ *cascade08™≈*cascade08≈Û *cascade08Ûõ*cascade08õú *cascade08úü*cascade08ü† *cascade08†Ÿ*cascade08Ÿ⁄ *cascade08⁄€*cascade08€‹ *cascade08‹*cascade08Ò *cascade08Ò˙*cascade08˙˚ *cascade08˚Ü*cascade08Üá *cascade08á…*cascade08…Ã *cascade08ÃÏ*cascade08ÏÌ *cascade08ÌÚ*cascade08ÚÛ *cascade08Ûˆ*cascade08ˆ˜ *cascade08˜¨*cascade08¨Æ *cascade08Æ∂*cascade08∂∑ *cascade08∑ª*cascade08ªº *cascade08ºø*cascade08ø¿ *cascade08¿¡*cascade08¡√ *cascade08√»*cascade08»… *cascade08…–*cascade08–“ *cascade08“Í*cascade08ÍÎ *cascade08ÎÒ*cascade08ÒÛ *cascade08Ûˇ*cascade08ˇÄ *cascade08Äã*cascade08ãå *cascade08å¥*cascade08¥∑ *cascade08∑ª*cascade08ªº *cascade08ºì*cascade08ì´ *cascade08´¨*cascade08¨¿ *cascade08¿ô*cascade08ôã *cascade08ãå*cascade08åò *cascade08ò“*cascade08“„ *cascade08„Ì*cascade08ÌÙ *cascade08Ù™*cascade08™´ *cascade08´¨*cascade08¨≠ *cascade08≠Ω*cascade08Ωæ *cascade08æÊ*cascade08ÊÁ *cascade08Áˇ*cascade08ˇÇ *cascade08Çë*cascade08ëí *cascade08íø*cascade08ø¿ *cascade08¿ó*cascade08óò *cascade08ò¢*cascade08¢£ *cascade08£§*cascade08§Æ *cascade08Æ∫*cascade08∫ª *cascade08ªÛ*cascade08ÛÙ *cascade08Ù˘*cascade08˘˚ *cascade08˚ˇ*cascade08ˇç *cascade08ç∞ *cascade08∞æ*cascade08æ» *cascade08»Ã*cascade08ÃÔ *cascade08Ôÿ*cascade08ÿ≈ *cascade08≈∆*cascade08∆ﬂ *cascade08ﬂ‡*cascade08‡§ *cascade08§™*cascade08™∞ *cascade08∞π*cascade08πﬂ *cascade08ﬂÁ*cascade08ÁÎ *cascade08ÎÏ*cascade08ÏÅ  *cascade08Å É *cascade08É Ñ  *cascade08Ñ ä *cascade08ä ï  *cascade08ï û *cascade08û ü  *cascade08ü ß *cascade08ß ®  *cascade08® ™ *cascade08™ ´  *cascade08´ ∂ *cascade08∂ ä! *cascade08ä!ê!*cascade08ê!ó! *cascade08ó!ú!*cascade08ú!∞! *cascade08∞!±!*cascade08±!Ã" *cascade08Ã"Õ"*cascade08Õ"Œ" *cascade08Œ"œ"*cascade08œ"–" *cascade08–"‘"*cascade08‘"’" *cascade08’"Ÿ" *cascade08Ÿ"⁄"*cascade08⁄"€" *cascade08€"‹"*cascade08‹"·" *cascade08·"‰"*cascade08‰"Ô" *cascade08Ô"Õ, *cascade08Õ,¢- *cascade08¢-¶- *cascade08¶-á.*cascade08á.ã. *cascade08ã.∑. *cascade08∑.„/ *cascade08„/Û/*cascade08Û/¸/ *cascade08¸/˝/*cascade08˝/ß6 *cascade08ß6∑6*cascade08∑6÷6 *cascade08÷6◊6*cascade08◊6¬; *cascade08¬;›; *cascade08›;Ô;*cascade08Ô;Ú; *cascade08Ú;Ù;*cascade08"(26a4b9c5f8760e16bc6e710453f074193ee56b0c26file:///c:/Users/rovie%20segubre/clipper/riddle_bot.py:(file:///c:/Users/rovie%20segubre/clipper