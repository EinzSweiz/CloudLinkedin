import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from mailer.models import EmailLog

logger = logging.getLogger(__name__)

@csrf_exempt
def mailgun_webhook(request):
    if request.method == "POST":
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            logger.warning("[MAILGUN WEBHOOK] Invalid JSON received")
            return JsonResponse({"status": "invalid json"}, status=400)

        event = payload.get("event")
        mailgun_id = payload.get("id")

        logger.info(f"[MAILGUN WEBHOOK] Event: {event} | ID: {mailgun_id}")

        log = EmailLog.objects.filter(mailgun_id=mailgun_id).first()
        if log:
            log.status = event
            log.save(update_fields=["status"])
            return JsonResponse({"status": "updated"}, status=200)

        # Optional fallback
        EmailLog.objects.create(
            email="unknown",
            subject="unknown",
            status=event,
            mailgun_id=mailgun_id,
            error_message="Webhook with unmatched mailgun_id"
        )
        logger.warning(f"[MAILGUN WEBHOOK] No matching EmailLog for ID: {mailgun_id} — fallback created.")
        return JsonResponse({"status": "fallback created"}, status=201)

    return JsonResponse({"status": "invalid method"}, status=405)
