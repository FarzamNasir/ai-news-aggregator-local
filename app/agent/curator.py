"""
Curator Agent

Takes recent digest entries and ranks them by relevance to the user's
profile and interests using the OpenAI Responses API with structured output.

Named after a news editor/curator who decides which stories matter most.
"""

import logging

from openai import OpenAI
from pydantic import BaseModel

from app.user_profile import USER_PROFILE

logger = logging.getLogger(__name__)

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
    Scores and ranks digest items by relevance to the user profile.

    Usage:
        curator = Curator()
        ranked = curator.rank_digests(digest_items)
    """

    def __init__(self, model: str = "gpt-4.1-mini"):
        self.model = model
        self._client = OpenAI()

    def rank_digests(
        self, digests: list[dict],
    ) -> list[ScoredItem]:
        """
        Score and rank a list of digest items.

        Args:
            digests: List of dicts with keys: id, title, summary.

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
            f"USER PROFILE:\n{USER_PROFILE}\n\n"
            f"DIGEST ITEMS ({len(digests)} total):\n\n"
            + "\n\n".join(items_text)
        )

        try:
            response = self._client.responses.parse(
                model=self.model,
                instructions=SYSTEM_PROMPT,
                input=[{"role": "user", "content": user_input}],
                text_format=CuratorOutput,
            )

            result = response.output_parsed
            # Sort by score descending
            ranked = sorted(result.items, key=lambda x: x.score, reverse=True)
            logger.info("Curator scored %d items", len(ranked))
            return ranked

        except Exception as exc:
            logger.error("Curator failed: %s", exc)
            return []
