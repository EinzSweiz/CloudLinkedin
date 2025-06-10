# ENHANCED captcha_watcher_with_gui.py - Complete version with status reporting and debugging
import os
import sys
import time
import json
import socket
import logging

# Fix the import path for Docker
sys.path.append('/app')

# FIXED: Ensure logs directory exists and use shared volume
os.makedirs('/app/logs', exist_ok=True)

# Configure logging with ACCESSIBLE log file path
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # Docker logs
        logging.FileHandler('/app/logs/captcha_watcher.log')  # ← FIXED: Accessible path
    ]
)
logger = logging.getLogger(__name__)

# Also create a debug log for detailed analysis
debug_handler = logging.FileHandler('/app/logs/captcha_watcher_debug.log')
debug_handler.setLevel(logging.DEBUG)
debug_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s')
debug_handler.setFormatter(debug_formatter)
logger.addHandler(debug_handler)

logger.info("🚀 CAPTCHA Watcher logging initialized")
logger.info(f"   Stdout logs: Available via 'docker logs captcha_watcher'")
logger.info(f"   File logs: /app/logs/captcha_watcher.log (accessible from host)")
logger.info(f"   Debug logs: /app/logs/captcha_watcher_debug.log")

# Test log accessibility
try:
    test_file = '/app/logs/captcha_watcher_test.log'
    with open(test_file, 'w') as f:
        f.write(f"Log test at {time.time()}\n")
    logger.info(f"✅ Log directory accessible: {test_file}")
except Exception as e:
    logger.error(f"❌ Log directory NOT accessible: {e}")
    logger.error("This means logs will only be visible via 'docker logs'")

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

def update_container_status(status: str, message: str = None):
    """Update container status via shared volume"""
    try:
        container_id = os.environ.get('HOSTNAME', 'unknown')
        email = os.environ.get('EMAIL', 'unknown')
        
        status_data = {
            'container_id': container_id,
            'email': email,
            'status': status,
            'message': message,
            'timestamp': time.time(),
            'updated_by': 'captcha_watcher'
        }
        
        status_file = f"/app/shared_volume/container_status_{container_id}.json"
        
        with open(status_file, 'w') as f:
            json.dump(status_data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        
        logger.info(f"✅ Container status updated: {status}")
        if message:
            logger.info(f"   Message: {message}")
            
    except Exception as e:
        logger.error(f"❌ Failed to update container status: {e}")



def ensure_vnc_ready(timeout=30):
    """Wait for VNC services to be ready"""
    logger.info("Waiting for VNC services to be ready...")
    
    for i in range(timeout):
        try:
            with socket.create_connection(("localhost", 5900), timeout=1):
                logger.info("VNC (5900) is accessible")
            with socket.create_connection(("localhost", 6080), timeout=1):
                logger.info("noVNC (6080) is accessible")
                logger.info("VNC services ready!")
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
                logger.info(f"Found credentials.json at: {path}")
                with open(path, 'r', encoding='utf-8') as file:
                    all_creds = json.load(file)
                for cred in all_creds:
                    if cred.get('email') == target_email:
                        logger.info(f"Found specific credentials for: {target_email}")
                        return cred
                logger.warning(f"Specific email {target_email} not found in credentials")
                break
        
        # Fallback to Credential class
        credential = Credential()
        creds = credential.get_credentials()
        if creds:
            logger.info(f"Using fallback credentials: {creds.get('email', 'unknown')}")
            return creds
        return None
    except Exception as e:
        logger.error(f"Error finding credentials: {e}")
        return None

def debug_session_transfer(email):
    """FIXED: Comprehensive session transfer debugging that actually returns data"""
    logger.info("="*80)
    logger.info("🔍 SESSION TRANSFER DEBUG MODE")
    logger.info("="*80)
    
    session_file = f"/app/shared_volume/captcha_session_{email}.json"
    
    # Check if specific session file exists
    logger.info(f"\n🎯 Target Session File Check:")
    logger.info(f"   Expected: {session_file}")
    logger.info(f"   Exists: {os.path.exists(session_file)}")
    
    if os.path.exists(session_file):
        try:
            size = os.path.getsize(session_file)
            mtime = os.path.getmtime(session_file)
            age = time.time() - mtime
            
            logger.info(f"   📏 Size: {size} bytes")
            logger.info(f"   🕐 Modified: {time.ctime(mtime)}")
            logger.info(f"   ⏱️ Age: {age:.1f} seconds")
            
            if size == 0:
                logger.error(f"   ❌ FILE IS EMPTY!")
                return None
            elif age > 300:
                logger.warning(f"   ⚠️ FILE IS OLD (over 5 minutes)")
            
            # Try to read and parse it
            with open(session_file, 'r') as f:
                session_data = json.load(f)
            
            logger.info(f"   📄 Content parsed successfully")
            logger.info(f"   📧 Contains email: {session_data.get('email', 'MISSING')}")
            logger.info(f"   🌐 Contains URL: {session_data.get('current_url', 'MISSING')}")
            logger.info(f"   🍪 Contains cookies: {len(session_data.get('cookies', []))}")
            
            required_fields = ['email', 'current_url', 'cookies']
            missing = [f for f in required_fields if f not in session_data]
            if missing:
                logger.error(f"      ❌ MISSING FIELDS: {missing}")
                return None
            else:
                logger.info(f"      ✅ All required fields present")
                
                # Validate cookies
                cookies = session_data.get('cookies', [])
                if isinstance(cookies, list) and len(cookies) > 0:
                    logger.info(f"      ✅ Valid cookies: {len(cookies)} entries")
                    logger.info("="*80)
                    return session_data
                else:
                    logger.error(f"      ❌ Invalid cookies: {type(cookies)}")
                    return None
                
        except json.JSONDecodeError as je:
            logger.error(f"      ❌ JSON DECODE ERROR: {je}")
            return None
        except Exception as re:
            logger.error(f"      ❌ READ ERROR: {re}")
            return None
    
    # If file doesn't exist, check what IS in the shared volume
    shared_volume = "/app/shared_volume"
    logger.info(f"📂 Checking shared volume: {shared_volume}")
    
    if os.path.exists(shared_volume):
        try:
            files = os.listdir(shared_volume)
            logger.info(f"📁 Files in shared volume ({len(files)}):")
            
            session_files = [f for f in files if f.startswith("captcha_session_")]
            if session_files:
                logger.info(f"Found other session files: {session_files}")
                
                # Try to use the first session file we find (in case of email mismatch)
                for session_file_name in session_files:
                    try:
                        file_path = os.path.join(shared_volume, session_file_name)
                        with open(file_path, 'r') as f:
                            session_data = json.load(f)
                        
                        # Check if this session is for our email or close enough
                        session_email = session_data.get('email', '')
                        if session_email == email or email in session_file_name:
                            logger.info(f"✅ Found matching session file: {session_file_name}")
                            logger.info("="*80)
                            return session_data
                            
                    except Exception as e:
                        logger.warning(f"Failed to read {session_file_name}: {e}")
                        continue
            else:
                logger.warning("⚠️ NO session files found in shared volume!")
                
        except Exception as e:
            logger.error(f"❌ Cannot list directory: {e}")
    
    logger.error(f"❌ No valid session data found for {email}")
    logger.info("="*80)
    return None
def wait_for_session_transfer(email, timeout=180):
    """FIXED: Enhanced session transfer waiting with debugging"""
    
    # First, run comprehensive debugging
    logger.info("🔍 Running session transfer diagnostics...")
    debug_result = debug_session_transfer(email)
    
    if debug_result:
        logger.info("✅ Session found during debug - using it immediately")
        # VALIDATE the session data before returning
        required_fields = ['email', 'current_url', 'cookies']
        missing_fields = [field for field in required_fields if field not in debug_result]
        
        if missing_fields:
            logger.error(f"Session data missing required fields: {missing_fields}")
            logger.error(f"Available fields: {list(debug_result.keys())}")
        else:
            # Validate cookies specifically
            cookies = debug_result.get('cookies', [])
            if isinstance(cookies, list) and len(cookies) > 0:
                logger.info(f"✅ Valid session data found with {len(cookies)} cookies")
                return debug_result
            else:
                logger.error(f"Invalid or empty cookies: {type(cookies)} with {len(cookies) if isinstance(cookies, list) else 'unknown'} items")
    
    # Only continue with waiting if debug didn't find valid session
    logger.info("Session not found in debug, starting enhanced waiting...")
    
    session_file = f"/app/shared_volume/captcha_session_{email}.json"
    
    logger.info("="*70)
    logger.info("🔍 ENHANCED SESSION TRANSFER SEARCH")
    logger.info("="*70)
    logger.info(f"Looking for: {session_file}")
    logger.info(f"Email: {email}")
    logger.info(f"Timeout: {timeout} seconds")
    
    start_time = time.time()
    check_count = 0
    
    while time.time() - start_time < timeout:
        check_count += 1
        
        # Check if session file exists and validate it
        if os.path.exists(session_file):
            try:
                # Check file size first
                file_size = os.path.getsize(session_file)
                if file_size == 0:
                    logger.warning(f"Session file exists but is empty ({file_size} bytes)")
                    time.sleep(2)
                    continue
                
                logger.info(f"Session file found! Size: {file_size} bytes")
                
                # Read and validate session file
                with open(session_file, 'r') as f:
                    session_data = json.load(f)
                
                # Enhanced validation
                required_fields = ['email', 'current_url', 'cookies']
                missing_fields = [field for field in required_fields if field not in session_data]
                
                if missing_fields:
                    logger.error(f"Session file missing fields: {missing_fields}")
                    logger.error(f"Available fields: {list(session_data.keys())}")
                    return None
                
                # Validate cookies specifically
                cookies = session_data.get('cookies', [])
                if not isinstance(cookies, list) or len(cookies) == 0:
                    logger.error(f"Invalid or empty cookies: {type(cookies)} with {len(cookies) if isinstance(cookies, list) else 'unknown'} items")
                    return None
                
                logger.info("="*70)
                logger.info("✅ SESSION TRANSFER DATA RECEIVED!")
                logger.info("="*70)
                logger.info(f"Email: {session_data.get('email', 'Unknown')}")
                logger.info(f"URL: {session_data.get('current_url', 'Unknown')}")
                logger.info(f"Cookies: {len(cookies)} cookies")
                logger.info(f"Page source: {len(session_data.get('page_source', ''))} chars")
                logger.info(f"Timestamp: {session_data.get('timestamp', 'Unknown')}")
                logger.info(f"User Agent: {session_data.get('user_agent', 'Unknown')[:50]}...")
                logger.info("="*70)
                
                return session_data
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                logger.error("File content might be corrupted or incomplete")
                time.sleep(5)
                continue
            except Exception as e:
                logger.error(f"Error reading session file: {e}")
                time.sleep(5)
                continue
        
        # Status updates every 10 seconds
        elapsed = time.time() - start_time
        if check_count % 5 == 0:  # Every 10 seconds (5 checks * 2 second intervals)
            remaining = timeout - elapsed
            logger.info(f"Still waiting for session data... Check #{check_count}, {remaining:.0f}s remaining")
        
        time.sleep(2)
    
    logger.error("="*70)
    logger.error("❌ TIMEOUT: NO SESSION TRANSFER DATA FOUND")
    logger.error("="*70)
    logger.error(f"Expected file: {session_file}")
    logger.error("This means the main application didn't save session data properly!")
    logger.error("="*70)
    
    return None

def restore_browser_session_enhanced(driver, session_data):
    """🔥 ENHANCED: Restore complete browser session with fingerprint matching"""
    
    logger.info("🔄 Enhanced session restoration starting...")
    
    try:
        # Step 1: Set browser fingerprint to match original
        if 'browser_fingerprint' in session_data:
            fingerprint = session_data['browser_fingerprint']
            
            # Set viewport to match exactly
            if 'viewport' in fingerprint:
                viewport = fingerprint['viewport']
                driver.set_window_size(viewport['width'], viewport['height'])
                logger.info(f"✅ Viewport restored: {viewport['width']}x{viewport['height']}")
            
            # 🔧 FIXED: Proper JavaScript injection with safe data handling
            platform = fingerprint.get("platform", "MacIntel")
            language = fingerprint.get("language", "en-US") 
            languages = str(fingerprint.get("languages", ["en-US", "en"])).replace("'", '"')  # Convert to JSON string
            timezone = fingerprint.get("timezone", "America/New_York")
            
            # Extract screen data safely
            screen_info = fingerprint.get("screen", {})
            screen_width = screen_info.get("width", 1920)
            screen_height = screen_info.get("height", 1080)
            screen_pixel_depth = screen_info.get("pixelDepth", 24)
            
            # Inject fingerprint spoofing with proper data
            fingerprint_script = f"""
                // Override navigator properties to match original session
                Object.defineProperty(navigator, 'platform', {{ get: () => '{platform}' }});
                Object.defineProperty(navigator, 'language', {{ get: () => '{language}' }});
                Object.defineProperty(navigator, 'languages', {{ get: () => {languages} }});
                
                // Override screen properties
                Object.defineProperty(screen, 'width', {{ get: () => {screen_width} }});
                Object.defineProperty(screen, 'height', {{ get: () => {screen_height} }});
                Object.defineProperty(screen, 'pixelDepth', {{ get: () => {screen_pixel_depth} }});
                
                // Override timezone
                if (Intl && Intl.DateTimeFormat) {{
                    const originalResolvedOptions = Intl.DateTimeFormat.prototype.resolvedOptions;
                    Intl.DateTimeFormat.prototype.resolvedOptions = function() {{
                        const options = originalResolvedOptions.call(this);
                        options.timeZone = '{timezone}';
                        return options;
                    }};
                }}
                
                // Hide webdriver property
                Object.defineProperty(navigator, 'webdriver', {{ get: () => undefined }});
                
                console.log('Browser fingerprint spoofing applied:', {{
                    platform: '{platform}',
                    language: '{language}',
                    screen: '{screen_width}x{screen_height}',
                    timezone: '{timezone}'
                }});
            """
            
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": fingerprint_script
            })
            logger.info("✅ Browser fingerprint spoofing applied")
            logger.info(f"   Platform: {platform}")
            logger.info(f"   Language: {language}")  
            logger.info(f"   Screen: {screen_width}x{screen_height}")
            logger.info(f"   Timezone: {timezone}")
        else:
            logger.warning("⚠️ No browser fingerprint data found in session - using defaults")
        
        # Step 2: Navigate to LinkedIn base with proper headers
        logger.info("🌐 Navigating to LinkedIn with enhanced headers...")
        
        if 'request_headers' in session_data:
            # Set request headers via CDP
            headers = session_data['request_headers']
            user_agent = session_data.get('user_agent', headers.get('user-agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15'))
            accept_language = headers.get('accept-language', 'en-US,en;q=0.9')
            platform = session_data.get('browser_fingerprint', {}).get('platform', 'MacIntel')
            
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": user_agent,
                "acceptLanguage": accept_language,
                "platform": platform
            })
            logger.info(f"✅ Enhanced headers set - UA: {user_agent[:50]}...")
        
        # Navigate to LinkedIn main page first
        driver.get("https://www.linkedin.com")
        time.sleep(3)
        
        # Step 3: Restore cookies with enhanced validation
        if 'cookies' in session_data:
            cookies = session_data['cookies']
            logger.info(f"🍪 Restoring {len(cookies)} cookies with validation...")
            
            successful_cookies = 0
            critical_cookies = ['li_rm', 'JSESSIONID', 'bcookie', 'chp_token']
            critical_found = []
            
            for cookie in cookies:
                try:
                    # Validate cookie structure
                    if not cookie.get('name') or not cookie.get('value'):
                        continue
                    
                    # Ensure domain compatibility
                    if 'domain' not in cookie:
                        cookie['domain'] = '.linkedin.com'
                    
                    # Create clean cookie
                    clean_cookie = {
                        'name': cookie['name'],
                        'value': cookie['value'],
                        'domain': cookie['domain']
                    }
                    
                    # Add optional fields safely
                    for field in ['path', 'secure', 'httpOnly', 'sameSite']:
                        if field in cookie and cookie[field] is not None:
                            clean_cookie[field] = cookie[field]
                    
                    driver.add_cookie(clean_cookie)
                    successful_cookies += 1
                    
                    # Track critical cookies
                    if cookie['name'] in critical_cookies:
                        critical_found.append(cookie['name'])
                    
                except Exception as e:
                    logger.debug(f"Cookie restore failed: {cookie.get('name', 'unknown')} - {e}")
                    continue
            
            logger.info(f"✅ Cookies restored: {successful_cookies}/{len(cookies)}")
            logger.info(f"✅ Critical cookies found: {critical_found}")
            
            if not critical_found:
                logger.warning("⚠️ No critical LinkedIn cookies found - session may be invalid")
                return False
        
        # Step 4: Restore storage (with better error handling)
        if session_data.get('local_storage') and session_data['local_storage'] != "{}":
            try:
                # Escape the localStorage string properly
                local_storage_str = session_data['local_storage'].replace('`', '\\`').replace('\\', '\\\\')
                driver.execute_script(f"Object.assign(localStorage, JSON.parse(`{local_storage_str}`));")
                logger.info("✅ localStorage restored")
            except Exception as e:
                logger.debug(f"localStorage restore failed: {e}")
        
        if session_data.get('session_storage') and session_data['session_storage'] != "{}":
            try:
                # Escape the sessionStorage string properly  
                session_storage_str = session_data['session_storage'].replace('`', '\\`').replace('\\', '\\\\')
                driver.execute_script(f"Object.assign(sessionStorage, JSON.parse(`{session_storage_str}`));")
                logger.info("✅ sessionStorage restored")
            except Exception as e:
                logger.debug(f"sessionStorage restore failed: {e}")
        
        # Step 5: Navigate to CAPTCHA with proper referrer chain
        original_url = session_data.get('current_url')
        if original_url:
            logger.info(f"🎯 Navigating to original CAPTCHA URL: {original_url}")
            
            # 🔧 IMPROVED: Better navigation strategy
            try:
                # First try to navigate via LinkedIn feed to establish proper referrer
                logger.info("Setting up referrer chain via LinkedIn feed...")
                driver.get("https://www.linkedin.com/feed/")
                time.sleep(3)
                
                # Check if we're already logged in at this point
                current_after_feed = driver.current_url
                if any(indicator in current_after_feed.lower() for indicator in ['/feed/', '/home/', '/mynetwork/']):
                    logger.info("🎉 Already logged in after cookie restoration!")
                    return "already_logged_in"
                
                # Now navigate to the CAPTCHA URL
                logger.info(f"Navigating to CAPTCHA URL: {original_url}")
                driver.get(original_url)
                time.sleep(5)
                
            except Exception as nav_error:
                logger.warning(f"Navigation error: {nav_error}")
                # Fallback: try direct navigation
                logger.info("Trying direct navigation to CAPTCHA URL...")
                driver.get(original_url)
                time.sleep(5)
            
            # Enhanced page validation
            current_url = driver.current_url
            current_source = driver.page_source.lower()
            page_title = driver.title.lower()
            
            logger.info("="*50)
            logger.info("🔍 PAGE VALIDATION AFTER RESTORATION")
            logger.info("="*50)
            logger.info(f"Expected URL: {original_url}")
            logger.info(f"Current URL:  {current_url}")
            logger.info(f"Page Title:   {page_title}")
            
            # Enhanced validation with multiple indicators
            captcha_indicators = ['captcha', 'challenge', 'checkpoint', 'verify', 'security']
            login_indicators = ['login', 'signin', 'authenticate', '/uas/']
            success_indicators = ['feed', 'home', 'mynetwork', 'sales', '/in/']
            
            # Check URL patterns
            is_captcha_url = any(indicator in current_url.lower() for indicator in captcha_indicators)
            is_login_url = any(indicator in current_url.lower() for indicator in login_indicators)
            is_success_url = any(indicator in current_url.lower() for indicator in success_indicators)
            
            # Check page content
            is_captcha_content = any(indicator in current_source for indicator in captcha_indicators)
            is_login_content = any(indicator in current_source for indicator in ['sign in', 'email', 'password'])
            
            # Check page title
            is_captcha_title = any(indicator in page_title for indicator in captcha_indicators)
            
            logger.info(f"URL Analysis:")
            logger.info(f"   CAPTCHA URL: {is_captcha_url}")
            logger.info(f"   Login URL: {is_login_url}")
            logger.info(f"   Success URL: {is_success_url}")
            logger.info(f"Content Analysis:")
            logger.info(f"   CAPTCHA Content: {is_captcha_content}")
            logger.info(f"   Login Content: {is_login_content}")
            logger.info(f"Title Analysis:")
            logger.info(f"   CAPTCHA Title: {is_captcha_title}")
            logger.info("="*50)
            
            # Decision logic
            if is_success_url:
                logger.info("🎉 Already logged in! No CAPTCHA needed.")
                return "already_logged_in"
            elif is_captcha_url or is_captcha_content or is_captcha_title:
                logger.info("✅ Successfully restored to CAPTCHA page!")
                return True
            elif is_login_url or is_login_content:
                logger.warning("⚠️ Redirected to login - session restoration failed")
                logger.warning("This indicates the session cookies were invalid or expired")
                return False
            else:
                logger.warning("⚠️ Unexpected page after restoration")
                logger.warning("Continuing anyway - may still work")
                return "unknown_page"
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Enhanced session restoration failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    
def notify_main_app_success(email, final_url):
    """Notify main application that CAPTCHA was solved successfully"""
    try:
        # Create success notification file
        success_data = {
            'email': email,
            'status': 'solved',
            'final_url': final_url,
            'timestamp': time.time(),
            'cookies_path': f"/app/cookies/linkedin_cookies_{email}.pkl",
            'message': 'CAPTCHA solved successfully in VNC'
        }
        
        success_file = f"/app/shared_volume/captcha_success_{email}.json"
        with open(success_file, 'w') as f:
            json.dump(success_data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        
        logger.info(f"✅ Success notification saved: {success_file}")
        
        # Also create a simple flag file for quick detection
        flag_file = f"/app/shared_volume/captcha_solved_{email.replace('@', '_')}.flag"
        with open(flag_file, 'w') as f:
            f.write(f"solved_at_{int(time.time())}")
        
        logger.info(f"✅ Success flag created: {flag_file}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to notify main app: {e}")
        return False
    
def copy_cookies_to_shared_volume(email, source_path):
    """Copy cookies to shared volume for main app access"""
    try:
        if not os.path.exists(source_path):
            logger.warning(f"Source cookies not found: {source_path}")
            return False
        
        # Copy to shared volume
        shared_cookies_path = f"/app/shared_volume/solved_cookies_{email}.pkl"
        import shutil
        shutil.copy2(source_path, shared_cookies_path)
        
        # Also save as JSON for debugging
        import pickle
        with open(source_path, 'rb') as f:
            cookies = pickle.load(f)
        
        json_path = f"/app/shared_volume/solved_cookies_{email}.json"
        with open(json_path, 'w') as f:
            json.dump(cookies, f, indent=2, default=str)
        
        logger.info(f"✅ Cookies copied to shared volume:")
        logger.info(f"   PKL: {shared_cookies_path}")
        logger.info(f"   JSON: {json_path}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Cookie copy failed: {e}")
        return False
# Updated resolve_with_gui_automatic to use enhanced restoration
def resolve_with_gui_automatic(email):
    """🔥 ENHANCED: FULLY AUTOMATIC GUI browser with fixed session transfer"""
    logger.info("="*70)
    logger.info("🚀 STARTING ENHANCED AUTOMATIC CAPTCHA RESOLUTION V2")
    logger.info("="*70)
    
    # Update status
    update_container_status("starting", "Initializing enhanced CAPTCHA resolution")
    
    # Wait for enhanced session transfer
    session_data = wait_for_session_transfer(email, timeout=180)
    
    if not session_data:
        logger.error("❌ No session transfer data - falling back to manual mode")
        update_container_status("failed", "Session transfer failed")
        return resolve_with_gui_manual_fallback(email)
    
    # Validate session data quality
    required_fields = ['current_url', 'cookies', 'browser_fingerprint', 'linkedin_state']
    missing_fields = [field for field in required_fields if field not in session_data]
    
    if missing_fields:
        logger.warning(f"⚠️ Session data missing fields: {missing_fields}")
        if 'current_url' in missing_fields or 'cookies' in missing_fields:
            logger.error("❌ Critical session data missing - falling back")
            return resolve_with_gui_manual_fallback(email)
    
    update_container_status("ready", "Enhanced session transfer completed")
    
    try:
        # Create enhanced browser
        os.environ['DISPLAY'] = ':0'
        options = Options()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--window-size=1400,900')
        options.add_argument('--start-maximized')
        
        # Use session-specific profile
        user_data_dir = f"/tmp/chrome-enhanced-{email.replace('@', '_')}-{int(time.time())}"
        os.makedirs(user_data_dir, exist_ok=True)
        options.add_argument(f'--user-data-dir={user_data_dir}')
        
        # Match original user agent exactly
        if 'user_agent' in session_data:
            options.add_argument(f'--user-agent={session_data["user_agent"]}')
        
        logger.info("Starting enhanced Chrome browser...")
        driver = uc.Chrome(options=options, version_main=136)
        
        # Enhanced session restoration
        logger.info("🔄 Starting enhanced session restoration...")
        restore_result = restore_browser_session_enhanced(driver, session_data)
        
        if restore_result == "already_logged_in":
            logger.info("🎉 Already logged in! Saving cookies...")
            save_cookies(driver, f"/app/cookies/linkedin_cookies_{email}.pkl")
            update_container_status("completed", "Already logged in - no CAPTCHA needed")
            driver.quit()
            return True
        elif restore_result == False:
            logger.error("❌ Enhanced session restoration failed")
            update_container_status("failed", "Session restoration failed")
            driver.quit()
            return resolve_with_gui_manual_fallback(email)
        elif restore_result == "unknown_page":
            logger.warning("⚠️ Unknown page after restoration - continuing with monitoring")
        
        # Continue with CAPTCHA monitoring...
        logger.info("="*70)
        logger.info("🎯 ENHANCED CAPTCHA READY FOR SOLVING")
        logger.info("="*70)
        logger.info(f"Email: {email}")
        logger.info(f"Current URL: {driver.current_url}")
        logger.info("Enhanced session restoration completed!")
        logger.info("="*70)
        
        update_container_status("solving", "Enhanced browser ready - CAPTCHA page loaded")
        
        # Enhanced monitoring with better detection
        max_wait = 900  # 15 minutes
        check_interval = 10
        start_time = time.time()
        last_url = driver.current_url
        
        while time.time() - start_time < max_wait:
            try:
                current_url = driver.current_url
                
                # URL change detection
                if current_url != last_url:
                    logger.info(f"🔄 Navigation detected: {current_url}")
                    last_url = current_url
                
                # Enhanced success detection
                success_patterns = [
                    '/feed/',
                    '/home/',
                    '/mynetwork/',
                    '/sales/',
                    'linkedin.com/in/',
                    '/notifications/'
                ]
                
                if any(pattern in current_url.lower() for pattern in success_patterns):
                    logger.info("🎉 SUCCESS! Enhanced CAPTCHA solved and login completed!")
                    logger.info(f"Final URL: {current_url}")
                    
                    # Enhanced cookie saving
                    os.makedirs("/app/cookies/", exist_ok=True)
                    cookie_path = f"/app/cookies/linkedin_cookies_{email}.pkl"
                    save_cookies(driver, cookie_path)
                    logger.info(f"✅ Enhanced cookies saved: {cookie_path}")
                    
                    # 🔥 NEW: Copy cookies to shared volume for main app
                    copy_cookies_to_shared_volume(email, cookie_path)
                    
                    # 🔥 NEW: Notify main application of success
                    notify_main_app_success(email, current_url)
                    
                    update_container_status("completed", "Enhanced CAPTCHA solved successfully")
                    
                    # 🔥 NEW: Keep container alive longer for main app to detect success
                    logger.info("Keeping container alive for 2 minutes for main app detection...")
                    time.sleep(120)
                    break
                
                # Still on CAPTCHA/checkpoint
                captcha_patterns = ['checkpoint', 'challenge', 'verify', 'captcha']
                if any(pattern in current_url.lower() for pattern in captcha_patterns):
                    elapsed = time.time() - start_time
                    remaining = (max_wait - elapsed) / 60
                    if int(elapsed) % 60 == 0:
                        logger.info(f"🧩 Enhanced CAPTCHA solving in progress... {remaining:.1f} min remaining")
                
                time.sleep(check_interval)
                
            except Exception as check_error:
                logger.warning(f"⚠️ Enhanced monitor error: {check_error}")
                time.sleep(check_interval)
        
        # Cleanup and final status
        final_url = driver.current_url
        success_patterns = ['/feed/', '/home/', '/mynetwork/', '/sales/']
        success = any(pattern in final_url.lower() for pattern in success_patterns)
        
        if not success:
            logger.warning("⚠️ Enhanced CAPTCHA resolution timeout")
            update_container_status("failed", "Enhanced CAPTCHA resolution timeout")
        
        time.sleep(30)
        driver.quit()
        
        # Cleanup
        try:
            import shutil
            shutil.rmtree(user_data_dir, ignore_errors=True)
        except:
            pass
        
        # Mark as processed
        with open(PROCESSED_FILE, "a") as f:
            f.write(f"{email}\n")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Enhanced automatic GUI error: {e}")
        update_container_status("failed", f"Enhanced browser error: {str(e)}")
        with open(PROCESSED_FILE, "a") as f:
            f.write(f"{email}\n")
        return False

def resolve_with_gui_manual_fallback(email):
    """🔄 Fallback to manual mode if session transfer fails"""
    logger.info("="*70)
    logger.info("🔄 FALLBACK TO MANUAL MODE")
    logger.info("="*70)
    logger.info(f"Email: {email}")
    logger.info("Reason: Session transfer failed or timed out")
    
    # Update status
    update_container_status("solving", "Using manual fallback mode")
    
    creds = find_credentials_for_email(email)
    if not creds:
        logger.error(f"❌ No credentials available for {email}")
        update_container_status("failed", "No credentials available for manual mode")
        with open(PROCESSED_FILE, "a") as f:
            f.write(f"{email}\n")
        return False

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
        time.sleep(5)
        
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
            logger.warning(f"⚠️ Could not pre-fill form: {form_error}")
        
        logger.info("="*70)
        logger.info("🔄 MANUAL FALLBACK MODE ACTIVE")
        logger.info("="*70)
        logger.info("USER INSTRUCTIONS:")
        logger.info("   1. 🖱️ Click 'Sign in' button to trigger CAPTCHA")
        logger.info("   2. 🧩 Solve the CAPTCHA challenge")
        logger.info("   3. ✅ Complete login manually")
        logger.info("="*70)
        
        # Manual monitoring
        max_wait = 900  # 15 minutes
        start_time = time.time()
        success = False
        
        while time.time() - start_time < max_wait:
            try:
                current_url = driver.current_url
                if any(indicator in current_url.lower() for indicator in ['feed', 'sales', 'mynetwork']):
                    logger.info("✅ Manual login completed!")
                    
                    # Save cookies
                    os.makedirs("/app/cookies/", exist_ok=True)
                    cookie_path = f"/app/cookies/linkedin_cookies_{email}.pkl"
                    save_cookies(driver, cookie_path)
                    logger.info(f"🍪 Cookies saved: {cookie_path}")
                    
                    update_container_status("completed", "Manual CAPTCHA solving completed")
                    success = True
                    break
                    
                time.sleep(15)
                
            except Exception as e:
                logger.warning(f"⚠️ Manual monitor error: {e}")
                time.sleep(15)
        
        if not success:
            logger.warning("⚠️ Manual mode timeout")
            update_container_status("failed", "Manual mode timeout")
        
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
            
        return success
            
    except Exception as e:
        logger.error(f"❌ Manual fallback error: {e}")
        update_container_status("failed", f"Manual fallback error: {str(e)}")
        with open(PROCESSED_FILE, "a") as f:
            f.write(f"{email}\n")
        return False

def watch_loop():
    """Main watch loop with enhanced status reporting"""
    time.sleep(8)
    logger.info("="*70)
    logger.info("🚀 ENHANCED AUTOMATIC CAPTCHA WATCHER STARTED")
    logger.info("="*70)
    logger.info("Features:")
    logger.info("✅ Enhanced session transfer with debugging")
    logger.info("✅ Improved error handling and retry logic")
    logger.info("✅ Better cookie loading and validation")
    logger.info("✅ Real-time status reporting")
    logger.info("✅ Fallback to manual mode if needed")
    logger.info("✅ Comprehensive logging and monitoring")
    logger.info("="*70)

    # Update initial status
    update_container_status("starting", "CAPTCHA watcher initialized and ready")
    
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
                        logger.info(f"🎯 NEW ENHANCED CAPTCHA REQUEST: {email}")
                        logger.info("*" * 70) 
                        try:
                            success = resolve_with_gui_automatic(email)
                            if success:
                                logger.info("🎉 CAPTCHA RESOLUTION SUCCESSFUL!")
                            else:
                                logger.warning("⚠️ CAPTCHA RESOLUTION FAILED")
                        except Exception as e:
                            logger.error(f"❌ Error processing CAPTCHA request: {e}")
                            update_container_status("failed", f"Processing error: {str(e)}")
                        finally:
                            processed.add(email)
                        logger.info("🏁 ENHANCED CAPTCHA PROCESSING COMPLETED")
                        logger.info("*" * 70)
                        
                # Update the queue file
                remaining = [e for e in lines if e not in processed]
                with open(WATCH_FILE, "w") as f:
                    for email in remaining:
                        f.write(f"{email}\n")
            else:
                # Update status when idle
                update_container_status("ready", "Waiting for CAPTCHA requests")
                        
            time.sleep(10)
            
        except KeyboardInterrupt:
            logger.info("="*70)
            logger.info("🛑 Enhanced Captcha watcher stopped by user")
            logger.info("="*70)
            update_container_status("stopping", "Stopped by user")
            break
        except Exception as e:
            logger.error(f"❌ Error in main loop: {e}", exc_info=True)
            update_container_status("failed", f"Main loop error: {str(e)}")
            time.sleep(5)

if __name__ == "__main__":
    logger.info("🚀 Starting ENHANCED CAPTCHA Watcher with Improved Session Transfer")
    logger.info(f"Container ID: {os.environ.get('HOSTNAME', 'unknown')}")
    logger.info(f"Email: {os.environ.get('EMAIL', 'unknown')}")
    
    # Initial status update
    update_container_status("initializing", "Starting enhanced CAPTCHA watcher")
    
    try:
        watch_loop()
    except Exception as e:
        logger.error(f"❌ Fatal error in CAPTCHA watcher: {e}")
        update_container_status("failed", f"Fatal error: {str(e)}")
        sys.exit(1)