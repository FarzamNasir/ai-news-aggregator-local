"""
Scraper Runner

Orchestrates all scrapers (YouTube, OpenAI, Anthropic), collects
recent content, and persists it to the database.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

from app.config import YOUTUBE_CHANNELS, LOOKBACK_HOURS
from app.scrapers.youtube import YouTubeScraper, VideoInfo
from app.scrapers.openai_blog import OpenAIScraper, ArticleInfo
from app.scrapers.anthropic_blog import AnthropicScraper, AnthropicArticle
from app.database.connection import get_session, engine
from app.database.models import Base
from app.database.repository import ArticleRepository
from app.agent.digest_service import process_digests
from app.agent.curation_service import curate_digests
from app.agent.email_agent import EmailAgent
from app.agent.email_sender import send_email

logger = logging.getLogger(__name__)


@dataclass
class ScrapeResult:
    """Combined result from all scrapers."""

    youtube_videos: list[VideoInfo] = field(default_factory=list)
    openai_articles: list[ArticleInfo] = field(default_factory=list)
    anthropic_articles: list[AnthropicArticle] = field(default_factory=list)
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # DB insert counts
    youtube_inserted: int = 0
    openai_inserted: int = 0
    anthropic_inserted: int = 0
    digests_created: int = 0

    @property
    def total_items(self) -> int:
        return len(self.youtube_videos) + len(self.openai_articles) + len(self.anthropic_articles)

    @property
    def total_inserted(self) -> int:
        return self.youtube_inserted + self.openai_inserted + self.anthropic_inserted

    def summary(self) -> str:
        lines = [
            f"Scrape completed at {self.scraped_at.strftime('%Y-%m-%d %H:%M UTC')}",
            f"  YouTube videos:     {len(self.youtube_videos)} scraped, {self.youtube_inserted} new",
            f"  OpenAI articles:    {len(self.openai_articles)} scraped, {self.openai_inserted} new",
            f"  Anthropic articles: {len(self.anthropic_articles)} scraped, {self.anthropic_inserted} new",
            f"  Digests created:    {self.digests_created}",
            f"  Total:              {self.total_items} scraped, {self.total_inserted} new",
        ]
        return "\n".join(lines)


def run_scrapers(
    lookback_hours: int = LOOKBACK_HOURS,
    fetch_transcripts: bool = True,
    save_to_db: bool = True,
) -> ScrapeResult:
    """
    Run all scrapers, optionally persist results to the database.

    Args:
        lookback_hours:  How many hours back to search for new content.
        fetch_transcripts: Whether to fetch YouTube video transcripts.
        save_to_db:      Whether to save scraped items to the database.

    Returns:
        ScrapeResult with content from all sources.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    result = ScrapeResult()

    logger.info("Starting scrape (looking back %d hours to %s)", lookback_hours, since.isoformat())

    # ── YouTube ──────────────────────────────────────────────────────────
    try:
        logger.info("Scraping YouTube (%d channels)...", len(YOUTUBE_CHANNELS))
        yt = YouTubeScraper(channel_ids=YOUTUBE_CHANNELS)
        result.youtube_videos = yt.get_latest_videos(
            since=since, fetch_transcripts=fetch_transcripts
        )
    except Exception as exc:
        logger.error("YouTube scraper failed: %s", exc)

    # ── OpenAI ───────────────────────────────────────────────────────────
    try:
        logger.info("Scraping OpenAI blog...")
        openai = OpenAIScraper()
        result.openai_articles = openai.get_latest_articles(since=since)
    except Exception as exc:
        logger.error("OpenAI scraper failed: %s", exc)

    # ── Anthropic ────────────────────────────────────────────────────────
    try:
        logger.info("Scraping Anthropic blog...")
        anthropic = AnthropicScraper()
        result.anthropic_articles = anthropic.get_latest_articles(since=since)

        # Fetch full article content
        for article in result.anthropic_articles:
            article.content = anthropic.fetch_article_content(article.url)
    except Exception as exc:
        logger.error("Anthropic scraper failed: %s", exc)

    # ── Persist to database ──────────────────────────────────────────────
    if save_to_db and result.total_items > 0:
        try:
            logger.info("Saving %d items to database...", result.total_items)
            session = get_session()
            repo = ArticleRepository(session)

            result.youtube_inserted = repo.save_youtube_videos(result.youtube_videos)
            result.openai_inserted = repo.save_openai_articles(result.openai_articles)
            result.anthropic_inserted = repo.save_anthropic_articles(result.anthropic_articles)

            session.close()
        except Exception as exc:
            logger.error("Database save failed: %s", exc)

    # ── Generate digests ─────────────────────────────────────────────────
    if save_to_db:
        try:
            session = get_session()
            result.digests_created = process_digests(session)
            session.close()
        except Exception as exc:
            logger.error("Digest processing failed: %s", exc)

    logger.info(result.summary())
    return result


def run_full_pipeline(lookback_hours: int = LOOKBACK_HOURS):
    """
    Run the complete pipeline: scrape → digest → curate → email.
    """
    print(f"\n{'=' * 60}")
    print(f"  Pipeline started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Lookback: {lookback_hours} hours")
    print(f"{'=' * 60}\n")

    # Ensure tables exist (idempotent — safe to call every run)
    Base.metadata.create_all(engine)

    # Step 1: Scrape + save + generate digests
    result = run_scrapers(lookback_hours=lookback_hours)
    print("\n" + result.summary())

    if result.youtube_videos:
        print("\n-- YouTube Videos --")
        for v in result.youtube_videos:
            print(f"  [{v.published_at.strftime('%Y-%m-%d')}] {v.title}")

    if result.openai_articles:
        print("\n-- OpenAI Articles --")
        for a in result.openai_articles:
            print(f"  [{a.published_at.strftime('%Y-%m-%d')}] {a.title}")

    if result.anthropic_articles:
        print("\n-- Anthropic Articles --")
        for a in result.anthropic_articles:
            print(f"  [{a.published_at.strftime('%Y-%m-%d')}] [{a.feed_source}] {a.title}")

    # Step 2: Curate and rank
    print("\n-- Curated Digest (ranked by relevance) --")
    session = get_session()
    ranked = curate_digests(session, lookback_hours=lookback_hours)

    for i, item in enumerate(ranked, 1):
        print(f"\n  {i}. [{item['score']}/10] {item['title']}")
        print(f"     {item['summary']}")
        print(f"     Reason: {item['reason']}")
        print(f"     {item['url']}")

    # Step 3: Compose and send email
    if ranked:
        email_agent = EmailAgent()
        email = email_agent.compose(ranked)

        if email:
            print("\n" + "=" * 60)
            print(f"  SUBJECT: {email.subject}")
            print("=" * 60)
            print(f"\n  {email.greeting}")
            print(f"  {email.intro}")
            print(f"\n  {'_' * 56}")
            for i, item in enumerate(email.items, 1):
                print(f"\n  {i}. {item['title']}")
                print(f"     {item['summary']}")
                print(f"     {item['url']}")
            print("\n" + "=" * 60)

            sent = send_email(email)
            if sent:
                print("\n  \u2705 Email sent successfully!")

                # Step 4: Mark sent digests so they aren't re-sent
                sent_ids = [item["digest_id"] for item in email.items if "digest_id" in item]
                if sent_ids:
                    from app.database.models import Digest
                    now = datetime.now(timezone.utc)
                    session.query(Digest).filter(
                        Digest.id.in_(sent_ids)
                    ).update({"sent_at": now}, synchronize_session="fetch")
                    session.commit()
                    logger.info("Marked %d digests as sent.", len(sent_ids))
            else:
                print("\n  \u274c Email sending failed. Check SMTP config in .env")

    session.close()
    print(f"\n  Pipeline finished at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    import sys
    import time

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(name)s | %(message)s",
    )

    # --reset: drop all tables and recreate from scratch
    if "--reset" in sys.argv:
        print("\n⚠️  Resetting database — dropping all tables...")
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        print("✅ Tables recreated from scratch.\n")

    if "--schedule" in sys.argv:
        INTERVAL_HOURS = 24
        print(f"Scheduler started. Will run every {INTERVAL_HOURS} hours.")
        print("Press Ctrl+C to stop.\n")

        while True:
            try:
                run_full_pipeline()
                next_run = datetime.now() + timedelta(hours=INTERVAL_HOURS)
                print(f"\n  Next run at: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  Sleeping for {INTERVAL_HOURS} hours...\n")
                time.sleep(INTERVAL_HOURS * 3600)
            except KeyboardInterrupt:
                print("\n\nScheduler stopped.")
                break
    else:
        run_full_pipeline()


