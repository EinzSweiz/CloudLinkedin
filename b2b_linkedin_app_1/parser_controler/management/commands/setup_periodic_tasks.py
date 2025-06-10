import json
import logging
from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, IntervalSchedule
from django.utils.timezone import now

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Setup periodic tasks for the application'

    def handle(self, *args, **kwargs):
        task_name = 'start_parsing'
        periodic_name = 'Start Parsing Daily'

        schedule, created = IntervalSchedule.objects.get_or_create(
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
            self.stdout.write(self.style.SUCCESS(f"Periodic task '{periodic_name}' created."))
        else:
            logger.info(f"Periodic task '{periodic_name}' already exists.")
            self.stdout.write(self.style.SUCCESS(f"Periodic task '{periodic_name}' already exists."))
