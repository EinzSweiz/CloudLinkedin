from django.contrib import admin
from django.shortcuts import get_object_or_404, redirect
from django.urls import path
from django.utils.html import format_html

from b2b_linkedin_app.permissions import PaidPermissionAdmin
from .models import EmailTemplate, EmailLog, MessagesBlueprintText, EmailMessage
from .tasks import smtp_send_mail


class MessagesBlueprintTextAdmin(PaidPermissionAdmin):
    list_display = ("id", "message_title", "creator")
    search_fields = ("message_title", "message_text", "creator__email")
    list_filter = ("creator",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(creator=request.user)

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is None:
            return True
        return obj.creator == request.user

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser or (request.user.is_staff and getattr(request.user, 'is_paid', False)):
            if obj is None:
                return True  # allow opening change form
            return obj.creator == request.user
        return False

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is None:
            return False
        return obj.creator == request.user

    def has_add_permission(self, request):
        return request.user.is_superuser or (request.user.is_staff and getattr(request.user, 'is_paid', False))



class EmailMessageAdmin(PaidPermissionAdmin):
    list_display = ("id", "message", "parsing_info", "status", "resend_mail_button")
    search_fields = ("message__message_title", "parsing_info__id")
    list_filter = ("status",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Ограничиваем просмотр по связанной модели MessagesBlueprintText
        return qs.filter(message__creator=request.user)

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is None:
            return True
        return obj.message.creator == request.user

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is None:
            return False
        return obj.message.creator == request.user

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is None:
            return False
        return obj.message.creator == request.user

    def has_add_permission(self, request):
        return request.user.is_superuser

    def resend_mail_button(self, obj):
        return format_html(
            '''
            <a href="{}" class="resend-mail-btn" style="
                display: inline-flex;
                align-items: center;
                gap: 8px;
                padding: 8px 16px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-decoration: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 500;
                border: 2px solid transparent;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                box-shadow: 0 2px 4px rgba(102, 126, 234, 0.2);
                position: relative;
                overflow: hidden;
            " 
            onmouseover="
                this.style.transform = 'translateY(-2px) scale(1.02)';
                this.style.boxShadow = '0 8px 25px rgba(102, 126, 234, 0.4)';
                this.style.background = 'linear-gradient(135deg, #5a67d8 0%, #667eea 100%)';
            " 
            onmouseout="
                this.style.transform = 'translateY(0) scale(1)';
                this.style.boxShadow = '0 2px 4px rgba(102, 126, 234, 0.2)';
                this.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
            "
            onmousedown="this.style.transform = 'translateY(0) scale(0.98)';"
            onmouseup="this.style.transform = 'translateY(-2px) scale(1.02)';">
                <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24" style="flex-shrink: 0;">
                    <path d="M1.946 9.315c-.522-.174-.527-.455.01-.634l19.087-6.362c.529-.176.832.12.684.638l-5.454 19.086c-.15.529-.455.547-.679.045L12 14l6-8-8 6-8.054-2.685z"/>
                </svg>
                <span>Resend Mail</span>
            </a>
            
            <style>
            /* Ensures compatibility with both light and dark themes */
            .resend-mail-btn {{
                filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.1));
            }}
            
            /* Dark theme compatibility */
            @media (prefers-color-scheme: dark) {{
                .resend-mail-btn {{
                    box-shadow: 0 2px 4px rgba(102, 126, 234, 0.3) !important;
                }}
                .resend-mail-btn:hover {{
                    box-shadow: 0 8px 25px rgba(102, 126, 234, 0.5) !important;
                }}
            }}
            
            /* Additional hover effect for better UX */
            .resend-mail-btn::before {{
                content: '';
                position: absolute;
                top: 0;
                left: -100%;
                width: 100%;
                height: 100%;
                background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
                transition: left 0.5s;
            }}
            
            .resend-mail-btn:hover::before {{
                left: 100%;
            }}
            </style>
            ''',
            f'{obj.pk}/resend-mail/'
        )
    resend_mail_button.short_description = "Actions"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:pk>/resend-mail/', self.admin_site.admin_view(self.resend_mail_view), name='resend-mail'),
        ]
        return custom_urls + urls

    def resend_mail_view(self, request, pk):
        email_message_obj = get_object_or_404(EmailMessage, pk=pk)

        message_blueprint_obj = email_message_obj.message
        if not message_blueprint_obj:
            self.message_user(request, "Шаблон сообщения не найден.", level="error")
            return redirect(request.META.get('HTTP_REFERER', '/admin/'))

        # Повторная отправка
        smtp_send_mail.delay(message_blueprint_obj.id, email_message_obj.parsing_info.id)

        self.message_user(request, f"Письмо повторно отправлено на {email_message_obj.parsing_info.email}.")
        return redirect(request.META.get('HTTP_REFERER', '/admin/'))

admin.site.register(EmailTemplate)
admin.site.register(MessagesBlueprintText, MessagesBlueprintTextAdmin)
admin.site.register(EmailMessage, EmailMessageAdmin)
admin.site.register(EmailLog)