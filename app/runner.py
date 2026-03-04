"""
Scraper Runner

Orchestrates all scrapers (YouTube, OpenAI, Anthropic) and collects
recent content into a single unified result.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.config import YOUTUBE_CHANNELS, LOOKBACK_HOURS
from app.scrapers.youtube import YouTubeScraper, VideoInfo
from app.scrapers.openai_blog import OpenAIScraper, ArticleInfo
from app.scrapers.anthropic_blog import AnthropicScraper, AnthropicArticle

logger = logging.getLogger(__name__)


@dataclass
class ScrapeResult:
    """Combined result from all scrapers."""

    youtube_videos: list[VideoInfo] = field(default_factory=list)
    openai_articles: list[ArticleInfo] = field(default_factory=list)
    anthropic_articles: list[AnthropicArticle] = field(default_factory=list)
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_items(self) -> int:
        return len(self.youtube_videos) + len(self.openai_articles) + len(self.anthropic_articles)

    def summary(self) -> str:
        lines = [
            f"Scrape completed at {self.scraped_at.strftime('%Y-%m-%d %H:%M UTC')}",
            f"  YouTube videos:     {len(self.youtube_videos)}",
            f"  OpenAI articles:    {len(self.openai_articles)}",
            f"  Anthropic articles: {len(self.anthropic_articles)}",
            f"  Total:              {self.total_items}",
        ]
        return "\n".join(lines)


def run_scrapers(
    lookback_hours: int = LOOKBACK_HOURS,
    fetch_transcripts: bool = True,
) -> ScrapeResult:
    """
    Run all scrapers and return combined results.

    Args:
        lookback_hours: How many hours back to search for new content.
        fetch_transcripts: Whether to fetch YouTube video transcripts.

    Returns:
        ScrapeResult with content from all sources.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    result = ScrapeResult()

    logger.info("Starting scrape (looking back %d hours to %s)", lookback_hours, since.isoformat())

    # ── YouTube ──────────────────────────────────────────────────────────
    try:
        logger.info("Scraping YouTube (%d channels)...", len(YOUTUBE_CHANNELS))
        yt = YouTubeScraper(channel_ids=YOUTUBE_CHANNELS)
        result.youtube_videos = yt.get_latest_videos(
            since=since, fetch_transcripts=fetch_transcripts
        )
    except Exception as exc:
        logger.error("YouTube scraper failed: %s", exc)

    # ── OpenAI ───────────────────────────────────────────────────────────
    try:
        logger.info("Scraping OpenAI blog...")
        openai = OpenAIScraper()
        result.openai_articles = openai.get_latest_articles(since=since)
    except Exception as exc:
        logger.error("OpenAI scraper failed: %s", exc)

    # ── Anthropic ────────────────────────────────────────────────────────
    try:
        logger.info("Scraping Anthropic blog...")
        anthropic = AnthropicScraper()
        result.anthropic_articles = anthropic.get_latest_articles(since=since)
    except Exception as exc:
        logger.error("Anthropic scraper failed: %s", exc)

    logger.info(result.summary())
    return result


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(name)s | %(message)s",
    )
    result = run_scrapers()
    print("\n" + result.summary())

    if result.youtube_videos:
        print("\n-- YouTube Videos --")
        for v in result.youtube_videos:
            print(f"  [{v.published_at.strftime('%Y-%m-%d')}] {v.title}")

    if result.openai_articles:
        print("\n-- OpenAI Articles --")
        for a in result.openai_articles:
            print(f"  [{a.published_at.strftime('%Y-%m-%d')}] {a.title}")

    if result.anthropic_articles:
        print("\n-- Anthropic Articles --")
        for a in result.anthropic_articles:
            print(f"  [{a.published_at.strftime('%Y-%m-%d')}] [{a.feed_source}] {a.title}")
