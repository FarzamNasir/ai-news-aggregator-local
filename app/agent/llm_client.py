"""
LLM Client Factory

Provides a unified interface for creating LLM clients that work with
both Groq (free, Llama models) and OpenAI as a fallback.

Both providers expose an OpenAI-compatible chat completions API,
so the downstream code stays the same regardless of provider.

Configuration (env vars):
    LLM_PROVIDER=groq       (default) or "openai"
    GROQ_API_KEY=gsk_...    (required if provider=groq)
    OPENAI_API_KEY=sk-...   (required if provider=openai)
    LLM_MODEL=...           (optional override)
"""

import os
import json
import logging

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Default models per provider
_DEFAULT_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "openai": "gpt-4.1-mini",
}


def get_provider() -> str:
    """Return the configured LLM provider name."""
    return os.getenv("LLM_PROVIDER", "groq").lower()


def get_model() -> str:
    """Return the model to use, respecting any override."""
    provider = get_provider()
    return os.getenv("LLM_MODEL", _DEFAULT_MODELS.get(provider, "llama-3.3-70b-versatile"))


def get_llm_client():
    """
    Create and return an LLM client based on the configured provider.

    Returns an OpenAI-compatible client (both Groq and OpenAI SDKs
    expose the same chat.completions.create() interface).
    """
    provider = get_provider()

    if provider == "groq":
        from groq import Groq
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is required when LLM_PROVIDER=groq")
        logger.debug("Using Groq LLM provider (model: %s)", get_model())
        return Groq(api_key=api_key)

    elif provider == "openai":
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required when LLM_PROVIDER=openai")
        logger.debug("Using OpenAI LLM provider (model: %s)", get_model())
        return OpenAI(api_key=api_key)

    else:
        raise ValueError(f"Unknown LLM_PROVIDER: '{provider}'. Use 'groq' or 'openai'.")


def chat_completion(
    client,
    system_prompt: str,
    user_input: str,
    response_model: type[BaseModel],
) -> BaseModel:
    """
    Send a chat completion request and parse the response into a Pydantic model.

    Uses JSON mode for structured output — works with both Groq and OpenAI.

    Args:
        client:         LLM client from get_llm_client()
        system_prompt:  System instructions
        user_input:     User message content
        response_model: Pydantic model class to parse the response into

    Returns:
        Parsed Pydantic model instance

    Raises:
        ValueError: If the response cannot be parsed
    """
    # Build the schema instruction for JSON mode
    schema = response_model.model_json_schema()
    json_instruction = (
        f"\n\nYou MUST respond with valid JSON matching this schema:\n"
        f"{json.dumps(schema, indent=2)}\n"
        f"Respond ONLY with the JSON object, no other text."
    )

    response = client.chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": system_prompt + json_instruction},
            {"role": "user", "content": user_input},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )

    raw = response.choices[0].message.content
    return response_model.model_validate_json(raw)
