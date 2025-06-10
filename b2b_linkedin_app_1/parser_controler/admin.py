from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect, get_object_or_404
from django.utils.html import format_html
from django.template.loader import render_to_string
from .models import ParsingInfo, ParserRequest
from .tasks import start_parsing
from b2b_linkedin_app.permissions import PaidPermissionAdmin

@admin.register(ParsingInfo)
class ParsingInfoAdmin(PaidPermissionAdmin):
    list_display = ("full_name", "position", "company_name", "email")
    search_fields = ("full_name", "position", "company_name", "email")


@admin.register(ParserRequest)
class ParserRequestAdmin(PaidPermissionAdmin):
    list_display = (
        'location', 'limit', 'start_page', 'end_page', 'created_at', 'status', 'start_parser_button', 'open_vnc'
    )
    list_filter = ('created_at', 'status')
    search_fields = ('location',)

    def open_vnc(self, obj):
        return render_to_string("vnc/open_vnc_monitor.html")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:pk>/start-parser/', self.admin_site.admin_view(self.start_parser_view), name='start-parser'),
        ]
        return custom_urls + urls

    def start_parser_button(self, obj):
        return format_html('<a class="button" href="{}">Start</a>', f'{obj.pk}/start-parser/')

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
