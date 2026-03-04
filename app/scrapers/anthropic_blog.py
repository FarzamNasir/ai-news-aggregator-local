"""
Anthropic Blog RSS Scraper

Fetches and parses Anthropic's News, Engineering, and Research RSS feeds,
returning a combined list of articles filtered by date.
"""

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

import httpx
import html2text
from pydantic import BaseModel

logger = logging.getLogger(__name__)

ANTHROPIC_FEEDS = [
    "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml",
    "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_engineering.xml",
    "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_research.xml",
]


class AnthropicArticle(BaseModel):
    """A single article from an Anthropic RSS feed."""

    title: str
    url: str
    category: str | None = None
    description: str | None = None
    published_at: datetime
    feed_source: str  # "news", "engineering", or "research"
    content: str | None = None


class AnthropicScraper:
    """
    Scrapes Anthropic's News, Engineering, and Research RSS feeds.

    Usage:
        scraper = AnthropicScraper()
        articles = scraper.get_latest_articles(since=datetime(...))
    """

    def __init__(self, feed_urls: list[str] | None = None):
        self.feed_urls = feed_urls or ANTHROPIC_FEEDS
        self._http_client = httpx.Client(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"},
        )
        self._html2text = html2text.HTML2Text()
        self._html2text.ignore_links = False
        self._html2text.ignore_images = True
        self._html2text.body_width = 0

    def get_latest_articles(self, since: datetime) -> list[AnthropicArticle]:
        """
        Fetch articles from all feeds published after *since*.

        Returns:
            Combined list of articles from all feeds, sorted newest-first.
        """
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)

        all_articles: list[AnthropicArticle] = []

        for feed_url in self.feed_urls:
            articles = self._fetch_feed(feed_url)
            all_articles.extend(a for a in articles if a.published_at >= since)

        # Deduplicate by URL (in case an article appears in multiple feeds)
        seen: set[str] = set()
        unique: list[AnthropicArticle] = []
        for article in all_articles:
            if article.url not in seen:
                seen.add(article.url)
                unique.append(article)

        unique.sort(key=lambda a: a.published_at, reverse=True)

        logger.info(
            "Anthropic feeds: %d articles since %s",
            len(unique),
            since.isoformat(),
        )
        return unique

    def _fetch_feed(self, feed_url: str) -> list[AnthropicArticle]:
        """Fetch and parse a single RSS feed."""
        try:
            resp = self._http_client.get(feed_url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Error fetching %s: %s", feed_url, exc)
            return []

        root = ET.fromstring(resp.text)

        # Derive feed source name from the feed's <title>
        feed_title = root.findtext(".//channel/title", "").strip().lower()
        if "engineering" in feed_title:
            feed_source = "engineering"
        elif "research" in feed_title:
            feed_source = "research"
        else:
            feed_source = "news"

        articles: list[AnthropicArticle] = []
        for item in root.findall(".//item"):
            article = self._parse_item(item, feed_source)
            if article:
                articles.append(article)

        logger.info("Fetched %d articles from Anthropic %s feed", len(articles), feed_source)
        return articles

    @staticmethod
    def _parse_item(item: ET.Element, feed_source: str) -> AnthropicArticle | None:
        """Parse a single <item> into an AnthropicArticle."""
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        pub_date_str = item.findtext("pubDate", "").strip()

        if not title or not link or not pub_date_str:
            return None

        published_at = parsedate_to_datetime(pub_date_str)

        return AnthropicArticle(
            title=title,
            url=link,
            category=item.findtext("category", "").strip() or None,
            description=item.findtext("description", "").strip() or None,
            published_at=published_at,
            feed_source=feed_source,
        )

    def fetch_article_content(self, url: str) -> str | None:
        """Fetch an article page and convert it to Markdown."""
        try:
            resp = self._http_client.get(url)
            resp.raise_for_status()
            markdown = self._html2text.handle(resp.text).strip()
            logger.info("Fetched content for %s (%d chars)", url, len(markdown))
            return markdown
        except Exception as exc:
            logger.warning("Could not fetch content for %s: %s", url, exc)
            return None
