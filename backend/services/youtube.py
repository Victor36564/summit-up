import re
from typing import Any

import requests

from cache import cache
from config import Settings
from schemas import VideoResult

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
COMMENTS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"


def parse_iso8601_duration(duration: str) -> float:
    match = re.fullmatch(
        r"P(?:(?P<days>\d+)D)?T?(?:(?P<hours>\d+)H)?"
        r"(?:(?P<minutes>\d+)M)?(?:(?P<seconds>[\d.]+)S)?",
        duration,
    )
    if not match:
        raise ValueError(f"Unsupported YouTube duration: {duration}")
    return (
        float(match.group("days") or 0) * 86400
        + float(match.group("hours") or 0) * 3600
        + float(match.group("minutes") or 0) * 60
        + float(match.group("seconds") or 0)
    )


def extract_hikes_master(text: str) -> list[str]:
    hikes: list[str] = []
    for raw_line in text.strip().splitlines():
        line = raw_line.strip()
        if not line:
            continue
        numbered = re.match(
            r"^(?:\d+/\d+|\d+)[.)]?\s*[-–—]*\s*"
            r"([A-Z][A-Za-z0-9\s'’]+?)(?:\s*[(:\-–—]|$)",
            line,
        )
        if numbered:
            hikes.append(numbered.group(1).strip())
            continue
        bulleted = re.match(
            r"^[-•]\s+([A-Z][A-Za-z0-9\s'’]+?)\s+[-–—:|]\s+",
            line,
        )
        if bulleted:
            hikes.append(bulleted.group(1).strip())

    if not hikes:
        trail_keywords = (
            r"(Track|Trail|Crossing|Walk|Pass|Hut|Hike|Route|Peak|Summit|"
            r"Tarns|Falls|Glacier|Saddle|Hill)"
        )
        prose_pattern = re.compile(
            rf"\b([A-Z][A-Za-z'’]+(?:\s+[A-Z][A-Za-z'’]+)*\s+{trail_keywords})\b"
        )
        hikes = [match[0] for match in prose_pattern.findall(text)]

    return list(dict.fromkeys(hikes))


def _get_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def search_shorts(settings: Settings, query: str, limit: int) -> list[VideoResult]:
    if not settings.youtube_api_key:
        raise RuntimeError("YOUTUBE_API_KEY is not configured")
    key = f"youtube:v2:{query.lower()}:{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    found: list[VideoResult] = []
    next_page_token = ""
    while len(found) < limit:
        search_params: dict[str, Any] = {
            "part": "id",
            "key": settings.youtube_api_key,
            "q": query,
            "type": "video",
            "videoDuration": "short",
            "maxResults": 30,
            "order": "relevance",
        }
        if next_page_token:
            search_params["pageToken"] = next_page_token
        search_response = _get_json(SEARCH_URL, search_params)
        video_ids = [
            item["id"]["videoId"]
            for item in search_response.get("items", [])
            if item.get("id", {}).get("videoId")
        ]
        if not video_ids:
            break
        video_response = _get_json(
            VIDEOS_URL,
            {
                "part": "contentDetails,snippet,player",
                "key": settings.youtube_api_key,
                "id": ",".join(video_ids),
                "maxHeight": 1080,
                "maxWidth": 1920,
            },
        )
        for video in video_response.get("items", []):
            try:
                duration = parse_iso8601_duration(video["contentDetails"]["duration"])
            except (KeyError, ValueError):
                continue
            player = video.get("player", {})
            width = int(player.get("embedWidth", 0) or 0)
            height = int(player.get("embedHeight", 0) or 0)
            if duration > 60 or height <= width or not height:
                continue
            snippet = video.get("snippet", {})
            description = snippet.get("description", "")
            if not description:
                continue
            hike_names = extract_hikes_master(description)
            if not hike_names:
                continue
            found.append(
                VideoResult(
                    video_id=video["id"],
                    title=snippet.get("title", "Untitled hike"),
                    duration_sec=duration,
                    dimensions=f"{width}x{height}",
                    tags=snippet.get("tags", []),
                    description=description,
                    url=f"https://www.youtube.com/shorts/{video['id']}",
                    hike_names=hike_names,
                )
            )
            if len(found) >= limit:
                break
        next_page_token = search_response.get("nextPageToken", "")
        if not next_page_token:
            break
    return cache.set(key, found[:limit], settings.cache_ttl_seconds)


def get_video_comments(settings: Settings, video_id: str, limit: int = 20) -> list[dict[str, Any]]:
    if not settings.youtube_api_key:
        raise RuntimeError("YOUTUBE_API_KEY is not configured")
    key = f"youtube:comments:v1:{video_id}:{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    response = _get_json(
        COMMENTS_URL,
        {
            "part": "snippet",
            "key": settings.youtube_api_key,
            "videoId": video_id,
            "maxResults": limit,
            "order": "relevance",
            "textFormat": "plainText",
        },
    )
    comments: list[dict[str, Any]] = []
    for item in response.get("items", []):
        snippet = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
        if not snippet:
            continue
        comments.append(
            {
                "author": snippet.get("authorDisplayName", "Anonymous"),
                "text": snippet.get("textDisplay", ""),
                "like_count": int(snippet.get("likeCount", 0) or 0),
                "published_at": snippet.get("publishedAt"),
            }
        )
    return cache.set(key, comments, settings.cache_ttl_seconds)
