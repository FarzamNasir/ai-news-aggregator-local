"""
Hugging Face Blog RSS Scraper

Fetches and parses the Hugging Face blog RSS feed, returning
a list of articles filtered by date.
"""

import xml.etree.ElementTree as ET
from datetime import datetime

from pydantic import BaseModel

from app.scrapers.base import RSSScraperBase

HUGGINGFACE_RSS_URL = "https://huggingface.co/blog/feed.xml"


class HuggingFaceArticle(BaseModel):
    """A single article from the Hugging Face blog RSS feed."""

    title: str
    url: str
    description: str | None = None
    published_at: datetime
    content: str | None = None


class HuggingFaceScraper(RSSScraperBase):
    """
    Scrapes the Hugging Face blog RSS feed for recent articles.

    Usage:
        scraper = HuggingFaceScraper()
        articles = scraper.get_latest_articles(since=datetime(...))
    """

    @property
    def feed_urls(self) -> list[str]:
        return [HUGGINGFACE_RSS_URL]

    @property
    def source_name(self) -> str:
        return "HuggingFace"

    def _parse_item(self, item: ET.Element, **kwargs) -> HuggingFaceArticle | None:
        """Parse a single <item> into a HuggingFaceArticle."""
        title = item.findtext("title", "").strip()
        pub_date_str = item.findtext("pubDate", "").strip()

        # HuggingFace feed uses <link> but may also have <guid>
        link = item.findtext("link", "").strip()
        if not link:
            # Fall back to guid if link is missing
            guid = item.find("guid")
            if guid is not None and guid.get("isPermaLink", "false").lower() == "true":
                link = (guid.text or "").strip()

        if not title or not link or not pub_date_str:
            return None

        return HuggingFaceArticle(
            title=title,
            url=link,
            description=item.findtext("description", "").strip() or None,
            published_at=self.parse_rss_date(pub_date_str),
        )
