# tasks.py

from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import OneTimeSub

@shared_task
def check_one_time_subscriptions():
    threshold_date = timezone.now().date() - timedelta(days=30)
    expired_subs = OneTimeSub.objects.filter(date__lt=threshold_date)

    for sub in expired_subs:
        user = sub.user
        sub.delete()
        user.is_paid = False
        user.save()
