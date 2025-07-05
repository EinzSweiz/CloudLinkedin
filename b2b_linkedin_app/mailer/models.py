from django.db import models
from django.db.models import CASCADE
from authorization.models import User

from parser_controler.models import ParsingInfo


class EmailTemplate(models.Model):
    name = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    html_template = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    

class EmailLog(models.Model):
    email = models.EmailField()
    subject = models.CharField(max_length=255)
    status = models.CharField(max_length=50, default="pending")
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    mailgun_id = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.email} — {self.status}"


class MessagesBlueprintText(models.Model):
    message_text = models.TextField(max_length=800)
    message_title = models.CharField(max_length=120)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, default=None)


class EmailMessageStatus(models.TextChoices):
    SENDED = 'sended', 'Sended'
    READED = 'readed', 'Readed'
    ERROR = 'error', 'Error'


class EmailMessage(models.Model):
    message = models.ForeignKey(MessagesBlueprintText, on_delete=CASCADE)
    parsing_info = models.OneToOneField(ParsingInfo, on_delete=CASCADE)
    status = models.CharField(
        max_length=10,
        choices=EmailMessageStatus.choices,
        default=EmailMessageStatus.SENDED
    )
