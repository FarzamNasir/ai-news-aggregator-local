"""
CRUD repository for the articles table.

Provides a simple interface to insert and query articles,
with built-in deduplication on URL.
"""

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database.models import Article, SourceType

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

    # ── Generic Save ─────────────────────────────────────────────────────

    def _save_items(
        self,
        items: list,
        source_type: SourceType,
        field_mapper: callable,
        label: str,
    ) -> int:
        """
        Generic insert method for any source type.

        Args:
            items:        List of Pydantic models (VideoInfo, ArticleInfo, etc.)
            source_type:  SourceType enum value
            field_mapper: Callable that takes an item and returns a dict of
                          Article column values (excluding source_type)
            label:        Human-readable label for logging

        Returns:
            Count of newly inserted rows.
        """
        count = 0
        for item in items:
            if self._url_exists(item.url):
                logger.debug("Skipping duplicate: %s", item.url)
                continue

            fields = field_mapper(item)
            article = Article(source_type=source_type, **fields)
            self.session.add(article)
            count += 1

        self.session.commit()
        logger.info("Inserted %d new %s (of %d)", count, label, len(items))
        return count

    # ── Source-Specific Wrappers ─────────────────────────────────────────

    def save_youtube_videos(self, videos: list) -> int:
        """Insert YouTube videos. Returns count of newly inserted rows."""
        return self._save_items(
            items=videos,
            source_type=SourceType.YOUTUBE,
            label="YouTube videos",
            field_mapper=lambda v: {
                "title": v.title,
                "url": v.url,
                "content": v.transcript.text if v.transcript else None,
                "channel_name": v.channel_name,
                "channel_id": v.channel_id,
                "published_at": v.published_at,
            },
        )

    def save_openai_articles(self, articles: list) -> int:
        """Insert OpenAI articles. Returns count of newly inserted rows."""
        return self._save_items(
            items=articles,
            source_type=SourceType.OPENAI,
            label="OpenAI articles",
            field_mapper=lambda a: {
                "title": a.title,
                "url": a.url,
                "content": a.content,
                "description": a.description,
                "category": getattr(a, "category", None),
                "published_at": a.published_at,
            },
        )

    def save_anthropic_articles(self, articles: list) -> int:
        """Insert Anthropic articles. Returns count of newly inserted rows."""
        return self._save_items(
            items=articles,
            source_type=SourceType.ANTHROPIC,
            label="Anthropic articles",
            field_mapper=lambda a: {
                "title": a.title,
                "url": a.url,
                "content": a.content,
                "description": a.description,
                "category": getattr(a, "category", None),
                "feed_source": a.feed_source,
                "published_at": a.published_at,
            },
        )

    def save_huggingface_articles(self, articles: list) -> int:
        """Insert Hugging Face blog articles. Returns count of newly inserted rows."""
        return self._save_items(
            items=articles,
            source_type=SourceType.HUGGINGFACE,
            label="HuggingFace articles",
            field_mapper=lambda a: {
                "title": a.title,
                "url": a.url,
                "content": a.content,
                "description": a.description,
                "published_at": a.published_at,
            },
        )

    def save_meta_ai_articles(self, articles: list) -> int:
        """Insert Meta AI blog articles. Returns count of newly inserted rows."""
        return self._save_items(
            items=articles,
            source_type=SourceType.META_AI,
            label="Meta AI articles",
            field_mapper=lambda a: {
                "title": a.title,
                "url": a.url,
                "content": a.content,
                "description": a.description,
                "published_at": a.published_at,
            },
        )

    def save_arxiv_papers(self, papers: list) -> int:
        """Insert arXiv papers. Returns count of newly inserted rows."""
        return self._save_items(
            items=papers,
            source_type=SourceType.ARXIV,
            label="arXiv papers",
            field_mapper=lambda p: {
                "title": p.title,
                "url": p.url,
                "content": p.content,    # abstract text
                "description": p.description,
                "category": p.category,
                "published_at": p.published_at,
            },
        )

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
        stmt = select(func.count()).select_from(Article)
        return self.session.execute(stmt).scalar() or 0

    # ── Helpers ──────────────────────────────────────────────────────────

    def _url_exists(self, url: str) -> bool:
        """Check if an article with this URL already exists."""
        stmt = select(Article.id).where(Article.url == url)
        return self.session.execute(stmt).first() is not None
