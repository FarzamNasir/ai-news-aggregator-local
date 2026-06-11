"""
arXiv RSS Scraper

Fetches recent papers from arXiv across cs.AI, cs.LG, and cs.CL categories.
Uses the paper abstract directly as content — no full-text fetch needed.

Volume note: arXiv publishes 300-500+ papers/day across these categories.
A max_results cap (default 10) prevents flooding the digest with academic papers.
"""

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime

from pydantic import BaseModel

from app.scrapers.base import RSSScraperBase

logger = logging.getLogger(__name__)

ARXIV_RSS_URL = "https://rss.arxiv.org/rss/cs.ai+cs.lg+cs.cl"

# Pattern to strip the arXiv metadata prefix from the description field:
# e.g. "arXiv:2406.12345v1 Announce Type: new\nAbstract: ..."
_ARXIV_PREFIX_RE = re.compile(
    r"^arXiv:\S+\s+Announce\s+Type:\s+\w+\s*\n\s*Abstract:\s*",
    re.IGNORECASE,
)


class ArXivPaper(BaseModel):
    """A single paper from the arXiv RSS feed."""

    title: str
    url: str
    description: str | None = None   # Full abstract (used as content)
    published_at: datetime
    category: str | None = None
    content: str | None = None        # Populated from abstract; no HTTP fetch


class ArXivScraper(RSSScraperBase):
    """
    Scrapes arXiv's combined cs.AI + cs.LG + cs.CL RSS feed.

    Key differences from other scrapers:
    - Uses the abstract (from <description>) as content — no HTTP fetch.
    - Caps results at max_results per run (default 10) to prevent volume flood.
    - All papers in the feed share the same pubDate (daily batch), so ordering
      is by feed position (newest arXiv ID first).

    Usage:
        scraper = ArXivScraper(max_results=10)
        papers = scraper.get_latest_articles(since=datetime(...))
    """

    def __init__(self, max_results: int = 10):
        """
        Args:
            max_results: Maximum number of papers to return per run.
                         Prevents flooding the digest with academic papers.
        """
        super().__init__()
        self.max_results = max_results

    @property
    def feed_urls(self) -> list[str]:
        return [ARXIV_RSS_URL]

    @property
    def source_name(self) -> str:
        return "arXiv"

    def get_latest_articles(self, since: datetime) -> list[ArXivPaper]:
        """Override to apply max_results cap after date filtering."""
        articles = super().get_latest_articles(since)
        if len(articles) > self.max_results:
            logger.info(
                "arXiv: capping %d papers to max_results=%d",
                len(articles),
                self.max_results,
            )
            articles = articles[: self.max_results]
        return articles

    def _parse_item(self, item: ET.Element, **kwargs) -> ArXivPaper | None:
        """Parse a single arXiv <item> into an ArXivPaper."""
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        pub_date_str = item.findtext("pubDate", "").strip()
        raw_description = item.findtext("description", "").strip()

        if not title or not link or not pub_date_str:
            return None

        # Strip the arXiv metadata prefix to get clean abstract text
        abstract = _ARXIV_PREFIX_RE.sub("", raw_description).strip()

        # Primary category (first <category> element)
        category_el = item.find("category")
        category = category_el.text.strip() if category_el is not None else None

        return ArXivPaper(
            title=title,
            url=link,
            description=abstract,
            published_at=self.parse_rss_date(pub_date_str),
            category=category,
            content=abstract,  # Use abstract as content — no HTTP fetch needed
        )
