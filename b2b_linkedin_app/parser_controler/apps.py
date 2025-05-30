from django.apps import AppConfig


class ParserControlerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'parser_controler'

    # def ready(self):
    #     from . import scheduler
    #     scheduler.setup_periodic_tasks()