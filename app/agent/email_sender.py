import os
import logging
import smtplib
import ssl
import threading
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.agent.email_agent import EmailContent

logger = logging.getLogger(__name__)


def _send_smtp(msg: MIMEMultipart, recipient: str) -> bool:
    """
    Low-level SMTP send via Gmail.

    Tries SMTP_SSL (port 465) first, falls back to STARTTLS (port 587).
    Includes a 15-second timeout on all connections.
    """
    smtp_email = os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_APP_PASSWORD")

    if not smtp_email or not smtp_password:
        logger.error("SMTP credentials missing (SMTP_EMAIL or SMTP_APP_PASSWORD)")
        return False

    # Attempt 1: SMTP_SSL on port 465 (preferred on cloud platforms)
    try:
        logger.info("Attempting SMTP_SSL (port 465) to %s ...", recipient)
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=15) as server:
            server.login(smtp_email, smtp_password)
            server.send_message(msg)
        logger.info("Email sent via SMTP_SSL (465) to %s", recipient)
        return True
    except Exception as exc:
        logger.warning("SMTP_SSL (465) failed for %s: %s. Trying STARTTLS (587)...", recipient, exc)

    # Attempt 2: STARTTLS on port 587 (fallback)
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
            server.starttls(context=context)
            server.login(smtp_email, smtp_password)
            server.send_message(msg)
        logger.info("Email sent via STARTTLS (587) to %s", recipient)
        return True
    except Exception as exc:
        logger.error("STARTTLS (587) also failed for %s: %s", recipient, exc)
        return False


def send_confirmation_email(
    recipient_email: str,
    name: str,
    confirm_url: str,
) -> bool:
    """
    Send a lightweight email asking the user to confirm their subscription.

    Sends in a background thread so the API responds instantly.
    Returns True immediately (fire-and-forget).
    """
    smtp_email = os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_APP_PASSWORD")

    if not all([smtp_email, smtp_password, recipient_email]):
        logger.error("Missing email config for confirmation email.")
        return False

    FONT = (
        "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
        "Helvetica, Arial, sans-serif"
    )

    html_body = f"""\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:0; background-color:#f4f4f5;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f4f4f5;">
<tr><td align="center" style="padding:40px 16px;">
<table role="presentation" width="520" cellpadding="0" cellspacing="0" border="0" style="max-width:520px; width:100%;">

  <!-- Header -->
  <tr><td style="background-color:#09090b; border-radius:12px 12px 0 0; padding:28px 32px;">
    <span style="font-family:{FONT}; font-size:11px; font-weight:600; letter-spacing:1.6px; color:#a1a1aa; text-transform:uppercase;">LUMIN</span>
  </td></tr>

  <!-- Body -->
  <tr><td style="background-color:#ffffff; padding:36px 32px; border-left:1px solid #e4e4e7; border-right:1px solid #e4e4e7;">
    <h1 style="font-family:{FONT}; font-size:22px; font-weight:600; color:#18181b; margin:0 0 16px; letter-spacing:-0.3px;">Confirm your subscription</h1>
    <p style="font-family:{FONT}; font-size:15px; line-height:24px; color:#52525b; margin:0 0 24px;">
      Hey {name}, thanks for signing up for Lumin. Please confirm your email address so we can start sending your personalized AI digest.
    </p>
    <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
      <td style="border-radius:8px; background-color:#18181b;">
        <a href="{confirm_url}" style="display:inline-block; padding:14px 32px; font-family:{FONT}; font-size:15px; font-weight:600; color:#fafafa; text-decoration:none; border-radius:8px;">Confirm my email</a>
      </td>
    </tr></table>
    <p style="font-family:{FONT}; font-size:13px; line-height:20px; color:#a1a1aa; margin:24px 0 0;">
      If the button doesn't work, copy and paste this URL into your browser:<br>
      <a href="{confirm_url}" style="color:#71717a; word-break:break-all;">{confirm_url}</a>
    </p>
  </td></tr>

  <!-- Footer -->
  <tr><td style="background-color:#09090b; border-radius:0 0 12px 12px; padding:20px 32px;">
    <p style="font-family:{FONT}; font-size:12px; color:#a1a1aa; margin:0;">
      If you didn't sign up for Lumin, you can safely ignore this email.
    </p>
  </td></tr>

</table>
</td></tr></table>
</body>
</html>"""

    plain_text = (
        f"Hey {name},\n\n"
        f"Thanks for signing up for Lumin. Please confirm your email by visiting:\n"
        f"{confirm_url}\n\n"
        f"If you didn't sign up, you can safely ignore this email.\n"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Confirm your Lumin subscription"
    msg["From"] = f"Lumin <{smtp_email}>"
    msg["To"] = recipient_email

    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    # Send in a background thread so the API responds instantly
    def _send():
        _send_smtp(msg, recipient_email)

    thread = threading.Thread(target=_send, daemon=True)
    thread.start()
    logger.info("Confirmation email queued for %s (background thread)", recipient_email)
    return True

# ── Design tokens (shadcn/ui zinc) ───────────────────────────────────────────
# background:#f4f4f5  card:#ffffff  border:#e4e4e7
# foreground:#18181b  muted-foreground:#71717a  muted:#fafafa
# header/footer:#09090b  muted-header:#a1a1aa
# score-high → green:  fg:#15803d  bg:#f0fdf4  border:#bbf7d0
# score-low  → amber:  fg:#c2410c  bg:#fff7ed  border:#fed7aa

FONT_STACK = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
    "Helvetica, Arial, sans-serif"
)
MONO_STACK = "'SF Mono', 'Roboto Mono', Consolas, monospace"


def _score_badge(score: float) -> str:
    """Return the score badge HTML with green (≥7) or amber (<7) styling."""
    score_str = f"{score:.1f}" if isinstance(score, float) else str(score)

    if float(score) >= 7:
        bg, border, fg = "#f0fdf4", "#bbf7d0", "#15803d"
    else:
        bg, border, fg = "#fff7ed", "#fed7aa", "#c2410c"

    return (
        f'<td style="background-color:{bg}; border:1px solid {border}; '
        f'border-radius:6px; padding:3px 9px;">'
        f'<span style="font-family:{MONO_STACK}; font-size:12px; '
        f'font-weight:600; color:{fg};">{score_str}</span></td>'
    )


def _build_story_card(index: int, item: dict) -> str:
    """Build one story card matching the monochromatic design."""
    rank = f"{index:02d}"
    score = item.get("score", 0)
    title = item.get("title", "")
    summary = item.get("summary", "")
    url = item.get("url", "#")

    badge_html = _score_badge(score)

    return f"""
          <tr>
            <td style="background-color:#fafafa; padding: 0 32px; border-left:1px solid #e4e4e7; border-right:1px solid #e4e4e7;" class="px-mobile">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#ffffff; border:1px solid #e4e4e7; border-radius:8px; margin-bottom:12px;">
                <tr>
                  <td style="padding: 20px 20px 16px 20px;">
                    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td valign="top" style="font-family:{MONO_STACK}; font-size:12px; color:#a1a1aa; padding-right:12px; padding-top:2px; white-space:nowrap;">
                          {rank}
                        </td>
                        <td valign="top">
                          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                            <tr>
                              <td style="font-family:{FONT_STACK}; font-size:15.5px; font-weight:600; line-height:21px; color:#18181b; padding-bottom:8px;">
                                {title}
                              </td>
                            </tr>
                            <tr>
                              <td style="font-family:{FONT_STACK}; font-size:13.5px; line-height:20px; color:#71717a; padding-bottom:14px;">
                                {summary}
                              </td>
                            </tr>
                            <tr>
                              <td>
                                <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                                  <tr>
                                    {badge_html}
                                    <td style="padding-left:10px; font-family:{FONT_STACK}; font-size:13px; color:#a1a1aa;">&middot;</td>
                                    <td style="padding-left:10px;">
                                      <a href="{url}" style="font-family:{FONT_STACK}; font-size:13px; font-weight:600; color:#18181b; text-decoration:none; border-bottom:1px solid #18181b;">Read more &rarr;</a>
                                    </td>
                                  </tr>
                                </table>
                              </td>
                            </tr>
                          </table>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>"""


def build_html_email(email: EmailContent, manage_url: str = "") -> str:
    """Render EmailContent into the monochromatic HTML email template."""

    num_stories = len(email.items)
    today = datetime.now().strftime("%A, %B\u00a0%d")  # e.g. "Friday, June 19"
    date_display = email.subject.replace("Your AI News Digest \u2014 ", "")

    # Preheader text (hidden preview)
    preheader = email.intro[:120] if email.intro else ""

    # Build all story cards
    story_cards = "\n".join(
        _build_story_card(i, item)
        for i, item in enumerate(email.items, 1)
    )

    # Footer manage/unsubscribe links
    if manage_url:
        footer_links = f"""
                <tr>
                  <td style="padding-top:10px; font-family:{FONT_STACK}; font-size:12px;">
                    <a href="{manage_url}" style="color:#71717a; text-decoration:underline;">Manage preferences</a>
                    <span style="color:#3f3f46;">&nbsp;&nbsp;&middot;&nbsp;&nbsp;</span>
                    <a href="{manage_url}" style="color:#71717a; text-decoration:underline;">Unsubscribe</a>
                  </td>
                </tr>"""
    else:
        footer_links = ""

    html = f"""\
<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<meta http-equiv="X-UA-Compatible" content="IE=edge" />
<title>{email.subject}</title>
<!--[if mso]>
<noscript>
<xml>
<o:OfficeDocumentSettings>
<o:PixelsPerInch>96</o:PixelsPerInch>
</o:OfficeDocumentSettings>
</xml>
</noscript>
<![endif]-->
<style>
  body, table, td, a {{ -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }}
  table, td {{ mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
  img {{ -ms-interpolation-mode: bicubic; border: 0; height: auto; line-height: 100%; outline: none; text-decoration: none; }}
  body {{ margin: 0; padding: 0; width: 100% !important; height: 100% !important; }}
  a {{ color: #18181b; }}

  @media screen and (max-width: 600px) {{
    .email-container {{ width: 100% !important; }}
    .px-mobile {{ padding-left: 20px !important; padding-right: 20px !important; }}
    .stack {{ display: block !important; width: 100% !important; }}
    .h1-mobile {{ font-size: 22px !important; }}
  }}
</style>
</head>
<body style="margin:0; padding:0; background-color:#f4f4f5;">

  <!-- Preheader (hidden) -->
  <div style="display:none; max-height:0; overflow:hidden; mso-hide:all; font-size:1px; line-height:1px; color:#fafafa; opacity:0;">
    {preheader}
  </div>

  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f4f4f5;">
    <tr>
      <td align="center" style="padding: 32px 16px;">

        <table role="presentation" class="email-container" width="600" cellpadding="0" cellspacing="0" border="0" style="width:600px; max-width:600px;">

          <!-- Header -->
          <tr>
            <td style="background-color:#09090b; border-radius:12px 12px 0 0; padding: 28px 32px;" class="px-mobile">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td valign="middle">
                    <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td style="font-family:{FONT_STACK}; font-size:11px; font-weight:600; letter-spacing:1.6px; color:#a1a1aa; text-transform:uppercase; padding-bottom:6px;">
                          DAILY AI DIGEST
                        </td>
                      </tr>
                      <tr>
                        <td class="h1-mobile" style="font-family:{FONT_STACK}; font-size:24px; font-weight:600; color:#fafafa; letter-spacing:-0.3px;">
                          {date_display}
                        </td>
                      </tr>
                    </table>
                  </td>
                  <td valign="middle" align="right">
                    <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td style="width:8px; height:8px; border-radius:50%; background-color:#4ade80; font-size:0; line-height:0;">&nbsp;</td>
                        <td style="font-family:{MONO_STACK}; font-size:11px; color:#a1a1aa; padding-left:6px;">{num_stories} stories</td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Greeting / summary card -->
          <tr>
            <td style="background-color:#ffffff; padding: 28px 32px 24px 32px; border-left:1px solid #e4e4e7; border-right:1px solid #e4e4e7;" class="px-mobile">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="font-family:{FONT_STACK}; font-size:17px; font-weight:600; color:#18181b; padding-bottom:10px;">
                    {email.greeting}
                  </td>
                </tr>
                <tr>
                  <td style="font-family:{FONT_STACK}; font-size:14px; line-height:22px; color:#52525b;">
                    {email.intro}
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Section label -->
          <tr>
            <td style="background-color:#fafafa; padding: 18px 32px 14px 32px; border-left:1px solid #e4e4e7; border-right:1px solid #e4e4e7; border-top:1px solid #e4e4e7;" class="px-mobile">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td class="stack" style="font-family:{MONO_STACK}; font-size:11px; font-weight:600; letter-spacing:1.2px; color:#71717a; text-transform:uppercase;">
                    Top {num_stories} stories, ranked for you
                  </td>
                  <td class="stack" align="right" style="font-family:{MONO_STACK}; font-size:11px; color:#a1a1aa; white-space:nowrap; padding-left:12px;">
                    score&nbsp;/&nbsp;10
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Story cards -->
{story_cards}

          <!-- Spacer before footer -->
          <tr>
            <td style="background-color:#fafafa; padding: 4px 32px 24px 32px; border-left:1px solid #e4e4e7; border-right:1px solid #e4e4e7;" class="px-mobile">
              &nbsp;
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color:#09090b; border-radius:0 0 12px 12px; padding: 22px 32px;" class="px-mobile">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="font-family:{FONT_STACK}; font-size:12px; color:#a1a1aa; line-height:18px;">
                    Curated by Lumin &mdash; scores reflect relevance to your profile.
                  </td>
                </tr>
{footer_links}
              </table>
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
        plain_text += (
            f"{i:02d}. [{item.get('score', '?')}/10] {item['title']}\n"
            f"    {item['summary']}\n"
            f"    {item['url']}\n\n"
        )
    if manage_url:
        plain_text += f"\n---\nManage preferences: {manage_url}\n"

    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    # Send via Gmail SMTP (uses shared helper with 465/587 fallback + timeout)
    return _send_smtp(msg, recipient)
