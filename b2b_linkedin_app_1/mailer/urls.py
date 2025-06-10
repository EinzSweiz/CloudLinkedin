from mailer.views import mailgun_webhook
from django.urls import path

urlpatterns = [
    path("api/mailgun/webhook/", mailgun_webhook, name="mailgun_webhook"),
]
