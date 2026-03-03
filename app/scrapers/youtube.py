"""
YouTube RSS Feed Scraper & Transcript Fetcher

Fetches latest videos from YouTube channels via their RSS feeds,
filters by date, and retrieves transcripts using youtube-transcript-api.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

import httpx
from youtube_transcript_api import YouTubeTranscriptApi

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

YOUTUBE_RSS_BASE = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
YOUTUBE_VIDEO_URL = "https://www.youtube.com/watch?v={video_id}"

# XML namespaces used in the YouTube Atom feed
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class VideoInfo:
    """Represents a single YouTube video extracted from the RSS feed."""

    video_id: str
    title: str
    url: str
    published_at: datetime
    channel_name: str
    channel_id: str
    thumbnail_url: str | None = None
    transcript: str | None = None


@dataclass
class ChannelFetchResult:
    """Result of fetching videos from a single channel."""

    channel_id: str
    channel_name: str | None = None
    videos: list[VideoInfo] = field(default_factory=list)
    error: str | None = None


# ── Core Functions ───────────────────────────────────────────────────────────


def fetch_channel_feed(channel_id: str) -> ChannelFetchResult:
    """
    Fetch the RSS feed for a YouTube channel and parse all video entries.

    Args:
        channel_id: The YouTube channel ID (e.g. "UCbfYPyITQ-7l4upoX8nvctg").

    Returns:
        ChannelFetchResult with parsed videos or an error message.
    """
    url = YOUTUBE_RSS_BASE.format(channel_id=channel_id)
    result = ChannelFetchResult(channel_id=channel_id)

    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        result.error = f"HTTP error fetching feed: {exc}"
        logger.error(result.error)
        return result

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as exc:
        result.error = f"XML parse error: {exc}"
        logger.error(result.error)
        return result

    # Channel metadata
    title_el = root.find("atom:title", NS)
    result.channel_name = title_el.text if title_el is not None else channel_id

    # Parse each <entry>
    for entry in root.findall("atom:entry", NS):
        video = _parse_entry(entry, result.channel_name, channel_id)
        if video:
            result.videos.append(video)

    logger.info(
        "Fetched %d videos from channel '%s' (%s)",
        len(result.videos),
        result.channel_name,
        channel_id,
    )
    return result


def _parse_entry(
    entry: ET.Element, channel_name: str, channel_id: str
) -> VideoInfo | None:
    """Parse a single <entry> element into a VideoInfo."""

    video_id_el = entry.find("yt:videoId", NS)
    title_el = entry.find("atom:title", NS)
    published_el = entry.find("atom:published", NS)

    if video_id_el is None or title_el is None or published_el is None:
        return None

    video_id = video_id_el.text
    title = title_el.text
    published_at = datetime.fromisoformat(published_el.text)

    # Thumbnail
    thumbnail_el = entry.find("media:group/media:thumbnail", NS)
    thumbnail_url = thumbnail_el.get("url") if thumbnail_el is not None else None

    return VideoInfo(
        video_id=video_id,
        title=title,
        url=YOUTUBE_VIDEO_URL.format(video_id=video_id),
        published_at=published_at,
        channel_name=channel_name,
        channel_id=channel_id,
        thumbnail_url=thumbnail_url,
    )


def filter_videos_by_date(
    videos: list[VideoInfo],
    since: datetime,
) -> list[VideoInfo]:
    """
    Filter a list of videos to only include those published after *since*.

    Args:
        videos: List of VideoInfo objects.
        since:  Timezone-aware datetime. Videos published after this are kept.

    Returns:
        Filtered list, sorted newest-first.
    """
    # Ensure `since` is timezone-aware
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)

    filtered = [v for v in videos if v.published_at >= since]
    filtered.sort(key=lambda v: v.published_at, reverse=True)
    return filtered


def fetch_transcript(video_id: str, languages: list[str] | None = None) -> str | None:
    """
    Attempt to fetch the transcript for a YouTube video.

    Args:
        video_id:  The YouTube video ID.
        languages: Preferred language codes, e.g. ["en"]. Defaults to ["en"].

    Returns:
        The full transcript as a single string, or None if unavailable.
    """
    if languages is None:
        languages = ["en"]

    try:
        ytt_api = YouTubeTranscriptApi()
        fetched = ytt_api.fetch(video_id, languages=languages)
        # Join all snippet texts into a single string
        full_text = " ".join(snippet.text for snippet in fetched)
        logger.info("Fetched transcript for video %s (%d chars)", video_id, len(full_text))
        return full_text
    except Exception as exc:
        logger.warning("Could not fetch transcript for video %s: %s", video_id, exc)
        return None


# ── High-Level Orchestrator ──────────────────────────────────────────────────


def get_latest_videos(
    channel_ids: list[str],
    since: datetime,
    fetch_transcripts: bool = True,
) -> list[VideoInfo]:
    """
    Main entry point: fetch recent videos from multiple channels.

    Args:
        channel_ids:       List of YouTube channel IDs.
        since:             Only include videos published after this datetime.
        fetch_transcripts: If True, also retrieve video transcripts.

    Returns:
        List of VideoInfo objects for all new videos across all channels.
    """
    all_videos: list[VideoInfo] = []

    for cid in channel_ids:
        result = fetch_channel_feed(cid)

        if result.error:
            logger.error("Skipping channel %s: %s", cid, result.error)
            continue

        recent = filter_videos_by_date(result.videos, since)
        logger.info(
            "Channel '%s': %d new videos since %s",
            result.channel_name,
            len(recent),
            since.isoformat(),
        )

        if fetch_transcripts:
            for video in recent:
                video.transcript = fetch_transcript(video.video_id)

        all_videos.extend(recent)

    all_videos.sort(key=lambda v: v.published_at, reverse=True)
    return all_videos
