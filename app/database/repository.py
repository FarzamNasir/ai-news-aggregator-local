"""
CRUD repository for the articles table.

Provides a simple interface to insert and query articles,
with built-in deduplication on URL.
"""

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.models import Article, SourceType
from app.scrapers.youtube import VideoInfo
from app.scrapers.openai_blog import ArticleInfo
from app.scrapers.anthropic_blog import AnthropicArticle

logger = logging.getLogger(__name__)


class ArticleRepository:
    """
    Repository for inserting and querying articles.

    Usage:
        from app.database.connection import get_session
        session = get_session()
        repo = ArticleRepository(session)
        repo.save_youtube_videos(videos)
    """

    def __init__(self, session: Session):
        self.session = session

    # ── Insert Methods ───────────────────────────────────────────────────

    def save_youtube_videos(self, videos: list[VideoInfo]) -> int:
        """Insert YouTube videos. Returns count of newly inserted rows."""
        count = 0
        for video in videos:
            if self._url_exists(video.url):
                logger.debug("Skipping duplicate: %s", video.url)
                continue

            article = Article(
                source_type=SourceType.YOUTUBE,
                title=video.title,
                url=video.url,
                content=video.transcript.text if video.transcript else None,
                channel_name=video.channel_name,
                channel_id=video.channel_id,
                published_at=video.published_at,
            )
            self.session.add(article)
            count += 1

        self.session.commit()
        logger.info("Inserted %d new YouTube videos (of %d)", count, len(videos))
        return count

    def save_openai_articles(self, articles: list[ArticleInfo]) -> int:
        """Insert OpenAI articles. Returns count of newly inserted rows."""
        count = 0
        for art in articles:
            if self._url_exists(art.url):
                logger.debug("Skipping duplicate: %s", art.url)
                continue

            article = Article(
                source_type=SourceType.OPENAI,
                title=art.title,
                url=art.url,
                content=art.content,
                description=art.description,
                category=art.category,
                published_at=art.published_at,
            )
            self.session.add(article)
            count += 1

        self.session.commit()
        logger.info("Inserted %d new OpenAI articles (of %d)", count, len(articles))
        return count

    def save_anthropic_articles(self, articles: list[AnthropicArticle]) -> int:
        """Insert Anthropic articles. Returns count of newly inserted rows."""
        count = 0
        for art in articles:
            if self._url_exists(art.url):
                logger.debug("Skipping duplicate: %s", art.url)
                continue

            article = Article(
                source_type=SourceType.ANTHROPIC,
                title=art.title,
                url=art.url,
                content=art.content,
                description=art.description,
                category=art.category,
                feed_source=art.feed_source,
                published_at=art.published_at,
            )
            self.session.add(article)
            count += 1

        self.session.commit()
        logger.info("Inserted %d new Anthropic articles (of %d)", count, len(articles))
        return count

    # ── Query Methods ────────────────────────────────────────────────────

    def get_articles_since(
        self,
        since: datetime,
        source_type: SourceType | None = None,
    ) -> list[Article]:
        """
        Get articles published after *since*, optionally filtered by source.

        Returns:
            List of Article rows, sorted newest-first.
        """
        stmt = select(Article).where(Article.published_at >= since)

        if source_type:
            stmt = stmt.where(Article.source_type == source_type)

        stmt = stmt.order_by(Article.published_at.desc())
        return list(self.session.execute(stmt).scalars().all())

    def get_all_articles(self) -> list[Article]:
        """Get all articles, sorted newest-first."""
        stmt = select(Article).order_by(Article.published_at.desc())
        return list(self.session.execute(stmt).scalars().all())

    def count_articles(self) -> int:
        """Return total number of articles in the database."""
        from sqlalchemy import func
        stmt = select(func.count()).select_from(Article)
        return self.session.execute(stmt).scalar() or 0

    # ── Helpers ──────────────────────────────────────────────────────────

    def _url_exists(self, url: str) -> bool:
        """Check if an article with this URL already exists."""
        stmt = select(Article.id).where(Article.url == url)
        return self.session.execute(stmt).first() is not None
