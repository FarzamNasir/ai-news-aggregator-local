"""
Quick test script for the YouTube scraper service.

Usage:
    python test_youtube.py

Tests with the "Two Minute Papers" channel (well-known, reliable feed).
"""

import sys
import os
from datetime import datetime, timedelta, timezone

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(__file__))

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")

from app.scrapers.youtube import (
    fetch_channel_feed,
    filter_videos_by_date,
    fetch_transcript,
    get_latest_videos,
)


# ── Test channels ────────────────────────────────────────────────────────────
# Two Minute Papers
TEST_CHANNEL_ID = "UCbfYPyITQ-7l4upoX8nvctg"


def main():
    print("=" * 60)
    print("  YouTube Scraper -- Integration Test")
    print("=" * 60)

    # 1) Fetch feed
    print("\n>> Fetching RSS feed...")
    result = fetch_channel_feed(TEST_CHANNEL_ID)

    if result.error:
        print(f"  [FAIL] Error: {result.error}")
        return

    print(f"  [OK] Channel: {result.channel_name}")
    print(f"  [OK] Total videos in feed: {len(result.videos)}")

    # 2) Show all videos in the feed
    print("\n>> All videos in feed:")
    for v in result.videos:
        print(f"    - [{v.published_at.strftime('%Y-%m-%d')}] {v.title}")
        print(f"      {v.url}")

    # 3) Filter by last 30 days (to ensure we get some results for the test)
    since = datetime.now(timezone.utc) - timedelta(days=30)
    recent = filter_videos_by_date(result.videos, since)
    print(f"\n>> Videos from last 30 days: {len(recent)}")
    for v in recent:
        print(f"    - [{v.published_at.strftime('%Y-%m-%d')}] {v.title}")

    # 4) Test transcript fetching on the most recent video
    if recent:
        test_video = recent[0]
        print(f"\n>> Fetching transcript for: {test_video.title} ({test_video.video_id})")
        transcript = fetch_transcript(test_video.video_id)
        if transcript:
            preview = transcript[:300] + "..." if len(transcript) > 300 else transcript
            print(f"  [OK] Transcript length: {len(transcript)} chars")
            print(f"  [OK] Preview: {preview}")
        else:
            print("  [SKIP] No transcript available (this is normal for some videos)")

    # 5) Test the full orchestrator
    print(f"\n>> Testing get_latest_videos() orchestrator (last 7 days, no transcripts)...")
    since_7d = datetime.now(timezone.utc) - timedelta(days=7)
    videos = get_latest_videos(
        channel_ids=[TEST_CHANNEL_ID],
        since=since_7d,
        fetch_transcripts=False,  # skip transcripts for speed
    )
    print(f"  [OK] Found {len(videos)} videos from last 7 days")
    for v in videos:
        print(f"    - [{v.published_at.strftime('%Y-%m-%d %H:%M')}] {v.title}")

    print("\n" + "=" * 60)
    print("  All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
