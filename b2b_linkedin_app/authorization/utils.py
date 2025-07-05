from django.utils import timezone
from .models import OneTimeSub
from django.contrib.auth.models import User

def create_one_time_sub(user: User) -> OneTimeSub:
    """
    Создает запись OneTimeSub для указанного пользователя, если такой записи еще нет на сегодня.
    """
    today = timezone.now().date()
    sub, created = OneTimeSub.objects.get_or_create(user=user, date=today)
    return sub