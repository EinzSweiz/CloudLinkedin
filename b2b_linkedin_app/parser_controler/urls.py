# parser_controler/urls.py - Updated with browser captcha URLs
from django.urls import path
from .views import (
    solve_captcha_vnc, 
    solve_captcha_browser,
    captcha_iframe,
    captcha_status_api,
    captcha_dashboard
)

urlpatterns = [
    # VNC captcha (existing)
    path("admin/solve-captcha-vnc/", solve_captcha_vnc, name="solve_captcha_vnc"),
    
    # Browser captcha (new)
    path("admin/solve-captcha/", solve_captcha_browser, name="solve_captcha_browser"),
    path("admin/captcha/iframe/", captcha_iframe, name="captcha_iframe"),
    path("admin/captcha/api/", captcha_status_api, name="captcha_status_api"),
    path("admin/captcha/dashboard/", captcha_dashboard, name="captcha_dashboard"),
]