"""
FastAPI Web Application

Serves the landing page and provides REST API endpoints for
subscriber management (subscribe, manage preferences, unsubscribe).
"""

import os
import secrets
import logging

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy import select

from app.database.connection import get_session, engine
from app.database.models import Base, Subscriber
from app.api.schemas import (
    SubscribeRequest,
    UpdatePreferencesRequest,
    SubscribeResponse,
    SubscriberInfo,
    MessageResponse,
    InterestsResponse,
    INTEREST_CATEGORIES,
)

logger = logging.getLogger(__name__)

# ── App Setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Lumin — AI News Digest",
    description="AI-curated newsletters built around what you actually care about.",
    version="1.0.0",
)

# Ensure tables exist on startup
@app.on_event("startup")
def on_startup():
    try:
        Base.metadata.create_all(engine)
        logger.info("Database tables verified/created.")
    except Exception as exc:
        logger.warning("Could not connect to database on startup: %s", exc)
        logger.warning("API endpoints requiring DB will fail until DB is available.")


# ── Static Files ─────────────────────────────────────────────────────────────

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── Pages ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def landing_page():
    """Serve the landing page."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    return FileResponse(index_path)


@app.get("/manage/{token}", response_class=HTMLResponse)
def manage_page(token: str):
    """Serve the preferences management page."""
    manage_path = os.path.join(STATIC_DIR, "manage.html")
    return FileResponse(manage_path)


# ── API Endpoints ────────────────────────────────────────────────────────────

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


@app.get("/api/interests", response_model=InterestsResponse)
def list_interests():
    """Return available interest categories."""
    return InterestsResponse(categories=INTEREST_CATEGORIES)


@app.post("/api/subscribe", response_model=SubscribeResponse)
def subscribe(req: SubscribeRequest):
    """Create a new subscriber or reactivate an existing one."""
    session = get_session()
    try:
        # Check if email already exists
        existing = session.execute(
            select(Subscriber).where(Subscriber.email == req.email)
        ).scalar_one_or_none()

        if existing:
            if existing.is_active:
                raise HTTPException(
                    status_code=409,
                    detail="This email is already subscribed."
                )
            # Reactivate
            existing.is_active = True
            existing.name = req.name
            existing.interests = req.interests
            existing.custom_note = req.custom_note
            session.commit()
            manage_url = f"{BASE_URL}/manage/{existing.manage_token}"
            return SubscribeResponse(
                message=f"Welcome back, {req.name}! Your subscription has been reactivated.",
                manage_url=manage_url,
            )

        # Create new subscriber
        token = secrets.token_urlsafe(32)
        subscriber = Subscriber(
            name=req.name,
            email=req.email,
            interests=req.interests,
            custom_note=req.custom_note,
            manage_token=token,
        )
        session.add(subscriber)
        session.commit()

        manage_url = f"{BASE_URL}/manage/{token}"
        logger.info("New subscriber: %s (%s)", req.name, req.email)

        return SubscribeResponse(
            message=f"Welcome, {req.name}! You'll receive your first AI digest tomorrow morning.",
            manage_url=manage_url,
        )
    except HTTPException:
        raise
    except Exception as exc:
        session.rollback()
        logger.error("Subscribe failed: %s", exc)
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")
    finally:
        session.close()


@app.get("/api/manage/{token}", response_model=SubscriberInfo)
def get_preferences(token: str):
    """Get subscriber preferences by manage token."""
    session = get_session()
    try:
        subscriber = session.execute(
            select(Subscriber).where(Subscriber.manage_token == token)
        ).scalar_one_or_none()

        if not subscriber:
            raise HTTPException(status_code=404, detail="Subscriber not found.")

        return SubscriberInfo(
            name=subscriber.name,
            email=subscriber.email,
            interests=list(subscriber.interests) if subscriber.interests else [],
            custom_note=subscriber.custom_note,
            is_active=subscriber.is_active,
        )
    finally:
        session.close()


@app.put("/api/manage/{token}", response_model=MessageResponse)
def update_preferences(token: str, req: UpdatePreferencesRequest):
    """Update subscriber preferences."""
    session = get_session()
    try:
        subscriber = session.execute(
            select(Subscriber).where(Subscriber.manage_token == token)
        ).scalar_one_or_none()

        if not subscriber:
            raise HTTPException(status_code=404, detail="Subscriber not found.")

        if req.name is not None:
            subscriber.name = req.name
        if req.interests is not None:
            subscriber.interests = req.interests
        if req.custom_note is not None:
            subscriber.custom_note = req.custom_note

        session.commit()
        return MessageResponse(message="Preferences updated successfully.")
    except HTTPException:
        raise
    except Exception as exc:
        session.rollback()
        logger.error("Update failed: %s", exc)
        raise HTTPException(status_code=500, detail="Something went wrong.")
    finally:
        session.close()


@app.delete("/api/manage/{token}", response_model=MessageResponse)
def unsubscribe(token: str):
    """Unsubscribe (deactivate) a subscriber."""
    session = get_session()
    try:
        subscriber = session.execute(
            select(Subscriber).where(Subscriber.manage_token == token)
        ).scalar_one_or_none()

        if not subscriber:
            raise HTTPException(status_code=404, detail="Subscriber not found.")

        subscriber.is_active = False
        session.commit()
        logger.info("Unsubscribed: %s", subscriber.email)

        return MessageResponse(message="You've been unsubscribed. Sorry to see you go!")
    except HTTPException:
        raise
    except Exception as exc:
        session.rollback()
        logger.error("Unsubscribe failed: %s", exc)
        raise HTTPException(status_code=500, detail="Something went wrong.")
    finally:
        session.close()
