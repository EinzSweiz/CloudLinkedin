import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'b2b_linkedin_app.settings')

app = Celery('b2b_linkedin_app')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
