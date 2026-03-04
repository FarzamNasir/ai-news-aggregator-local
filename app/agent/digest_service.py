"""
Digest Processing Service

Reads articles from the database that don't have a digest yet,
runs the LLM summarizer on each, and saves the results.
"""

import logging

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.models import Article, Digest
from app.agent.summarizer import Summarizer

logger = logging.getLogger(__name__)


def process_digests(session: Session) -> int:
    """
    Generate digests for all articles that don't have one yet.

    Args:
        session: Active SQLAlchemy session.

    Returns:
        Number of new digests created.
    """
    # Find articles without a digest
    stmt = (
        select(Article)
        .outerjoin(Digest, Article.id == Digest.article_id)
        .where(Digest.id.is_(None))
        .order_by(Article.published_at.desc())
    )
    articles = list(session.execute(stmt).scalars().all())

    if not articles:
        logger.info("No articles need digests — all up to date.")
        return 0

    logger.info("Processing %d articles without digests...", len(articles))

    summarizer = Summarizer()
    created = 0

    for article in articles:
        result = summarizer.summarize(
            title=article.title,
            content=article.content,
            description=article.description,
            source_type=article.source_type.value,
        )

        if result is None:
            continue

        digest = Digest(
            article_id=article.id,
            url=article.url,
            title=result.title,
            summary=result.summary,
        )
        session.add(digest)
        created += 1

    session.commit()
    logger.info("Created %d new digests (of %d articles processed).", created, len(articles))
    return created
