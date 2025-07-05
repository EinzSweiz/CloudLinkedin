from django.conf import settings
from django.core.mail import send_mail

from parser_controler.models import ParsingInfo
from .mailgun import send_email
from celery import shared_task, group
from django.utils.html import escape
import logging

from .models import EmailMessageStatus, EmailMessage, MessagesBlueprintText

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


@shared_task(name="smtp_send_mail")
def smtp_send_mail(message_blueprint_obj_id, parsing_info_obj_id):
    message_blueprint_obj = MessagesBlueprintText.objects.get(pk=message_blueprint_obj_id)
    parsing_info_obj = ParsingInfo.objects.get(pk=parsing_info_obj_id)
    if not parsing_info_obj or not message_blueprint_obj:
        return

    recipient_email = parsing_info_obj.email  # Email получателя
    sender_email = settings.EMAIL_HOST_USER  # Email отправителя

    if not recipient_email:
        return  # Не отправляем, если email отсутствует

    subject = message_blueprint_obj.message_title if message_blueprint_obj else "Default Subject"
    message_body = message_blueprint_obj.message_text if message_blueprint_obj else "Default Message"

    try:
        send_mail(subject, message_body, sender_email, [recipient_email], fail_silently=False)
        status = EmailMessageStatus.SENDED
    except Exception:
        status = EmailMessageStatus.ERROR

    # Сохранение результата в EmailMessage
    EmailMessage.objects.create(
        message=message_blueprint_obj,
        parsing_info=parsing_info_obj,
        status=status
    )