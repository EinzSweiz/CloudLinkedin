# login.py - Enhanced with automatic session transfer using NEW docker manager
import os
import time
import json
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

from parser.engine.core.captcha_handler import FullyAutomatedCaptchaHandler
from parser_controler.docker_manager import get_manager, AutomatedCaptchaHandler
from parser.engine.core.acount_credits_operator import Credential

credential = Credential()
logger = logging.getLogger(__name__)
LINKEDIN_LOGIN_URL = settings.LINKEDIN_LOGIN_URL
LOGS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

def save_captcha_session_for_transfer(driver, email):
    """Save current session data for automatic transfer to VNC using NEW shared volume system"""
    try:
        session_data = {
            'email': email,
            'current_url': driver.current_url,
            'cookies': driver.get_cookies(),
            'page_source': driver.page_source[:10000],
            'timestamp': time.time(),
            'user_agent': driver.execute_script("return navigator.userAgent;"),
            'window_size': driver.get_window_size(),
            'local_storage': driver.execute_script("return JSON.stringify(localStorage);"),
            'session_storage': driver.execute_script("return JSON.stringify(sessionStorage);")
        }
        
        # 🔧 NEW: Save to shared volume that NEW docker manager mounts
        session_file = f"/app/shared_volume/captcha_session_{email}.json"
        os.makedirs(os.path.dirname(session_file), exist_ok=True)
        
        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        logger.info(f"💾 Session data saved for NEW docker manager transfer: {session_file}")
        logger.info(f"   URL: {session_data['current_url']}")
        logger.info(f"   Cookies: {len(session_data['cookies'])}")
        logger.info(f"   Page source: {len(session_data['page_source'])} chars")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to save session data: {e}")
        return False

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
            
            # 🚀 NEW: Save session data for automatic transfer to NEW docker manager
            logger.info("💾 Saving session data for NEW docker manager VNC transfer...")
            if save_captcha_session_for_transfer(driver, EMAIL):
                logger.info("✅ Session data saved successfully for NEW docker system")
            else:
                logger.warning("⚠️ Failed to save session data - VNC will use fallback mode")
            
            # 🔧 NEW: Use the enhanced captcha handler with NEW docker manager
            captcha_handler = FullyAutomatedCaptchaHandler(
                auto_open_browser=True,  # Auto-open browser to VNC
                timeout=900  # 15 minutes timeout
            )
            
            cred_id = creds.get("cred_id", EMAIL)
            
            logger.info("🤖 Starting FULLY AUTOMATIC CAPTCHA resolution with NEW docker manager...")
            logger.info("   Features:")
            logger.info("   ✅ NEW docker manager with auto port assignment")
            logger.info("   ✅ Session data transferred automatically")
            logger.info("   ✅ VNC will show the exact CAPTCHA page")
            logger.info("   ✅ Zero manual navigation required")
            logger.info("   ✅ Real-time monitoring and auto-cleanup")
            
            # 🎯 NEW: This uses FullyAutomatedCaptchaHandler.solve_captcha() 
            #         which internally uses AutomatedCaptchaHandler and ScalableCaptchaManager
            if captcha_handler.solve_captcha(EMAIL, cred_id):
                logger.info("🎉 NEW docker manager CAPTCHA resolution completed!")
                
                # Wait a moment for VNC resolution and cookie saving
                logger.info("⏳ Waiting for automatic CAPTCHA resolution...")
                time.sleep(30)  # Give VNC time to solve and save cookies
                
                # Check if cookies were updated by VNC
                if load_cookies(driver, cookie_path):
                    logger.info(f"[LOGIN] ✅ Success after NEW docker manager VNC resolution: {EMAIL}")
                    return driver

                # Try refreshing current session
                try:
                    driver.refresh()
                    time.sleep(5)
                    
                    current_url = driver.current_url
                    if "feed" in current_url:
                        save_cookies(driver, cookie_path)
                        logger.info(f"[LOGIN] ✅ Success after session refresh: {EMAIL}")
                        return driver
                    else:
                        logger.warning(f"[LOGIN] Still not logged in after NEW docker resolution: {EMAIL}")
                        
                except Exception as refresh_error:
                    logger.error(f"[LOGIN] Error refreshing session: {refresh_error}")

                # Final attempt - navigate to feed directly
                try:
                    driver.get("https://www.linkedin.com/feed/")
                    time.sleep(3)

                    if "feed" in driver.current_url:
                        save_cookies(driver, cookie_path)
                        logger.info(f"[LOGIN] ✅ Success after direct navigation: {EMAIL}")
                        return driver
                        
                except Exception as nav_error:
                    logger.error(f"[LOGIN] Navigation error: {nav_error}")

                # If all methods fail
                logger.warning(f"[LOGIN] ❌ NEW docker manager CAPTCHA resolution failed for: {EMAIL}")
                credential.mark_invalid(reason="new_docker_captcha_failed")
                driver.quit()
                raise Exception("new_docker_captcha_resolution_failed")

            else:
                # NEW docker manager captcha timeout or failure
                logger.error(f"[LOGIN] ❌ NEW docker manager CAPTCHA handler failed: {EMAIL}")
                credential.mark_invalid(reason="new_docker_captcha_timeout")
                driver.quit()
                raise Exception("new_docker_captcha_timeout")

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

# 🔧 NEW: Additional utility function to check NEW docker manager status
def get_captcha_manager_status():
    """Get status of the NEW docker manager"""
    try:
        manager = get_manager()
        active_containers = manager.get_active_containers()
        
        return {
            "active_containers": len(active_containers),
            "max_capacity": manager.max_containers,
            "containers": active_containers
        }
    except Exception as e:
        logger.error(f"Error getting NEW docker manager status: {e}")
        return {"error": str(e)}