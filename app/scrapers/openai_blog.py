"""
OpenAI Blog RSS Scraper

Fetches and parses the OpenAI News RSS feed, returning
a list of articles filtered by date.

Feed URL: https://openai.com/news/rss.xml
"""

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

import httpx
import html2text
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

OPENAI_RSS_URL = "https://openai.com/news/rss.xml"


class ArticleInfo(BaseModel):
    """A single article from the OpenAI blog RSS feed."""

    title: str
    url: str
    category: str | None = None
    description: str | None = None
    published_at: datetime
    content: str | None = None


class OpenAIScraper:
    """
    Scrapes the OpenAI News RSS feed for recent articles.

    Usage:
        scraper = OpenAIScraper()
        articles = scraper.get_latest_articles(since=datetime(...))
    """

    def __init__(self, feed_url: str = OPENAI_RSS_URL):
        self.feed_url = feed_url
        self._http_client = httpx.Client(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"},
        )
        self._html2text = html2text.HTML2Text()
        self._html2text.ignore_links = False
        self._html2text.ignore_images = True
        self._html2text.body_width = 0  # no wrapping

    def get_latest_articles(self, since: datetime) -> list[ArticleInfo]:
        """
        Fetch articles published after *since*.

        Args:
            since: Timezone-aware datetime cutoff (articles after this are kept).

        Returns:
            List of ArticleInfo, sorted newest-first.
        """
        articles = self._fetch_feed()

        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)

        filtered = [a for a in articles if a.published_at >= since]
        filtered.sort(key=lambda a: a.published_at, reverse=True)

        logger.info(
            "OpenAI feed: %d articles since %s (of %d total)",
            len(filtered),
            since.isoformat(),
            len(articles),
        )
        return filtered

    def _fetch_feed(self) -> list[ArticleInfo]:
        """Fetch and parse the full RSS feed."""
        resp = self._http_client.get(self.feed_url)
        resp.raise_for_status()

        root = ET.fromstring(resp.text)
        articles: list[ArticleInfo] = []

        for item in root.findall(".//item"):
            article = self._parse_item(item)
            if article:
                articles.append(article)

        return articles

    @staticmethod
    def _parse_item(item: ET.Element) -> ArticleInfo | None:
        """Parse a single <item> into an ArticleInfo."""
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        pub_date_str = item.findtext("pubDate", "").strip()

        if not title or not link or not pub_date_str:
            return None

        published_at = parsedate_to_datetime(pub_date_str)

        return ArticleInfo(
            title=title,
            url=link,
            category=item.findtext("category", "").strip() or None,
            description=item.findtext("description", "").strip() or None,
            published_at=published_at,
        )

    def fetch_article_content(self, url: str) -> str | None:
        """
        Fetch an article's page and convert it to Markdown.

        Args:
            url: The full URL of the article.

        Returns:
            Markdown string of the article content, or None on failure.
        """
        try:
            resp = self._http_client.get(url)
            resp.raise_for_status()
            markdown = self._html2text.handle(resp.text).strip()
            logger.info("Fetched content for %s (%d chars)", url, len(markdown))
            return markdown
        except Exception as exc:
            logger.warning("Could not fetch content for %s: %s", url, exc)
            return None
