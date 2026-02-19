ï"import os
import re
from typing import Dict, List, Optional

from googleapiclient.discovery import build

from clipper.auth.youtube_auth import get_authenticated_credentials


YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")


def _build_service():
    """Build YouTube Data API client.

    Prefers API key for read-only calls. If not provided, falls back to OAuth credentials.
    """

    if YOUTUBE_API_KEY:
        return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    creds = get_authenticated_credentials(interactive=True)
    return build("youtube", "v3", credentials=creds)


def _extract_handle(channel_url: str) -> Optional[str]:
    if not channel_url:
        return None
    if "youtube.com/@" in channel_url:
        handle = channel_url.split("youtube.com/@", 1)[1]
        handle = handle.split("/", 1)[0]
        return handle.strip() or None
    if channel_url.startswith("@"):
        return channel_url[1:].strip() or None
    return None


def extract_channel_id(channel_url: str) -> str:
    """Extract channel id from URL or return the string if already an ID."""
    # Accept channel URL formats: https://www.youtube.com/@handle or /channel/ID or direct ID
    if channel_url.startswith("http"):
        parts = channel_url.rstrip("/").split("/")
        if len(parts) >= 2 and parts[-2] == "channel":
            return parts[-1]
        return channel_url
    return channel_url


def parse_duration(duration_iso: str) -> int:
    """Parse ISO 8601 duration (PT1H2M10S) to seconds."""
    # Regex to capture hours, minutes, seconds
    pattern = re.compile(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?')
    match = pattern.match(duration_iso)
    if not match:
        return 0
    
    h = int(match.group(1) or 0)
    m = int(match.group(2) or 0)
    s = int(match.group(3) or 0)
    
    return h * 3600 + m * 60 + s


def get_channel_videos(channel_url: str, max_results: int = 10, query: str = None) -> List[Dict]:
    """
    Return recent videos metadata for a channel URL or ID.
    If query is provided, searches within the channel.
    Fetches contentDetails to get duration.
    """
    svc = _build_service()
    channel = extract_channel_id(channel_url)

    # Resolve @handle using channels().list(forHandle=...)
    handle = _extract_handle(channel_url)
    if handle:
        resp = svc.channels().list(part="id", forHandle=handle).execute()
        items = resp.get("items", [])
        if not items:
            raise ValueError(f"Could not resolve channel handle: @{handle}")
        channel_id = items[0]["id"]
    elif channel.startswith("http"):
        # Fallback: try search by query
        request = svc.search().list(part="snippet", q=channel, type="channel", maxResults=1)
        resp = request.execute()
        items = resp.get("items", [])
        if not items:
            raise ValueError(f"Could not resolve channel: {channel}")
        channel_id = items[0]["snippet"]["channelId"]
    else:
        channel_id = channel

    # 1. Search for videos (IDs)
    search_kwargs = {
        "part": "snippet",
        "channelId": channel_id,
        "type": "video",
        "maxResults": max_results
    }
    
    if query:
        # If searching, we rely on relevance, not date
        search_kwargs["q"] = query
    else:
        # Default to gathering latest
        search_kwargs["order"] = "date"

    req = svc.search().list(**search_kwargs)
    res = req.execute()
    
    video_items = res.get('items', [])
    if not video_items:
        return []
        
    # 2. Batch fetch details for duration
    video_ids = [item['id']['videoId'] for item in video_items]
    
    stats_req = svc.videos().list(
        part="contentDetails,snippet",
        id=",".join(video_ids)
    )
    stats_res = stats_req.execute()
    
    # Map back to simpler dict
    videos = []
    for item in stats_res.get('items', []):
        duration_iso = item['contentDetails'].get('duration', 'PT0S')
        sec = parse_duration(duration_iso)
        
        vid = {
            'id': item['id'],
            'title': item['snippet']['title'],
            'publishedAt': item['snippet']['publishedAt'],
            'description': item['snippet'].get('description', ''),
            'duration_seconds': sec
        }
        videos.append(vid)
        
    return videos
ï"*cascade08"(26a4b9c5f8760e16bc6e710453f074193ee56b0c2Ffile:///c:/Users/rovie%20segubre/clipper/src/clipper/youtube_client.py:(file:///c:/Users/rovie%20segubre/clipper