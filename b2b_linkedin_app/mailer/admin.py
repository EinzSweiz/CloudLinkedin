from django.contrib import admin
from .models import EmailTemplate, EmailLog

admin.site.register(EmailTemplate)
admin.site.register(EmailLog)