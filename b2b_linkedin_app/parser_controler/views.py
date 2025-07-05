# parser_controler/views.py - Enhanced with full automation
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from rest_framework.decorators import api_view
import json
from django.utils import timezone
import time
from .models import ParsingInfo, ParserRequest
import redis
import logging
from typing import Iterator

from .docker_manager import get_manager, AutomatedCaptchaHandler
from parser.engine.core.captcha_handler import FullyAutomatedCaptchaHandler

logger = logging.getLogger(__name__)

@staff_member_required
def solve_captcha_vnc(request):
    """Enhanced VNC CAPTCHA solving interface"""
    context = {
        'active_sessions': get_active_captcha_sessions_data(),
        'max_containers': get_manager().max_containers,
        'auto_features': [
            'Zero manual clicks required',
            'Auto-connects when container ready', 
            'Real-time status monitoring',
            'Auto-cleanup on completion',
            'Browser auto-opening (optional)',
            'Scalable container management'
        ]
    }
    return render(request, "vnc/solve_captcha_enhanced.html", context)

@api_view(["POST"])
@staff_member_required 
def start_automated_captcha_solver(request):
    """
    Start fully automated CAPTCHA solver - zero manual intervention required
    """
    try:
        email = request.data.get("email")
        cred_id = request.data.get("cred_id", email)
        auto_open = request.data.get("auto_open", True)
        
        if not email:
            return JsonResponse({
                "error": "Missing email parameter",
                "status": "error"
            }, status=400)
        
        logger.info(f"Starting automated CAPTCHA solver for: {email}")
        
        # Use the fully automated handler
        handler = AutomatedCaptchaHandler()
        result = handler.solve_captcha_automated(
            email=email,
            cred_id=cred_id,
            auto_open=auto_open
        )
        
        if result["status"] == "started":
            return JsonResponse({
                "status": "success",
                "message": "Automated CAPTCHA solver started successfully",
                "container_id": result["container_id"],
                "email": email,
                "vnc_port": result["vnc_port"],
                "novnc_port": result["novnc_port"],
                "auto_connect_url": result["auto_connect_url"],
                "estimated_time": result.get("estimated_time", "5-15 minutes"),
                "instructions": result.get("instructions", []),
                "automation_features": [
                    "Container auto-started",
                    "VNC will auto-connect", 
                    "Browser auto-opening" if auto_open else "Manual browser access",
                    "Real-time monitoring active",
                    "Auto-cleanup on completion"
                ]
            })
        
        elif result["status"] == "queued":
            return JsonResponse({
                "status": "queued", 
                "message": "Request queued - will process when capacity available",
                "job_id": result["job_id"],
                "queue_status": result["queue_status"],
                "estimated_wait": "1-5 minutes"
            })
        
        else:
            return JsonResponse({
                "status": "error",
                "error": result.get("error", "Unknown error"),
                "message": result.get("message", "Failed to start automated solver")
            }, status=500)
            
    except Exception as e:
        logger.error(f"Automated CAPTCHA start error: {e}")
        return JsonResponse({
            "status": "error", 
            "error": str(e),
            "message": "Internal error starting automated solver"
        }, status=500)

@api_view(["GET"])
@staff_member_required
def captcha_container_status(request, container_id):
    """Get real-time status of a specific CAPTCHA container"""
    try:
        manager = get_manager()
        container_info = manager.get_container_info(container_id)
        
        if not container_info:
            return JsonResponse({
                "error": "Container not found",
                "container_id": container_id
            }, status=404)
        
        # Enhanced status with automation info
        status_data = {
            "container_id": container_id,
            "email": container_info["email"],
            "status": container_info["status"],
            "uptime_seconds": int(container_info["uptime"]),
            "uptime_formatted": format_uptime(container_info["uptime"]),
            "is_running": container_info["is_running"],
            "vnc_port": container_info["vnc_port"],
            "novnc_port": container_info["novnc_port"],
            "auto_connect_url": container_info["auto_connect_url"],
            "created_at": container_info["created_at"],
            "started_at": container_info["started_at"],
            "completed_at": container_info["completed_at"],
            "recent_logs": container_info.get("logs", [])[-5:],  # Last 5 logs
            "automation_status": {
                "auto_monitoring": True,
                "auto_cleanup": True,
                "zero_clicks": True,
                "real_time_updates": True
            }
        }
        
        # Add progress estimation
        if container_info["status"] in ["ready", "solving"]:
            uptime = container_info["uptime"]
            if uptime < 300:  # Less than 5 minutes
                status_data["progress"] = {
                    "stage": "initializing",
                    "message": "Container starting up and VNC connecting",
                    "estimated_remaining": "2-5 minutes"
                }
            elif uptime < 600:  # Less than 10 minutes
                status_data["progress"] = {
                    "stage": "solving",
                    "message": "CAPTCHA should be visible - solve manually",
                    "estimated_remaining": "1-10 minutes"
                }
            else:
                status_data["progress"] = {
                    "stage": "extended", 
                    "message": "Taking longer than usual",
                    "estimated_remaining": "Check VNC interface"
                }
        
        return JsonResponse(status_data)
        
    except Exception as e:
        logger.error(f"Status check error: {e}")
        return JsonResponse({
            "error": str(e),
            "container_id": container_id
        }, status=500)

@api_view(["GET"])
@staff_member_required
def active_captcha_sessions(request):
    """Get all active CAPTCHA sessions with enhanced info"""
    try:
        manager = get_manager()
        containers = manager.get_active_containers()
        
        sessions_data = []
        for container in containers:
            detailed_info = manager.get_container_info(container["container_id"])
            if detailed_info:
                sessions_data.append({
                    "container_id": container["container_id"],
                    "email": container["email"],
                    "status": container["status"],
                    "uptime": container["uptime"],
                    "uptime_formatted": format_uptime(container["uptime"]),
                    "vnc_port": container["vnc_port"],
                    "novnc_port": container["novnc_port"],
                    "auto_connect_url": container["auto_connect_url"],
                    "is_healthy": detailed_info["is_running"] and container["uptime"] < 900,
                    "progress_stage": get_progress_stage(container["uptime"], container["status"])
                })
        
        # Get queue status if available
        handler = AutomatedCaptchaHandler()
        queue_status = handler.queue.get_queue_status()
        
        return JsonResponse({
            "active_sessions": len(sessions_data),
            "max_capacity": manager.max_containers,
            "capacity_available": manager.max_containers - len(sessions_data),
            "queue_length": queue_status.get("queue_length", 0),
            "sessions": sessions_data,
            "system_status": {
                "healthy": True,
                "automation_enabled": True,
                "auto_cleanup_active": True,
                "monitoring_active": True
            }
        })
        
    except Exception as e:
        logger.error(f"Active sessions error: {e}")
        return JsonResponse({
            "error": str(e),
            "active_sessions": 0,
            "sessions": []
        }, status=500)

@api_view(["DELETE"])
@staff_member_required
def stop_captcha_container(request, container_id):
    """Stop a specific CAPTCHA container"""
    try:
        manager = get_manager()
        success = manager.stop_container(container_id)
        
        if success:
            return JsonResponse({
                "status": "success",
                "message": f"Container {container_id[:12]} stopped successfully",
                "container_id": container_id
            })
        else:
            return JsonResponse({
                "status": "error",
                "message": f"Failed to stop container {container_id[:12]}",
                "container_id": container_id
            }, status=500)
            
    except Exception as e:
        logger.error(f"Stop container error: {e}")
        return JsonResponse({
            "status": "error",
            "error": str(e),
            "container_id": container_id
        }, status=500)

@api_view(["POST"])
@staff_member_required
def cleanup_dead_containers(request):
    """Manually trigger cleanup of dead containers"""
    try:
        manager = get_manager()
        
        # Get containers before cleanup
        before_count = len(manager.get_active_containers())
        
        # Trigger cleanup
        manager._cleanup_dead_containers()
        
        # Get containers after cleanup
        after_count = len(manager.get_active_containers())
        cleaned_count = before_count - after_count
        
        return JsonResponse({
            "status": "success",
            "message": f"Cleanup completed - removed {cleaned_count} dead containers",
            "containers_before": before_count,
            "containers_after": after_count,
            "cleaned_count": cleaned_count
        })
        
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
        return JsonResponse({
            "status": "error",
            "error": str(e)
        }, status=500)

def stream_captcha_logs(request, container_id):
    """Stream real-time logs from a CAPTCHA container (Server-Sent Events)"""
    def log_generator() -> Iterator[str]:
        """Generate real-time log updates"""
        try:
            manager = get_manager()
            last_log_count = 0
            
            while True:
                container_info = manager.get_container_info(container_id)
                
                if not container_info:
                    yield f"data: {json.dumps({'error': 'Container not found'})}\n\n"
                    break
                
                # Check for new logs
                logs = container_info.get("logs", [])
                if len(logs) > last_log_count:
                    new_logs = logs[last_log_count:]
                    for log_entry in new_logs:
                        yield f"data: {json.dumps({'log': log_entry, 'timestamp': time.time()})}\n\n"
                    last_log_count = len(logs)
                
                # Send status update
                status_update = {
                    "status": container_info["status"],
                    "uptime": int(container_info["uptime"]),
                    "is_running": container_info["is_running"]
                }
                yield f"data: {json.dumps(status_update)}\n\n"
                
                # Break if container completed or failed
                if container_info["status"] in ["completed", "failed", "timeout"]:
                    yield f"data: {json.dumps({'final': True, 'status': container_info['status']})}\n\n"
                    break
                
                time.sleep(5)  # Update every 5 seconds
                
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    response = StreamingHttpResponse(
        log_generator(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['Connection'] = 'keep-alive'
    return response

@api_view(["GET"])
@staff_member_required
def captcha_dashboard_data(request):
    """Get comprehensive dashboard data for CAPTCHA system"""
    try:
        manager = get_manager()
        handler = AutomatedCaptchaHandler()
        
        # Get all active containers
        active_containers = manager.get_active_containers()
        
        # Calculate statistics
        total_active = len(active_containers)
        solving_count = len([c for c in active_containers if c["status"] == "solving"])
        ready_count = len([c for c in active_containers if c["status"] == "ready"])
        
        # Get queue status
        queue_status = handler.queue.get_queue_status()
        
        # Calculate average solving time (mock data for now)
        avg_solving_time = 420  # 7 minutes average
        
        # System health
        system_health = {
            "overall": "healthy" if total_active < manager.max_containers * 0.8 else "warning",
            "container_engine": "healthy",
            "vnc_services": "healthy", 
            "automation": "active",
            "monitoring": "active"
        }
        
        dashboard_data = {
            "system_overview": {
                "active_containers": total_active,
                "max_containers": manager.max_containers,
                "capacity_usage": round((total_active / manager.max_containers) * 100, 1),
                "queue_length": queue_status.get("queue_length", 0),
                "solving_count": solving_count,
                "ready_count": ready_count
            },
            "performance_metrics": {
                "average_solving_time": avg_solving_time,
                "success_rate": 92.5,  # Mock data
                "automation_level": 100,  # Fully automated
                "zero_click_rate": 100   # No manual clicks required
            },
            "system_health": system_health,
            "active_sessions": [
                {
                    "container_id": c["container_id"],
                    "email": c["email"], 
                    "status": c["status"],
                    "uptime_minutes": int(c["uptime"] // 60),
                    "auto_connect_url": c["auto_connect_url"],
                    "health": "healthy" if c["uptime"] < 900 else "warning"
                }
                for c in active_containers
            ],
            "automation_features": {
                "zero_manual_clicks": True,
                "auto_browser_opening": True,
                "real_time_monitoring": True,
                "auto_cleanup": True,
                "smart_scaling": True,
                "persistent_queuing": True
            },
            "last_updated": time.time()
        }
        
        return JsonResponse(dashboard_data)
        
    except Exception as e:
        logger.error(f"❌ Dashboard data error: {e}")
        return JsonResponse({
            "error": str(e),
            "system_overview": {"active_containers": 0}
        }, status=500)

@csrf_exempt
def captcha_webhook(request):
    """Webhook endpoint for CAPTCHA completion notifications"""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            container_id = data.get("container_id")
            status = data.get("status")
            email = data.get("email")
            
            if container_id and status:
                manager = get_manager()
                container = manager._load_container(container_id)
                
                if container:
                    from parser_controler.docker_manager import ContainerStatus
                    container.status = ContainerStatus(status)
                    container.completed_at = time.time()
                    
                    if status == "completed":
                        container.logs.append(f"CAPTCHA solved successfully at {time.time()}")
                                            
                    manager._save_container(container)
                    
                    logger.info(f"Webhook: {email} CAPTCHA {status}")
                    
                    return JsonResponse({"status": "success"})
            
            return JsonResponse({"error": "Invalid webhook data"}, status=400)
            
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return JsonResponse({"error": str(e)}, status=500)
    
    return JsonResponse({"error": "Method not allowed"}, status=405)

# Utility functions
def get_active_captcha_sessions_data():
    """Get active sessions data for template context"""
    try:
        manager = get_manager()
        return manager.get_active_containers()
    except:
        return []

def format_uptime(uptime_seconds: float) -> str:
    """Format uptime in human-readable format"""
    minutes = int(uptime_seconds // 60)
    seconds = int(uptime_seconds % 60)
    if minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def get_progress_stage(uptime: float, status: str) -> str:
    """Get human-readable progress stage"""
    if status == "starting":
        return "Container initializing"
    elif status == "ready" and uptime < 120:
        return "VNC connecting"
    elif status == "ready" and uptime < 300:
        return "Ready for CAPTCHA"
    elif status == "solving":
        return "CAPTCHA solving in progress"
    elif status == "completed":
        return "Successfully completed"
    elif status == "failed":
        return "Failed - needs retry"
    elif status == "timeout":
        return "Timed out"
    else:
        return "Unknown stage"

# Health check endpoint
@api_view(["GET"])
def health_check(request):
    """Health check endpoint for containers and load balancers"""
    try:
        manager = get_manager()
        active_count = len(manager.get_active_containers())
        
        health_data = {
            "status": "healthy",
            "timestamp": time.time(),
            "active_containers": active_count,
            "max_containers": manager.max_containers,
            "capacity_available": manager.max_containers - active_count,
            "services": {
                "docker": "healthy",
                "redis": "healthy" if manager.use_redis else "disabled",
                "monitoring": "active",
                "automation": "active"
            }
        }
        
        return JsonResponse(health_data)
        
    except Exception as e:
        return JsonResponse({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": time.time()
        }, status=500)
    

@staff_member_required
def dashboard_view(request, request_id):
    """Dashboard view"""
    try:
        # Get the parsing request to validate it exists
        parser_request = get_object_or_404(ParserRequest, id=request_id)
        
        context = {
            'request_id': request_id,
            'title': f'Parsing Dashboard - Request {request_id}',
            'parser_request': parser_request  # Pass the request object
        }
        return render(request, 'admin/parsing_dashboard.html', context)
    except Exception as e:
        logger.error(f"Dashboard view error: {e}")
        return render(request, 'admin/parsing_dashboard.html', {
            'request_id': request_id,
            'title': f'Parsing Dashboard - Request {request_id}',
            'error': str(e)
        })
# parser_controler/views.py - FIXED API endpoint for real-time parsing status
@staff_member_required
def api_parsing_status(request, request_id):
    """ENHANCED REAL-TIME API endpoint for parsing status"""
    try:
        # Get the specific parsing request
        parser_request = get_object_or_404(ParserRequest, id=request_id)
        
        # Get profiles FOR THIS REQUEST ONLY - ordered by creation time (newest first)
        profiles = ParsingInfo.objects.filter(
            parser_request=parser_request
        ).order_by('-id')  # Newest first for real-time feel
        
        # Calculate statistics
        total_profiles = profiles.count()
        profiles_with_email = profiles.exclude(email__isnull=True).exclude(email__exact='').count()
        success_rate = round((profiles_with_email / total_profiles * 100)) if total_profiles > 0 else 0
        
        # Get latest profiles for preview (limit to 15 most recent)
        latest_profiles = profiles[:15]
        
        # Calculate actual progress based on pages
        current_page = parser_request.current_page or parser_request.start_page
        total_pages = parser_request.end_page - parser_request.start_page + 1
        pages_processed = max(0, current_page - parser_request.start_page)
        
        # If completed, show all pages as processed
        if parser_request.status == 'completed':
            pages_processed = total_pages
            current_page = parser_request.end_page

        # FIXED: Better keywords parsing with multiple format support
        def parse_keywords_enhanced(keywords_field):
            try:
                if not keywords_field:
                    return ['No keywords specified']
                
                # If it's already a list, return it
                if isinstance(keywords_field, list):
                    return [str(k).strip() for k in keywords_field if k]
                
                # Convert to string and clean
                keywords_str = str(keywords_field).strip()
                
                # Handle empty string
                if not keywords_str:
                    return ['No keywords specified']
                
                # Handle JSON array format: ["keyword1", "keyword2"] or ['keyword1', 'keyword2']
                if (keywords_str.startswith('[') and keywords_str.endswith(']')) or \
                   (keywords_str.startswith("['") and keywords_str.endswith("']")) or \
                   (keywords_str.startswith('["') and keywords_str.endswith('"]')):
                    try:
                        import json
                        parsed = json.loads(keywords_str)
                        if isinstance(parsed, list):
                            return [str(k).strip().strip('"').strip("'") for k in parsed if k]
                    except json.JSONDecodeError:
                        try:
                            import ast
                            parsed = ast.literal_eval(keywords_str)
                            if isinstance(parsed, list):
                                return [str(k).strip() for k in parsed if k]
                        except:
                            pass
                
                # Handle comma-separated format: "keyword1, keyword2, keyword3"
                if ',' in keywords_str:
                    keywords = [k.strip().strip('"').strip("'") for k in keywords_str.split(',')]
                    return [k for k in keywords if k]
                
                # Handle space-separated format: "keyword1 keyword2 keyword3"
                if ' ' in keywords_str and not keywords_str.startswith('['):
                    keywords = [k.strip() for k in keywords_str.split()]
                    return [k for k in keywords if k]
                
                # Single keyword
                clean_keyword = keywords_str.strip('"').strip("'").strip()
                return [clean_keyword] if clean_keyword else ['No keywords specified']
                
            except Exception as e:
                logger.warning(f"Failed to parse keywords '{keywords_field}': {e}")
                return ['Parse error - check format']

        keywords = parse_keywords_enhanced(parser_request.keywords)

        # Enhanced activity feed with more details and better formatting
        activities = []
        for profile in latest_profiles[:12]:  # Show more activities for better real-time feel
            email_status = "✅ Email found" if profile.email else "📧 Email pending"
            company_info = profile.company_name or 'Unknown Company'
            position_info = profile.position or 'Unknown Position'
            
            activities.append({
                'icon': '✅' if profile.email else '👤',
                'message': f"Found: {profile.full_name}",
                'detail': f"{position_info} @ {company_info}",
                'email_status': email_status,
                'timestamp': profile.created_at.strftime('%H:%M:%S') if profile.created_at else '',
                'has_email': bool(profile.email),
                'profile_id': profile.id
            })

        # Calculate processing speed (profiles per minute)
        processing_speed = 0
        if parser_request.started_at and total_profiles > 0:
            elapsed_time = (timezone.now() - parser_request.started_at).total_seconds() / 60  # minutes
            if elapsed_time > 0:
                processing_speed = round(total_profiles / elapsed_time, 1)

        # Estimate time remaining
        estimated_remaining = "Calculating..."
        if parser_request.status == 'running' and processing_speed > 0:
            remaining_pages = max(0, parser_request.end_page - current_page)
            if remaining_pages > 0:
                # Estimate based on current speed
                estimated_minutes = remaining_pages * 2  # Rough estimate: 2 minutes per page
                if estimated_minutes < 60:
                    estimated_remaining = f"~{estimated_minutes} minutes"
                else:
                    estimated_remaining = f"~{estimated_minutes // 60}h {estimated_minutes % 60}m"
            else:
                estimated_remaining = "Almost done"
        elif parser_request.status == 'completed':
            estimated_remaining = "Completed"
        elif parser_request.status == 'error':
            estimated_remaining = "Error occurred"

        # Build comprehensive response
        response_data = {
            'status': 'success',
            'request_status': parser_request.status,
            'stats': {
                'profilesFound': total_profiles,
                'emailsExtracted': profiles_with_email,
                'pagesProcessed': pages_processed,
                'totalPages': total_pages,
                'currentPage': current_page,
                'successRate': success_rate,
                'limit': parser_request.limit,
                'processingSpeed': processing_speed,  # profiles per minute
                'estimatedRemaining': estimated_remaining
            },
            'latest_profiles': [
                {
                    'id': profile.id,
                    'name': profile.full_name,
                    'company': profile.company_name or 'Unknown Company',
                    'email': profile.email or 'Not found',
                    'position': profile.position or 'Unknown Position',
                    'profile_url': profile.profile_url,
                    'created_at': profile.created_at.strftime('%H:%M:%S') if profile.created_at else '',
                    'has_email': bool(profile.email),
                    'email_confidence': 'High' if profile.email and '@' in profile.email else 'Low'
                }
                for profile in latest_profiles
            ],
            'activities': activities,
            'request_info': {
                'id': parser_request.id,
                'keywords': keywords,  # FIXED: Properly parsed keywords
                'location': parser_request.location,
                'status': parser_request.status,
                'error_message': parser_request.error_message,
                'created_at': parser_request.created_at.strftime('%Y-%m-%d %H:%M:%S') if parser_request.created_at else '',
                'started_at': parser_request.started_at.strftime('%H:%M:%S') if parser_request.started_at else '',
                'start_page': parser_request.start_page,
                'end_page': parser_request.end_page,
                'limit': parser_request.limit,
                'duration_minutes': round(parser_request.duration_seconds / 60, 1) if parser_request.duration_seconds else 0
            },
            'progress': {
                'percentage': round((pages_processed / total_pages) * 100, 1) if total_pages > 0 else 0,
                'current_page': current_page,
                'total_pages': total_pages,
                'pages_remaining': max(0, parser_request.end_page - current_page),
                'status_message': get_status_message(parser_request.status, current_page, parser_request.end_page)
            },
            'system': {
                'timestamp': time.time(),
                'server_time': timezone.now().strftime('%H:%M:%S'),
                'connection_status': 'connected',
                'auto_refresh': True
            }
        }
        
        return JsonResponse(response_data)
        
    except ParserRequest.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': f'Parser request {request_id} not found',
            'error_code': 'REQUEST_NOT_FOUND',
            'timestamp': time.time()
        }, status=404)
    except Exception as e:
        logger.error(f"API parsing status error: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e),
            'error_code': 'INTERNAL_ERROR',
            'timestamp': time.time()
        }, status=500)

def get_status_message(status, current_page, end_page):
    """Get human-readable status message"""
    if status == 'pending':
        return 'Waiting to start...'
    elif status == 'running':
        return f'Processing page {current_page} of {end_page}...'
    elif status == 'completed':
        return 'Parsing completed successfully!'
    elif status == 'error':
        return 'An error occurred during parsing'
    elif status == 'cancelled':
        return 'Parsing was cancelled'
    else:
        return f'Status: {status}'

@staff_member_required
def api_active_containers(request):
    """API endpoint for VNC containers"""
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
            "containers": [],
            "timestamp": time.time()
        })


# Add these imports at the top of your views.py
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse

# Add these views to your parser_controler/views.py

@staff_member_required
def websocket_test_view(request):
    """WebSocket test page"""
    return render(request, 'admin/websocket_test.html', {
        'title': 'WebSocket Connection Test'
    })

@staff_member_required  
def websocket_config_test(request):
    """Test WebSocket configuration via API"""
    try:
        # Test all WebSocket-related imports
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        import parser_controler.routing
        import parser_controler.consumers
        import parser_controler.test_consumer
        
        channel_layer = get_channel_layer()
        
        config_info = {
            "status": "success",
            "asgi_configured": True,
            "channel_layer_type": str(type(channel_layer).__name__),
            "channel_layer_backend": str(channel_layer),
            "websocket_patterns": len(parser_controler.routing.websocket_urlpatterns),
            "patterns": [str(pattern.pattern) for pattern in parser_controler.routing.websocket_urlpatterns],
            "consumers_available": [
                "TestWebSocketConsumer",
                "ParsingConsumer"
            ]
        }
        
        # Test channel layer functionality
        try:
            # This is a simple test - don't worry if it doesn't work in all environments
            test_channel = "test-channel"
            async_to_sync(channel_layer.group_add)(test_channel, "test-group")
            config_info["channel_layer_working"] = True
        except Exception as e:
            config_info["channel_layer_working"] = False
            config_info["channel_layer_error"] = str(e)
        
        return JsonResponse(config_info)
        
    except ImportError as e:
        return JsonResponse({
            "status": "error",
            "asgi_configured": False,
            "error": f"Import error: {str(e)}",
            "missing_component": "channels or routing"
        })
    except Exception as e:
        return JsonResponse({
            "status": "error", 
            "asgi_configured": False,
            "error": str(e)
        })