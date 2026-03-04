"""
YouTube RSS Feed Scraper & Transcript Fetcher

Fetches latest videos from YouTube channels via their RSS feeds,
filters by date, and retrieves transcripts using youtube-transcript-api.
"""

import logging
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

import httpx
from pydantic import BaseModel, Field
from youtube_transcript_api import YouTubeTranscriptApi

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

YOUTUBE_RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
YOUTUBE_VIDEO_URL = "https://www.youtube.com/watch?v={video_id}"

# XML namespaces used in the YouTube Atom feed
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}


# ── Data Classes ─────────────────────────────────────────────────────────────

class TranscriptInfo(BaseModel):
    """Transcript content for a YouTube video."""

    text: str


class VideoInfo(BaseModel):
    """Represents a single YouTube video extracted from the RSS feed."""

    video_id: str
    title: str
    url: str
    published_at: datetime
    channel_name: str
    channel_id: str
    thumbnail_url: str | None = None
    transcript: TranscriptInfo | None = None


class ChannelFetchResult(BaseModel):
    """Result of fetching videos from a single channel."""

    channel_id: str
    channel_name: str | None = None
    videos: list[VideoInfo] = Field(default_factory=list)
    error: str | None = None


# ── Service Class ────────────────────────────────────────────────────────────


class YouTubeScraper:
    """
    Service that fetches recent videos from YouTube channels via RSS
    and optionally retrieves their transcripts.

    Usage:
        scraper = YouTubeScraper(channel_ids=["UCYO_jab_esuFRV4b17AJtAw"])
        videos = scraper.get_latest_videos(since=datetime(...))

        for video in videos:
            print(video.title, video.transcript)
    """

    def __init__(
        self,
        channel_ids: list[str],
        transcript_languages: list[str] | None = None,
    ):
        """
        Args:
            channel_ids:          List of YouTube channel IDs to monitor.
            transcript_languages: Preferred transcript language codes. Defaults to ["en"].
        """
        self.channel_ids = channel_ids
        self.transcript_languages = transcript_languages or ["en"]
        self._http_client = httpx.Client(timeout=15, follow_redirects=True)
        self._transcript_api = YouTubeTranscriptApi()

    # ── Public API ───────────────────────────────────────────────────────

    def get_latest_videos(
        self,
        since: datetime,
        fetch_transcripts: bool = True,
    ) -> list[VideoInfo]:
        """
        Main entry point: fetch recent videos from all configured channels.

        Args:
            since:             Only include videos published after this datetime.
            fetch_transcripts: If True, also retrieve video transcripts.

        Returns:
            List of VideoInfo objects, sorted newest-first.
        """
        all_videos: list[VideoInfo] = []

        for channel_id in self.channel_ids:
            result = self.fetch_channel_feed(channel_id)

            if result.error:
                logger.error("Skipping channel %s: %s", channel_id, result.error)
                continue

            recent = self._filter_by_date(result.videos, since)
            logger.info(
                "Channel '%s': %d new videos since %s",
                result.channel_name,
                len(recent),
                since.isoformat(),
            )

            if fetch_transcripts:
                for video in recent:
                    transcript_text = self.fetch_transcript(video.video_id)
                    if transcript_text:
                        video.transcript = TranscriptInfo(text=transcript_text)

            all_videos.extend(recent)

        all_videos.sort(key=lambda v: v.published_at, reverse=True)
        return all_videos

    def fetch_channel_feed(self, channel_id: str) -> ChannelFetchResult:
        """
        Fetch the RSS feed for a single YouTube channel and parse all entries.

        Args:
            channel_id: The YouTube channel ID (e.g. "UCbfYPyITQ-7l4upoX8nvctg").

        Returns:
            ChannelFetchResult with parsed videos or an error message.
        """
        url = YOUTUBE_RSS_URL.format(channel_id=channel_id)
        result = ChannelFetchResult(channel_id=channel_id)

        try:
            resp = self._http_client.get(url)
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
            video = self._parse_entry(entry, result.channel_name, channel_id)
            if video:
                result.videos.append(video)

        logger.info(
            "Fetched %d videos from channel '%s' (%s)",
            len(result.videos),
            result.channel_name,
            channel_id,
        )
        return result

    def fetch_transcript(self, video_id: str) -> str | None:
        """
        Fetch the transcript for a YouTube video.

        Args:
            video_id: The YouTube video ID.

        Returns:
            The full transcript as a single string, or None if unavailable.
        """
        try:
            fetched = self._transcript_api.fetch(
                video_id, languages=self.transcript_languages
            )
            full_text = " ".join(snippet.text for snippet in fetched)
            logger.info(
                "Fetched transcript for video %s (%d chars)", video_id, len(full_text)
            )
            return full_text
        except Exception as exc:
            logger.warning(
                "Could not fetch transcript for video %s: %s", video_id, exc
            )
            return None

    # ── Private Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _parse_entry(
        entry: ET.Element, channel_name: str, channel_id: str
    ) -> VideoInfo | None:
        """Parse a single <entry> element from the RSS feed into a VideoInfo."""

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

    @staticmethod
    def _filter_by_date(
        videos: list[VideoInfo], since: datetime
    ) -> list[VideoInfo]:
        """Return only videos published after *since*, sorted newest-first."""
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)

        filtered = [v for v in videos if v.published_at >= since]
        filtered.sort(key=lambda v: v.published_at, reverse=True)
        return filtered