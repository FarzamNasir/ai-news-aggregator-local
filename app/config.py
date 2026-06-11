"""
Configuration for the AI News Aggregator.

YouTube channels, environment settings, and scraper config.
"""

import os

# ── Environment ──────────────────────────────────────────────────────────────

ENVIRONMENT = os.getenv("ENVIRONMENT", "local")  # "local" or "production"

def is_production() -> bool:
    return ENVIRONMENT == "production"

def is_local() -> bool:
    return ENVIRONMENT == "local"


# ── YouTube Channels to Monitor ──────────────────────────────────────────────
# Add channel IDs here. To find a channel ID:
#   Go to the channel page → "...More" → "Share channel" → "Copy channel ID"

YOUTUBE_CHANNELS = [
    "UCbfYPyITQ-7l4upoX8nvctg",  # Two Minute Papers
    "UCYO_jab_esuFRV4b17AJtAw",  # 3Blue1Brown
    "UCZHItN4EWJ932jYq23y4s_Q",  # Yannic Kilcher
    "UCNJ1Ymd5yFuUPtn21xtRbbw",  # AI Explained
]


# ── Scraper Settings ─────────────────────────────────────────────────────────

# How many hours to look back when fetching new content
LOOKBACK_HOURS = 24

# Maximum arXiv papers to include per pipeline run (prevents volume flood)
# arXiv publishes 300-500+ papers/day across cs.AI + cs.LG + cs.CL
ARXIV_MAX_RESULTS = 10

