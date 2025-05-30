from django.contrib.postgres.fields import ArrayField
from django.db import models

class ParsingInfo(models.Model):
    full_name = models.CharField("Full Name", max_length=255)
    position = models.CharField("Position", max_length=255)
    company_name = models.CharField("Company Name", max_length=255)
    email = models.EmailField("Email", max_length=255, blank=True, null=True)
    profile_url = models.URLField("Profile URL", max_length=500, blank=True, null=True)  # Добавленное поле

    class Meta:
        verbose_name = "Parsing Info"
        verbose_name_plural = "Parsing Info"
        ordering = ["company_name", "full_name"]

    def __str__(self):
        return f"{self.full_name} – {self.position} @ {self.company_name}"

class ParserRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('error', 'Error'),
    ]

    keywords = ArrayField(
        models.CharField(max_length=100),
        blank=True,
        null=True,
        verbose_name="Keywords",
        help_text="Список ключевых слов, например: ['Python', 'Remote']"
    )
    location = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Location",
        help_text="Страна или город, например: 'Germany'"
    )
    limit = models.PositiveIntegerField(
        default=50,
        verbose_name="Limit",
        help_text="Максимум профилей к возврату"
    )
    start_page = models.PositiveIntegerField(
        default=1,
        verbose_name="Start Page",
        help_text="С какой страницы начать парсинг"
    )
    end_page = models.PositiveIntegerField(
        default=5,
        verbose_name="End Page",
        help_text="До какой страницы дойти включительно"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    #Новый статус:
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Status",
        help_text="Текущий статус парсинга"
    )

    class Meta:
        verbose_name = "Parser Request"
        verbose_name_plural = "Parser Requests"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Request: keywords={self.keywords}, location={self.location}, pages={self.start_page}-{self.end_page}"
