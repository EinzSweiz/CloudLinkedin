# parser_controler/urls.py - Enhanced with full automation endpoints
from django.urls import path
from .views import (
    # Enhanced VNC interface
    solve_captcha_vnc,
    
    # Fully automated CAPTCHA solving
    start_automated_captcha_solver,
    captcha_container_status,
    active_captcha_sessions,
    stop_captcha_container,
    cleanup_dead_containers,
    
    # Real-time monitoring
    stream_captcha_logs,
    captcha_dashboard_data,
    captcha_webhook,
    
    # Health and utilities
    health_check
)

urlpatterns = [
    # Main interfaces
    path("admin/solve-captcha-vnc/", solve_captcha_vnc, name="solve_captcha_vnc"),
    
    # Fully automated CAPTCHA solving API
    path("api/captcha/start-automated/", start_automated_captcha_solver, name="start_automated_captcha"),
    path("api/captcha/status/<str:container_id>/", captcha_container_status, name="captcha_status"),
    path("api/captcha/sessions/", active_captcha_sessions, name="active_sessions"),
    path("api/captcha/stop/<str:container_id>/", stop_captcha_container, name="stop_captcha"),
    path("api/captcha/cleanup/", cleanup_dead_containers, name="cleanup_containers"),
    
    # Real-time monitoring
    path("api/captcha/logs/<str:container_id>/", stream_captcha_logs, name="stream_logs"),
    path("api/captcha/dashboard/", captcha_dashboard_data, name="dashboard_data"),
    
    # Webhooks and notifications
    path("webhook/captcha/", captcha_webhook, name="captcha_webhook"),
    
    # Health check
    path("health/", health_check, name="health_check"),
    
    # Legacy compatibility (deprecated but maintained)
    path("start-captcha-container/", start_automated_captcha_solver, name="legacy_start_captcha"),
    path("active-containers/", active_captcha_sessions, name="legacy_active_containers"),
]

# WebSocket URL patterns (if using Django Channels)
# websocket_urlpatterns = [
#     path("ws/captcha/status/", CaptchaStatusConsumer.as_asgi()),
#     path("ws/captcha/logs/<str:container_id>/", CaptchaLogsConsumer.as_asgi()),
# ]