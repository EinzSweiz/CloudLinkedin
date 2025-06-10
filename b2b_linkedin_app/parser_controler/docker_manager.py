# parser_controler/docker_manager.py - CORRECTLY FIXED: Session preservation version
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

def cleanup_old_result_files_only(email):
    """Clean up ONLY result files, NEVER touch session files that VNC needs"""
    # 🔧 FIXED: Only clean RESULT files, PRESERVE ALL session transfer files
    files_to_clean = [
        f"/app/shared_volume/captcha_success_{email}.json",
        f"/app/shared_volume/solved_cookies_{email}.pkl", 
        f"/app/shared_volume/captcha_solved_{email.replace('@', '_')}.flag",
        # ❌ NEVER DELETE: f"/app/shared_volume/captcha_session_{email}.json"  # VNC NEEDS THIS!
    ]
    
    cleaned_count = 0
    for file_path in files_to_clean:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"🧹 Cleaned up old result file: {os.path.basename(file_path)}")
                cleaned_count += 1
            except Exception as e:
                logger.warning(f"Failed to clean {file_path}: {e}")
    
    # 🔧 CRITICAL: Check and PRESERVE session file
    session_file = f"/app/shared_volume/captcha_session_{email}.json"
    if os.path.exists(session_file):
        try:
            size = os.path.getsize(session_file)
            mtime = os.path.getmtime(session_file)
            age = time.time() - mtime
            logger.info(f"✅ PRESERVED session file for VNC container:")
            logger.info(f"   📄 File: {os.path.basename(session_file)}")
            logger.info(f"   📏 Size: {size} bytes")
            logger.info(f"   🕐 Age: {age:.1f}s")
            
            if size == 0:
                logger.error(f"❌ Session file is EMPTY - VNC will fail!")
            elif age > 600:  # 10 minutes
                logger.warning(f"⚠️ Session file is old (>10min) - may be stale")
            else:
                logger.info(f"   ✅ Session file looks good for VNC transfer")
                
            # Validate session content briefly
            with open(session_file, 'r') as f:
                session_data = json.load(f)
            
            required_fields = ['current_url', 'cookies', 'email']
            missing = [f for f in required_fields if f not in session_data]
            
            if missing:
                logger.error(f"❌ Session file missing critical fields: {missing}")
            else:
                logger.info(f"   ✅ Session contains: URL, {len(session_data.get('cookies', []))} cookies")
                
        except Exception as e:
            logger.error(f"❌ Error validating session file: {e}")
    else:
        logger.warning(f"⚠️ NO session file found for {email} - VNC will use fallback manual mode")
    
    return cleaned_count

def cleanup_session_files_after_success(email):
    """ONLY clean session files AFTER successful completion"""
    logger.info(f"🧹 Final cleanup after successful CAPTCHA resolution for {email}")
    
    files_to_clean = [
        f"/app/shared_volume/captcha_success_{email}.json",
        f"/app/shared_volume/solved_cookies_{email}.pkl", 
        f"/app/shared_volume/captcha_solved_{email.replace('@', '_')}.flag",
        f"/app/shared_volume/captcha_session_{email}.json",  # NOW safe to delete
    ]
    
    cleaned_count = 0
    for file_path in files_to_clean:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"   🗑️ Cleaned: {os.path.basename(file_path)}")
                cleaned_count += 1
            except Exception as e:
                logger.warning(f"Failed to clean {file_path}: {e}")
    
    logger.info(f"✅ Final cleanup completed: {cleaned_count} files removed")
    return cleaned_count

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
                logger.info("Connected to Redis for persistent storage")
            except Exception as e:
                logger.warning(f"Redis unavailable, falling back to in-memory: {e}")
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

    def is_container_ready(self, container_id: str) -> bool:
        """Check if ready flag file exists"""
        flag_path = f"/captcha_ready_flags/{container_id}.txt"
        return os.path.exists(flag_path)
    
    def update_container_status_from_watcher(self, container_id: str, new_status: str, message: str = None):
        """Update container status from the VNC watcher process"""
        try:
            container = self._load_container(container_id)
            if container:
                old_status = container.status.value
                container.status = ContainerStatus(new_status)
                
                # Add log entry
                if message:
                    container.logs.append(f"{time.time()}: {message}")
                
                # Update timestamps
                if new_status == "ready":
                    container.started_at = time.time()
                elif new_status in ["completed", "failed", "timeout"]:
                    container.completed_at = time.time()
                
                self._save_container(container)
                
                logger.info(f"Container {container_id[:12]} status: {old_status} → {new_status}")
                if message:
                    logger.info(f"Message: {message}")
                    
                return True
            else:
                logger.warning(f"Container {container_id[:12]} not found for status update")
                return False
                
        except Exception as e:
            logger.error(f"Error updating container status: {e}")
            return False

    def mark_container_ready(self, container_id: str):
        """Mark container as ready when VNC and session transfer are complete"""
        return self.update_container_status_from_watcher(
            container_id, 
            "ready", 
            "VNC initialized and session transfer completed"
        )
    def mark_container_solving(self, container_id: str):
        """Mark container as actively solving CAPTCHA"""
        return self.update_container_status_from_watcher(
            container_id, 
            "solving", 
            "CAPTCHA challenge detected and user interaction required"
        )

    def mark_container_completed(self, container_id: str):
        """Mark container as completed when CAPTCHA is solved"""
        return self.update_container_status_from_watcher(
            container_id, 
            "completed", 
            "CAPTCHA solved successfully and cookies saved"
        )
    
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
        """🔧 PROPERLY FIXED: Start container while preserving session files"""
        try:
            # Check if we're at capacity
            active_containers = self.get_active_containers()
            if len(active_containers) >= self.max_containers:
                # Try cleanup first
                self._cleanup_dead_containers()
                active_containers = self.get_active_containers()
                
                if len(active_containers) >= self.max_containers:
                    logger.warning(f"At capacity: {len(active_containers)}/{self.max_containers}")
                    return None
            
            # 🔧 CRITICAL FIX: Only clean result files, PRESERVE session files
            logger.info(f"🧹 Cleaning up old result files (preserving session data) for {email}...")
            cleanup_old_result_files_only(email)
            
            # 🔧 VALIDATE: Ensure session file exists and is valid
            session_file = f"/app/shared_volume/captcha_session_{email}.json"
            session_available = False
            
            if os.path.exists(session_file):
                try:
                    size = os.path.getsize(session_file)
                    if size > 0:
                        with open(session_file, 'r') as f:
                            session_data = json.load(f)
                        
                        # Check required fields
                        if ('current_url' in session_data and 
                            'cookies' in session_data and 
                            len(session_data.get('cookies', [])) > 0):
                            session_available = True
                            logger.info(f"✅ Valid session file available:")
                            logger.info(f"   📄 Size: {size} bytes")
                            logger.info(f"   🌐 URL: {session_data.get('current_url', 'Unknown')}")
                            logger.info(f"   🍪 Cookies: {len(session_data.get('cookies', []))}")
                        else:
                            logger.warning(f"⚠️ Session file missing required data")
                    else:
                        logger.warning(f"⚠️ Session file is empty")
                except Exception as e:
                    logger.error(f"❌ Error validating session file: {e}")
            
            if not session_available:
                logger.warning(f"⚠️ No valid session file - VNC will use manual fallback mode")
            
            # Generate container name
            container_name = f"captcha_{uuid.uuid4().hex[:8]}"
            
            # Start container with session preservation
            cmd = [
                "docker", "run", "-d",
                "--name", container_name,
                "--label", "type=captcha_solver", 
                "--label", f"email={email}",
                "--label", f"cred_id={cred_id}",
                "-e", f"EMAIL={email}",
                "-e", f"CRED_ID={cred_id}",
                "-e", "DISPLAY=:0",
                "-v", "b2b_linkedin_app_shared_data:/app/shared_volume",
                "-v", "b2b_linkedin_app_cookies:/app/cookies",
                "--network", "b2b_linkedin_app_app-network",
                "--expose", "5900",
                "--expose", "6080", 
                "-P",
                "--memory=2g",
                "--cpus=1.0",
                "--restart=no",
                self.image_name
            ]
            
            logger.info(f"🚀 Starting VNC container for {email}...")
            logger.info(f"   Session data: {'✅ Available' if session_available else '❌ Manual mode'}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                container_id = result.stdout.strip()
                
                # Get assigned ports
                try:
                    vnc_port, novnc_port = self._get_assigned_ports(container_id)
                    logger.info(f"✅ Container started successfully:")
                    logger.info(f"   🐳 ID: {container_id[:12]}")
                    logger.info(f"   🖥️ VNC: {vnc_port}")
                    logger.info(f"   🌐 noVNC: {novnc_port}")
                except Exception as port_error:
                    logger.error(f"Failed to get assigned ports: {port_error}")
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
                
                # Start container monitoring
                self._start_container_monitor(container_id)
                
                logger.info(f"🎯 VNC CAPTCHA solver ready:")
                logger.info(f"   📧 Email: {email}")
                logger.info(f"   🔗 URL: http://localhost:{novnc_port}/auto_connect.html")
                logger.info(f"   🔄 Mode: {'Automatic session transfer' if session_available else 'Manual fallback'}")
                
                return {
                    "container_id": container_id,
                    "container_name": container_name,
                    "vnc_port": vnc_port,
                    "novnc_port": novnc_port,
                    "auto_connect_url": f"http://localhost:{novnc_port}/auto_connect.html",
                    "email": email,
                    "status": container.status.value,
                    "session_available": session_available
                }
            else:
                logger.error(f"Docker start failed: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("Docker start timeout")
            return None
        except Exception as e:
            logger.error(f"Error starting container: {e}")
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
            logger.error(f"Error getting assigned ports: {e}")
            raise
    
    def stop_container(self, container_id: str) -> bool:
        """Stop container with proper cleanup timing"""
        try:
            container = self._load_container(container_id)
            email = None
            
            if container:
                email = container.email
                container.status = ContainerStatus.STOPPING
                self._save_container(container)
            
            logger.info(f"🛑 Stopping container: {container_id[:12]}")
            
            # Stop container
            subprocess.run(["docker", "stop", container_id], timeout=30)
            
            # Remove container
            subprocess.run(["docker", "rm", container_id], timeout=10)
            
            # 🔧 IMPORTANT: Only cleanup session files if container completed successfully
            if container and container.status == ContainerStatus.COMPLETED and email:
                logger.info(f"✅ Container completed successfully - performing final cleanup")
                cleanup_session_files_after_success(email)
            elif email:
                logger.info(f"⚠️ Container stopped without completion - preserving session files for potential retry")
            
            # Remove from storage
            self._delete_container(container_id)
            
            logger.info(f"✅ Container removed: {container_id[:12]}")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping container {container_id[:12]}: {e}")
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
                logger.info(f"Cleaning up dead container: {container.container_id[:12]}")
                self._delete_container(container.container_id)
                cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} dead containers")

    def _start_container_monitor(self, container_id: str):
        """Start monitoring container with proper session preservation"""
        def monitor():
            try:
                container = self._load_container(container_id)
                if not container:
                    return
                    
                email = container.email
                logger.info(f"🔍 Starting monitoring for {email} ({container_id[:12]})")
                
                # 🔧 CRITICAL: NO session file cleanup during monitoring!
                monitor_start_time = time.time()
                
                # Wait for container initialization
                minimum_wait = 90
                logger.info(f"⏳ Waiting {minimum_wait}s for CAPTCHA solving...")
                
                initial_wait_count = 0
                while initial_wait_count < minimum_wait and not self.stop_monitoring.is_set():
                    self.stop_monitoring.wait(5)
                    initial_wait_count += 5
                    if initial_wait_count % 30 == 0:
                        logger.info(f"   ⏳ Still waiting... {minimum_wait - initial_wait_count}s remaining")
                
                logger.info("✅ Now monitoring for CAPTCHA completion...")
                
                while not self.stop_monitoring.is_set():
                    container = self._load_container(container_id)
                    if not container:
                        break
                    
                    # Check for success
                    success_file = f"/app/shared_volume/captcha_success_{email}.json"
                    cookies_file = f"/app/shared_volume/solved_cookies_{email}.pkl"
                    
                    if os.path.exists(success_file) and os.path.exists(cookies_file):
                        try:
                            # Validate timestamps
                            success_mtime = os.path.getmtime(success_file)
                            cookies_mtime = os.path.getmtime(cookies_file)
                            
                            if (success_mtime > monitor_start_time and 
                                cookies_mtime > monitor_start_time):
                                
                                # Validate content
                                with open(success_file, 'r') as f:
                                    success_data = json.load(f)
                                
                                cookies_size = os.path.getsize(cookies_file)
                                
                                if (success_data.get('status') == 'solved' and 
                                    cookies_size > 1000):
                                    
                                    # Validate cookies contain LinkedIn data
                                    import pickle
                                    with open(cookies_file, 'rb') as f:
                                        cookies = pickle.load(f)
                                    
                                    cookie_names = [c.get('name', '') for c in cookies if isinstance(c, dict)]
                                    required_cookies = ['li_rm', 'JSESSIONID', 'bcookie']
                                    
                                    if any(req in cookie_names for req in required_cookies):
                                        logger.info(f"🎉 CAPTCHA SUCCESS DETECTED for {email}!")
                                        logger.info(f"   📄 Success file: ✅")
                                        logger.info(f"   🍪 Cookies: {cookies_size} bytes")
                                        logger.info(f"   ✅ LinkedIn cookies: ✅")
                                        
                                        container.status = ContainerStatus.COMPLETED
                                        container.completed_at = time.time()
                                        self._save_container(container)
                                        
                                        # Give main app time to detect
                                        logger.info("⏳ Waiting 2 minutes for main app to detect success...")
                                        time.sleep(120)
                                        
                                        # Now stop and cleanup
                                        logger.info(f"🛑 Stopping successful container: {container_id[:12]}")
                                        self.stop_container(container_id)
                                        break
                                        
                        except Exception as e:
                            logger.debug(f"Success validation error: {e}")
                    
                    # Check if container still running
                    if not self._is_container_running(container_id):
                        logger.warning(f"⚠️ Container died: {container_id[:12]}")
                        container.status = ContainerStatus.FAILED
                        container.completed_at = time.time()
                        self._save_container(container)
                        break
                    
                    # Check timeout
                    elapsed_time = time.time() - container.created_at
                    if elapsed_time > self.container_timeout:
                        logger.warning(f"⏰ Container timeout: {container_id[:12]} (after {elapsed_time:.0f}s)")
                        container.status = ContainerStatus.TIMEOUT
                        self._save_container(container)
                        self.stop_container(container_id)
                        break
                    
                    # Update health check
                    container.last_health_check = time.time()
                    self._save_container(container)
                    
                    # Check every 10 seconds
                    self.stop_monitoring.wait(10)
                    
            except Exception as e:
                logger.error(f"Monitor error for {container_id[:12]}: {e}")
        
        threading.Thread(target=monitor, daemon=True).start()
                
    def start_monitoring(self):
        """Start the global monitoring thread"""
        def global_monitor():
            logger.info("Started global container monitoring")
            
            while not self.stop_monitoring.is_set():
                try:
                    # Cleanup dead containers
                    self._cleanup_dead_containers()
                    
                    # Log active status
                    active = self.get_active_containers()
                    if active:
                        logger.info(f"Active containers: {len(active)}/{self.max_containers}")
                    
                    # Wait before next check
                    self.stop_monitoring.wait(self.health_check_interval)
                    
                except Exception as e:
                    logger.error(f"Global monitor error: {e}")
                    self.stop_monitoring.wait(10)
            
            logger.info("Global monitoring stopped")
        
        if not self.monitoring_thread or not self.monitoring_thread.is_alive():
            self.monitoring_thread = threading.Thread(target=global_monitor, daemon=True)
            self.monitoring_thread.start()
    
    def stop_monitoring(self):
        """Stop all monitoring"""
        logger.info("Stopping monitoring...")
        self.stop_monitoring.set()
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
    
    def cleanup_all_containers(self):
        """Emergency cleanup - stop all managed containers"""
        logger.info("Emergency cleanup - stopping all containers...")
        containers = self._list_all_containers()
        
        for container in containers:
            try:
                self.stop_container(container.container_id)
            except Exception as e:
                logger.error(f"Failed to stop {container.container_id[:12]}: {e}")
        
        logger.info("Emergency cleanup completed")
    
    def _cleanup_handler(self, signum, frame):
        """Handle cleanup on exit"""
        logger.info(f"Received signal {signum}, cleaning up...")
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

def auto_open_browser(container_info: Dict, delay: int = 3):
    """Auto-open browser to VNC interface (Docker-compatible)"""
    import threading
    import subprocess
    import webbrowser
    import shutil

    def delayed_open():
        try:
            time.sleep(delay)
            url = container_info.get("auto_connect_url")
            if not url:
                logger.warning("No auto_connect_url provided for browser auto-open.")
                return

            logger.warning(f"Auto-opening browser: {url}")

            # Method 1: Try launching Chromium with --no-sandbox (safe for Docker)
            if shutil.which("chromium-browser"):
                subprocess.Popen(["chromium-browser", "--no-sandbox", url])
                logger.info("Browser opened using chromium-browser with --no-sandbox")
                return
            elif shutil.which("google-chrome"):
                subprocess.Popen(["google-chrome", "--no-sandbox", url])
                logger.info("Browser opened using google-chrome with --no-sandbox")
                return

            # Method 2: Try xdg-open (not safe in Docker unless browser configured)
            try:
                subprocess.Popen(["xdg-open", url])
                logger.info("Browser opened using xdg-open")
                return
            except Exception as e:
                logger.debug(f"xdg-open failed: {e}")

            # Method 3: Try Python webbrowser module (rarely works in headless Docker)
            try:
                webbrowser.open(url)
                logger.info("Browser opened using webbrowser module")
                return
            except Exception as e:
                logger.debug(f"webbrowser module failed: {e}")

            # Fallback
            logger.warning("=" * 80)
            logger.warning("BROWSER AUTO-OPEN FAILED - MANUAL ACTION REQUIRED")
            logger.warning(f"Please open this URL manually: {url}")
            logger.warning("=" * 80)
            print("\nOpen CAPTCHA manually:", url)

        except Exception as e:
            logger.warning(f"Failed to auto-open browser: {e}")
            logger.warning(f"Please manually open: {container_info.get('auto_connect_url', 'N/A')}")

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
                print("CAPTCHA SOLVER READY")
                print("="*80)
                print(f"Open this URL in your browser to solve the CAPTCHA:")
                print(f"   {url}")
                print("="*80)
                print("The VNC interface will auto-connect - no password needed!")
                print("="*80 + "\n")
                
                logger.info(f"VNC Interface ready: {url}")
                
        except Exception as e:
            logger.error(f"Error logging URL: {e}")
    
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
        
        logger.info(f"Job queued: {job_id} for {email}")
        
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
            logger.info(f"Job processed immediately: {job_data['job_id']}")
            return result["container_id"]
        else:
            logger.warning(f"Failed to process job: {job_data['job_id']}")
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
                    logger.info(f"Processed queued job: {job_data['job_id']}")
                    
                    # Store job-to-container mapping
                    self.manager.redis_client.hset(
                        "job_container_mapping",
                        job_data["job_id"],
                        result["container_id"]
                    )
                else:
                    logger.warning(f"Failed to process queued job: {job_data['job_id']}")
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


class AutomatedCaptchaHandler:
    """Enhanced captcha handler with full automation"""
    
    def __init__(self):
        self.manager = get_manager()
        self.queue = CaptchaJobQueue(self.manager)
    
    def solve_captcha_automated(self, email: str, cred_id: str, auto_open: bool = True) -> dict:
        try:
            logger.info(f"🚀 Starting automated CAPTCHA solving for: {email}")
            
            # 🔧 CRITICAL: Check if session file exists BEFORE starting container
            session_file = f"/app/shared_volume/captcha_session_{email}.json"
            if not os.path.exists(session_file):
                logger.warning(f"⚠️ No session file found for {email}")
                logger.warning("   This means the main app didn't save session data properly!")
                logger.warning("   VNC container will use manual fallback mode")
            else:
                logger.info(f"✅ Session file found: {session_file}")
                size = os.path.getsize(session_file)
                logger.info(f"   📏 Size: {size} bytes")
            
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
            
            # Add to queue file for VNC watcher
            queue_file = "/app/shared_volume/captcha_queue.txt"
            try:
                with open(queue_file, "a") as f:
                    f.write(f"{email}\n")
                logger.info(f"✅ Added {email} to CAPTCHA queue for VNC processing")
            except Exception as queue_error:
                logger.error(f"❌ Failed to write to queue file: {queue_error}")
            
            print(f"""
    {'='*80}
    🎯 AUTOMATED CAPTCHA SOLVER STARTED (SESSION PRESERVED)
    {'='*80}
    📧 Email: {email}
    🐳 Container: {container_id[:12]}
    🖥️ VNC Port: {result['vnc_port']}
    🌐 noVNC Port: {result['novnc_port']}
    🔗 Web Interface: {result['auto_connect_url']}
    📄 Session Data: {'✅ Available' if result.get('session_available') else '❌ Manual mode'}

    STATUS:
    ✅ Container started with session preservation
    ✅ Email added to VNC queue for processing
    {'✅ Automatic session transfer mode' if result.get('session_available') else '⚠️ Manual fallback mode - no session data found'}

    Will auto-cleanup in 15 minutes if not completed
    {'='*80}
    """)

            # Auto-open browser if requested
            if auto_open:
                auto_open_browser(result, delay=5)
                print("🌐 Browser will auto-open in 5 seconds...")

            # Wait for container readiness
            timeout = 30
            start = time.time()
            while time.time() - start < timeout:
                if self.manager.is_container_ready(container_id):
                    logger.info(f"✅ Container {container_id[:12]} is ready")
                    break
                time.sleep(1)
            else:
                logger.warning(f"⚠️ Container {container_id[:12]} not ready after {timeout}s")

            # Start result monitoring
            self._start_result_monitoring(container_id, email)

            return {
                "status": "started",
                "container_id": container_id,
                "email": email,
                "vnc_port": result["vnc_port"],
                "novnc_port": result["novnc_port"],
                "auto_connect_url": result["auto_connect_url"],
                "session_available": result.get("session_available", False),
                "message": "CAPTCHA solver started successfully with session preservation",
                "estimated_time": "5-15 minutes",
                "mode": "Automatic session transfer" if result.get("session_available") else "Manual fallback",
                "instructions": [
                    "1. Browser will auto-open to VNC interface",
                    "2. VNC will auto-connect (no button clicks needed)", 
                    "3. CAPTCHA watcher will handle session restoration automatically" if result.get("session_available") else "3. Manual login required - session data not available",
                    "4. Solve the CAPTCHA in the browser window",
                    "5. System will auto-detect completion",
                    "6. Container will auto-cleanup"
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
        """Monitor for CAPTCHA completion results"""
        def monitor():
            try:
                timeout = 900  # 15 minutes
                start_time = time.time()
                check_interval = 30
                
                logger.info(f"🔍 Starting result monitoring for {email}")
                
                while time.time() - start_time < timeout:
                    if not self.manager._is_container_running(container_id):
                        logger.info(f"📦 Container stopped: {container_id[:12]}")
                        break
                    
                    if self._check_captcha_solved(email):
                        logger.info(f"🎉 CAPTCHA solved detected for {email}")
                        container = self.manager._load_container(container_id)
                        if container:
                            container.status = ContainerStatus.COMPLETED
                            container.completed_at = time.time()
                            self.manager._save_container(container)
                        
                        # Let main app detect success
                        time.sleep(30)
                        self.manager.stop_container(container_id)
                        break
                    
                    time.sleep(check_interval)
                
                if time.time() - start_time >= timeout:
                    logger.warning(f"⏰ CAPTCHA timeout for {email}")
                    self.manager.stop_container(container_id)
            
            except Exception as e:
                logger.error(f"❌ Result monitoring error: {e}")
        
        threading.Thread(target=monitor, daemon=True).start()
    
    def _check_captcha_solved(self, email: str) -> bool:
        """Check if CAPTCHA was solved based on multiple indicators"""
        # Check success file
        success_file = f"/app/shared_volume/captcha_success_{email}.json"
        if os.path.exists(success_file):
            try:
                with open(success_file, 'r') as f:
                    data = json.load(f)
                if data.get('status') == 'solved':
                    return True
            except:
                pass
        
        # Check cookies file
        cookie_path = f"/app/cookies/linkedin_cookies_{email}.pkl"
        if os.path.exists(cookie_path):
            try:
                mtime = os.path.getmtime(cookie_path)
                # Recent cookies (within 5 minutes)
                if time.time() - mtime < 300:
                    return True
            except:
                pass
                
        return False

    def get_status(self, container_id: str = None, email: str = None) -> dict:
        """Get status of CAPTCHA solving process"""
        if container_id:
            return self.manager.get_container_info(container_id)
        elif email:
            containers = self.manager.get_active_containers()
            for container in containers:
                if container["email"] == email:
                    return self.manager.get_container_info(container["container_id"])
        return {"error": "Container not found"}