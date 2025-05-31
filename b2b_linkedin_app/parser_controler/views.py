# parser_controler/views.py - Fixed import path
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required

from parser.engine.core.captcha_handler import browser_captcha_handler

@staff_member_required
def solve_captcha_vnc(request):
    return render(request, "vnc/solve_captcha.html")

@staff_member_required
def solve_captcha_browser(request):
    """Show captcha resolution interface in browser"""
    session_id = request.GET.get('session')
    
    if not session_id:
        return HttpResponse("No captcha session specified", status=400)
    
    session_data = browser_captcha_handler.get_session_data(session_id)
    
    if not session_data:
        return HttpResponse("Captcha session not found or expired", status=404)
    
    context = {
        'session_id': session_id,
        'email': session_data.get('email'),
        'current_url': session_data.get('current_url'),
        'created_at': session_data.get('created_at'),
        'screenshot_path': session_data.get('screenshot_path', '').replace('/app/shared_volume/', '/static/captcha/')
    }
    
    return render(request, "captcha/solve_captcha_browser.html", context)

@staff_member_required
def captcha_iframe(request):
    """Serve LinkedIn captcha in iframe"""
    session_id = request.GET.get('session')
    
    if not session_id:
        return HttpResponse("No session specified", status=400)
    
    session_data = browser_captcha_handler.get_session_data(session_id)
    
    if not session_data:
        return HttpResponse("Session not found", status=404)
    
    # Create an iframe that loads LinkedIn with the saved cookies
    linkedin_url = session_data.get('current_url', 'https://www.linkedin.com/login')
    
    context = {
        'linkedin_url': linkedin_url,
        'session_id': session_id,
        'cookies': json.dumps(session_data.get('cookies', [])),
        'user_agent': session_data.get('user_agent', '')
    }
    
    return render(request, "captcha/captcha_iframe.html", context)

@csrf_exempt
@staff_member_required
def captcha_status_api(request):
    """API endpoint to check/update captcha status"""
    
    if request.method == 'GET':
        # Get status of all pending captchas
        pending_sessions = browser_captcha_handler.get_all_pending_sessions()
        return JsonResponse({
            'pending_count': len(pending_sessions),
            'sessions': pending_sessions
        })
    
    elif request.method == 'POST':
        # Update captcha status
        data = json.loads(request.body)
        session_id = data.get('session_id')
        action = data.get('action')  # 'resolved' or 'failed'
        
        if not session_id or not action:
            return JsonResponse({'error': 'Missing session_id or action'}, status=400)
        
        if action == 'resolved':
            success = browser_captcha_handler.mark_session_resolved(session_id)
        elif action == 'failed':
            success = browser_captcha_handler.mark_session_failed(session_id)
        else:
            return JsonResponse({'error': 'Invalid action'}, status=400)
        
        return JsonResponse({'success': success})

@staff_member_required
def captcha_dashboard(request):
    """Dashboard showing all active captcha sessions"""
    pending_sessions = browser_captcha_handler.get_all_pending_sessions()
    
    context = {
        'pending_sessions': pending_sessions,
        'pending_count': len(pending_sessions)
    }
    
    return render(request, "captcha/dashboard.html", context)