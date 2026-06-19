"""
Curation Service

Pulls recent unsent digests from the database, runs the Curator agent to
score and rank them, and returns the ranked results.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.models import Digest, Article
from app.agent.curator import Curator, ScoredItem

logger = logging.getLogger(__name__)


def curate_digests(
    session: Session,
    user_profile: str,
    lookback_hours: int = 24,
) -> list[dict]:
    """
    Score and rank recent unsent digests by user relevance.

    Args:
        session:        Active SQLAlchemy session.
        user_profile:   Text describing the user's interests and background.
        lookback_hours: How far back to look for articles (by publish date).

    Returns:
        List of dicts with digest info + score + reason, sorted by score desc.
        Only includes digests that haven't been sent yet.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    # Filter by article PUBLISH date + exclude already-sent digests
    stmt = (
        select(Digest)
        .join(Article, Digest.article_id == Article.id)
        .where(Article.published_at >= since)
        .where(Digest.sent_at.is_(None))  # only unsent digests
        .order_by(Article.published_at.desc())
    )
    digests = list(session.execute(stmt).scalars().all())

    if not digests:
        logger.info("No unsent digests found in the last %d hours.", lookback_hours)
        return []

    logger.info("Found %d unsent digests to curate.", len(digests))

    # Build input for the curator
    digest_items = [
        {
            "id": str(d.id),
            "title": d.title,
            "summary": d.summary,
        }
        for d in digests
    ]

    # Score and rank using the user's profile
    curator = Curator()
    scored_items = curator.rank_digests(digest_items, user_profile=user_profile)

    # Merge scores back with full digest info
    digest_lookup = {str(d.id): d for d in digests}
    ranked_results = []

    for item in scored_items:
        digest = digest_lookup.get(item.id)
        if digest:
            ranked_results.append({
                "digest_id": str(digest.id),
                "title": digest.title,
                "summary": digest.summary,
                "url": digest.url,
                "score": item.score,
                "reason": item.reason,
            })

    return ranked_results
