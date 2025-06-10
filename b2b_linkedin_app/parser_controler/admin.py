# parser_controler/admin.py - SIMPLIFIED VERSION

from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect, get_object_or_404
from django.utils.html import format_html
from django.http import JsonResponse
from .models import ParsingInfo, ParserRequest
from .tasks import start_parsing
from b2b_linkedin_app.permissions import PaidPermissionAdmin
import redis
import json
import time

@admin.register(ParsingInfo)
class ParsingInfoAdmin(PaidPermissionAdmin):
    list_display = ("full_name", "position", "company_name", "email")
    search_fields = ("full_name", "position", "company_name", "email")

@admin.register(ParserRequest)
class ParserRequestAdmin(PaidPermissionAdmin):
    list_display = (
        'location', 'limit', 'start_page', 'end_page', 'created_at', 'status', 
        'start_parser_button', 'dashboard_button', 'open_vnc'
    )
    list_filter = ('created_at', 'status')
    search_fields = ('location',)

    def dashboard_button(self, obj):
        """Link to real-time dashboard for this parsing request"""
        return format_html(
            '<a class="button" href="/parser_controler/dashboard/{}" target="_blank" style="background: #4ade80; color: white; margin-left: 5px;">📊 Dashboard</a>',
            obj.id
        )
    dashboard_button.short_description = "Monitor"

    def open_vnc(self, obj):
        """Simple VNC indicator - check if there's an active VNC for this request"""
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
                        return format_html(
                            '<a href="http://localhost:{}/auto_connect.html" target="_blank" style="color: green; font-weight: bold;">🖥️ Port:{}</a>',
                            novnc_port, novnc_port
                        )
                except json.JSONDecodeError:
                    continue
            
            return format_html('<span style="color: gray;">No VNC</span>')
            
        except Exception as e:
            return format_html('<span style="color: red;">Error</span>')

    open_vnc.short_description = "VNC"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:pk>/start-parser/', self.admin_site.admin_view(self.start_parser_view), name='start-parser'),
            path('api/active-containers/', self.admin_site.admin_view(self.api_active_containers), name='api-active-containers'),
        ]
        return custom_urls + urls

    def start_parser_button(self, obj):
        return format_html('<a class="button" href="{}">Start</a>', f'{obj.pk}/start-parser/')
    start_parser_button.short_description = "Actions"

    def start_parser_view(self, request, pk):
        obj = get_object_or_404(ParserRequest, pk=pk)
        start_parsing.apply_async(kwargs={
            "keywords": obj.keywords,
            "location": obj.location,
            "limit": obj.limit,
            "start_page": obj.start_page,
            "end_page": obj.end_page,
            "parser_request_id": obj.id,
        })
        self.message_user(request, f"Parsing task for location '{obj.location}' has been started.")
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