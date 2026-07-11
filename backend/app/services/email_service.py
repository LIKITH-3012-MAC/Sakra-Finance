"""
Email service using Resend API with development mode fallback.
"""
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger("sakra.email")


def send_email(to_email: str, subject: str, body_html: str) -> tuple[bool, Optional[str]]:
    """
    Send an email using the Resend API.

    In development mode or when using a mock API key, the email is printed
    to the console instead of being sent.

    Args:
        to_email: Recipient email address
        subject: Email subject line
        body_html: HTML body content

    Returns:
        A tuple of (success, message_id)
    """
    import secrets
    api_key = getattr(settings, "RESEND_API_KEY", "")
    is_mock = api_key.startswith("re_mock") if api_key else True

    if is_mock:
        logger.info(
            "📧 [DEV MODE] Email not sent. Details:\n"
            "  To: %s\n"
            "  Subject: %s\n"
            "  Body:\n%s",
            to_email,
            subject,
            body_html,
        )
        print(f"\n{'='*60}")
        print(f"📧 DEV MODE EMAIL")
        print(f"{'='*60}")
        print(f"To:      {to_email}")
        print(f"Subject: {subject}")
        print(f"Body:    {body_html[:500]}{'...' if len(body_html) > 500 else ''}")
        print(f"{'='*60}\n")
        return True, f"re_mock_{secrets.token_hex(16)}"

    try:
        import resend

        resend.api_key = api_key
        sender_email = getattr(settings, "SENDER_EMAIL", "noreply@sakra.finance")

        response = resend.Emails.send({
            "from": sender_email,
            "to": [to_email],
            "subject": subject,
            "html": body_html,
        })

        msg_id = response.get("id")
        logger.info("Email sent successfully to %s, id=%s", to_email, msg_id)
        return True, msg_id

    except Exception as e:
        logger.error("Failed to send email to %s: %s", to_email, str(e))
        return False, None
