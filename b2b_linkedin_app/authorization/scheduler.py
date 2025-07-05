import logging
from django_celery_beat.models import PeriodicTask, IntervalSchedule
from django.utils.timezone import now
import json

logger = logging.getLogger(__name__)

def setup_periodic_tasks(sender, **kwargs):
    task_name = 'check_one_time_subscriptions'
    periodic_name = 'Check One-Time Subscriptions Daily'

    schedule, _ = IntervalSchedule.objects.get_or_create(
        every=1,
        period=IntervalSchedule.DAYS
    )

    task, created = PeriodicTask.objects.get_or_create(
        name=periodic_name,
        defaults={
            'interval': schedule,
            'task': task_name,
            'start_time': now(),
            'enabled': True,
            'args': json.dumps([]),
        }
    )

    if created:
        logger.info(f"Periodic task '{periodic_name}' created.")
    else:
        logger.info(f"Periodic task '{periodic_name}' already exists.")
