# parser/engine/linkedin/login_with_manual_captcha.py
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

logger = logging.getLogger(__name__)
LINKEDIN_LOGIN_URL = "https://www.linkedin.com/login"

class ManualCaptchaHandler:
    def __init__(self):
        self.captcha_queue_file = "./shared_volume/captcha_queue.txt"
        self.captcha_resolved_file = "./shared_volume/captcha_resolved.txt"
        self.max_wait_time = 600  # 10 minutes for manual resolution
        
    def show_captcha_to_user(self, email: str, driver) -> bool:
        """
        Shows the captcha/checkpoint page to user for manual resolution
        Returns True if user successfully resolves it, False if timeout
        """
        try:
            # 1. Add email to queue file for monitoring
            logger.info(f"[CAPTCHA] Adding {email} to manual resolution queue")
            with open(self.captcha_queue_file, "a") as f:
                f.write(f"{email}\n")
            
            # 2. Take screenshot for reference
            screenshot_path = f"./shared_volume/captcha_{email}_{int(time.time())}.png"
            driver.save_screenshot(screenshot_path)
            logger.info(f"[CAPTCHA] Screenshot saved: {screenshot_path}")
            
            # 3. Switch to non-headless mode for user interaction
            current_url = driver.current_url
            profile_dir = driver.capabilities.get('chrome', {}).get('userDataDir', '')
            
            logger.info(f"[CAPTCHA] Launching visible browser for manual captcha resolution...")
            
            # Close headless driver temporarily but keep the session
            driver.quit()
            
            # Launch visible browser with same profile to maintain session
            visible_driver = self._launch_visible_browser(email, profile_dir)
            
            if visible_driver:
                # Navigate to the checkpoint page
                visible_driver.get(current_url)
                time.sleep(2)
                
                # Wait for user to solve captcha manually
                success = self._wait_for_manual_resolution(email, visible_driver)
                
                if success:
                    # Save cookies after successful resolution
                    cookie_path = f"./cookies/linkedin_cookies_{email}.pkl"
                    save_cookies(visible_driver, cookie_path)
                    
                # Close visible browser
                visible_driver.quit()
                
                return success
            
            return False
            
        except Exception as e:
            logger.error(f"[CAPTCHA] Error in manual captcha handler: {e}")
            return False
        finally:
            self._cleanup_queue_entry(email)
    
    def _launch_visible_browser(self, email: str, profile_dir: str = None):
        """Launch a visible browser for manual captcha solving"""
        try:
            options = Options()
            
            # Make browser visible (remove headless)
            options.add_argument(f'--user-agent={user_agents.get_random_user_agent()}')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--window-size=1200,800')
            
            # Use existing profile if available
            if profile_dir and os.path.exists(profile_dir):
                options.add_argument(f"--user-data-dir={profile_dir}")
            else:
                # Create new profile directory
                new_profile = f"/app/profiles/manual_{email}_{int(time.time())}"
                os.makedirs(new_profile, exist_ok=True)
                options.add_argument(f"--user-data-dir={new_profile}")
            
            # Add proxy if needed (optional for manual resolution)
            try:
                ip, port, user, pwd = proxies.get_random_proxy()
                plugin_path = create_proxy_auth_extension(
                    proxy_host=ip, 
                    proxy_port=int(port), 
                    proxy_username=user, 
                    proxy_password=pwd
                )
                options.add_extension(plugin_path)
            except Exception as proxy_error:
                logger.warning(f"[CAPTCHA] Could not set proxy for manual browser: {proxy_error}")
            
            driver = uc.Chrome(options=options, version_main=136)
            
            # Anti-detection measures
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.navigator.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                """
            })
            
            return driver
            
        except Exception as e:
            logger.error(f"[CAPTCHA] Failed to launch visible browser: {e}")
            return None
    
    def _wait_for_manual_resolution(self, email: str, driver) -> bool:
        """
        Wait for user to manually solve the captcha and login
        Monitor the URL changes to detect success
        """
        logger.info(f"[CAPTCHA] 🔐 MANUAL CAPTCHA RESOLUTION REQUIRED")
        logger.info(f"[CAPTCHA] Account: {email}")
        logger.info(f"[CAPTCHA] Please solve the captcha/challenge in the opened browser window")
        logger.info(f"[CAPTCHA] The system will automatically detect when you're logged in")
        logger.info(f"[CAPTCHA] Waiting up to {self.max_wait_time/60:.1f} minutes...")
        
        print(f"\n" + "="*60)
        print(f"🔐 CAPTCHA RESOLUTION REQUIRED FOR: {email}")
        print(f"📋 Please complete the following steps:")
        print(f"   1. Look at the opened Chrome browser window")
        print(f"   2. Solve any captcha or security challenge")
        print(f"   3. Complete the login process")
        print(f"   4. Wait until you see the LinkedIn feed")
        print(f"   5. The system will automatically continue")
        print(f"⏰ Timeout: {self.max_wait_time/60:.1f} minutes")
        print("="*60 + "\n")
        
        start_time = time.time()
        last_url = driver.current_url
        
        while time.time() - start_time < self.max_wait_time:
            try:
                current_url = driver.current_url
                page_title = driver.title.lower()
                
                # Check if user has successfully logged in
                if "feed" in current_url or "linkedin.com/in/" in current_url:
                    logger.info(f"[CAPTCHA] ✅ SUCCESS! User successfully logged in: {email}")
                    print(f"✅ SUCCESS! Login detected for {email}")
                    
                    # Mark as resolved
                    with open(self.captcha_resolved_file, "a") as f:
                        f.write(f"{email}\n")
                    
                    return True
                
                # Check if still on login/checkpoint page
                elif "login" in current_url or "checkpoint" in current_url or "challenge" in current_url:
                    # Still working on captcha - continue waiting
                    if current_url != last_url:
                        logger.info(f"[CAPTCHA] Page changed, user is working on it...")
                        last_url = current_url
                
                # Check for other successful indicators
                elif "linkedin.com" in current_url and "login" not in current_url:
                    # Try to navigate to feed to confirm login
                    try:
                        driver.get("https://www.linkedin.com/feed/")
                        time.sleep(3)
                        if "feed" in driver.current_url:
                            logger.info(f"[CAPTCHA] ✅ SUCCESS! Confirmed login via feed: {email}")
                            print(f"✅ SUCCESS! Login confirmed for {email}")
                            
                            with open(self.captcha_resolved_file, "a") as f:
                                f.write(f"{email}\n")
                            
                            return True
                    except Exception as nav_error:
                        logger.debug(f"[CAPTCHA] Navigation test failed: {nav_error}")
                
                # Wait before next check
                time.sleep(10)  # Check every 10 seconds
                
                # Print progress every minute
                elapsed = time.time() - start_time
                if int(elapsed) % 60 == 0 and int(elapsed) > 0:
                    remaining = (self.max_wait_time - elapsed) / 60
                    print(f"⏰ Still waiting... {remaining:.1f} minutes remaining")
                
            except Exception as e:
                logger.warning(f"[CAPTCHA] Error during resolution wait: {e}")
                time.sleep(5)
        
        # Timeout reached
        logger.warning(f"[CAPTCHA] ❌ TIMEOUT: User did not resolve captcha in time for {email}")
        print(f"❌ TIMEOUT: Captcha not resolved in time for {email}")
        return False
    
    def _cleanup_queue_entry(self, email: str):
        """Remove email from queue and resolved files"""
        for filepath in [self.captcha_queue_file, self.captcha_resolved_file]:
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r") as f:
                        lines = f.readlines()
                    
                    with open(filepath, "w") as f:
                        for line in lines:
                            if line.strip() != email:
                                f.write(line)
                except Exception as e:
                    logger.warning(f"[CAPTCHA] Error cleaning up {filepath}: {e}")


def get_logged_driver_with_manual_captcha(retry_count=3):
    credential = Credential()
    captcha_handler = ManualCaptchaHandler()

    for attempt in range(retry_count):
        logger.info(f"[LOGIN] Attempt {attempt + 1}/{retry_count}")

        try:
            creds = credential.get_credentials()
            if not creds:
                raise Exception("No valid credentials available")

            EMAIL = creds["email"]
            PASSWORD = creds["password"]

            profile_path = f"/app/profiles/{EMAIL}_{int(time.time())}"
            os.makedirs(profile_path, exist_ok=True)

            ip, port, user, pwd = proxies.get_random_proxy()

            options = Options()
            options.add_argument('--headless=chrome')  # headless first
            options.add_argument(f'--user-agent={user_agents.get_random_user_agent()}')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument(f"--user-data-dir={profile_path}")

            plugin_path = create_proxy_auth_extension(
                proxy_host=ip, proxy_port=int(port),
                proxy_username=user, proxy_password=pwd
            )
            options.add_extension(plugin_path)

            driver = uc.Chrome(options=options, version_main=136)

            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.navigator.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                """
            })

            cookie_path = f"/app/cookies/linkedin_cookies_{EMAIL}.pkl"
            if load_cookies(driver, cookie_path):
                logger.info(f"[LOGIN] ✅ Success with saved cookies: {EMAIL}")
                return driver

            logger.info(f"[LOGIN] Attempting manual login for: {EMAIL}")
            driver.get(LINKEDIN_LOGIN_URL)

            wait = WebDriverWait(driver, 30)
            email_input = wait.until(EC.presence_of_element_located((By.ID, "username")))
            password_input = wait.until(EC.presence_of_element_located((By.ID, "password")))

            email_input.clear()
            email_input.send_keys(EMAIL)
            time.sleep(1)

            password_input.clear()
            password_input.send_keys(PASSWORD)
            time.sleep(1)

            password_input.send_keys(Keys.RETURN)
            time.sleep(5)

            current_url = driver.current_url
            page_title = driver.title.lower()

            if "feed" in current_url:
                save_cookies(driver, cookie_path)
                logger.info(f"[LOGIN] ✅ Successful login: {EMAIL}")
                return driver

            elif "checkpoint" in current_url or "verify" in page_title or "security" in page_title:
                logger.warning(f"[CAPTCHA DETECTED] For: {EMAIL}")
                if captcha_handler.show_captcha_to_user(EMAIL, driver):
                    try:
                        driver.get("https://www.linkedin.com/feed/")
                        time.sleep(3)
                        if "feed" in driver.current_url:
                            save_cookies(driver, cookie_path)
                            logger.info(f"[LOGIN] ✅ Success after captcha resolution: {EMAIL}")
                            return driver
                        else:
                            credential.mark_invalid(reason="captcha_failed")
                            driver.quit()
                            raise Exception("captcha_resolution_failed")
                    except Exception as nav_error:
                        logger.error(f"[LOGIN] Error after captcha resolution: {nav_error}")
                        credential.mark_invalid(reason="captcha_navigation_failed")
                        driver.quit()
                        raise Exception("captcha_navigation_failed")
                else:
                    credential.mark_invalid(reason="captcha_timeout")
                    driver.quit()
                    raise Exception("captcha_timeout")

            elif "login" in current_url:
                credential.mark_invalid(reason="invalid_credentials")
                driver.quit()
                raise Exception("invalid_credentials")
            else:
                credential.mark_invalid(reason="unknown_redirect")
                driver.quit()
                raise Exception(f"unknown_redirect_to_{current_url}")

        except Exception as e:
            logger.error(f"[LOGIN] Attempt {attempt + 1} failed: {e}")
            try:
                driver.quit()
            except:
                pass

            if attempt == retry_count - 1:
                logger.error(f"[LOGIN] All {retry_count} attempts failed")
                raise
            else:
                time.sleep(10)

    raise Exception("All login attempts exhausted")