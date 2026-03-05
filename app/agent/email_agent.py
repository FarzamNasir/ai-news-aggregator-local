"""
Email Agent

Takes the top-ranked curated digest items and generates an email-ready
structure with a personalized introduction and the ranked article list.
Uses the OpenAI Responses API for the intro text.
"""

import logging
from datetime import datetime, timezone

from openai import OpenAI
from pydantic import BaseModel

from app.user_profile import USER_NAME

logger = logging.getLogger(__name__)

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
        agent = EmailAgent()
        email = agent.compose(ranked_items)
    """

    def __init__(self, model: str = "gpt-4.1-mini", top_n: int = 10):
        self.model = model
        self.top_n = top_n
        self._client = OpenAI()

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

        today = datetime.now(timezone.utc).strftime("%B %d, %Y")
        subject = f"Your AI News Digest — {today}"

        return EmailContent(
            subject=subject,
            greeting=intro.greeting,
            intro=intro.body,
            items=top_items,
            generated_at=datetime.now(timezone.utc),
        )

    def _generate_intro(self, items: list[dict]) -> EmailIntro | None:
        """Generate the personalized intro paragraph."""
        today = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")

        # Build the article list for context
        article_list = "\n".join(
            f"- [{item['score']}/10] {item['title']}: {item['summary']}"
            for item in items
        )

        user_input = (
            f"Reader's name: {USER_NAME}\n"
            f"Today's date: {today}\n"
            f"Number of articles: {len(items)}\n\n"
            f"RANKED ARTICLES:\n{article_list}"
        )

        try:
            response = self._client.responses.parse(
                model=self.model,
                instructions=INTRO_PROMPT,
                input=[{"role": "user", "content": user_input}],
                text_format=EmailIntro,
            )

            result = response.output_parsed
            logger.info("Generated email intro for %s", USER_NAME)
            return result

        except Exception as exc:
            logger.error("Email intro generation failed: %s", exc)
            return None
