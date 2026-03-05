"""
Curation Service

Pulls recent digests from the database, runs the Curator agent to
score and rank them, and returns the ranked results.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.models import Digest
from app.agent.curator import Curator, ScoredItem

logger = logging.getLogger(__name__)


def curate_digests(
    session: Session,
    lookback_hours: int = 24,
) -> list[dict]:
    """
    Score and rank recent digests by user relevance.

    Args:
        session:        Active SQLAlchemy session.
        lookback_hours: How far back to look for digests.

    Returns:
        List of dicts with digest info + score + reason, sorted by score desc.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    stmt = (
        select(Digest)
        .where(Digest.created_at >= since)
        .order_by(Digest.created_at.desc())
    )
    digests = list(session.execute(stmt).scalars().all())

    if not digests:
        logger.info("No digests found in the last %d hours.", lookback_hours)
        return []

    logger.info("Found %d digests to curate.", len(digests))

    # Build input for the curator
    digest_items = [
        {
            "id": str(d.id),
            "title": d.title,
            "summary": d.summary,
        }
        for d in digests
    ]

    # Score and rank
    curator = Curator()
    scored_items = curator.rank_digests(digest_items)

    # Merge scores back with full digest info
    digest_lookup = {str(d.id): d for d in digests}
    ranked_results = []

    for item in scored_items:
        digest = digest_lookup.get(item.id)
        if digest:
            ranked_results.append({
                "title": digest.title,
                "summary": digest.summary,
                "url": digest.url,
                "score": item.score,
                "reason": item.reason,
            })

    return ranked_results
