"""
Email Agent

Takes the top-ranked curated digest items and generates an email-ready
structure with a personalized introduction and the ranked article list.
Uses the configured LLM (Groq/OpenAI) for the intro text.
"""

import logging
from datetime import datetime, timezone

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

INTRO_PROMPT = """\
You are writing the opening paragraph of a personalized daily AI news digest email.

Rules:
- Address the reader by their first name.
- Mention today's date in a natural way.
- In 2-3 sentences, give a brief teaser of the top themes across the articles \
  (you will receive the ranked list of titles and summaries).
- Keep the tone friendly, professional, and concise — like a knowledgeable colleague.
- Do NOT list individual articles — just set the stage for what's coming below.
"""


class EmailIntro(BaseModel):
    """Structured output for the email introduction."""

    greeting: str   # e.g. "Hey Dave,"
    body: str       # 2-3 sentence intro paragraph


class EmailContent(BaseModel):
    """Complete email content ready for delivery."""

    subject: str
    greeting: str
    intro: str
    items: list[dict]  # ranked digest items
    generated_at: datetime


class EmailAgent:
    """
    Generates email-ready content from curated digest items.

    Usage:
        agent = EmailAgent(user_name="Farzam")
        email = agent.compose(ranked_items)
    """

    def __init__(self, user_name: str = "Subscriber", top_n: int = 10):
        self.user_name = user_name
        self.top_n = top_n
        self._client = get_llm_client()

    def compose(self, ranked_items: list[dict]) -> EmailContent | None:
        """
        Generate email content from ranked digest items.

        Args:
            ranked_items: List of dicts with title, summary, url, score, reason.
                          Should already be sorted by score (highest first).

        Returns:
            EmailContent with subject, greeting, intro, and top items.
        """
        # Take only the top N
        top_items = ranked_items[:self.top_n]

        if not top_items:
            logger.warning("No items to compose email from.")
            return None

        # Generate the intro
        intro = self._generate_intro(top_items)
        if not intro:
            return None

        today = datetime.now().strftime("%B %d, %Y")
        subject = f"Your AI News Digest \u2014 {today}"

        return EmailContent(
            subject=subject,
            greeting=intro.greeting,
            intro=intro.body,
            items=top_items,
            generated_at=datetime.now(timezone.utc),
        )

    def _generate_intro(self, items: list[dict]) -> EmailIntro | None:
        """Generate the personalized intro paragraph (with retry)."""
        today = datetime.now().strftime("%A, %B %d, %Y")

        # Build the article list for context
        article_list = "\n".join(
            f"- [{item['score']}/10] {item['title']}: {item['summary']}"
            for item in items
        )

        user_input = (
            f"Reader's name: {self.user_name}\n"
            f"Today's date: {today}\n"
            f"Number of articles: {len(items)}\n\n"
            f"RANKED ARTICLES:\n{article_list}"
        )

        try:
            result = self._call_api(user_input)
            logger.info("Generated email intro for %s", self.user_name)
            return result
        except Exception as exc:
            logger.error("Email intro generation failed after retries: %s", exc)
            return None

    @_llm_retry
    def _call_api(self, user_input: str) -> EmailIntro:
        """Internal: call LLM API with automatic retry."""
        return chat_completion(
            client=self._client,
            system_prompt=INTRO_PROMPT,
            user_input=user_input,
            response_model=EmailIntro,
        )
