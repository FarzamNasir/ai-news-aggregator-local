"""
SQLAlchemy database models.

A single `articles` table stores all content types (YouTube videos,
OpenAI blog posts, Anthropic blog posts) distinguished by `source_type`.

A `digests` table stores LLM-generated summaries linked to articles.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, String, Text, DateTime, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship
import enum


class Base(DeclarativeBase):
    pass


class SourceType(str, enum.Enum):
    YOUTUBE = "youtube"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class Article(Base):
    """
    Unified table for all scraped content.

    - YouTube videos  → source_type='youtube', content=transcript
    - OpenAI posts    → source_type='openai',  content=article body
    - Anthropic posts → source_type='anthropic', content=article body
    """

    __tablename__ = "articles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_type = Column(SAEnum(SourceType), nullable=False, index=True)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False, unique=True)
    content = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=True)
    channel_name = Column(String, nullable=True)       # YouTube only
    channel_id = Column(String, nullable=True)          # YouTube only
    feed_source = Column(String, nullable=True)         # Anthropic only (news/engineering/research)
    published_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    digest = relationship("Digest", back_populates="article", uselist=False)

    def __repr__(self) -> str:
        return f"<Article({self.source_type}: {self.title[:50]})>"


class Digest(Base):
    """
    LLM-generated summary for an article.

    One digest per article (1:1 relationship).
    """

    __tablename__ = "digests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    article_id = Column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    url = Column(String, nullable=False)           # copied from article for convenience
    title = Column(String, nullable=False)         # LLM-generated title
    summary = Column(Text, nullable=False)         # 2-3 sentence LLM summary
    sent_at = Column(DateTime(timezone=True), nullable=True)  # NULL = unsent
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    article = relationship("Article", back_populates="digest")

    def __repr__(self) -> str:
        return f"<Digest({self.title[:50]})>"
