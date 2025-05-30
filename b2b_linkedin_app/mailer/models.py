from django.db import models

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