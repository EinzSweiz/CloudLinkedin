# login.py - Fixed version using VNC captcha handler
import os
import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
import undetected_chromedriver as uc
from django.conf import settings
from parser.engine.core.cookies import save_cookies, load_cookies
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from parser.engine.core.proxy_extension import create_proxy_auth_extension
from parser.engine.core.proxy import proxies
from parser.engine.core.user_agents import user_agents
from parser.engine.core.acount_credits_operator import Credential

credential = Credential()
logger = logging.getLogger(__name__)
LINKEDIN_LOGIN_URL = settings.LINKEDIN_LOGIN_URL
LOGS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

def get_logged_driver(retry_count=3):
    logger.info("[LOGIN] Attempting login using saved cookies or credentials...")
    
    try:
        ip, port, user, pwd = proxies.get_random_proxy()
        profile_path = f"/app/profiles/{int(time.time())}"
        os.makedirs(profile_path, exist_ok=True)

        options = Options()
        options.add_argument('--headless=chrome')
        options.add_argument(f'--user-agent={user_agents.get_random_user_agent()}')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument(f"--user-data-dir={profile_path}")
        options.add_argument('--disable-gpu')
        options.add_argument('--remote-debugging-port=0')
        
        plugin_path = create_proxy_auth_extension(proxy_host=ip, proxy_port=int(port), proxy_username=user, proxy_password=pwd)
        if not os.path.exists(plugin_path):
            raise ValueError("Proxy plugin creation failed or path is invalid")
        options.add_extension(plugin_path)

        logger.info(f"[CHROME] Starting Chrome driver...")
        driver = uc.Chrome(options=options, version_main=136)
        driver.set_page_load_timeout(60)
        driver.implicitly_wait(20)
        logger.info(f"[CHROME] ✅ Chrome started successfully")

        # Anti-detection
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            """
        })

        # Get credentials
        creds = credential.get_credentials()
        if not creds:
            raise Exception("no_valid_credentials")

        EMAIL = creds["email"]
        PASSWORD = creds["password"]
        cookie_path = f"/app/cookies/linkedin_cookies_{EMAIL}.pkl"

        # Try cookies first
        logger.info(f"[LOGIN] Trying cookies for: {EMAIL}")
        if load_cookies(driver, cookie_path):
            logger.info(f"[LOGIN] ✅ Success with cookies: {EMAIL}")
            return driver
        else:
            if os.path.exists(cookie_path):
                os.remove(cookie_path)

        # Manual login
        logger.info(f"[LOGIN] Attempting manual login for: {EMAIL}")
        driver.get(LINKEDIN_LOGIN_URL)
        
        wait = WebDriverWait(driver, 30)
        email_input = wait.until(EC.presence_of_element_located((By.ID, "username")))
        password_input = wait.until(EC.presence_of_element_located((By.ID, "password")))
        
        email_input.clear()
        email_input.send_keys(EMAIL)
        
        password_input.clear()
        password_input.send_keys(PASSWORD)
        password_input.send_keys(Keys.RETURN)
        
        time.sleep(6)

        current_url = driver.current_url
        title = driver.title.lower()
        
        logger.info(f"[LOGIN] After login attempt - URL: {current_url}")

        if "feed" in current_url:
            save_cookies(driver, cookie_path)
            logger.info(f"[LOGIN] ✅ Direct login success: {EMAIL}")
            return driver
            
        elif "checkpoint" in current_url or "verify" in title or "security" in title:
            logger.warning(f"[CAPTCHA DETECTED] For: {EMAIL}")
            
            # Use VNC captcha handler (the one that actually works!)
            captcha_handler = VNCCaptchaHandler()
            
            if captcha_handler.request_manual_captcha_solve(EMAIL, driver):
                # Captcha resolved, test navigation
                try:
                    driver.get("https://www.linkedin.com/feed/")
                    time.sleep(3)
                    
                    if "feed" in driver.current_url:
                        save_cookies(driver, cookie_path)
                        logger.info(f"[LOGIN] ✅ Success after VNC captcha resolution: {EMAIL}")
                        return driver
                    else:
                        logger.warning(f"[LOGIN] ❌ Still not logged in after VNC captcha: {EMAIL}")
                        credential.mark_invalid(reason="vnc_captcha_failed")
                        driver.quit()
                        raise Exception("vnc_captcha_resolution_failed")
                except Exception as nav_error:
                    logger.error(f"[LOGIN] Error after VNC captcha resolution: {nav_error}")
                    credential.mark_invalid(reason="vnc_captcha_navigation_failed")
                    driver.quit()
                    raise Exception("vnc_captcha_navigation_failed")
            else:
                # VNC captcha timeout
                credential.mark_invalid(reason="vnc_captcha_timeout")
                driver.quit()
                raise Exception("vnc_captcha_timeout")

        elif "login" in current_url:
            credential.mark_invalid(reason="bad_login")
            raise Exception("bad_login")
        else:
            credential.mark_invalid(reason="unknown")
            raise Exception("unknown")

    except Exception as e:
        logger.error(f"[LOGIN ERROR] {e}")
        
        # Save debug info if possible
        try:
            if 'driver' in locals():
                screenshot_path = os.path.join(LOGS_DIR, f"login_error_{int(time.time())}.png")
                html_path = os.path.join(LOGS_DIR, f"page_source_{int(time.time())}.html")
                driver.save_screenshot(screenshot_path)
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                logger.info(f"[DEBUG] Saved screenshot: {screenshot_path}")
        except Exception as save_error:
            logger.error(f"[SAVE ERROR] {save_error}")
        
        # Always cleanup driver
        try:
            if 'driver' in locals():
                driver.quit()
        except:
            pass

        if retry_count > 0 and str(e) == "bad_login":
            logger.info(f"[RETRY] Retrying login... {retry_count} attempts left")
            return get_logged_driver(retry_count - 1)
        else:
            raise

# VNC Captcha Handler - This actually works in Docker!
class VNCCaptchaHandler:
    def __init__(self):
        self.captcha_queue_file = "/app/shared_volume/captcha_queue.txt"
        self.captcha_resolved_file = "/app/shared_volume/captcha_resolved.txt"
        self.max_wait_time = 600  # 10 minutes
    
    def request_manual_captcha_solve(self, email: str, driver) -> bool:
        """VNC-based captcha handler that actually works in Docker"""
        try:
            logger.info(f"[CAPTCHA] 🔐 Adding {email} to VNC captcha queue")
            
            # Add to queue
            os.makedirs("/app/shared_volume", exist_ok=True)
            with open(self.captcha_queue_file, "a") as f:
                f.write(f"{email}\n")
            
            print(f"""
{'='*80}
🔐 CAPTCHA DETECTED - VNC RESOLUTION REQUIRED
{'='*80}
Account: {email}

📺 OPTION 1: VNC Client
   Connect to: localhost:5900
   Password: password

🌐 OPTION 2: Web Browser  
   Open: http://localhost:6080/vnc.html
   (No password needed)

⏰ Waiting up to {self.max_wait_time/60} minutes...
{'='*80}
""")
            
            # Wait for resolution
            start_time = time.time()
            while time.time() - start_time < self.max_wait_time:
                if self._is_resolved(email):
                    logger.info(f"[CAPTCHA] ✅ VNC resolution completed for {email}")
                    self._cleanup(email)
                    return True
                
                # Progress update every minute
                elapsed = time.time() - start_time
                if int(elapsed) % 60 == 0 and elapsed > 0:
                    remaining = (self.max_wait_time - elapsed) / 60
                    print(f"⏰ Still waiting... {remaining:.1f} minutes remaining")
                
                time.sleep(10)
            
            logger.warning(f"[CAPTCHA] ❌ Timeout waiting for VNC resolution: {email}")
            self._cleanup(email)
            return False
            
        except Exception as e:
            logger.error(f"[CAPTCHA] Error: {e}")
            return False
    
    def _is_resolved(self, email: str) -> bool:
        if not os.path.exists(self.captcha_resolved_file):
            return False
        with open(self.captcha_resolved_file, "r") as f:
            return email in f.read()
    
    def _cleanup(self, email: str):
        for filepath in [self.captcha_queue_file, self.captcha_resolved_file]:
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r") as f:
                        lines = f.readlines()
                    with open(filepath, "w") as f:
                        for line in lines:
                            if line.strip() != email:
                                f.write(line)
                except:
                    pass