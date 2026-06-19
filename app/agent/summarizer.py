"""
Article Summarizer Agent

Uses the configured LLM (Groq/OpenAI) to generate structured digest
summaries (title + 2-3 sentence summary) for scraped articles and videos.
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
You are an AI news digest summarizer. Your job is to read articles and videos \
about AI, machine learning, and technology, then produce a concise digest entry.

Rules:
- "title": Create a short, catchy, informative title (max 15 words). \
  Do NOT just copy the original title — rephrase it to highlight the key takeaway.
- "summary": Write exactly 2-3 sentences that capture the most important points. \
  Be specific about what was announced, discovered, or built. \
  Write for a technical audience who wants to stay informed quickly.

If the content is a YouTube video transcript, focus on the main topic discussed.
If the content is a blog post, focus on the key announcement or finding.
"""


class DigestOutput(BaseModel):
    """Structured output from the summarizer."""

    title: str
    summary: str


class Summarizer:
    """
    Generates digest summaries using the configured LLM provider.

    Usage:
        summarizer = Summarizer()
        result = summarizer.summarize(title, content)
        print(result.title, result.summary)
    """

    def __init__(self):
        self._client = get_llm_client()

    def summarize(
        self,
        title: str,
        content: str | None = None,
        description: str | None = None,
        source_type: str = "article",
    ) -> DigestOutput | None:
        """
        Generate a digest for a single article/video.

        Args:
            title:       Original title of the article/video.
            content:     Full text (article body or transcript).
            description: Short description/excerpt if content is unavailable.
            source_type: "youtube", "openai", "anthropic", etc.

        Returns:
            DigestOutput with generated title and summary, or None on failure.
        """
        # Build the input text
        parts = [f"Source: {source_type}", f"Original Title: {title}"]

        if content:
            # Truncate very long content to stay within context limits
            text = content[:15000] if len(content) > 15000 else content
            parts.append(f"Content:\n{text}")
        elif description:
            parts.append(f"Description:\n{description}")
        else:
            parts.append("(No content available — summarize based on title only)")

        user_input = "\n\n".join(parts)

        try:
            result = self._call_api(user_input)
            logger.info("Summarized: %s", title[:60])
            return result
        except Exception as exc:
            logger.error("Failed to summarize '%s' after retries: %s", title[:60], exc)
            return None

    @_llm_retry
    def _call_api(self, user_input: str) -> DigestOutput:
        """Internal: call LLM API with automatic retry."""
        return chat_completion(
            client=self._client,
            system_prompt=SYSTEM_PROMPT,
            user_input=user_input,
            response_model=DigestOutput,
        )
