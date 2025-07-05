# Enhanced admin.py with beautiful styling integration - NO EMOJIS

from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect, get_object_or_404
from django.utils.html import format_html
from django.template.loader import render_to_string
from django.db import models
from mailer.models import MessagesBlueprintText
from mailer.tasks import smtp_send_mail
from django.http import JsonResponse
from .models import ParsingInfo, ParserRequest
from .tasks import start_parsing
from b2b_linkedin_app.permissions import PaidPermissionAdmin
import redis
import json
import time


@admin.register(ParsingInfo)
class ParsingInfoAdmin(PaidPermissionAdmin):
    list_display = ("full_name", "position", "company_name", "email", "send_email_button")
    search_fields = ("full_name", "position", "company_name", "email")
    list_filter = ("company_name", "email", "creator")

    # Include the beautiful CSS
    class Media:
        css = {
            'all': ('admin/css/beautiful_admin.css',),
        }

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(
            models.Q(creator=request.user) | 
            models.Q(parser_request__user=request.user)
        ).distinct()

    def save_model(self, request, obj, form, change):
        if not change or not obj.creator_id:
            obj.creator = request.user
        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj:
            readonly.append('creator')
        return readonly

    def send_email_button(self, obj):
        return format_html(
            '''
            <a href="{}" class="admin-btn admin-btn-green">
                <svg width="12" height="12" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M1.946 9.315c-.522-.174-.527-.455.01-.634l19.087-6.362c.529-.176.832.12.684.638l-5.454 19.086c-.15.529-.455.547-.679.045L12 14l6-8-8 6-8.054-2.685z"/>
                </svg>
                Send Mail
            </a>
            ''',
            f'{obj.pk}/send-email/'
        )
    send_email_button.short_description = "Actions"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:pk>/send-email/', self.admin_site.admin_view(self.send_email_view), name='send-email'),
        ]
        return custom_urls + urls

    def send_email_view(self, request, pk):
        parsing_info_obj = get_object_or_404(ParsingInfo, pk=pk)
        message_blueprint_obj = MessagesBlueprintText.objects.filter(
            creator=request.user
        ).order_by("?").first()

        if not message_blueprint_obj:
            self.message_user(request, "Нет доступных шаблонов сообщений для этого пользователя.", level="error")
            return redirect(request.META.get('HTTP_REFERER', '/admin/'))

        if parsing_info_obj.email is None:
            self.message_user(request, "Email Error.", level="error")
            return redirect(request.META.get('HTTP_REFERER', '/admin/'))

        smtp_send_mail.delay(message_blueprint_obj.id, parsing_info_obj.id)
        self.message_user(request, f"Письмо отправлено для {parsing_info_obj.full_name}.")
        return redirect(request.META.get('HTTP_REFERER', '/admin/'))


@admin.register(ParserRequest)
class ParserRequestAdmin(PaidPermissionAdmin):
    list_display = (
        'id', 'assigned_user_display', 'location', 'limit', 'start_page', 'end_page', 
        'status_badge', 'profiles_found', 'emails_extracted', 'created_at',
        'action_buttons'
    )
    list_filter = ('created_at', 'status', 'user', 'location')
    search_fields = ('location', 'user__email', 'user__first_name', 'user__last_name')
    
    # Include the beautiful CSS
    class Media:
        css = {
            'all': ('admin/css/beautiful_admin.css',),
        }
    
    fields = (
        'user',
        'keywords', 'location', 'limit', 'start_page', 'end_page',
        'status', 'current_page', 'profiles_found', 'emails_extracted',
        'error_message'
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

    def assigned_user_display(self, obj):
        if obj.user:
            return format_html(
                '<div style="display: flex; align-items: center; gap: 8px;">'
                '<div style="width: 8px; height: 8px; background: #10b981; border-radius: 50%;"></div>'
                '<span style="font-weight: 500;">{}</span>'
                '</div>',
                obj.user.email
            )
        return format_html(
            '<div style="display: flex; align-items: center; gap: 8px;">'
            '<div style="width: 8px; height: 8px; background: #ef4444; border-radius: 50%;"></div>'
            '<span style="color: #ef4444; font-weight: 500;">Unassigned</span>'
            '</div>'
        )
    assigned_user_display.short_description = "Assigned User"
    assigned_user_display.admin_order_field = "user__email"

    def status_badge(self, obj):
        """Display status as a beautiful badge with clean text only"""
        status_colors = {
            'completed': 'status-completed',
            'error': 'status-error', 
            'pending': 'status-pending',
            'running': 'status-running',
        }
        
        css_class = status_colors.get(obj.status.lower(), 'status-pending')
        
        return format_html(
            '<span class="status-badge {}">{}</span>',
            css_class, obj.status.title()
        )
    status_badge.short_description = "Status"
    status_badge.admin_order_field = "status"

    def action_buttons(self, obj):
        """Beautiful action buttons with proper CSS classes"""
        
        buttons_html = '<div style="display: flex; flex-wrap: wrap; gap: 8px; align-items: center; justify-content: center;">'
        
        # Start button
        if obj.user:
            buttons_html += f'''
                <a href="{obj.pk}/start-parser/" class="admin-btn admin-btn-blue">
                    <svg width="12" height="12" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M8 5v14l11-7z"/>
                    </svg>
                    Start
                </a>
            '''
        else:
            buttons_html += '''
                <span class="admin-btn admin-btn-red" style="cursor: not-allowed; opacity: 0.7;">
                    No User
                </span>
            '''
        
        # Dashboard button
        buttons_html += f'''
            <a href="/parser_controler/dashboard/{obj.id}" target="_blank" class="admin-btn admin-btn-green">
                <svg width="12" height="12" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/>
                </svg>
                Monitor
            </a>
        '''
        
        # VNC button
        vnc_button = self.get_vnc_button(obj)
        if vnc_button:
            buttons_html += vnc_button
        
        buttons_html += '</div>'
        
        return format_html(buttons_html)
    
    action_buttons.short_description = "Actions"

    def get_vnc_button(self, obj):
        """Get VNC button with beautiful CSS styling"""
        try:
            r = redis.Redis(host="redis", port=6379, decode_responses=True)
            all_containers = r.hgetall("captcha_containers")
            
            for container_key, value in all_containers.items():
                try:
                    data = json.loads(value)
                    cred_match = str(data.get("cred_id")) == str(obj.id)
                    novnc_port = data.get("novnc_port")
                    status = data.get("status", "").lower()
                    
                    if cred_match and novnc_port and status in ["starting", "ready", "solving"]:
                        return f'''
                            <a href="http://localhost:{novnc_port}/auto_connect.html" target="_blank" class="admin-btn admin-btn-purple">
                                <svg width="12" height="12" fill="currentColor" viewBox="0 0 24 24">
                                    <path d="M20 3H4c-1.11 0-2 .89-2 2v11c0 1.11.89 2 2 2h3l-1 1v1h1l.5-.5.5.5h8l.5-.5.5.5h1v-1l-1-1h3c1.11 0 2-.89 2-2V5c0-1.11-.89-2-2-2zM2 5c0-.55.45-1 1-1h16c.55 0 1 .45 1 1v11c0 .55-.45 1-1 1H3c-.55 0-1-.45-1-1V5z"/>
                                </svg>
                                VNC
                            </a>
                        '''
                except json.JSONDecodeError:
                    continue
            
            return None
            
        except Exception as e:
            return None

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:pk>/start-parser/', self.admin_site.admin_view(self.start_parser_view), name='start-parser'),
            path('api/active-containers/', self.admin_site.admin_view(self.api_active_containers), name='api-active-containers'),
        ]
        return custom_urls + urls

    def start_parser_view(self, request, pk):
        obj = get_object_or_404(ParserRequest, pk=pk)
        
        if not obj.user:
            self.message_user(request, "Cannot start parsing: No user assigned to this request.", level="error")
            return redirect(request.META.get('HTTP_REFERER', '/admin/'))
        
        start_parsing.apply_async(kwargs={
            "keywords": obj.keywords,
            "location": obj.location,
            "limit": obj.limit,
            "start_page": obj.start_page,
            "end_page": obj.end_page,
            "parser_request_id": obj.id,
            "user_email": obj.user.email,
            "creator_email": obj.user.email,
            "creator_id": obj.user.id
        })
        self.message_user(request, f"Parsing task for location '{obj.location}' assigned to {obj.user.email} has been started.")
        return redirect(request.META.get('HTTP_REFERER', '/admin/'))

    def api_active_containers(self, request):
        """API endpoint that frontend polls"""
        try:
            r = redis.Redis(host="redis", port=6379, decode_responses=True)
            all_containers = r.hgetall("captcha_containers")
            
            active_containers = []
            
            for container_key, value in all_containers.items():
                try:
                    data = json.loads(value)
                    status = data.get("status", "").lower()
                    
                    if status in ["starting", "ready", "solving"] and data.get("novnc_port"):
                        active_containers.append({
                            "container_id": data.get("container_id"),
                            "email": data.get("email", "unknown"),
                            "cred_id": data.get("cred_id"),
                            "novnc_port": data.get("novnc_port"),
                            "vnc_port": data.get("vnc_port"),
                            "status": status,
                            "created_at": data.get("created_at"),
                            "auto_connect_url": f"http://localhost:{data.get('novnc_port')}/auto_connect.html"
                        })
                        
                except json.JSONDecodeError:
                    continue
            
            return JsonResponse({
                "status": "success",
                "containers": active_containers,
                "count": len(active_containers),
                "timestamp": time.time()
            })
            
        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": str(e),
                "containers": []
            })