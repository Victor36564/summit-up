#!/usr/bin/env python3
"""Search YouTube for short hiking videos in New Zealand.

The script retrieves video metadata only; it does not download video files.
Set YOUTUBE_API_KEY in the repository's .env file, as an environment variable,
or pass --api-key before running it.
"""

import argparse
import json
import os
import re
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from dotenv import load_dotenv, find_dotenv


SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(REPO_ROOT, ".env"))

def get_api_key() -> str | None:
	"""Resolve the API key with environment variables taking precedence."""
	return os.environ.get("YOUTUBE_API_KEY")


def youtube_get(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
	"""Call a YouTube Data API endpoint and return its JSON response."""
	url = f"{endpoint}?{urlencode(params)}"
	request = Request(url, headers={"Accept": "application/json"})
	try:
		with urlopen(request, timeout=30) as response:
			return json.load(response)
	except HTTPError as error:
		details = error.read().decode("utf-8", errors="replace")
		raise RuntimeError(f"YouTube API returned HTTP {error.code}: {details}") from error
	except URLError as error:
		raise RuntimeError(f"Could not connect to YouTube: {error.reason}") from error


def parse_iso8601_duration(duration: str) -> float:
	"""Convert a YouTube ISO 8601 duration such as PT45S to seconds."""
	match = re.fullmatch(
		r"P(?:(?P<days>\d+)D)?T?(?:(?P<hours>\d+)H)?"
		r"(?:(?P<minutes>\d+)M)?(?:(?P<seconds>[\d.]+)S)?",
		duration,
	)
	if not match:
		raise ValueError(f"Unsupported YouTube duration: {duration}")
	return (
		(float(match.group("days") or 0) * 86400)
		+ (float(match.group("hours") or 0) * 3600)
		+ (float(match.group("minutes") or 0) * 60)
		+ float(match.group("seconds") or 0)
	)


def get_youtube_shorts_with_orientation(
	api_key: str, query: str, max_shorts_limit: int = 5
) -> list[dict[str, Any]]:
	"""Find videos that are at most 60 seconds long and portrait-oriented."""
	shorts_found: list[dict[str, Any]] = []
	next_page_token = ""

	while len(shorts_found) < max_shorts_limit:
		search_params: dict[str, Any] = {
			"part": "id",
			"key": api_key,
			"q": query,
			"type": "video",
			"videoDuration": "short",
			"maxResults": 50,
			"order": "relevance",
		}
		if next_page_token:
			search_params["pageToken"] = next_page_token

		search_response = youtube_get(SEARCH_URL, search_params)
		video_ids = [
			item["id"]["videoId"]
			for item in search_response.get("items", [])
			if item.get("id", {}).get("videoId")
		]
		if not video_ids:
			break

		video_response = youtube_get(
			VIDEOS_URL,
			{
				"part": "contentDetails,snippet,player",
				"key": api_key,
				"id": ",".join(video_ids),
				"maxHeight": 1080,
				"maxWidth": 1920,
			},
		)

		for video in video_response.get("items", []):
			content_details = video.get("contentDetails", {})
			try:
				duration_seconds = parse_iso8601_duration(content_details["duration"])
			except (KeyError, ValueError):
				continue

			player_info = video.get("player", {})
			width = int(player_info.get("embedWidth", 0) or 0)
			height = int(player_info.get("embedHeight", 0) or 0)
			if duration_seconds > 60 or height <= width or not height:
				continue

			shorts_found.append(
				{
					"video_id": video["id"],
					"title": video.get("snippet", {}).get("title", ""),
					"duration_sec": duration_seconds,
					"dimensions": f"{width}x{height}",
					"url": f"https://www.youtube.com/shorts/{video['id']}",
				}
			)
			if len(shorts_found) >= max_shorts_limit:
				break

		next_page_token = search_response.get("nextPageToken", "")
		if not next_page_token:
			break

	return shorts_found[:max_shorts_limit]


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument(
		"--api-key",
		default=get_api_key(),
		help="YouTube Data API key (defaults to YOUTUBE_API_KEY or .env)",
	)
	parser.add_argument(
		"--query",
		default="hiking New Zealand",
		help="Search query (default: hiking New Zealand)",
	)
	parser.add_argument(
		"--max-results",
		type=int,
		default=25,
		help="Number of portrait Shorts to retrieve (default: 25)",
	)
	parser.add_argument(
		"--output",
		help="Optional path for saving results as JSON",
	)
	return parser.parse_args()


def main() -> int:
	args = parse_args()
	if not args.api_key:
		print("Set YOUTUBE_API_KEY or pass --api-key.", file=sys.stderr)
		return 2
	if not 1 <= args.max_results <= 500:
		print("--max-results must be between 1 and 500.", file=sys.stderr)
		return 2

	try:
		videos = get_youtube_shorts_with_orientation(
			args.api_key, args.query, args.max_results
		)
	except RuntimeError as error:
		print(error, file=sys.stderr)
		return 1

	if args.output:
		with open(args.output, "w", encoding="utf-8") as output_file:
			json.dump(videos, output_file, indent=2, ensure_ascii=False)
			output_file.write("\n")

	for number, video in enumerate(videos, start=1):
		print(
			f"{number}. {video['title']} | "
			f"{video['duration_sec']:.1f}s | {video['dimensions']} | {video['url']}"
		)
	print(f"\nFound {len(videos)} portrait Shorts for: {args.query}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
