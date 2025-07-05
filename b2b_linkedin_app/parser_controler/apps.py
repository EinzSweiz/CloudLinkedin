from django.apps import AppConfig
from django.db.models.signals import post_migrate


class ParserControlerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'parser_controler'

    # def ready(self):
    #     from . import scheduler
    #
    #     post_migrate.connect(scheduler.setup_periodic_tasks, sender=self)