# parser_controler/models.py - FIXED with default value
from django.db import models
from django.utils import timezone

from authorization.models import User


class ParserRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('error', 'Error'),
        ('cancelled', 'Cancelled'),
    ]
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='assigned_parser_requests',
        help_text="User assigned to this parser request",
        null=True,
        blank=True
    )
    
    # Search parameters - FIXED: Added default value
    keywords = models.TextField(
        default='["linkedin"]',  # Default keywords as JSON array
        help_text="Keywords to search for (JSON array or comma-separated)"
    )
    location = models.CharField(max_length=100, default="France")
    limit = models.IntegerField(default=50)
    start_page = models.IntegerField(default=1)
    end_page = models.IntegerField(default=10)
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    current_page = models.IntegerField(null=True, blank=True, help_text="Current page being processed")
    
    # Results tracking
    profiles_found = models.IntegerField(default=0, help_text="Total profiles found")
    emails_extracted = models.IntegerField(default=0, help_text="Emails successfully extracted")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Error handling
    error_message = models.TextField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Parser Request"
        verbose_name_plural = "Parser Requests"
    
    def __str__(self):
        return f"Request {self.id} - {self.location} ({self.status})"
    
    def save(self, *args, **kwargs):
        # Auto-set started_at when status changes to running
        if self.status == 'running' and not self.started_at:
            self.started_at = timezone.now()
        
        # Auto-set completed_at when status changes to completed
        if self.status in ['completed', 'error', 'cancelled'] and not self.completed_at:
            self.completed_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    @property
    def success_rate(self):
        """Calculate email extraction success rate"""
        if self.profiles_found > 0:
            return round((self.emails_extracted / self.profiles_found) * 100, 1)
        return 0
    
    @property
    def duration_seconds(self):
        """Calculate duration in seconds"""
        if self.started_at:
            end_time = self.completed_at or timezone.now()
            return (end_time - self.started_at).total_seconds()
        return 0
    
    @property
    def progress_percentage(self):
        """Calculate progress percentage based on pages"""
        if self.current_page and self.start_page and self.end_page:
            total_pages = self.end_page - self.start_page + 1
            completed_pages = max(0, self.current_page - self.start_page + 1)
            return min(100, round((completed_pages / total_pages) * 100, 1))
        return 0


class ParsingInfo(models.Model):
    creator = models.ForeignKey(User, on_delete=models.CASCADE)


    # Link to the parser request
    parser_request = models.ForeignKey(
        ParserRequest, 
        on_delete=models.CASCADE, 
        related_name='profiles',
        null=True, 
        blank=True,
        help_text="The parser request that found this profile"
    )
    
    # Profile information
    full_name = models.CharField(max_length=255)
    position = models.CharField(max_length=500, null=True, blank=True)
    company_name = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    profile_url = models.URLField(null=True, blank=True)
    
    # Additional metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Search metadata
    search_keywords = models.TextField(null=True, blank=True, help_text="Keywords used to find this profile")
    search_location = models.CharField(max_length=100, null=True, blank=True)
    page_found = models.IntegerField(null=True, blank=True, help_text="Page number where profile was found")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Parsing Info"
        verbose_name_plural = "Parsing Info"
        
        # Prevent duplicate profiles within the same request
        unique_together = ['parser_request', 'full_name', 'company_name']
    
    def __str__(self):
        return f"{self.full_name} @ {self.company_name or 'Unknown Company'}"
    
    @property
    def has_email(self):
        """Check if profile has a valid email"""
        return bool(self.email and self.email.strip())
    
    @property
    def company_display(self):
        """Get company name for display"""
        return self.company_name or "Unknown Company"
    
    @property
    def position_display(self):
        """Get position for display"""
        return self.position or "Unknown Position"
    @property
    def assigned_user(self):
        """Get the user assigned to this parsing info through the parser request"""
        return self.parser_request.user if self.parser_request else self.creator