"""
Quick read-only inspection of the production database.
Run with: uv run python check_db.py
"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import os
os.environ["DATABASE_URL"] = (
    "postgresql://aggregator:y9UilXdpXU22yex2aVP3gxkE8DjYhPt3"
    "@dpg-d8kn24ldt1ts73a8e8qg-a.frankfurt-postgres.render.com/news_aggregator_i9me"
)

from sqlalchemy import func
from app.database.connection import get_session
from app.database.models import Article, Digest, SourceType

session = get_session()

# ── Counts by source ─────────────────────────────────────────────────────────
print("=" * 65)
print("  ARTICLES BY SOURCE")
print("=" * 65)
counts = (
    session.query(Article.source_type, func.count(Article.id))
    .group_by(Article.source_type)
    .all()
)
if counts:
    for source, count in counts:
        label = source.value if hasattr(source, "value") else str(source)
        print(f"  {label:<20} {count} articles")
else:
    print("  (no articles yet)")

total_articles = session.query(Article).count()
print(f"\n  TOTAL: {total_articles} articles")

# ── Latest 15 articles ───────────────────────────────────────────────────────
print()
print("=" * 65)
print("  ALL ARTICLES (newest first)")
print("=" * 65)
articles = (
    session.query(Article)
    .order_by(Article.published_at.desc())
    .all()
)
for a in articles:
    date_str = a.published_at.strftime("%Y-%m-%d")
    source = a.source_type.value if hasattr(a.source_type, "value") else str(a.source_type)
    title = (a.title[:58] + "..") if len(a.title) > 60 else a.title
    has_content = "[Y] content" if a.content else "[N] no content"
    print(f"  [{source:<10}] {date_str}  {has_content}  {title}")

# ── Digest stats ─────────────────────────────────────────────────────────────
print()
print("=" * 65)
print("  DIGEST STATS")
print("=" * 65)
digest_count = session.query(Digest).count()
sent_count = session.query(Digest).filter(Digest.sent_at.isnot(None)).count()
unsent_count = digest_count - sent_count
print(f"  Total digests : {digest_count}")
print(f"  Sent in email : {sent_count}")
print(f"  Unsent (queue): {unsent_count}")

# ── All digests ───────────────────────────────────────────────────────────────
print()
print("=" * 65)
print("  ALL DIGESTS")
print("=" * 65)
digests = (
    session.query(Digest, Article)
    .join(Article)
    .order_by(Article.published_at.desc())
    .all()
)
if digests:
    for d, a in digests:
        sent = "SENT" if d.sent_at else "unsent"
        source = a.source_type.value if hasattr(a.source_type, "value") else str(a.source_type)
        title = (d.title[:55] + "..") if len(d.title) > 57 else d.title
        summary_preview = (d.summary[:80] + "...") if d.summary and len(d.summary) > 80 else (d.summary or "")
        print(f"  [{sent}] [{source}] {title}")
        print(f"    {summary_preview}")
        print()
else:
    print("  (no digests yet)")

session.close()
print("=" * 65)
