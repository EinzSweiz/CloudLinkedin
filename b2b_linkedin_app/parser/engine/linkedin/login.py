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

def check_captcha_success(email, timeout=120):
    """Check if CAPTCHA was solved in VNC container"""
    logger.info(f"🔍 Checking for CAPTCHA success notification for {email}...")
    
    success_file = f"/app/shared_volume/captcha_success_{email}.json"
    flag_file = f"/app/shared_volume/captcha_solved_{email.replace('@', '_')}.flag"
    shared_cookies = f"/app/shared_volume/solved_cookies_{email}.pkl"
    
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        # Check for success notification
        if os.path.exists(success_file):
            try:
                with open(success_file, 'r') as f:
                    success_data = json.load(f)
                
                logger.info("🎉 CAPTCHA SUCCESS DETECTED!")
                logger.info(f"   Status: {success_data.get('status')}")
                logger.info(f"   Final URL: {success_data.get('final_url')}")
                logger.info(f"   Solved at: {time.ctime(success_data.get('timestamp', 0))}")
                
                # Check if cookies are available
                if os.path.exists(shared_cookies):
                    logger.info(f"✅ Solved cookies found: {shared_cookies}")
                    return success_data
                else:
                    logger.warning("⚠️ Success detected but cookies not found")
                    
            except Exception as e:
                logger.error(f"Error reading success data: {e}")
        
        # Alternative: check for flag file
        elif os.path.exists(flag_file):
            logger.info("🎉 CAPTCHA success flag detected!")
            if os.path.exists(shared_cookies):
                return {"status": "solved", "cookies_available": True}
        
        time.sleep(5)  # Check every 5 seconds
    
    logger.warning(f"⚠️ No CAPTCHA success detected within {timeout} seconds")
    return None

def recover_solved_session(driver, email, success_data):
    """Recover the solved session from VNC container"""
    try:
        shared_cookies = f"/app/shared_volume/solved_cookies_{email}.pkl"
        local_cookies = f"/app/cookies/linkedin_cookies_{email}.pkl"
        
        # Copy solved cookies to local path
        if os.path.exists(shared_cookies):
            import shutil
            os.makedirs("/app/cookies/", exist_ok=True)
            shutil.copy2(shared_cookies, local_cookies)
            logger.info(f"✅ Copied solved cookies: {shared_cookies} → {local_cookies}")
            
            # Test the cookies by loading them
            if load_cookies(driver, local_cookies):
                logger.info("✅ Successfully loaded solved cookies!")
                
                # Navigate to LinkedIn feed to verify
                driver.get("https://www.linkedin.com/feed/")
                time.sleep(5)
                
                if "feed" in driver.current_url:
                    logger.info("🎉 Session recovery successful! Ready for parsing.")
                    return True
                else:
                    logger.warning("⚠️ Cookies loaded but not fully logged in")
                    return False
            else:
                logger.error("❌ Failed to load solved cookies")
                return False
        else:
            logger.error(f"❌ Solved cookies not found: {shared_cookies}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Session recovery failed: {e}")
        return False

def save_captcha_session_for_transfer(driver, email):
    """Enhanced session data capture with browser state preservation"""
    try:
        # Get comprehensive browser state
        session_data = {
            'email': email,
            'current_url': driver.current_url,
            'cookies': driver.get_cookies(),
            'page_source': driver.page_source[:10000],
            'timestamp': time.time(),
            'user_agent': driver.execute_script("return navigator.userAgent;"),
            'window_size': driver.get_window_size(),
            'local_storage': driver.execute_script("return JSON.stringify(localStorage);"),
            'session_storage': driver.execute_script("return JSON.stringify(sessionStorage);"),
            
            # Enhanced browser state capture
            'browser_fingerprint': {
                'platform': driver.execute_script("return navigator.platform;"),
                'language': driver.execute_script("return navigator.language;"),
                'languages': driver.execute_script("return navigator.languages;"),
                'timezone': driver.execute_script("return Intl.DateTimeFormat().resolvedOptions().timeZone;"),
                'screen': driver.execute_script("return {width: screen.width, height: screen.height, pixelDepth: screen.pixelDepth};"),
                'viewport': driver.execute_script("return {width: window.innerWidth, height: window.innerHeight};"),
            },
            
            # Capture request headers and network state
            'request_headers': driver.execute_script("""
                return {
                    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'accept-language': navigator.language + ',en;q=0.5',
                    'accept-encoding': 'gzip, deflate, br',
                    'cache-control': 'no-cache',
                    'pragma': 'no-cache',
                    'sec-fetch-dest': 'document',
                    'sec-fetch-mode': 'navigate',
                    'sec-fetch-site': 'same-origin',
                    'upgrade-insecure-requests': '1'
                };
            """),
            
            # Capture form data if present
            'form_data': driver.execute_script("""
                try {
                    var forms = document.forms;
                    var formData = {};
                    for(var i = 0; i < forms.length; i++) {
                        var form = forms[i];
                        formData[form.id || 'form_' + i] = {
                            action: form.action,
                            method: form.method,
                            elements: Array.from(form.elements).map(el => ({
                                name: el.name,
                                type: el.type,
                                value: el.type === 'password' ? '' : el.value
                            }))
                        };
                    }
                    return formData;
                } catch(e) { return {}; }
            """),
            
            # Page state indicators
            'page_state': {
                'title': driver.title,
                'ready_state': driver.execute_script("return document.readyState;"),
                'has_captcha': 'captcha' in driver.page_source.lower(),
                'has_challenge': 'challenge' in driver.current_url.lower(),
                'checkpoint_type': _detect_checkpoint_type(driver),
            },
            
            'linkedin_state': _capture_linkedin_state(driver),
        }
        
        # Save to shared volume
        session_file = f"/app/shared_volume/captcha_session_{email}.json"
        os.makedirs(os.path.dirname(session_file), exist_ok=True)
        
        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        logger.info(f"Enhanced session data saved: {session_file}")
        logger.info(f"   URL: {session_data['current_url']}")
        logger.info(f"   Cookies: {len(session_data['cookies'])}")
        logger.info(f"   Checkpoint Type: {session_data['page_state']['checkpoint_type']}")
        logger.info(f"   Browser Fingerprint: Captured")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to save enhanced session data: {e}")
        return False

def _detect_checkpoint_type(driver):
    """Detect specific type of LinkedIn checkpoint"""
    try:
        url = driver.current_url.lower()
        source = driver.page_source.lower()
        
        if 'captcha' in url or 'captcha' in source:
            return 'captcha_challenge'
        elif 'phone' in url or 'sms' in source:
            return 'phone_verification'
        elif 'email' in url or 'email' in source:
            return 'email_verification'
        elif 'challenge' in url:
            return 'security_challenge'
        elif 'checkpoint' in url:
            return 'general_checkpoint'
        else:
            return 'unknown'
    except:
        return 'detection_failed'

def _capture_linkedin_state(driver):
    """Capture LinkedIn-specific state information"""
    try:
        return driver.execute_script("""
            try {
                return {
                    // LinkedIn app data
                    app_version: window.appVersion || null,
                    page_instance: document.querySelector('meta[name="pageInstance"]')?.content || null,
                    page_key: document.querySelector('meta[name="pageKey"]')?.content || null,
                    tree_id: document.querySelector('meta[name="treeID"]')?.content || null,
                    
                    // CSRF and security tokens
                    csrf_token: document.querySelector('input[name="csrfToken"]')?.value || null,
                    challenge_id: window.location.pathname.split('/').pop() || null,
                    
                    // Form state
                    challenge_form: document.querySelector('form')?.action || null,
                    submit_button: document.querySelector('button[type="submit"]')?.textContent || null,
                    
                    // Page elements
                    has_captcha_iframe: !!document.querySelector('iframe[src*="captcha"]'),
                    has_recaptcha: !!document.querySelector('.g-recaptcha'),
                    has_challenge_text: !!document.querySelector('.challenge-description'),
                };
            } catch(e) {
                return { error: e.message };
            }
        """)
    except:
        return {'error': 'script_execution_failed'}

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
        driver.set_page_load_timeout(120)
        driver.implicitly_wait(10)
        logger.info(f"[CHROME] Chrome started successfully")

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
            logger.info(f"[LOGIN] Success with cookies: {EMAIL}")
            return driver
        else:
            if os.path.exists(cookie_path):
                os.remove(cookie_path)

        # Manual login - FIXED VERSION
        logger.info(f"[LOGIN] Attempting manual login for: {EMAIL}")
        driver.get(LINKEDIN_LOGIN_URL)

        # Add debugging
        logger.info(f"[LOGIN] Manual login - URL after navigation: {driver.current_url}")
        logger.info(f"[LOGIN] Manual login - Page title: {driver.title}")

        time.sleep(3)

        # Check what type of page we landed on
        page_source = driver.page_source.lower()
        current_url = driver.current_url.lower()

        if "welcome back" in page_source or "welcome back" in driver.title.lower():
            logger.info(f"[WELCOME BACK] Detected welcome back screen immediately for: {EMAIL}")
            
            try:
                # On welcome back page, only password field exists
                wait = WebDriverWait(driver, 15)
                password_input = wait.until(EC.presence_of_element_located((By.ID, "password")))
                
                logger.info("[WELCOME BACK] Found password field, filling it...")
                password_input.clear()
                password_input.send_keys(PASSWORD)
                
                # Submit the form
                try:
                    # Try to find and click the Sign in button
                    sign_in_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Sign in') or @type='submit']")
                    sign_in_btn.click()
                    logger.info("[WELCOME BACK] Clicked Sign in button")
                except:
                    # Fallback: press Enter
                    password_input.send_keys(Keys.RETURN)
                    logger.info("[WELCOME BACK] Pressed Enter on password field")
                
                time.sleep(8)  # Wait longer for response
                
                # Check result
                current_url_after = driver.current_url.lower()
                logger.info(f"[WELCOME BACK] After submission - URL: {current_url_after}")
                
                if "feed" in current_url_after:
                    save_cookies(driver, cookie_path)
                    logger.info(f"[LOGIN] ✅ Success with welcome back: {EMAIL}")
                    return driver
                elif "checkpoint" in current_url_after:
                    logger.warning(f"[WELCOME BACK] Redirected to checkpoint")
                    # Handle checkpoint below
                    current_url = current_url_after
                    title = driver.title.lower()
                else:
                    logger.warning(f"[WELCOME BACK] Unexpected result: {current_url_after}")
                    
            except Exception as welcome_error:
                logger.error(f"[WELCOME BACK] Error handling welcome back: {welcome_error}")
                # Continue to regular login handling below

        else:
            # Regular login page - check for username and password fields
            logger.info("[LOGIN] Detected regular login page")
            
            try:
                wait = WebDriverWait(driver, 20)
                
                # Check if username field exists (regular login)
                try:
                    email_input = wait.until(EC.presence_of_element_located((By.ID, "username")))
                    password_input = wait.until(EC.presence_of_element_located((By.ID, "password")))
                    
                    logger.info("[LOGIN] Found username and password fields")
                    
                    email_input.clear()
                    email_input.send_keys(EMAIL)
                    
                    password_input.clear()
                    password_input.send_keys(PASSWORD)
                    password_input.send_keys(Keys.RETURN)
                    
                    logger.info("[LOGIN] Submitted regular login form")
                    time.sleep(8)
                    
                except Exception as form_error:
                    logger.error(f"[LOGIN] Could not find login form elements: {form_error}")
                    raise Exception("login_form_not_found")
                    
            except Exception as login_error:
                logger.error(f"[LOGIN] Regular login failed: {login_error}")
                raise Exception("regular_login_failed")

        # Check final result after either welcome back or regular login
        current_url = driver.current_url.lower()
        title = driver.title.lower()
        page_source = driver.page_source

        logger.info(f"[LOGIN] Final check - URL: {current_url}")
        logger.info(f"[LOGIN] Final check - Title: {title}")

        if "feed" in current_url:
            save_cookies(driver, cookie_path)
            logger.info(f"[LOGIN] ✅ Direct login success: {EMAIL}")
            return driver
        
        elif "checkpoint" in current_url or "verify" in title or "security" in title:
            logger.warning(f"[CAPTCHA DETECTED] For: {EMAIL}")
            
            # Save session data for automatic transfer to NEW docker manager
            logger.info("Saving session data for NEW docker manager VNC transfer...")
            if save_captcha_session_for_transfer(driver, EMAIL):
                logger.info("Session data saved successfully for NEW docker system")
            else:
                logger.warning("⚠️ Failed to save session data - VNC will use fallback mode")
            
            # Use the enhanced captcha handler with NEW docker manager
            captcha_handler = FullyAutomatedCaptchaHandler(
                auto_open_browser=True,  # Auto-open browser to VNC
                timeout=900  # 15 minutes timeout
            )
            
            cred_id = creds.get("cred_id", EMAIL)
            
            logger.info("Starting FULLY AUTOMATIC CAPTCHA resolution with NEW docker manager...")
            logger.info("   Features:")
            logger.info("   NEW docker manager with auto port assignment")
            logger.info("   Session data transferred automatically")
            logger.info("   VNC will show the exact CAPTCHA page")
            logger.info("   Zero manual navigation required")
            logger.info("   Real-time monitoring and auto-cleanup")
            
            logger.info("🚀 Starting VNC CAPTCHA solving process...")
            captcha_result = captcha_handler.solve_captcha(EMAIL, cred_id)
            
            if captcha_result:
                logger.info("✅ VNC CAPTCHA container started successfully!")
                
                logger.info("🔍 Monitoring VNC container for CAPTCHA success...")
                success_data = check_captcha_success(EMAIL, timeout=900)  # 15 minutes
                
                if success_data:
                    logger.info("🎉 VNC CAPTCHA solved successfully!")
                    
                    if recover_solved_session(driver, EMAIL, success_data):
                        logger.info("🎉 Session recovery completed! Ready for parsing.")
                        return driver
                    else:
                        logger.warning("⚠️ Session recovery failed, trying direct cookie load...")
                        
                        # Fallback: try loading cookies directly
                        cookie_path = f"/app/cookies/linkedin_cookies_{EMAIL}.pkl"
                        if load_cookies(driver, cookie_path):
                            logger.info(f"✅ Success with direct cookie load: {EMAIL}")
                            return driver
                        else:
                            logger.error("❌ All recovery methods failed")
                else:
                    logger.warning("⚠️ VNC CAPTCHA solving timeout or failed")
                
                # Try refreshing current session
                try:
                    driver.refresh()
                    time.sleep(5)
                    
                    current_url = driver.current_url
                    if "feed" in current_url:
                        save_cookies(driver, cookie_path)
                        logger.info(f"[LOGIN] Success after session refresh: {EMAIL}")
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
                        logger.info(f"[LOGIN] Success after direct navigation: {EMAIL}")
                        return driver
                        
                except Exception as nav_error:
                    logger.error(f"[LOGIN] Navigation error: {nav_error}")

                # If all methods fail
                logger.warning(f"[LOGIN] NEW docker manager CAPTCHA resolution failed for: {EMAIL}")
                credential.mark_invalid(reason="new_docker_captcha_failed")
                driver.quit()
                raise Exception("new_docker_captcha_resolution_failed")

            else:
                # NEW docker manager captcha timeout or failure
                logger.error(f"[LOGIN] NEW docker manager CAPTCHA handler failed: {EMAIL}")
                credential.mark_invalid(reason="new_docker_captcha_timeout")
                driver.quit()
                raise Exception("new_docker_captcha_timeout")

        elif "login" in current_url:
            logger.warning(f"[LOGIN] Still on login page, form submission may have failed")
            raise Exception("login_form_submission_failed")
            
        else:
            logger.warning(f"[LOGIN] Unknown state after login attempt: {current_url}")
            raise Exception("unknown_post_login_state")

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