from .mailgun import send_email
from celery import shared_task, group
from django.utils.html import escape
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60, name="send_email_task")
def send_email_task(self, email: str, name: str, subject: str, template: str):
    try:
        html = template.replace("{{name}}", escape(name))
        result = send_email(email, subject, html)
        if result:
            logger.info(f"[EMAIL SUCCESS] {email} — sent successfully.")
        else:
            logger.warning(f"[EMAIL FAILURE] {email} — failed to send.")
        return result
    except Exception as e:
        logger.exception(f"[EMAIL ERROR] Exception for {email}: {e}")
        raise self.retry(exc=e)

@shared_task(name="send_bulk_emails")
def send_bulk_emails(recipients: list, subject: str, template: str):
    tasks = []
    for r in recipients:
        email = r.get("email")
        name = r.get("name", "Friend")
        if not email:
            logger.warning(f"[SKIP] Skipped empty email for {name}")
            continue
        tasks.append(send_email_task.s(email, name, subject, template))

    job = group(tasks)
    logger.info(f"[EMAIL GROUP] Created group with {len(tasks)} emails.")
    return job.apply_async()
