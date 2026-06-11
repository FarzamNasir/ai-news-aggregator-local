"""
Meta AI Blog RSS Scraper

Fetches and parses the Meta AI blog RSS feed via the community-maintained
Olshansk rss-feeds mirror (same provider used by Anthropic feeds).
"""

import xml.etree.ElementTree as ET
from datetime import datetime

from pydantic import BaseModel

from app.scrapers.base import RSSScraperBase

META_AI_RSS_URL = (
    "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_meta_ai.xml"
)


class MetaAIArticle(BaseModel):
    """A single article from the Meta AI blog RSS feed."""

    title: str
    url: str
    description: str | None = None
    published_at: datetime
    content: str | None = None


class MetaAIScraper(RSSScraperBase):
    """
    Scrapes the Meta AI blog RSS feed for recent articles.

    Uses a community-maintained RSS mirror (Olshansk/rss-feeds on GitHub),
    the same provider used for Anthropic feeds.

    Usage:
        scraper = MetaAIScraper()
        articles = scraper.get_latest_articles(since=datetime(...))
    """

    @property
    def feed_urls(self) -> list[str]:
        return [META_AI_RSS_URL]

    @property
    def source_name(self) -> str:
        return "Meta AI"

    def _parse_item(self, item: ET.Element, **kwargs) -> MetaAIArticle | None:
        """Parse a single <item> into a MetaAIArticle."""
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        pub_date_str = item.findtext("pubDate", "").strip()

        if not title or not link or not pub_date_str:
            return None

        return MetaAIArticle(
            title=title,
            url=link,
            description=item.findtext("description", "").strip() or None,
            published_at=self.parse_rss_date(pub_date_str),
        )
