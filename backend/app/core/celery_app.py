"""
Celery background worker task configurations.
"""
import os
import logging
from celery import Celery

logger = logging.getLogger("sakra.celery")

# Configuration matching environment settings
redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

celery_app = Celery(
    "sakra_tasks",
    broker=redis_url,
    backend=redis_url
)

# Use eager execution as a dev fallback to prevent execution blocking if worker is off
celery_app.conf.update(
    task_always_eager=True,
    task_ignore_result=True,
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
)

@celery_app.task
def send_email_async(to_email: str, subject: str, html_content: str, template: str = "custom"):
    """
    Asynchronous Celery task to send emails and commit entries to MailLog history.
    """
    from app.services.email_service import send_email
    from app.models.mail_log import MailLog
    from app.database.session import SessionLocal

    logger.info("Executing Celery email task for %s", to_email)
    success, provider_message_id = send_email(to_email, subject, html_content)

    # Establish db connection to record mail log
    db = SessionLocal()
    try:
        mail_entry = MailLog(
            recipient=to_email,
            subject=subject,
            template=template,
            status="SENT" if success else "FAILED",
            provider_message_id=provider_message_id
        )
        db.add(mail_entry)
        db.commit()
        logger.info("Mail log created for %s, message_id=%s", to_email, provider_message_id)
    except Exception as e:
        logger.error("Failed to commit mail log: %s", str(e))
        db.rollback()
    finally:
        db.close()
