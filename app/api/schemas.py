"""
API Schemas

Pydantic models for request/response validation in the FastAPI endpoints.
"""

from pydantic import BaseModel, EmailStr


# ── Predefined Interest Categories ───────────────────────────────────────────

INTEREST_CATEGORIES = [
    "Large Language Models (LLMs)",
    "Computer Vision",
    "Robotics & Embodied AI",
    "AI Safety & Alignment",
    "AI Engineering & MLOps",
    "Reinforcement Learning",
    "Generative AI & Diffusion",
    "Natural Language Processing",
    "AI Research Papers",
    "AI Products & Launches",
    "Developer Tools & SDKs",
    "AI Business & Industry",
]


# ── Request Schemas ──────────────────────────────────────────────────────────

class SubscribeRequest(BaseModel):
    """Request body for subscribing to the newsletter."""
    name: str
    email: EmailStr
    interests: list[str]
    custom_note: str | None = None


class UpdatePreferencesRequest(BaseModel):
    """Request body for updating subscriber preferences."""
    name: str | None = None
    interests: list[str] | None = None
    custom_note: str | None = None


# ── Response Schemas ─────────────────────────────────────────────────────────

class SubscribeResponse(BaseModel):
    """Response after successful subscription."""
    message: str
    manage_url: str


class SubscriberInfo(BaseModel):
    """Subscriber details returned by the manage endpoint."""
    name: str
    email: str
    interests: list[str]
    custom_note: str | None
    is_active: bool


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str


class InterestsResponse(BaseModel):
    """List of available interest categories."""
    categories: list[str]
