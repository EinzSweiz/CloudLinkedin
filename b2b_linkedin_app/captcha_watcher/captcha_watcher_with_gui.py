import os
import sys
import time
import json

# Fix the import path for Docker
sys.path.append('/app')

try:
    from parser.engine.core.cookies import save_cookies
    from parser.engine.core.acount_credits_operator import Credential
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the correct directory")
    sys.exit(1)

from selenium.webdriver.chrome.options import Options
import undetected_chromedriver as uc

WATCH_FILE = "./shared_volume/captcha_queue.txt"
PROCESSED_FILE = "./shared_volume/captcha_resolved.txt"

def find_credentials_for_email(target_email):
    """Find specific credentials for the given email in the JSON file"""
    try:
        # Try to read credentials directly from JSON file
        json_path = 'credentials.json'
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as file:
                all_creds = json.load(file)
                
            # Find the specific email
            for cred in all_creds:
                if cred.get('email') == target_email:
                    print(f"✅ Found specific credentials for: {target_email}")
                    return cred
            
            print(f"⚠️  Specific email {target_email} not found in credentials")
        
        # Fallback: use any valid credential
        credential = Credential()
        creds = credential.get_credentials()
        if creds:
            print(f"🔄 Using fallback credentials: {creds.get('email', 'unknown')}")
            return creds
        
        return None
        
    except Exception as e:
        print(f"❌ Error finding credentials: {e}")
        # Last resort - try the Credential class
        try:
            credential = Credential()
            return credential.get_credentials()
        except:
            return None

def resolve_with_gui(email):
    """This shows ACTUAL GUI browser via VNC"""
    print(f"🔍 Looking for credentials for: {email}")
    creds = find_credentials_for_email(email)
    
    if not creds:
        print(f"❌ No credentials available for {email}")
        # Mark as processed to avoid infinite loop
        with open(PROCESSED_FILE, "a") as f:
            f.write(f"{email}\n")
        return

    EMAIL = creds.get("email", "unknown")
    PASSWORD = creds.get("password", "unknown")
    
    print(f"\n{'='*60}")
    print(f"🔐 GUI CAPTCHA RESOLUTION")
    print(f"{'='*60}")
    print(f"📧 Target Email: {email}")
    print(f"📧 Using Email: {EMAIL[:3]}***@{EMAIL.split('@')[1] if '@' in EMAIL else 'domain'}")
    print(f"🌐 Opening GUI browser...")
    print(f"📺 Connect via VNC to localhost:5900")
    print(f"🔒 VNC Password: password")
    print(f"{'='*60}")
    
    try:
        # Create visible browser (works with VNC)
        options = Options()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--window-size=1200,800')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--disable-web-security')
        options.add_argument('--allow-running-insecure-content')
        # NO headless - this creates visible window in VNC
        
        print(f"🚀 Starting Chrome browser...")
        driver = uc.Chrome(options=options, version_main=136)
        
        # Navigate to LinkedIn login
        print(f"🌐 Navigating to LinkedIn login...")
        driver.get("https://www.linkedin.com/login")
        time.sleep(3)
        
        # Pre-fill the form to help the user
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            # Wait for and fill email field
            wait = WebDriverWait(driver, 10)
            email_field = wait.until(EC.presence_of_element_located((By.ID, "username")))
            email_field.clear()
            email_field.send_keys(EMAIL)
            
            # Fill password field
            password_field = driver.find_element(By.ID, "password")
            password_field.clear()
            password_field.send_keys(PASSWORD)
            
            print(f"✅ Pre-filled login form with credentials")
            
        except Exception as form_error:
            print(f"⚠️  Could not pre-fill form: {form_error}")
        
        print(f"")
        print(f"📺 VNC INSTRUCTIONS:")
        print(f"   1. Open VNC Viewer on your computer")
        print(f"   2. Connect to: localhost:5900")
        print(f"   3. Enter password: password")
        print(f"   4. You'll see Chrome with LinkedIn login")
        print(f"   5. Credentials are pre-filled - just solve captcha/click login")
        print(f"   6. Wait for successful login to LinkedIn")
        print(f"")
        print(f"⏰ Auto-monitoring for completion...")
        
        # Monitor for successful login
        max_wait = 600  # 10 minutes
        check_interval = 20  # Check every 20 seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                current_url = driver.current_url
                
                # Check if successfully logged in
                success_indicators = ['feed', 'sales', 'mynetwork', 'in/']
                if any(indicator in current_url.lower() for indicator in success_indicators):
                    print(f"🎉 SUCCESS! Login completed!")
                    print(f"📍 Final URL: {current_url}")
                    break
                
                # Check if still on login/checkpoint page
                if any(indicator in current_url.lower() for indicator in ['login', 'checkpoint', 'challenge']):
                    elapsed = time.time() - start_time
                    remaining = (max_wait - elapsed) / 60
                    print(f"⏰ Still on login page... {remaining:.1f} min remaining")
                    print(f"📍 Current: {current_url}")
                else:
                    print(f"🔍 Navigating... Current URL: {current_url}")
                
                time.sleep(check_interval)
                
            except Exception as check_error:
                print(f"⚠️  Monitor error: {check_error}")
                time.sleep(check_interval)
                continue
        
        # Final status check and cookie saving
        try:
            final_url = driver.current_url
            success_indicators = ['feed', 'sales', 'mynetwork', 'in/']
            
            if any(indicator in final_url.lower() for indicator in success_indicators):
                print(f"💾 Login successful! Saving cookies...")
                
                # Save cookies for the EMAIL that was actually used
                cookie_path = f"./cookies/linkedin_cookies_{EMAIL}.pkl"
                save_cookies(driver, cookie_path)
                print(f"✅ Cookies saved to: {cookie_path}")
                
                # Also save for the requested email if different
                if EMAIL != email:
                    cookie_path_requested = f"./cookies/linkedin_cookies_{email}.pkl"
                    save_cookies(driver, cookie_path_requested)
                    print(f"✅ Cookies also saved for requested email: {cookie_path_requested}")
                
            else:
                print(f"⚠️  Login may not be complete")
                print(f"📍 Final URL: {final_url}")
                
        except Exception as save_error:
            print(f"❌ Error saving cookies: {save_error}")
        
        print(f"🔒 Closing browser...")
        driver.quit()
        
        # Mark as resolved
        with open(PROCESSED_FILE, "a") as f:
            f.write(f"{email}\n")
        
        print(f"✅ {email} marked as resolved!")
        
    except Exception as e:
        print(f"❌ Error with GUI browser: {e}")
        import traceback
        traceback.print_exc()
        
        # Still mark as processed to prevent infinite retry
        with open(PROCESSED_FILE, "a") as f:
            f.write(f"{email}\n")

def watch_loop():
    """Enhanced watch loop with GUI support"""
    print("🔍 GUI CAPTCHA WATCHER STARTED")
    print("📺 VNC Server should be running on port 5900")
    print("🔒 VNC Password: password")
    
    # Show credential info on startup
    try:
        credential = Credential()
        print(f"📊 Credential manager initialized")
        # Don't call get_credentials() here as it marks one as used
        if os.path.exists('credentials.json'):
            with open('credentials.json', 'r') as f:
                all_creds = json.load(f)
                valid_count = sum(1 for c in all_creds if c.get('status', 'valid') == 'valid')
                print(f"📈 Available credentials: {valid_count}/{len(all_creds)} valid")
    except Exception as debug_error:
        print(f"⚠️  Could not check credentials: {debug_error}")
    
    print("Watching for captcha resolution requests...")
    processed = set()

    while True:
        try:
            if os.path.exists(WATCH_FILE):
                with open(WATCH_FILE, "r") as f:
                    lines = [line.strip() for line in f.readlines()]
                    
                for email in lines:
                    if email and email not in processed:
                        print(f"\n🎯 NEW CAPTCHA REQUEST: {email}")
                        resolve_with_gui(email)
                        processed.add(email)
                        
                # Clean up processed entries
                if lines:
                    remaining = [e for e in lines if e not in processed]
                    with open(WATCH_FILE, "w") as f:
                        for email in remaining:
                            f.write(f"{email}\n")
            
            time.sleep(10)
            
        except KeyboardInterrupt:
            print("\n👋 GUI Captcha watcher stopped")
            break
        except Exception as e:
            print(f"❌ Error in main loop: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(5)

if __name__ == "__main__":
    watch_loop()