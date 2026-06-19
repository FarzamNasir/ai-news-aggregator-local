"""
Scraper Runner

Orchestrates all scrapers (YouTube, OpenAI, Anthropic, HuggingFace,
Meta AI, arXiv), collects recent content, and persists it to the database.
"""

import os
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

from app.config import YOUTUBE_CHANNELS, LOOKBACK_HOURS, ARXIV_MAX_RESULTS
from app.scrapers.youtube import YouTubeScraper, VideoInfo
from app.scrapers.openai_blog import OpenAIScraper, ArticleInfo
from app.scrapers.anthropic_blog import AnthropicScraper, AnthropicArticle
from app.scrapers.huggingface_blog import HuggingFaceScraper, HuggingFaceArticle
from app.scrapers.meta_ai_blog import MetaAIScraper, MetaAIArticle
from app.scrapers.arxiv_scraper import ArXivScraper, ArXivPaper
from app.database.connection import get_session, engine
from app.database.models import Base, Digest, Subscriber, DigestSend
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
    huggingface_articles: list[HuggingFaceArticle] = field(default_factory=list)
    meta_ai_articles: list[MetaAIArticle] = field(default_factory=list)
    arxiv_papers: list[ArXivPaper] = field(default_factory=list)
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # DB insert counts
    youtube_inserted: int = 0
    openai_inserted: int = 0
    anthropic_inserted: int = 0
    huggingface_inserted: int = 0
    meta_ai_inserted: int = 0
    arxiv_inserted: int = 0
    digests_created: int = 0

    @property
    def total_items(self) -> int:
        return (
            len(self.youtube_videos)
            + len(self.openai_articles)
            + len(self.anthropic_articles)
            + len(self.huggingface_articles)
            + len(self.meta_ai_articles)
            + len(self.arxiv_papers)
        )

    @property
    def total_inserted(self) -> int:
        return (
            self.youtube_inserted
            + self.openai_inserted
            + self.anthropic_inserted
            + self.huggingface_inserted
            + self.meta_ai_inserted
            + self.arxiv_inserted
        )

    def summary(self) -> str:
        lines = [
            f"Scrape completed at {self.scraped_at.strftime('%Y-%m-%d %H:%M UTC')}",
            f"  YouTube videos:        {len(self.youtube_videos)} scraped, {self.youtube_inserted} new",
            f"  OpenAI articles:       {len(self.openai_articles)} scraped, {self.openai_inserted} new",
            f"  Anthropic articles:    {len(self.anthropic_articles)} scraped, {self.anthropic_inserted} new",
            f"  HuggingFace articles:  {len(self.huggingface_articles)} scraped, {self.huggingface_inserted} new",
            f"  Meta AI articles:      {len(self.meta_ai_articles)} scraped, {self.meta_ai_inserted} new",
            f"  arXiv papers:          {len(self.arxiv_papers)} scraped, {self.arxiv_inserted} new",
            f"  Digests created:       {self.digests_created}",
            f"  Total:                 {self.total_items} scraped, {self.total_inserted} new",
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

        # Fetch full article content for better summaries
        for article in result.openai_articles:
            article.content = openai.fetch_article_content(article.url)
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

    # ── HuggingFace ──────────────────────────────────────────────────────
    try:
        logger.info("Scraping Hugging Face blog...")
        hf = HuggingFaceScraper()
        result.huggingface_articles = hf.get_latest_articles(since=since)

        # Fetch full article content for better summaries
        for article in result.huggingface_articles:
            article.content = hf.fetch_article_content(article.url)
    except Exception as exc:
        logger.error("HuggingFace scraper failed: %s", exc)

    # ── Meta AI ──────────────────────────────────────────────────────────
    try:
        logger.info("Scraping Meta AI blog...")
        meta = MetaAIScraper()
        result.meta_ai_articles = meta.get_latest_articles(since=since)

        # Fetch full article content for better summaries
        for article in result.meta_ai_articles:
            article.content = meta.fetch_article_content(article.url)
    except Exception as exc:
        logger.error("Meta AI scraper failed: %s", exc)

    # ── arXiv ────────────────────────────────────────────────────────────
    try:
        logger.info("Scraping arXiv (cs.AI+cs.LG+cs.CL, max %d)...", ARXIV_MAX_RESULTS)
        arxiv = ArXivScraper(max_results=ARXIV_MAX_RESULTS)
        result.arxiv_papers = arxiv.get_latest_articles(since=since)
        # No content fetch needed — abstract is already in article.content
    except Exception as exc:
        logger.error("arXiv scraper failed: %s", exc)

    # ── Persist to database ──────────────────────────────────────────────
    if save_to_db and result.total_items > 0:
        session = None
        try:
            logger.info("Saving %d items to database...", result.total_items)
            session = get_session()
            repo = ArticleRepository(session)

            result.youtube_inserted = repo.save_youtube_videos(result.youtube_videos)
            result.openai_inserted = repo.save_openai_articles(result.openai_articles)
            result.anthropic_inserted = repo.save_anthropic_articles(result.anthropic_articles)
            result.huggingface_inserted = repo.save_huggingface_articles(result.huggingface_articles)
            result.meta_ai_inserted = repo.save_meta_ai_articles(result.meta_ai_articles)
            result.arxiv_inserted = repo.save_arxiv_papers(result.arxiv_papers)
        except Exception as exc:
            logger.error("Database save failed: %s", exc)
        finally:
            if session:
                session.close()

    # ── Generate digests ─────────────────────────────────────────────────
    if save_to_db:
        session = None
        try:
            session = get_session()
            result.digests_created = process_digests(session)
        except Exception as exc:
            logger.error("Digest processing failed: %s", exc)
        finally:
            if session:
                session.close()

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

    if result.huggingface_articles:
        print("\n-- Hugging Face Articles --")
        for a in result.huggingface_articles:
            print(f"  [{a.published_at.strftime('%Y-%m-%d')}] {a.title}")

    if result.meta_ai_articles:
        print("\n-- Meta AI Articles --")
        for a in result.meta_ai_articles:
            print(f"  [{a.published_at.strftime('%Y-%m-%d')}] {a.title}")

    if result.arxiv_papers:
        print("\n-- arXiv Papers --")
        for p in result.arxiv_papers:
            cat = f"[{p.category}] " if p.category else ""
            print(f"  [{p.published_at.strftime('%Y-%m-%d')}] {cat}{p.title}")

    # Step 2: Curate and send per-subscriber
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    session = get_session()
    try:
        from sqlalchemy import select

        # Get all active subscribers
        subscribers = list(
            session.execute(
                select(Subscriber).where(Subscriber.is_active == True)
            ).scalars().all()
        )

        if not subscribers:
            # Fallback: use hardcoded profile if no subscribers exist yet
            from app.user_profile import USER_PROFILE, USER_NAME
            logger.info("No subscribers found. Using hardcoded profile for %s.", USER_NAME)
            subscribers_data = [
                {
                    "name": USER_NAME,
                    "email": os.getenv("RECIPIENT_EMAIL"),
                    "profile": USER_PROFILE,
                    "manage_token": None,
                }
            ]
        else:
            subscribers_data = [
                {
                    "name": sub.name,
                    "email": sub.email,
                    "profile": sub.build_profile_text(),
                    "manage_token": sub.manage_token,
                    "id": str(sub.id),
                }
                for sub in subscribers
            ]

        logger.info("Processing %d subscriber(s)...", len(subscribers_data))

        for sub_data in subscribers_data:
            sub_name = sub_data["name"]
            sub_email = sub_data["email"]
            sub_profile = sub_data["profile"]
            manage_token = sub_data.get("manage_token")

            if not sub_email:
                logger.warning("Skipping subscriber '%s' — no email.", sub_name)
                continue

            print(f"\n-- Curating for {sub_name} ({sub_email}) --")

            # Curate digests for this subscriber's profile
            ranked = curate_digests(
                session, user_profile=sub_profile, lookback_hours=lookback_hours
            )

            if not ranked:
                print(f"  No relevant articles for {sub_name}.")
                continue

            for i, item in enumerate(ranked[:5], 1):
                print(f"  {i}. [{item['score']}/10] {item['title']}")

            # Compose personalized email
            email_agent = EmailAgent(user_name=sub_name)
            email = email_agent.compose(ranked)

            if not email:
                logger.warning("Email composition failed for %s.", sub_name)
                continue

            # Build manage URL
            manage_url = f"{base_url}/manage/{manage_token}" if manage_token else ""

            # Send
            sent = send_email(
                email,
                recipient_email=sub_email,
                manage_url=manage_url,
            )

            if sent:
                print(f"  ✅ Email sent to {sub_email}")

                # Record sends in digest_sends table (if subscriber is in DB)
                sub_id = sub_data.get("id")
                if sub_id:
                    for item in email.items:
                        digest_id = item.get("digest_id")
                        if digest_id:
                            send_record = DigestSend(
                                subscriber_id=sub_id,
                                digest_id=digest_id,
                            )
                            session.merge(send_record)
                    session.commit()
                    logger.info("Recorded %d digest sends for %s.", len(email.items), sub_name)
            else:
                print(f"  ❌ Email failed for {sub_email}. Check SMTP config.")

    except Exception as exc:
        logger.error("Subscriber pipeline failed: %s", exc)
    finally:
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


