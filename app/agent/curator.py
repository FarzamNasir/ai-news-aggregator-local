"""
Curator Agent

Takes recent digest entries and ranks them by relevance to a user's
profile and interests using the configured LLM with structured output.

Named after a news editor/curator who decides which stories matter most.
"""

import logging

from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from app.agent.llm_client import get_llm_client, chat_completion

logger = logging.getLogger(__name__)


def _is_retryable(exc: Exception) -> bool:
    """Check if an exception is worth retrying (API/network errors)."""
    exc_type = type(exc).__name__
    return exc_type in (
        "APIError", "APIConnectionError", "RateLimitError",
        "InternalServerError", "APIStatusError",
    )


_llm_retry = retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)

SYSTEM_PROMPT = """\
You are an AI news curator. Your job is to score a list of AI news digest items \
based on how relevant and interesting they are to a specific reader.

You will receive:
1. A USER PROFILE describing the reader's background and interests.
2. A list of DIGEST ITEMS, each with an id, title, and summary.

For each digest item, provide:
- "id": the original id of the digest item (copy it exactly)
- "score": an integer from 1 to 10 indicating relevance to the user
  - 10 = must-read, perfectly aligned with user's core interests
  - 7-9 = highly relevant, strong technical or practical value
  - 4-6 = somewhat relevant, tangentially interesting
  - 1-3 = low relevance, not aligned with user's interests
- "reason": one sentence explaining why you gave this score

Be discriminating. Not everything is a 10. Use the full range of scores.
"""


class ScoredItem(BaseModel):
    """A single scored digest item."""

    id: str
    score: int
    reason: str


class CuratorOutput(BaseModel):
    """Structured output from the curator: a list of scored items."""

    items: list[ScoredItem]


class Curator:
    """
    Scores and ranks digest items by relevance to a user profile.

    Usage:
        curator = Curator()
        ranked = curator.rank_digests(digest_items, user_profile="...")
    """

    def __init__(self):
        self._client = get_llm_client()

    def rank_digests(
        self,
        digests: list[dict],
        user_profile: str,
    ) -> list[ScoredItem]:
        """
        Score and rank a list of digest items.

        Args:
            digests:      List of dicts with keys: id, title, summary.
            user_profile: Text describing the user's interests and background.

        Returns:
            List of ScoredItem sorted by score (highest first).
        """
        if not digests:
            return []

        # Build the digest list for the prompt
        items_text = []
        for d in digests:
            items_text.append(
                f"- ID: {d['id']}\n"
                f"  Title: {d['title']}\n"
                f"  Summary: {d['summary']}"
            )

        user_input = (
            f"USER PROFILE:\n{user_profile}\n\n"
            f"DIGEST ITEMS ({len(digests)} total):\n\n"
            + "\n\n".join(items_text)
        )

        try:
            ranked = self._call_api(user_input)
            logger.info("Curator scored %d items", len(ranked))
            return ranked
        except Exception as exc:
            logger.error("Curator failed after retries: %s", exc)
            return []

    @_llm_retry
    def _call_api(self, user_input: str) -> list[ScoredItem]:
        """Internal: call LLM API with automatic retry."""
        result = chat_completion(
            client=self._client,
            system_prompt=SYSTEM_PROMPT,
            user_input=user_input,
            response_model=CuratorOutput,
        )
        return sorted(result.items, key=lambda x: x.score, reverse=True)
