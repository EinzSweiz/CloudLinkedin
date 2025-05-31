# Browser-Based Captcha Handler - Shows captcha in user's web browser
import os
import time
import logging
import json
import uuid
from typing import Optional
from selenium.webdriver.remote.webdriver import WebDriver
from django.urls import reverse
from django.conf import settings

logger = logging.getLogger(__name__)

class BrowserCaptchaHandler:
    def __init__(self):
        self.captcha_sessions = {}  # Store active captcha sessions
        self.max_wait_time = 600  # 10 minutes
    
    def request_manual_captcha_solve(self, email: str, driver: WebDriver) -> bool:
        """
        Shows captcha in user's web browser through Django interface
        """
        try:
            logger.info(f"[CAPTCHA] 🔐 BROWSER CAPTCHA for: {email}")
            
            # 1. Create unique captcha session
            session_id = str(uuid.uuid4())
            
            # 2. Save session data
            session_data = self._save_captcha_session(session_id, email, driver)
            
            # 3. Store in memory for web interface
            self.captcha_sessions[session_id] = {
                'email': email,
                'status': 'pending',
                'created_at': time.time(),
                'current_url': driver.current_url,
                'cookies': driver.get_cookies(),
                'user_agent': driver.execute_script("return navigator.userAgent;")
            }
            
            # 4. Display instructions to user
            self._show_browser_instructions(session_id, email)
            
            # 5. Wait for resolution via web interface
            return self._wait_for_browser_resolution(session_id, email)
            
        except Exception as e:
            logger.error(f"[CAPTCHA] Error in browser captcha handler: {e}")
            return False
    
    def _save_captcha_session(self, session_id: str, email: str, driver: WebDriver) -> dict:
        """Save captcha session data for web interface"""
        try:
            session_data = {
                'session_id': session_id,
                'email': email,
                'current_url': driver.current_url,
                'cookies': driver.get_cookies(),
                'user_agent': driver.execute_script("return navigator.userAgent;"),
                'timestamp': int(time.time()),
                'screenshot_path': f"/app/shared_volume/captcha_{session_id}.png"
            }
            
            # Take screenshot
            driver.save_screenshot(session_data['screenshot_path'])
            
            # Save to file for persistence
            session_file = f"/app/shared_volume/captcha_session_{session_id}.json"
            with open(session_file, 'w') as f:
                json.dump(session_data, f, indent=2, default=str)
            
            return session_data
            
        except Exception as e:
            logger.error(f"[CAPTCHA] Error saving session: {e}")
            return {}
    
    def _show_browser_instructions(self, session_id: str, email: str):
        """Show instructions for browser-based captcha resolution"""
        
        # Get the captcha resolution URL
        captcha_url = f"http://localhost:8001/admin/solve-captcha/?session={session_id}"
        
        instructions = f"""
{'='*80}
🔐 CAPTCHA RESOLUTION REQUIRED - WEB BROWSER
{'='*80}

Account: {email}
Session ID: {session_id}

🌐 OPEN IN YOUR BROWSER:
   {captcha_url}

📋 INSTRUCTIONS:
   1. Open the URL above in your web browser
   2. You'll see the LinkedIn captcha page
   3. Solve the captcha/security challenge
   4. Complete login until you reach LinkedIn feed
   5. The system will automatically detect completion

⏰ Timeout: {self.max_wait_time/60:.0f} minutes

{'='*80}
        """
        
        print(instructions)
        
        # Also save instructions to file
        instructions_file = f"/app/shared_volume/captcha_instructions_{session_id}.txt"
        with open(instructions_file, 'w') as f:
            f.write(instructions)
    
    def _wait_for_browser_resolution(self, session_id: str, email: str) -> bool:
        """Wait for captcha resolution via web interface"""
        start_time = time.time()
        
        while time.time() - start_time < self.max_wait_time:
            try:
                # Check if session was resolved
                if session_id in self.captcha_sessions:
                    session = self.captcha_sessions[session_id]
                    
                    if session['status'] == 'resolved':
                        logger.info(f"[CAPTCHA] ✅ Browser captcha resolved for: {email}")
                        # Cleanup
                        del self.captcha_sessions[session_id]
                        return True
                    elif session['status'] == 'failed':
                        logger.warning(f"[CAPTCHA] ❌ Browser captcha failed for: {email}")
                        del self.captcha_sessions[session_id]
                        return False
                
                # Progress update every minute
                elapsed = time.time() - start_time
                if int(elapsed) % 60 == 0 and elapsed > 0:
                    remaining = (self.max_wait_time - elapsed) / 60
                    print(f"⏰ Still waiting for browser resolution... {remaining:.1f} minutes remaining")
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.warning(f"[CAPTCHA] Error during browser wait: {e}")
                time.sleep(5)
        
        # Timeout
        logger.warning(f"[CAPTCHA] ❌ Browser captcha timeout for {email}")
        if session_id in self.captcha_sessions:
            del self.captcha_sessions[session_id]
        return False
    
    def mark_session_resolved(self, session_id: str) -> bool:
        """Mark captcha session as resolved (called from web interface)"""
        if session_id in self.captcha_sessions:
            self.captcha_sessions[session_id]['status'] = 'resolved'
            self.captcha_sessions[session_id]['resolved_at'] = time.time()
            logger.info(f"[CAPTCHA] Session {session_id} marked as resolved")
            return True
        return False
    
    def mark_session_failed(self, session_id: str) -> bool:
        """Mark captcha session as failed (called from web interface)"""
        if session_id in self.captcha_sessions:
            self.captcha_sessions[session_id]['status'] = 'failed'
            self.captcha_sessions[session_id]['failed_at'] = time.time()
            logger.info(f"[CAPTCHA] Session {session_id} marked as failed")
            return True
        return False
    
    def get_session_data(self, session_id: str) -> dict:
        """Get captcha session data (for web interface)"""
        return self.captcha_sessions.get(session_id, {})
    
    def get_all_pending_sessions(self) -> dict:
        """Get all pending captcha sessions"""
        return {
            sid: data for sid, data in self.captcha_sessions.items() 
            if data.get('status') == 'pending'
        }

# Global instance for use across the application
browser_captcha_handler = BrowserCaptchaHandler()

# Alias for compatibility
CaptchaHandler = BrowserCaptchaHandler