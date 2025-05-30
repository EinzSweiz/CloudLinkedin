import requests
from django.conf import settings
from mailer.models import EmailLog
import logging

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, html_message: str) -> bool:
    try:
        response = requests.post(
            f"https://api.mailgun.net/v3/{settings.MAILGUN_DOMAIN}/messages",
            auth=("api", settings.MAILGUN_API_KEY),
            data={
                "from": f"SolidWay <mailgun@{settings.MAILGUN_DOMAIN}>",
                "to": [to_email],
                "subject": subject,
                "html": html_message,
                "text": "Your email client does not support HTML.",
            },
        )
        mailgun_id = None
        status = "sent"
        error_message = ""

        if response.status_code == 200:
            mailgun_id = response.json().get("id")
            logger.info(f"[MAIL] Email sent to {to_email}")
            success = True
        else:
            status = "failed"
            error_message = response.text
            logger.warning(f"[MAIL] Failed to send email: {response.text}")
            success = False

        EmailLog.objects.create(
            email=to_email,
            subject=subject,
            status=status,
            mailgun_id=mailgun_id,
            error_message=error_message,
        )

        return success

    except Exception as e:
        logger.exception("[MAIL] Exception during sending email:")
        EmailLog.objects.create(
            email=to_email,
            subject=subject,
            status="error",
            error_message=str(e),
        )
        return False
