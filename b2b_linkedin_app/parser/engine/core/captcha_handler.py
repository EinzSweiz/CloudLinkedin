# parser/engine/core/captcha_handler.py - Enhanced version with full automation
import os
import time
import logging
import threading
import webbrowser
from typing import Dict, Optional
from parser_controler.docker_manager import get_manager, AutomatedCaptchaHandler

logger = logging.getLogger(__name__)

class FullyAutomatedCaptchaHandler:
    """
    Fully automated CAPTCHA handler that requires ZERO manual intervention
    except for solving the actual CAPTCHA in the browser
    """
    
    def __init__(self, auto_open_browser: bool = True, timeout: int = 900):
        self.auto_open_browser = auto_open_browser
        self.timeout = timeout  # 15 minutes default
        self.automated_handler = AutomatedCaptchaHandler()
        
    def solve_captcha(self, email: str, cred_id: str = None) -> bool:
        """
        Main CAPTCHA solving method - completely automated
        
        Args:
            email: Email account that needs CAPTCHA solving
            cred_id: Credential ID (optional, defaults to email)
            
        Returns:
            bool: True if CAPTCHA was solved successfully
        """
        if not cred_id:
            cred_id = email
            
        try:
            logger.info(f"🤖 Starting fully automated CAPTCHA solving for: {email}")
            
            # Start automated container
            result = self.automated_handler.solve_captcha_automated(
                email=email,
                cred_id=cred_id,
                auto_open=self.auto_open_browser
            )
            
            if result["status"] == "error":
                logger.error(f"❌ Failed to start CAPTCHA solver: {result.get('error')}")
                return False
            
            if result["status"] == "queued":
                logger.info(f"📋 CAPTCHA request queued: {result.get('job_id')}")
                logger.info(f"""
🕒 CAPTCHA REQUEST QUEUED
========================
Email: {email}
Job ID: {result.get('job_id')}
Queue Position: {result.get('queue_status', {}).get('queue_length', 'Unknown')}

Your request has been queued and will be processed automatically
when a container becomes available.
""")
                # Wait for queue processing (could implement WebSocket updates here)
                return self._wait_for_queue_processing(result.get('job_id'))
            
            container_id = result.get("container_id")
            if not container_id:
                logger.error("❌ No container ID returned")
                return False
            
            # Display user-friendly status
            self._display_captcha_status(result)
            
            # Wait for completion with real-time updates
            return self._wait_for_completion_with_updates(container_id, email)
            
        except Exception as e:
            logger.error(f"❌ Automated CAPTCHA solving failed: {e}")
            return False
    
    def _display_captcha_status(self, result: Dict):
        """Display user-friendly status information"""
        logger.info(f"""
🚀 AUTOMATED CAPTCHA SOLVER ACTIVE
===================================
Email: {result['email']}
Container: {result['container_id'][:12]}
Status: {result['status'].upper()}

🌐 VNC Interface: {result['auto_connect_url']}
📺 Direct VNC: localhost:{result['vnc_port']}

🤖 AUTOMATION STATUS:
✅ Container started and initializing
✅ VNC server starting up
✅ Auto-connect interface preparing
{'✅ Browser will auto-open in 5 seconds' if self.auto_open_browser else '🔗 Use the URL above to connect manually'}

⏳ Estimated time: {result.get('estimated_time', '5-15 minutes')}
🔄 Monitoring for completion automatically...

INSTRUCTIONS:
{chr(10).join(f'   {instruction}' for instruction in result.get('instructions', []))}
===================================
""")
    
    def _wait_for_completion_with_updates(self, container_id: str, email: str) -> bool:
        """Wait for CAPTCHA completion with real-time status updates"""
        start_time = time.time()
        last_status_time = 0
        status_interval = 60  # Update every minute
        
        logger.info("🔄 Monitoring CAPTCHA solving progress...")
        logger.info("   (Updates every minute, solving typically takes 2-10 minutes)")
        
        while time.time() - start_time < self.timeout:
            try:
                # Get current status
                status = self.automated_handler.get_status(container_id=container_id)
                
                if not status or status.get("error"):
                    logger.warning(f"⚠️ Could not get container status: {status}")
                    time.sleep(30)
                    continue
                
                # Check if completed
                container_status = status.get("status", "unknown")
                
                if container_status == "completed":
                    logger.info("🎉 SUCCESS! CAPTCHA has been solved!")
                    logger.info(f"✅ Total time: {int(time.time() - start_time)} seconds")
                    return True
                
                if container_status in ["failed", "timeout"]:
                    logger.info(f"❌ CAPTCHA solving failed: {container_status}")
                    return False
                
                # Periodic status updates
                current_time = time.time()
                if current_time - last_status_time >= status_interval:
                    elapsed = int(current_time - start_time)
                    remaining = int(self.timeout - elapsed)
                    
                    logger.info(f"⏳ Still solving... ({elapsed//60}:{elapsed%60:02d} elapsed, ~{remaining//60} min remaining)")
                    logger.info(f"   Container Status: {container_status}")
                    logger.info(f"   VNC Interface: {status.get('auto_connect_url', 'N/A')}")
                    
                    # Check if browser is accessible
                    if self._check_vnc_accessibility(status.get('novnc_port')):
                        logger.info("   🌐 VNC interface is accessible and ready")
                    else:
                        logger.info("   ⏳ VNC interface still initializing...")
                    
                    last_status_time = current_time
                
                # Check more frequently for completion
                time.sleep(15)
                
            except KeyboardInterrupt:
                logger.info("\n⚠️ Interrupted by user")
                logger.info(f"Container {container_id[:12]} is still running - you can reconnect manually")
                logger.info(f"Or use: docker stop {container_id}")
                return False
            except Exception as e:
                logger.warning(f"⚠️ Status check error: {e}")
                time.sleep(30)
                continue
        
        # Timeout reached
        logger.info(f"⏰ TIMEOUT: CAPTCHA solving took longer than {self.timeout//60} minutes")
        logger.info(f"Container {container_id[:12]} will be stopped automatically")
        return False
    
    def _wait_for_queue_processing(self, job_id: str) -> bool:
        """Wait for queued job to be processed"""
        # This could be enhanced with WebSocket updates
        # For now, simple polling
        timeout = 300  # 5 minutes to wait for queue processing
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            queue_status = self.automated_handler.queue.get_queue_status()
            logger.info(f"📋 Queue status: {queue_status['queue_length']} waiting, {queue_status['active_containers']}/{queue_status['max_containers']} active")
            
            # Check if our job started (would need to implement job tracking)
            # For now, just wait and retry
            time.sleep(30)
        
        logger.info("⏰ Queue timeout - please try again later")
        return False
    
    def _check_vnc_accessibility(self, port: int) -> bool:
        """Check if VNC web interface is accessible"""
        try:
            import requests
            response = requests.get(f"http://localhost:{port}/", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def get_active_captcha_sessions(self) -> Dict:
        """Get information about all active CAPTCHA sessions"""
        manager = get_manager()
        active_containers = manager.get_active_containers()
        
        sessions = []
        for container in active_containers:
            sessions.append({
                "container_id": container["container_id"],
                "email": container["email"],
                "status": container["status"],
                "uptime_minutes": int(container["uptime"] // 60),
                "vnc_url": f"http://localhost:{container['novnc_port']}/auto_connect.html",
                "direct_vnc": f"localhost:{container['vnc_port']}"
            })
        
        return {
            "active_sessions": len(sessions),
            "max_capacity": manager.max_containers,
            "sessions": sessions
        }
    
    def stop_captcha_session(self, email: str = None, container_id: str = None) -> bool:
        """Stop a specific CAPTCHA session"""
        manager = get_manager()
        
        if container_id:
            return manager.stop_container(container_id)
        elif email:
            # Find container by email
            active_containers = manager.get_active_containers()
            for container in active_containers:
                if container["email"] == email:
                    return manager.stop_container(container["container_id"])
        
        return False