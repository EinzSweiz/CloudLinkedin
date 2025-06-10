# parser_controler/docker_manager.py - Fixed version with auto port assignment and working browser auto-open
import subprocess
import uuid
import time
import json
import logging
import threading
import signal
import sys
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, List, Optional
import redis
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ContainerStatus(Enum):
    STARTING = "starting"
    READY = "ready" 
    SOLVING = "solving"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    STOPPING = "stopping"

@dataclass
class CaptchaContainer:
    container_id: str
    email: str
    cred_id: str
    vnc_port: int
    novnc_port: int
    status: ContainerStatus
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    last_health_check: Optional[float] = None
    attempts: int = 0
    max_attempts: int = 3
    logs: List[str] = None
    
    def __post_init__(self):
        if self.logs is None:
            self.logs = []

class ScalableCaptchaManager:
    def __init__(self, 
                 image_name="captcha_watcher_image",
                 max_containers=10,
                 container_timeout=900,  # 15 minutes
                 health_check_interval=30,
                 use_redis=True):
        
        self.image_name = image_name
        self.max_containers = max_containers
        self.container_timeout = container_timeout
        self.health_check_interval = health_check_interval
        
        # Storage backend
        self.use_redis = use_redis
        if use_redis:
            try:
                self.redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)
                self.redis_client.ping()  # Test connection
                logger.info("✅ Connected to Redis for persistent storage")
            except Exception as e:
                logger.warning(f"❌ Redis unavailable, falling back to in-memory: {e}")
                self.use_redis = False
                
        if not self.use_redis:
            self.containers = {}  # In-memory fallback
            
        self.monitoring_thread = None
        self.stop_monitoring = threading.Event()
        
        # Start background monitoring
        self.start_monitoring()
        
        # Cleanup on exit
        signal.signal(signal.SIGTERM, self._cleanup_handler)
        signal.signal(signal.SIGINT, self._cleanup_handler)
    
    def _get_container_key(self, container_id: str) -> str:
        return f"captcha_container:{container_id}"
    
    def _save_container(self, container: CaptchaContainer):
        """Save container info to storage backend"""
        if self.use_redis:
            key = self._get_container_key(container.container_id)
            data = asdict(container)
            data['status'] = container.status.value  # Convert enum to string
            self.redis_client.hset("captcha_containers", key, json.dumps(data))
        else:
            self.containers[container.container_id] = container
    
    def _load_container(self, container_id: str) -> Optional[CaptchaContainer]:
        """Load container info from storage backend"""
        if self.use_redis:
            key = self._get_container_key(container_id)
            data = self.redis_client.hget("captcha_containers", key)
            if data:
                parsed = json.loads(data)
                parsed['status'] = ContainerStatus(parsed['status'])  # Convert back to enum
                return CaptchaContainer(**parsed)
        else:
            return self.containers.get(container_id)
        return None
    
    def _delete_container(self, container_id: str):
        """Remove container from storage"""
        if self.use_redis:
            key = self._get_container_key(container_id)
            self.redis_client.hdel("captcha_containers", key)
        else:
            self.containers.pop(container_id, None)
    
    def _list_all_containers(self) -> List[CaptchaContainer]:
        """List all containers from storage"""
        containers = []
        if self.use_redis:
            all_data = self.redis_client.hgetall("captcha_containers")
            for key, data in all_data.items():
                try:
                    parsed = json.loads(data)
                    parsed['status'] = ContainerStatus(parsed['status'])
                    containers.append(CaptchaContainer(**parsed))
                except Exception as e:
                    logger.warning(f"Failed to parse container data for {key}: {e}")
        else:
            containers = list(self.containers.values())
        return containers
    
    def start_captcha_container(self, email: str, cred_id: str) -> Optional[Dict]:
        """Start a new CAPTCHA solving container with auto port assignment"""
        try:
            # Check if we're at capacity
            active_containers = self.get_active_containers()
            if len(active_containers) >= self.max_containers:
                # Try cleanup first
                self._cleanup_dead_containers()
                active_containers = self.get_active_containers()
                
                if len(active_containers) >= self.max_containers:
                    logger.warning(f"❌ At capacity: {len(active_containers)}/{self.max_containers}")
                    return None
            
            # Generate container name
            container_name = f"captcha_{uuid.uuid4().hex[:8]}"
            
            # 🚀 FIXED: Let Docker auto-assign ports to avoid conflicts
            cmd = [
                "docker", "run", "-d",
                "--name", container_name,
                "--label", "type=captcha_solver",
                "--label", f"email={email}",
                "--label", f"cred_id={cred_id}",
                "-e", f"EMAIL={email}",
                "-e", f"CRED_ID={cred_id}",
                "-e", "DISPLAY=:0",
                "-v", "shared_volume:/app/shared_volume",
                "-v", "cookies:/app/cookies",
                "--expose", "5900",  # VNC port
                "--expose", "6080",  # noVNC port
                "-P",
                "--memory=2g",
                "--cpus=1.0",   # CPU limit
                "--restart=no", # Don't auto-restart
                self.image_name
            ]
            
            logger.info(f"🚀 Starting container for {email} with auto port assignment...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                container_id = result.stdout.strip()
                
                # 🔧 NEW: Inspect container to get the actual assigned ports
                try:
                    vnc_port, novnc_port = self._get_assigned_ports(container_id)
                    logger.info(f"✅ Docker assigned ports - VNC: {vnc_port}, noVNC: {novnc_port}")
                except Exception as port_error:
                    logger.error(f"❌ Failed to get assigned ports: {port_error}")
                    # Cleanup the container since we can't get ports
                    subprocess.run(["docker", "rm", "-f", container_id], timeout=10)
                    return None
                
                # Create container object
                container = CaptchaContainer(
                    container_id=container_id,
                    email=email,
                    cred_id=cred_id,
                    vnc_port=vnc_port,
                    novnc_port=novnc_port,
                    status=ContainerStatus.STARTING,
                    created_at=time.time()
                )
                
                # Save to storage
                self._save_container(container)
                
                logger.info(f"✅ Container started: {container_name}")
                logger.info(f"🌐 noVNC: http://localhost:{novnc_port}/auto_connect.html")
                logger.info(f"📺 VNC: localhost:{vnc_port}")
                
                # Start individual container monitoring
                self._start_container_monitor(container_id)
                
                return {
                    "container_id": container_id,
                    "container_name": container_name,
                    "vnc_port": vnc_port,
                    "novnc_port": novnc_port,
                    "auto_connect_url": f"http://localhost:{novnc_port}/auto_connect.html",
                    "email": email,
                    "status": container.status.value
                }
            else:
                logger.error(f"❌ Docker start failed: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("❌ Docker start timeout")
            return None
        except Exception as e:
            logger.error(f"❌ Error starting container: {e}")
            return None
    
    def _get_assigned_ports(self, container_id: str) -> tuple[int, int]:
        """Get the ports that Docker assigned to the container"""
        try:
            # Method 1: Use docker inspect with format template
            inspect_cmd = [
                "docker", "inspect", container_id, "--format",
                "{{(index (index .NetworkSettings.Ports \"5900/tcp\") 0).HostPort}}:{{(index (index .NetworkSettings.Ports \"6080/tcp\") 0).HostPort}}"
            ]
            
            result = subprocess.run(inspect_cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                ports_str = result.stdout.strip()
                if ":" in ports_str and "<no value>" not in ports_str:
                    vnc_port_str, novnc_port_str = ports_str.split(":")
                    vnc_port = int(vnc_port_str)
                    novnc_port = int(novnc_port_str)
                    return vnc_port, novnc_port
            
            # Method 2: Fallback - parse full JSON inspect output
            logger.warning("Template method failed, trying JSON parsing...")
            inspect_json_cmd = ["docker", "inspect", container_id]
            result = subprocess.run(inspect_json_cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                container_data = json.loads(result.stdout)[0]
                ports = container_data["NetworkSettings"]["Ports"]
                
                vnc_port = None
                novnc_port = None
                
                if "5900/tcp" in ports and ports["5900/tcp"]:
                    vnc_port = int(ports["5900/tcp"][0]["HostPort"])
                
                if "6080/tcp" in ports and ports["6080/tcp"]:
                    novnc_port = int(ports["6080/tcp"][0]["HostPort"])
                
                if vnc_port and novnc_port:
                    return vnc_port, novnc_port
            
            raise Exception("Could not parse port information from Docker inspect")
            
        except Exception as e:
            logger.error(f"❌ Error getting assigned ports: {e}")
            raise
    
    def stop_container(self, container_id: str) -> bool:
        """Stop and remove a container"""
        try:
            container = self._load_container(container_id)
            if container:
                container.status = ContainerStatus.STOPPING
                self._save_container(container)
            
            logger.info(f"🛑 Stopping container: {container_id[:12]}")
            
            # Stop container
            subprocess.run(["docker", "stop", container_id], timeout=30)
            
            # Remove container
            subprocess.run(["docker", "rm", container_id], timeout=10)
            
            # Remove from storage
            self._delete_container(container_id)
            
            logger.info(f"✅ Container removed: {container_id[:12]}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error stopping container {container_id[:12]}: {e}")
            return False
    
    def get_active_containers(self) -> List[Dict]:
        """Get list of active containers"""
        containers = self._list_all_containers()
        active = []
        
        for container in containers:
            if container.status not in [ContainerStatus.COMPLETED, ContainerStatus.FAILED]:
                # Check if container is actually running
                if self._is_container_running(container.container_id):
                    active.append({
                        "container_id": container.container_id,
                        "email": container.email,
                        "vnc_port": container.vnc_port,
                        "novnc_port": container.novnc_port,
                        "status": container.status.value,
                        "created_at": container.created_at,
                        "uptime": time.time() - container.created_at,
                        "auto_connect_url": f"http://localhost:{container.novnc_port}/auto_connect.html"
                    })
                else:
                    # Container not running but marked as active - clean up
                    self._delete_container(container.container_id)
        
        return active
    
    def get_container_info(self, container_id: str) -> Optional[Dict]:
        """Get detailed info about a specific container"""
        container = self._load_container(container_id)
        if not container:
            return None
            
        return {
            "container_id": container.container_id,
            "email": container.email,
            "cred_id": container.cred_id,
            "vnc_port": container.vnc_port,
            "novnc_port": container.novnc_port,
            "status": container.status.value,
            "created_at": container.created_at,
            "started_at": container.started_at,
            "completed_at": container.completed_at,
            "attempts": container.attempts,
            "uptime": time.time() - container.created_at,
            "is_running": self._is_container_running(container.container_id),
            "auto_connect_url": f"http://localhost:{container.novnc_port}/auto_connect.html",
            "logs": container.logs[-10:] if container.logs else []  # Last 10 logs
        }
    
    
    def _is_container_running(self, container_id: str) -> bool:
        """Check if container is actually running"""
        try:
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", container_id],
                capture_output=True, text=True, timeout=5
            )
            return "true" in result.stdout.lower()
        except:
            return False
    
    def _cleanup_dead_containers(self):
        """Remove containers that are no longer running"""
        containers = self._list_all_containers()
        cleaned_count = 0
        
        for container in containers:
            if not self._is_container_running(container.container_id):
                logger.info(f"🧹 Cleaning up dead container: {container.container_id[:12]}")
                self._delete_container(container.container_id)
                cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"✅ Cleaned up {cleaned_count} dead containers")
    
    def _start_container_monitor(self, container_id: str):
        """Start monitoring a specific container"""
        def monitor():
            try:
                while not self.stop_monitoring.is_set():
                    container = self._load_container(container_id)
                    if not container:
                        break
                    
                    # Check if container is still running
                    if not self._is_container_running(container_id):
                        logger.warning(f"⚠️ Container died: {container_id[:12]}")
                        container.status = ContainerStatus.FAILED
                        container.completed_at = time.time()
                        self._save_container(container)
                        break
                    
                    # Check timeout
                    if container.created_at and time.time() - container.created_at > self.container_timeout:
                        logger.warning(f"⏰ Container timeout: {container_id[:12]}")
                        container.status = ContainerStatus.TIMEOUT
                        container.logs.append(f"Container timed out after {self.container_timeout}s")
                        self._save_container(container)
                        self.stop_container(container_id)
                        break
                    
                    # Update health check
                    container.last_health_check = time.time()
                    self._save_container(container)
                    
                    # Check every 30 seconds
                    self.stop_monitoring.wait(30)
                    
            except Exception as e:
                logger.error(f"❌ Monitor error for {container_id[:12]}: {e}")
        
        threading.Thread(target=monitor, daemon=True).start()
    
    def start_monitoring(self):
        """Start the global monitoring thread"""
        def global_monitor():
            logger.info("🔍 Started global container monitoring")
            
            while not self.stop_monitoring.is_set():
                try:
                    # Cleanup dead containers
                    self._cleanup_dead_containers()
                    
                    # Log active status
                    active = self.get_active_containers()
                    if active:
                        logger.info(f"📊 Active containers: {len(active)}/{self.max_containers}")
                    
                    # Wait before next check
                    self.stop_monitoring.wait(self.health_check_interval)
                    
                except Exception as e:
                    logger.error(f"❌ Global monitor error: {e}")
                    self.stop_monitoring.wait(10)
            
            logger.info("🔍 Global monitoring stopped")
        
        if not self.monitoring_thread or not self.monitoring_thread.is_alive():
            self.monitoring_thread = threading.Thread(target=global_monitor, daemon=True)
            self.monitoring_thread.start()
    
    def stop_monitoring(self):
        """Stop all monitoring"""
        logger.info("🛑 Stopping monitoring...")
        self.stop_monitoring.set()
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
    
    def cleanup_all_containers(self):
        """Emergency cleanup - stop all managed containers"""
        logger.info("🧹 Emergency cleanup - stopping all containers...")
        containers = self._list_all_containers()
        
        for container in containers:
            try:
                self.stop_container(container.container_id)
            except Exception as e:
                logger.error(f"❌ Failed to stop {container.container_id[:12]}: {e}")
        
        logger.info("✅ Emergency cleanup completed")
    
    def _cleanup_handler(self, signum, frame):
        """Handle cleanup on exit"""
        logger.info(f"🔄 Received signal {signum}, cleaning up...")
        self.stop_monitoring()
        # Optionally cleanup all containers on exit
        # self.cleanup_all_containers()
        sys.exit(0)

# Singleton instance
_manager_instance = None

def get_manager() -> ScalableCaptchaManager:
    """Get singleton manager instance"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ScalableCaptchaManager()
    return _manager_instance

# Legacy compatibility functions
def start_container(email: str, cred_id: str) -> Optional[str]:
    """Legacy function for backward compatibility"""
    manager = get_manager()
    result = manager.start_captcha_container(email, cred_id)
    return result["container_id"] if result else None

def stop_container(container_id: str) -> bool:
    """Legacy function for backward compatibility"""
    manager = get_manager()
    return manager.stop_container(container_id)

def list_active() -> List[Dict]:
    """Legacy function for backward compatibility"""
    manager = get_manager()
    return manager.get_active_containers()

def cleanup_dead_containers():
    """Legacy function for backward compatibility"""
    manager = get_manager()
    manager._cleanup_dead_containers()

# Health check endpoint function
def container_health_check(container_id: str) -> Dict:
    """Health check for a specific container"""
    manager = get_manager()
    container_info = manager.get_container_info(container_id)
    
    if not container_info:
        return {"status": "not_found", "healthy": False}
    
    is_running = manager._is_container_running(container_id)
    uptime = container_info.get("uptime", 0)
    
    health_status = {
        "status": container_info["status"],
        "healthy": is_running and uptime < manager.container_timeout,
        "uptime": uptime,
        "is_running": is_running,
        "container_id": container_id,
        "email": container_info["email"],
        "ports": {
            "vnc": container_info["vnc_port"],
            "novnc": container_info["novnc_port"]
        }
    }
    
    return health_status

# 🔧 FIXED: Docker-compatible browser auto-opening function
def auto_open_browser(container_info: Dict, delay: int = 3):
    """Auto-open browser to VNC interface (Docker-compatible)"""
    import threading
    import subprocess
    import webbrowser
    
    def delayed_open():
        try:
            time.sleep(delay)
            url = container_info.get("auto_connect_url")
            if url:
                logger.warning(f"🌐 Auto-opening browser: {url}")
                
                # Method 1: Try Python webbrowser module first (most reliable in containers)
                try:
                    webbrowser.open(url)
                    logger.info("✅ Browser opened successfully with webbrowser module")
                    return
                except Exception as e:
                    logger.debug(f"webbrowser method failed: {e}")
                
                # Method 2: Try xdg-open (Linux default)
                try:
                    subprocess.run(["xdg-open", url], timeout=5, capture_output=True, check=True)
                    logger.info("✅ Browser opened successfully with xdg-open")
                    return
                except Exception as e:
                    logger.debug(f"xdg-open method failed: {e}")
                
                # Method 3: Try firefox directly
                try:
                    subprocess.run(["firefox", url], timeout=5, capture_output=True, check=True)
                    logger.info("✅ Browser opened successfully with Firefox")
                    return
                except Exception as e:
                    logger.debug(f"Firefox method failed: {e}")
                
                # Method 4: Try chromium
                try:
                    subprocess.run(["chromium-browser", "--no-sandbox", url], timeout=5, capture_output=True, check=True)
                    logger.info("✅ Browser opened successfully with Chromium")
                    return
                except Exception as e:
                    logger.debug(f"Chromium method failed: {e}")
                
                # Method 5: Fallback - prominent URL logging for manual opening
                logger.warning("="*80)
                logger.warning("🌐 BROWSER AUTO-OPEN FAILED - MANUAL ACTION REQUIRED")
                logger.warning("="*80)
                logger.warning(f"Please copy and paste this URL into your browser:")
                logger.warning(f"   {url}")
                logger.warning("="*80)
                logger.warning("The VNC interface will connect automatically - no password needed!")
                logger.warning("="*80)
                
                # Also print to console for visibility
                print("\n" + "="*80)
                print("🌐 CAPTCHA SOLVER READY")
                print("="*80)
                print(f"Open this URL in your browser to solve the CAPTCHA:")
                print(f"   {url}")
                print("="*80)
                print("The VNC interface will auto-connect - no password needed!")
                print("="*80 + "\n")
                
        except Exception as e:
            logger.warning(f"❌ Failed to auto-open browser: {e}")
            # Still provide the URL for manual opening
            url = container_info.get("auto_connect_url", "Unknown")
            logger.warning(f"🌐 Please manually open: {url}")
    
    threading.Thread(target=delayed_open, daemon=True).start()

# Alternative simple URL logging function
def log_browser_url(container_info: Dict, delay: int = 3):
    """Log the VNC URL prominently for manual opening"""
    import threading
    
    def delayed_log():
        try:
            time.sleep(delay)
            url = container_info.get("auto_connect_url")
            if url:
                print("\n" + "="*80)
                print("🌐 CAPTCHA SOLVER READY")
                print("="*80)
                print(f"Open this URL in your browser to solve the CAPTCHA:")
                print(f"   {url}")
                print("="*80)
                print("The VNC interface will auto-connect - no password needed!")
                print("="*80 + "\n")
                
                logger.info(f"🌐 VNC Interface ready: {url}")
                
        except Exception as e:
            logger.error(f"❌ Error logging URL: {e}")
    
    threading.Thread(target=delayed_log, daemon=True).start()

class CaptchaJobQueue:
    """Job queue for handling multiple CAPTCHA requests"""
    
    def __init__(self, manager: ScalableCaptchaManager):
        self.manager = manager
        self.queue_key = "captcha_job_queue"
        
    def submit_job(self, email: str, cred_id: str, priority: int = 0) -> str:
        """Submit a CAPTCHA job to the queue"""
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        job_data = {
            "job_id": job_id,
            "email": email,
            "cred_id": cred_id,
            "priority": priority,
            "submitted_at": time.time(),
            "status": "queued"
        }
        
        if self.manager.use_redis:
            # Add to Redis queue with priority
            self.manager.redis_client.zadd(
                self.queue_key, 
                {json.dumps(job_data): priority}
            )
        else:
            # Fallback to immediate processing
            return self._process_job_immediately(job_data)
        
        logger.info(f"📝 Job queued: {job_id} for {email}")
        
        # Try to process immediately if capacity available
        self._try_process_next()
        
        return job_id
    
    def _process_job_immediately(self, job_data: Dict) -> str:
        """Process job immediately without queue"""
        result = self.manager.start_captcha_container(
            job_data["email"], 
            job_data["cred_id"]
        )
        
        if result:
            logger.info(f"✅ Job processed immediately: {job_data['job_id']}")
            return result["container_id"]
        else:
            logger.warning(f"❌ Failed to process job: {job_data['job_id']}")
            return None
    
    def _try_process_next(self):
        """Try to process the next job in queue if capacity available"""
        if not self.manager.use_redis:
            return
            
        active_count = len(self.manager.get_active_containers())
        
        if active_count < self.manager.max_containers:
            # Get highest priority job
            jobs = self.manager.redis_client.zrevrange(
                self.queue_key, 0, 0, withscores=True
            )
            
            if jobs:
                job_data_str, priority = jobs[0]
                job_data = json.loads(job_data_str)
                
                # Remove from queue
                self.manager.redis_client.zrem(self.queue_key, job_data_str)
                
                # Process job
                result = self.manager.start_captcha_container(
                    job_data["email"], 
                    job_data["cred_id"]
                )
                
                if result:
                    logger.info(f"✅ Processed queued job: {job_data['job_id']}")
                    
                    # Store job-to-container mapping
                    self.manager.redis_client.hset(
                        "job_container_mapping",
                        job_data["job_id"],
                        result["container_id"]
                    )
                else:
                    logger.warning(f"❌ Failed to process queued job: {job_data['job_id']}")
                    # Re-queue with lower priority
                    job_data["status"] = "failed_retry"
                    self.manager.redis_client.zadd(
                        self.queue_key,
                        {json.dumps(job_data): max(0, priority - 1)}
                    )
    
    def get_queue_status(self) -> Dict:
        """Get current queue status"""
        if not self.manager.use_redis:
            return {"queue_length": 0, "active_containers": len(self.manager.get_active_containers())}
        
        queue_length = self.manager.redis_client.zcard(self.queue_key)
        active_count = len(self.manager.get_active_containers())
        
        return {
            "queue_length": queue_length,
            "active_containers": active_count,
            "max_containers": self.manager.max_containers,
            "capacity_available": self.manager.max_containers - active_count
        }

# Enhanced captcha handler integration
class AutomatedCaptchaHandler:
    """Enhanced captcha handler with full automation"""
    
    def __init__(self):
        self.manager = get_manager()
        self.queue = CaptchaJobQueue(self.manager)
    
    def solve_captcha_automated(self, email: str, cred_id: str, auto_open: bool = True) -> Dict:
        """
        Fully automated CAPTCHA solving with optional browser auto-open
        
        Returns:
            Dict with status, container info, and connection details
        """
        try:
            logger.info(f"🚀 Starting automated CAPTCHA solving for: {email}")
            
            # Start container
            result = self.manager.start_captcha_container(email, cred_id)
            
            if not result:
                # Try queuing if at capacity
                job_id = self.queue.submit_job(email, cred_id, priority=1)
                return {
                    "status": "queued",
                    "job_id": job_id,
                    "message": "Added to queue - will process when capacity available",
                    "queue_status": self.queue.get_queue_status()
                }
            
            container_id = result["container_id"]
            
            print(f"""
{'='*80}
🤖 AUTOMATED CAPTCHA SOLVER STARTED
{'='*80}
Email: {email}
Container: {container_id[:12]}
VNC Port: {result['vnc_port']} (Docker auto-assigned)
noVNC Port: {result['novnc_port']} (Docker auto-assigned)
Web Interface: {result['auto_connect_url']}

🔄 STATUS:
✅ Container started successfully
✅ Ports auto-assigned by Docker (no conflicts!)
✅ VNC server initializing
✅ Auto-connect interface ready

🌐 ACCESS OPTIONS:
   Auto-Connect: {result['auto_connect_url']}
   Manual VNC: localhost:{result['vnc_port']}

⚡ AUTOMATION FEATURES:
✅ Zero manual clicks required
✅ Auto-connects when ready
✅ Real-time status monitoring
✅ Auto-cleanup on completion
✅ No more port conflicts!

⏰ Will auto-cleanup in 15 minutes if not completed
{'='*80}
""")
            
            # Auto-open browser if requested
            if auto_open:
                auto_open_browser(result, delay=5)
                print("🌐 Browser will auto-open in 5 seconds...")
            
            # Start result monitoring
            self._start_result_monitoring(container_id, email)
            
            return {
                "status": "started",
                "container_id": container_id,
                "email": email,
                "vnc_port": result["vnc_port"],
                "novnc_port": result["novnc_port"],
                "auto_connect_url": result["auto_connect_url"],
                "message": "CAPTCHA solver started successfully with auto-assigned ports",
                "estimated_time": "5-15 minutes",
                "instructions": [
                    "1. Browser will auto-open to VNC interface",
                    "2. VNC will auto-connect (no button clicks needed)",
                    "3. Solve the CAPTCHA in the browser window",
                    "4. System will auto-detect completion",
                    "5. Container will auto-cleanup"
                ]
            }
            
        except Exception as e:
            logger.error(f"❌ Automated CAPTCHA solving failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to start automated CAPTCHA solver"
            }
    
    def _start_result_monitoring(self, container_id: str, email: str):
        """Monitor for CAPTCHA completion"""
        def monitor():
            try:
                timeout = 900  # 15 minutes
                start_time = time.time()
                check_interval = 30  # Check every 30 seconds
                
                while time.time() - start_time < timeout:
                    # Check if container is still running
                    if not self.manager._is_container_running(container_id):
                        logger.info(f"📋 Container stopped: {container_id[:12]}")
                        break
                    
                    # Check for CAPTCHA completion (would integrate with actual detection logic)
                    if self._check_captcha_solved(email):
                        logger.info(f"🎉 CAPTCHA solved for {email}!")
                        
                        # Update container status
                        container = self.manager._load_container(container_id)
                        if container:
                            container.status = ContainerStatus.COMPLETED
                            container.completed_at = time.time()
                            self.manager._save_container(container)
                        
                        # Auto-cleanup after success
                        time.sleep(30)  # Give user time to see result
                        self.manager.stop_container(container_id)
                        break
                    
                    time.sleep(check_interval)
                
                # Timeout handling
                if time.time() - start_time >= timeout:
                    logger.warning(f"⏰ CAPTCHA timeout for {email}")
                    self.manager.stop_container(container_id)
                
            except Exception as e:
                logger.error(f"❌ Result monitoring error: {e}")
        
        threading.Thread(target=monitor, daemon=True).start()
    
    def _check_captcha_solved(self, email: str) -> bool:
        """Check if CAPTCHA was solved (integrate with actual detection logic)"""
        # This would integrate with your existing captcha detection logic
        # For now, check if cookies file was updated recently
        cookie_path = f"/app/cookies/linkedin_cookies_{email}.pkl"
        try:
            if os.path.exists(cookie_path):
                mtime = os.path.getmtime(cookie_path)
                return time.time() - mtime < 300  # Updated in last 5 minutes
        except:
            pass
        return False
    
    def get_status(self, container_id: str = None, email: str = None) -> Dict:
        """Get status of CAPTCHA solving process"""
        if container_id:
            return self.manager.get_container_info(container_id)
        elif email:
            # Find container by email
            containers = self.manager.get_active_containers()
            for container in containers:
                if container["email"] == email:
                    return self.manager.get_container_info(container["container_id"])
        
        return {"error": "Container not found"}