"""
FastAPI Web Application

Serves the landing page and provides REST API endpoints for
subscriber management (subscribe, manage preferences, unsubscribe).
"""

import os
import secrets
import logging
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy import select

from app.database.connection import get_session, engine
from app.database.models import Base, Subscriber
from app.agent.email_sender import send_confirmation_email
from app.api.schemas import (
    SubscribeRequest,
    UpdatePreferencesRequest,
    SubscribeResponse,
    SubscriberInfo,
    MessageResponse,
    InterestsResponse,
    INTEREST_CATEGORIES,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
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


@app.get("/about", response_class=HTMLResponse)
def about_page():
    """Serve the about page."""
    about_path = os.path.join(STATIC_DIR, "about.html")
    return FileResponse(about_path)


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
    """Create a new subscriber (pending confirmation) and send confirmation email."""
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
            # Existing but inactive — could be unconfirmed or unsubscribed.
            # Re-generate confirmation token and resend.
            existing.name = req.name
            existing.interests = req.interests
            existing.custom_note = req.custom_note
            conf_token = secrets.token_urlsafe(32)
            existing.confirmation_token = conf_token
            existing.confirmed_at = None
            session.commit()

            confirm_url = f"{BASE_URL}/api/confirm/{conf_token}"
            send_confirmation_email(req.email, req.name, confirm_url)

            return SubscribeResponse(
                message=f"We've sent a confirmation email to {req.email}. Please check your inbox.",
                manage_url="",
            )

        # Create new subscriber (inactive until confirmed)
        manage_tok = secrets.token_urlsafe(32)
        conf_token = secrets.token_urlsafe(32)

        subscriber = Subscriber(
            name=req.name,
            email=req.email,
            interests=req.interests,
            custom_note=req.custom_note,
            manage_token=manage_tok,
            confirmation_token=conf_token,
            is_active=False,
        )
        session.add(subscriber)
        session.commit()

        confirm_url = f"{BASE_URL}/api/confirm/{conf_token}"
        send_confirmation_email(req.email, req.name, confirm_url)

        logger.info("New subscriber (pending confirmation): %s (%s)", req.name, req.email)

        return SubscribeResponse(
            message=f"We've sent a confirmation email to {req.email}. Please check your inbox.",
            manage_url="",
        )
    except HTTPException:
        raise
    except Exception as exc:
        session.rollback()
        logger.error("Subscribe failed: %s", exc)
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")
    finally:
        session.close()


@app.get("/api/confirm/{token}", response_class=HTMLResponse)
def confirm_subscription(token: str):
    """Confirm a subscriber's email and activate their subscription."""
    session = get_session()
    try:
        subscriber = session.execute(
            select(Subscriber).where(Subscriber.confirmation_token == token)
        ).scalar_one_or_none()

        if not subscriber:
            return HTMLResponse(
                content=_confirmation_page("Invalid link", "This confirmation link is invalid or has expired.", False),
                status_code=404,
            )

        if subscriber.is_active and subscriber.confirmed_at:
            manage_url = f"{BASE_URL}/manage/{subscriber.manage_token}"
            return HTMLResponse(
                content=_confirmation_page(
                    "Already confirmed",
                    f"Your email is already confirmed. You'll receive your daily AI digest.",
                    True,
                    manage_url=manage_url,
                ),
            )

        # Activate the subscriber
        subscriber.is_active = True
        subscriber.confirmed_at = datetime.now(timezone.utc)
        subscriber.confirmation_token = None  # one-time use
        session.commit()

        manage_url = f"{BASE_URL}/manage/{subscriber.manage_token}"
        logger.info("Subscriber confirmed: %s (%s)", subscriber.name, subscriber.email)

        return HTMLResponse(
            content=_confirmation_page(
                "You're in!",
                f"Welcome, {subscriber.name}! Your subscription is confirmed. "
                f"You'll receive your first AI digest tomorrow morning.",
                True,
                manage_url=manage_url,
            ),
        )
    except Exception as exc:
        session.rollback()
        logger.error("Confirmation failed: %s", exc)
        return HTMLResponse(
            content=_confirmation_page("Something went wrong", "Please try again later.", False),
            status_code=500,
        )
    finally:
        session.close()


def _confirmation_page(title: str, message: str, success: bool, manage_url: str = "") -> str:
    """Render a simple confirmation result page."""
    color = "#15803d" if success else "#dc2626"
    icon = "&#10003;" if success else "&#10007;"
    manage_link = ""
    if manage_url:
        manage_link = (
            f'<p style="margin-top:20px;">'
            f'<a href="{manage_url}" style="color:#18181b; font-weight:500; text-decoration:underline;">Manage your preferences &rarr;</a>'
            f'</p>'
        )
    home_link = f'<p style="margin-top:12px;"><a href="{BASE_URL}" style="color:#71717a; font-size:14px;">Back to Lumin</a></p>'

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — Lumin</title>
</head>
<body style="margin:0; padding:0; background-color:#f4f4f5; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="min-height:100vh;">
<tr><td align="center" valign="middle" style="padding:40px 20px;">
  <div style="max-width:440px; text-align:center;">
    <div style="width:56px; height:56px; border-radius:50%; background-color:{color}; color:#fff; font-size:28px; line-height:56px; margin:0 auto 20px; font-weight:bold;">{icon}</div>
    <h1 style="font-size:24px; font-weight:600; color:#18181b; margin:0 0 12px;">{title}</h1>
    <p style="font-size:16px; line-height:24px; color:#52525b; margin:0;">{message}</p>
    {manage_link}
    {home_link}
  </div>
</td></tr>
</table>
</body>
</html>"""


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
