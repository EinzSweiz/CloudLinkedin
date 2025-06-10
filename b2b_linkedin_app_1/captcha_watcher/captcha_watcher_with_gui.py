# FIXED captcha_watcher_with_gui.py - Properly reads session transfer from main app
import os
import sys
import time
import json
import socket
import logging

# Fix the import path for Docker
sys.path.append('/app')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/var/log/captcha_watcher.log')
    ]
)
logger = logging.getLogger(__name__)

try:
    from parser.engine.core.cookies import save_cookies
    from parser.engine.core.acount_credits_operator import Credential
except ImportError as e:
    logger.error(f"Import error: {e}")
    logger.error("Make sure you're running from the correct directory")
    sys.exit(1)

from selenium.webdriver.chrome.options import Options
import undetected_chromedriver as uc

# File paths for session transfer
WATCH_FILE = "/app/shared_volume/captcha_queue.txt"
PROCESSED_FILE = "/app/shared_volume/captcha_resolved.txt"

def ensure_vnc_ready(timeout=30):
    """Wait for VNC services to be ready"""
    logger.info("🔄 Waiting for VNC services to be ready...")
    
    for i in range(timeout):
        try:
            with socket.create_connection(("localhost", 5900), timeout=1):
                logger.info("✅ VNC (5900) is accessible")
            with socket.create_connection(("localhost", 6080), timeout=1):
                logger.info("✅ noVNC (6080) is accessible")
                logger.info("🎯 VNC services ready!")
                return True
        except Exception as e:
            logger.debug(f"Waiting for VNC services... ({i+1}/{timeout}): {e}")
            time.sleep(1)
    logger.error("❌ Timeout waiting for VNC services")
    return False

def find_credentials_for_email(target_email):
    """Find credentials for email"""
    try:
        possible_paths = [
            '/app/credentials.json',
            '/app/shared_volume/credentials.json',
            '/app/captcha_watcher/credentials.json',
            './credentials.json',
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"📁 Found credentials.json at: {path}")
                with open(path, 'r', encoding='utf-8') as file:
                    all_creds = json.load(file)
                for cred in all_creds:
                    if cred.get('email') == target_email:
                        logger.info(f"✅ Found specific credentials for: {target_email}")
                        return cred
                logger.warning(f"⚠️ Specific email {target_email} not found in credentials")
                break
        
        # Fallback to Credential class
        credential = Credential()
        creds = credential.get_credentials()
        if creds:
            logger.info(f"🔄 Using fallback credentials: {creds.get('email', 'unknown')}")
            return creds
        return None
    except Exception as e:
        logger.error(f"❌ Error finding credentials: {e}")
        return None

def wait_for_session_transfer(email, timeout=120):
    """🔥 FIXED: Wait for session transfer data from main application"""
    session_file = f"/app/shared_volume/captcha_session_{email}.json"
    
    logger.info("="*70)
    logger.info("🔍 SEARCHING FOR SESSION TRANSFER DATA")
    logger.info("="*70)
    logger.info(f"📂 Looking for: {session_file}")
    logger.info(f"📧 Email: {email}")
    logger.info(f"⏰ Timeout: {timeout} seconds")
    
    # 🔧 FIXED: Check what files actually exist in shared volume
    try:
        shared_volume_files = os.listdir("/app/shared_volume/")
        logger.info(f"📁 Files in shared volume: {shared_volume_files}")
        
        # Look for any session files
        session_files = [f for f in shared_volume_files if f.startswith("captcha_session_")]
        if session_files:
            logger.info(f"🎯 Found session files: {session_files}")
        else:
            logger.warning("⚠️ NO session files found in shared volume!")
            
    except Exception as e:
        logger.error(f"❌ Error listing shared volume: {e}")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        if os.path.exists(session_file):
            try:
                # Read and validate session file
                with open(session_file, 'r') as f:
                    session_data = json.load(f)
                
                # Validate session data
                required_fields = ['email', 'current_url', 'cookies']
                missing_fields = [field for field in required_fields if field not in session_data]
                
                if missing_fields:
                    logger.error(f"❌ Session file missing fields: {missing_fields}")
                    return None
                
                logger.info("="*70)
                logger.info("✅ SESSION TRANSFER DATA RECEIVED!")
                logger.info("="*70)
                logger.info(f"📧 Email: {session_data.get('email', 'Unknown')}")
                logger.info(f"🌐 URL: {session_data.get('current_url', 'Unknown')}")
                logger.info(f"🍪 Cookies: {len(session_data.get('cookies', []))} cookies")
                logger.info(f"📄 Page source: {len(session_data.get('page_source', ''))} chars")
                logger.info(f"⏰ Timestamp: {session_data.get('timestamp', 'Unknown')}")
                logger.info("="*70)
                
                return session_data
                
            except Exception as e:
                logger.error(f"❌ Error reading session file: {e}")
                return None
        
        # Log progress every 10 seconds
        elapsed = time.time() - start_time
        if int(elapsed) % 10 == 0 and int(elapsed) > 0:
            remaining = timeout - elapsed
            logger.info(f"⏳ Still waiting for session data... {remaining:.0f}s remaining")
        
        time.sleep(2)
    
    logger.error("="*70)
    logger.error("❌ TIMEOUT: NO SESSION TRANSFER DATA FOUND")
    logger.error("="*70)
    logger.error(f"📂 Expected file: {session_file}")
    logger.error("This means the main application didn't save session data!")
    logger.error("="*70)
    
    return None

def resolve_with_gui_automatic(email):
    """🔥 FIXED: FULLY AUTOMATIC GUI browser with proper session transfer"""
    logger.info("="*70)
    logger.info("🤖 STARTING AUTOMATIC CAPTCHA RESOLUTION")
    logger.info("="*70)
    logger.info(f"📧 Email: {email}")
    logger.info(f"🔄 Step 1: Wait for session transfer from main app")
    
    # 🔥 FIXED: Wait for session transfer with better error handling
    session_data = wait_for_session_transfer(email, timeout=120)  # 2 minutes
    
    if not session_data:
        logger.error("❌ No session transfer data - falling back to manual mode")
        return resolve_with_gui_manual_fallback(email)
    
    logger.info("🔄 Step 2: Create Chrome browser in VNC")
    
    try:
        # Create visible browser for VNC
        os.environ['DISPLAY'] = ':0'
        options = Options()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--window-size=1400,900')
        options.add_argument('--window-position=0,0')
        options.add_argument('--display=:0')
        options.add_argument('--disable-gpu')
        options.add_argument('--start-maximized')
        options.add_argument('--remote-debugging-port=9223')
        
        # Use unique user data directory
        user_data_dir = f"/tmp/chrome-vnc-session-{int(time.time())}"
        os.makedirs(user_data_dir, exist_ok=True)
        options.add_argument(f'--user-data-dir={user_data_dir}')
        
        logger.info("🚀 Starting Chrome browser for VNC...")
        driver = uc.Chrome(options=options, version_main=136)
        
        logger.info("🔄 Step 3: Transfer session to VNC browser")
        
        # First navigate to LinkedIn base domain to set cookies
        logger.info("🌐 Navigating to LinkedIn base domain...")
        driver.get("https://www.linkedin.com")
        time.sleep(3)
        
        # Load cookies from main session
        if 'cookies' in session_data and len(session_data['cookies']) > 0:
            logger.info(f"🍪 Loading {len(session_data['cookies'])} session cookies...")
            
            cookies_loaded = 0
            for cookie in session_data['cookies']:
                try:
                    # Ensure cookie has required fields
                    if 'name' not in cookie or 'value' not in cookie:
                        continue
                        
                    # Add domain if missing
                    if 'domain' not in cookie:
                        cookie['domain'] = '.linkedin.com'
                    
                    # Remove problematic fields
                    cookie_clean = {
                        'name': cookie['name'],
                        'value': cookie['value'],
                        'domain': cookie['domain']
                    }
                    
                    # Add optional fields if present
                    if 'path' in cookie:
                        cookie_clean['path'] = cookie['path']
                    if 'secure' in cookie:
                        cookie_clean['secure'] = cookie['secure']
                    
                    driver.add_cookie(cookie_clean)
                    cookies_loaded += 1
                    
                except Exception as cookie_error:
                    logger.debug(f"Cookie error (non-critical): {cookie_error}")
                    continue
            
            logger.info(f"✅ Successfully loaded {cookies_loaded} cookies")
        else:
            logger.warning("⚠️ No cookies found in session data!")
        
        # Navigate to the exact CAPTCHA page
        captcha_url = session_data.get('current_url', 'https://www.linkedin.com/checkpoint/lg/login-submit')
        logger.info(f"🎯 Step 4: Navigate to CAPTCHA page: {captcha_url}")
        
        driver.get(captcha_url)
        time.sleep(5)
        
        # Verify we're on the right page
        current_url = driver.current_url
        current_source = driver.page_source.lower()
        
        logger.info("="*70)
        logger.info("🔍 VERIFYING SESSION TRANSFER")
        logger.info("="*70)
        logger.info(f"🌐 Current URL: {current_url}")
        logger.info(f"🎯 Expected URL: {captcha_url}")
        
        if 'captcha' in current_source or 'challenge' in current_source or 'checkpoint' in current_url:
            logger.info("✅ SUCCESS! CAPTCHA page loaded correctly!")
            logger.info("🎯 Session transfer completed successfully!")
        else:
            logger.warning("⚠️ CAPTCHA not immediately visible")
            logger.warning("This might be normal - user should check the VNC interface")
        
        logger.info("="*70)
        logger.info("🎯 CAPTCHA READY FOR SOLVING")
        logger.info("="*70)
        logger.info(f"📧 Email: {email}")
        logger.info(f"🌐 Current URL: {driver.current_url}")
        logger.info("")
        logger.info("👤 USER INSTRUCTIONS:")
        logger.info("   1. ✅ CAPTCHA session has been transferred automatically")
        logger.info("   2. ✅ You should see the LinkedIn CAPTCHA/checkpoint page")
        logger.info("   3. 🎯 Solve the CAPTCHA challenge in this browser")
        logger.info("   4. ✅ System will auto-detect completion and save cookies")
        logger.info("="*70)
        
        # Monitor for successful login
        max_wait = 600  # 10 minutes
        check_interval = 15  # Check every 15 seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                current_url = driver.current_url
                
                # Check if successfully logged in
                success_indicators = ['feed', 'sales', 'mynetwork', 'in/', '/home']
                if any(indicator in current_url.lower() for indicator in success_indicators):
                    logger.info("🎉 SUCCESS! CAPTCHA solved and login completed!")
                    logger.info(f"✅ Final URL: {current_url}")
                    break
                
                # Check if still on captcha/checkpoint page
                if any(indicator in current_url.lower() for indicator in ['login', 'checkpoint', 'challenge']):
                    elapsed = time.time() - start_time
                    remaining = (max_wait - elapsed) / 60
                    logger.info(f"⏳ CAPTCHA solving in progress... {remaining:.1f} min remaining")
                else:
                    logger.info(f"🔄 Navigation detected: {current_url}")
                
                time.sleep(check_interval)
                
            except Exception as check_error:
                logger.warning(f"Monitor error: {check_error}")
                time.sleep(check_interval)
                continue
        
        # Save cookies and cleanup
        try:
            final_url = driver.current_url
            success_indicators = ['feed', 'sales', 'mynetwork', 'in/', '/home']
            
            if any(indicator in final_url.lower() for indicator in success_indicators):
                logger.info("💾 Saving cookies after successful CAPTCHA resolution...")
                
                # Ensure cookies folder exists
                os.makedirs("/app/cookies/", exist_ok=True)
                
                # Save cookies for the email
                cookie_path = f"/app/cookies/linkedin_cookies_{email}.pkl"
                save_cookies(driver, cookie_path)
                logger.info(f"✅ Cookies saved: {cookie_path}")
                
                # Cleanup session transfer file
                session_file = f"/app/shared_volume/captcha_session_{email}.json"
                if os.path.exists(session_file):
                    os.remove(session_file)
                    logger.info("🧹 Session transfer file cleaned up")
                    
            else:
                logger.warning("⚠️ CAPTCHA resolution incomplete or timeout")
                logger.warning(f"Final URL: {final_url}")
                
        except Exception as save_error:
            logger.error(f"Error saving cookies: {save_error}")
        
        logger.info("Closing browser in 30 seconds...")
        time.sleep(30)
        driver.quit()
        
        # Cleanup
        try:
            import shutil
            shutil.rmtree(user_data_dir, ignore_errors=True)
        except:
            pass
        
        # Mark as resolved
        with open(PROCESSED_FILE, "a") as f:
            f.write(f"{email}\n")
        
        logger.info(f"✅ {email} marked as resolved!")
        
    except Exception as e:
        logger.error(f"❌ Error with automatic GUI browser: {e}", exc_info=True)
        
        # Mark as processed to prevent infinite retry
        with open(PROCESSED_FILE, "a") as f:
            f.write(f"{email}\n")

def resolve_with_gui_manual_fallback(email):
    """Fallback to manual mode if session transfer fails"""
    logger.info("="*70)
    logger.info("🔄 FALLBACK TO MANUAL MODE")
    logger.info("="*70)
    logger.info(f"📧 Email: {email}")
    logger.info("Reason: Session transfer failed or timed out")
    
    creds = find_credentials_for_email(email)
    if not creds:
        logger.error(f"No credentials available for {email}")
        with open(PROCESSED_FILE, "a") as f:
            f.write(f"{email}\n")
        return

    EMAIL = creds.get("email", "unknown")
    PASSWORD = creds.get("password", "unknown")
    
    try:
        # Create visible browser
        os.environ['DISPLAY'] = ':0'
        options = Options()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1400,900')
        options.add_argument('--start-maximized')
        
        user_data_dir = f"/tmp/chrome-vnc-manual-{int(time.time())}"
        os.makedirs(user_data_dir, exist_ok=True)
        options.add_argument(f'--user-data-dir={user_data_dir}')
        
        driver = uc.Chrome(options=options, version_main=136)
        
        # Navigate to LinkedIn and pre-fill
        driver.get("https://www.linkedin.com/login")
        time.sleep(3)
        
        # Pre-fill credentials
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            wait = WebDriverWait(driver, 10)
            email_field = wait.until(EC.presence_of_element_located((By.ID, "username")))
            email_field.clear()
            email_field.send_keys(EMAIL)
            
            password_field = driver.find_element(By.ID, "password")
            password_field.clear()
            password_field.send_keys(PASSWORD)
            
            logger.info("✅ Login form pre-filled - user needs to click Sign In")
            
        except Exception as form_error:
            logger.warning(f"Could not pre-fill form: {form_error}")
        
        logger.info("="*70)
        logger.info("🔧 MANUAL FALLBACK MODE ACTIVE")
        logger.info("="*70)
        logger.info("👤 USER INSTRUCTIONS:")
        logger.info("   1. Click 'Sign in' button to trigger CAPTCHA")
        logger.info("   2. Solve the CAPTCHA challenge")
        logger.info("   3. Complete login manually")
        logger.info("="*70)
        
        # Manual monitoring
        max_wait = 600
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                current_url = driver.current_url
                if any(indicator in current_url.lower() for indicator in ['feed', 'sales', 'mynetwork']):
                    logger.info("✅ Manual login completed!")
                    
                    # Save cookies
                    os.makedirs("/app/cookies/", exist_ok=True)
                    cookie_path = f"/app/cookies/linkedin_cookies_{email}.pkl"
                    save_cookies(driver, cookie_path)
                    logger.info(f"✅ Cookies saved: {cookie_path}")
                    break
                    
                time.sleep(15)
                
            except Exception as e:
                logger.warning(f"Manual monitor error: {e}")
                time.sleep(15)
        
        time.sleep(30)
        driver.quit()
        
        # Cleanup
        try:
            import shutil
            shutil.rmtree(user_data_dir, ignore_errors=True)
        except:
            pass
            
        with open(PROCESSED_FILE, "a") as f:
            f.write(f"{email}\n")
            
    except Exception as e:
        logger.error(f"❌ Manual fallback error: {e}")
        with open(PROCESSED_FILE, "a") as f:
            f.write(f"{email}\n")

def watch_loop():
    """Main watch loop"""
    time.sleep(8)
    logger.info("="*70)
    logger.info("🤖 AUTOMATIC CAPTCHA WATCHER STARTED")
    logger.info("="*70)
    logger.info("Features:")
    logger.info("✅ Automatic session transfer from main app")
    logger.info("✅ Zero manual navigation required")
    logger.info("✅ Improved error handling and debugging")
    logger.info("✅ Fallback to manual mode if needed")
    logger.info("="*70)

    ensure_vnc_ready()

    processed = set()
    while True:
        try:
            if os.path.exists(WATCH_FILE):
                with open(WATCH_FILE, "r") as f:
                    lines = [line.strip() for line in f.readlines()]
                for email in lines:
                    if email and email not in processed:
                        logger.info("*" * 70) 
                        logger.info(f"🤖 NEW AUTOMATIC CAPTCHA REQUEST: {email}")
                        logger.info("*" * 70) 
                        try:
                            resolve_with_gui_automatic(email)
                        finally:
                            processed.add(email)
                        logger.info("🤖 AUTOMATIC CAPTCHA PROCESSING COMPLETED")
                        logger.info("*" * 70)
                        
                # Update the queue file
                remaining = [e for e in lines if e not in processed]
                with open(WATCH_FILE, "w") as f:
                    for email in remaining:
                        f.write(f"{email}\n")
                        
            time.sleep(10)
            
        except KeyboardInterrupt:
            logger.info("="*70)
            logger.info("🤖 Automatic Captcha watcher stopped by user")
            logger.info("="*70)
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
            time.sleep(5)

if __name__ == "__main__":
    logger.info("🚀 Starting FIXED CAPTCHA Watcher with Session Transfer")
    logger.info(f"🔧 Container ID: {os.environ.get('HOSTNAME', 'unknown')}")
    watch_loop()