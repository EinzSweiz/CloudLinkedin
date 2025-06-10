# Add this to: b2b_linkedin_app/b2b_linkedin_app/views.py

from django.shortcuts import render
from django.http import JsonResponse
import requests
import socket

def vnc_monitor(request):
    """Serve the VNC monitor page"""
    return render(request, 'vnc/vnc_monitor.html')

def vnc_status_api(request):
    """API endpoint to check VNC status - bypasses CORS"""
    try:
        # Try to connect to the VNC websockify server
        response = requests.get('http://captcha_watcher:6080/', timeout=5)
        
        return JsonResponse({
            'status': 'success',
            'message': 'VNC server accessible',
            'http_status': response.status_code,
            'vnc_url': 'http://localhost:6080/',
            'vnc_manual': 'http://localhost:6080/vnc.html'
        })
    except requests.exceptions.ConnectionError:
        return JsonResponse({
            'status': 'error',
            'message': 'Cannot connect to VNC server - container may be down',
            'vnc_url': 'http://localhost:6080/',
        })
    except requests.exceptions.Timeout:
        return JsonResponse({
            'status': 'error',
            'message': 'VNC server timeout - slow response',
            'vnc_url': 'http://localhost:6080/',
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'VNC server error: {str(e)}',
            'vnc_url': 'http://localhost:6080/',
        })

def check_vnc_ports(request):
    """Check if VNC ports are accessible"""
    ports_status = {}
    
    # Check VNC port 5900
    try:
        sock = socket.create_connection(('captcha_watcher', 5900), timeout=3)
        sock.close()
        ports_status['vnc_5900'] = 'open'
    except:
        ports_status['vnc_5900'] = 'closed'
    
    # Check websockify port 6080
    try:
        sock = socket.create_connection(('captcha_watcher', 6080), timeout=3)
        sock.close()
        ports_status['websockify_6080'] = 'open'
    except:
        ports_status['websockify_6080'] = 'closed'
    
    return JsonResponse({
        'status': 'success',
        'ports': ports_status,
        'overall_status': 'healthy' if all(status == 'open' for status in ports_status.values()) else 'unhealthy'
    })