"""
Email Sender

Renders the EmailContent into a beautiful HTML email and
sends it via Gmail SMTP with App Password authentication.
"""

import os
import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.agent.email_agent import EmailContent

logger = logging.getLogger(__name__)


def _build_article_row(index: int, item: dict) -> str:
    """Build the HTML for a single article card."""
    score = item.get("score", 0)

    # Score badge color
    if score >= 8:
        badge_bg = "#10b981"
        badge_text = "#ffffff"
    elif score >= 5:
        badge_bg = "#f59e0b"
        badge_text = "#ffffff"
    else:
        badge_bg = "#6b7280"
        badge_text = "#ffffff"

    return f"""
    <tr>
      <td style="padding: 0 0 16px 0;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e5e7eb;">
          <tr>
            <td style="padding: 20px 24px;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="vertical-align: top; width: 36px; padding-right: 14px;">
                    <div style="background-color: {badge_bg}; color: {badge_text}; font-size: 13px; font-weight: 700; width: 36px; height: 36px; line-height: 36px; text-align: center; border-radius: 8px; font-family: 'Inter', Arial, sans-serif;">
                      {score}
                    </div>
                  </td>
                  <td style="vertical-align: top;">
                    <p style="margin: 0 0 6px 0; font-size: 16px; font-weight: 700; color: #111827; font-family: 'Inter', Arial, sans-serif; line-height: 1.4;">
                      {item['title']}
                    </p>
                    <p style="margin: 0 0 10px 0; font-size: 14px; color: #4b5563; font-family: 'Inter', Arial, sans-serif; line-height: 1.6;">
                      {item['summary']}
                    </p>
                    <a href="{item['url']}" style="display: inline-block; font-size: 13px; font-weight: 600; color: #6366f1; text-decoration: none; font-family: 'Inter', Arial, sans-serif;">
                      Read more &rarr;
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </td>
    </tr>"""


def build_html_email(email: EmailContent, manage_url: str = "") -> str:
    """Render EmailContent into a complete HTML email string."""

    # Build article rows
    article_rows = "\n".join(
        _build_article_row(i, item)
        for i, item in enumerate(email.items, 1)
    )

    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{email.subject}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f3f4f6; font-family: 'Inter', Arial, Helvetica, sans-serif; -webkit-font-smoothing: antialiased;">

  <!-- Wrapper -->
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f3f4f6;">
    <tr>
      <td align="center" style="padding: 32px 16px;">

        <!-- Main Container -->
        <table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px; width: 100%;">

          <!-- Header -->
          <tr>
            <td style="background: linear-gradient(135deg, #6366f1, #8b5cf6); padding: 32px 32px 28px 32px; border-radius: 16px 16px 0 0;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td>
                    <p style="margin: 0 0 4px 0; font-size: 13px; font-weight: 600; color: rgba(255,255,255,0.8); text-transform: uppercase; letter-spacing: 1.5px; font-family: 'Inter', Arial, sans-serif;">
                      Daily AI Digest
                    </p>
                    <p style="margin: 0; font-size: 24px; font-weight: 800; color: #ffffff; font-family: 'Inter', Arial, sans-serif; line-height: 1.3;">
                      {email.subject.replace('Your AI News Digest — ', '')}
                    </p>
                  </td>
                  <td style="text-align: right; vertical-align: top;">
                    <div style="background-color: rgba(255,255,255,0.15); border-radius: 10px; padding: 8px 14px; display: inline-block;">
                      <span style="font-size: 20px; line-height: 1;">&#129302;</span>
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Intro Section -->
          <tr>
            <td style="background-color: #ffffff; padding: 28px 32px; border-bottom: 1px solid #e5e7eb;">
              <p style="margin: 0 0 8px 0; font-size: 18px; font-weight: 700; color: #111827; font-family: 'Inter', Arial, sans-serif;">
                {email.greeting}
              </p>
              <p style="margin: 0; font-size: 15px; color: #4b5563; line-height: 1.7; font-family: 'Inter', Arial, sans-serif;">
                {email.intro}
              </p>
            </td>
          </tr>

          <!-- Section Header -->
          <tr>
            <td style="background-color: #f9fafb; padding: 20px 32px 12px 32px;">
              <p style="margin: 0; font-size: 12px; font-weight: 700; color: #6b7280; text-transform: uppercase; letter-spacing: 1.2px; font-family: 'Inter', Arial, sans-serif;">
                Top {len(email.items)} stories ranked for you
              </p>
            </td>
          </tr>

          <!-- Articles -->
          <tr>
            <td style="background-color: #f9fafb; padding: 8px 32px 24px 32px;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                {article_rows}
              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color: #1f2937; padding: 24px 32px; border-radius: 0 0 16px 16px; text-align: center;">
              <p style="margin: 0 0 8px 0; font-size: 13px; color: rgba(255,255,255,0.6); font-family: 'Inter', Arial, sans-serif;">
                Curated by Lumin &mdash; your AI news assistant
              </p>
              {f'''<p style="margin: 0 0 8px 0; font-size: 13px; font-family: 'Inter', Arial, sans-serif;">
                <a href="{manage_url}" style="color: #818cf8; text-decoration: none;">Manage preferences</a>
                &nbsp;&bull;&nbsp;
                <a href="{manage_url}" style="color: rgba(255,255,255,0.4); text-decoration: none;">Unsubscribe</a>
              </p>''' if manage_url else ''}
              <p style="margin: 0; font-size: 12px; color: rgba(255,255,255,0.35); font-family: 'Inter', Arial, sans-serif;">
                Scores reflect relevance to your profile
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>"""

    return html


def send_email(
    email_content: EmailContent,
    recipient_email: str | None = None,
    manage_url: str = "",
) -> bool:
    """
    Build and send the digest email via Gmail SMTP.

    Args:
        email_content:   The composed email content.
        recipient_email: Where to send. Falls back to RECIPIENT_EMAIL env var.
        manage_url:      Magic-link URL for manage/unsubscribe (added to footer).

    Environment variables required:
        SMTP_EMAIL:        Your Gmail address
        SMTP_APP_PASSWORD: Gmail App Password (16 chars)

    Returns:
        True if sent successfully, False otherwise.
    """
    smtp_email = os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_APP_PASSWORD")
    recipient = recipient_email or os.getenv("RECIPIENT_EMAIL")

    if not all([smtp_email, smtp_password, recipient]):
        logger.error(
            "Missing email config. Set SMTP_EMAIL, SMTP_APP_PASSWORD, "
            "and provide a recipient_email or RECIPIENT_EMAIL in .env."
        )
        return False

    # Build the HTML
    html_body = build_html_email(email_content, manage_url=manage_url)

    # Build the email message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = email_content.subject
    msg["From"] = f"Lumin AI Digest <{smtp_email}>"
    msg["To"] = recipient

    # Plain text fallback
    plain_text = f"{email_content.greeting}\n\n{email_content.intro}\n\n"
    for i, item in enumerate(email_content.items, 1):
        plain_text += f"{i}. {item['title']}\n   {item['summary']}\n   {item['url']}\n\n"
    if manage_url:
        plain_text += f"\n---\nManage preferences: {manage_url}\n"

    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    # Send via Gmail SMTP
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls(context=context)
            server.login(smtp_email, smtp_password)
            server.send_message(msg)

        logger.info("Email sent successfully to %s", recipient)
        return True

    except Exception as exc:
        logger.error("Failed to send email to %s: %s", recipient, exc)
        return False
