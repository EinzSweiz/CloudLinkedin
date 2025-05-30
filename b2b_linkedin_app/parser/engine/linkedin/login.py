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

def relaunch_for_captcha(email: str, user_data_dir: str):
    options = Options()
    options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = uc.Chrome(options=options, version_main=136)
    driver.get(LINKEDIN_LOGIN_URL)
    logger.info(f"[MANUAL CAPTCHA] Opened GUI browser for: {email}")
    print(f"\n🔐 CAPTCHA REQUIRED — GUI Chrome opened for: {email}\n")
    print("✅ После прохождения закрой браузер.")
    return driver

def get_logged_driver(retry_count=3):
    logger.info("[LOGIN] Attempting login using saved cookies or credentials...")
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

    plugin_path = create_proxy_auth_extension(proxy_host=ip, proxy_port=int(port), proxy_username=user, proxy_password=pwd)
    if not os.path.exists(plugin_path):
        raise ValueError("Proxy plugin creation failed or path is invalid")
    options.add_extension(plugin_path)

    driver = uc.Chrome(options=options, version_main=136)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        window.navigator.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        """
    })

    try:
        creds = credential.get_credentials()
        if not creds:
            raise Exception("no_valid_credentials")

        EMAIL = creds["email"]
        PASSWORD = creds["password"]
        cookie_path = f"/app/cookies/linkedin_cookies_{EMAIL}.pkl"

        if load_cookies(driver, cookie_path):
            logger.info(f"[LOGIN] Success with cookies: {EMAIL}")
            return driver
        else:
            if os.path.exists(cookie_path):
                os.remove(cookie_path)

        driver.get(LINKEDIN_LOGIN_URL)
        wait = WebDriverWait(driver, 30)
        email_input = wait.until(EC.presence_of_element_located((By.ID, "username")))
        password_input = wait.until(EC.presence_of_element_located((By.ID, "password")))
        email_input.send_keys(EMAIL)
        password_input.send_keys(PASSWORD)
        password_input.send_keys(Keys.RETURN)
        time.sleep(6)

        current_url = driver.current_url
        title = driver.title.lower()

        if "feed" in current_url:
            save_cookies(driver, cookie_path)
            return driver
        elif "checkpoint" in current_url or "verify" in title or "security" in title:
            logger.warning(f"[CAPTCHA DETECTED] For: {EMAIL}")
            driver.quit()
            relaunch_for_captcha(EMAIL, profile_path)
            raise Exception("checkpoint_manual")
        elif "login" in current_url:
            credential.mark_invalid(reason="bad_login")
            raise Exception("bad_login")
        else:
            credential.mark_invalid(reason="unknown")
            raise Exception("unknown")

    except Exception as e:
        logger.error(f"[LOGIN ERROR] {e}")
        try:
            screenshot_path = os.path.join(LOGS_DIR, f"{EMAIL}_login_error.png")
            html_path = os.path.join(LOGS_DIR, f"{EMAIL}_page_source.html")
            driver.save_screenshot(screenshot_path)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
        except Exception as save_error:
            logger.error(f"[SAVE ERROR] {save_error}")
        finally:
            driver.quit()

        if retry_count > 0 and str(e) == "bad_login":
            return get_logged_driver(retry_count - 1)
        else:
            raise

# def get_logged_driver():
#     logger.info("[LOGIN] Skipping proxy for debugging...")

#     options = Options()
#     # options.add_argument('--headless=new')
#     options.add_argument(f'user-agent={user_agents.get_random_user_agent()}')
#     options.add_argument('--no-sandbox')
#     options.add_argument('--disable-dev-shm-usage')
#     options.add_argument('--disable-blink-features=AutomationControlled')

#     driver = uc.Chrome(options=options)

#     try:
#         # 1. Попробуем загрузить cookies
#         driver.get("https://www.linkedin.com")
#         driver.add_cookie({
#             "name": "li_at",
#             "value": "AQEDAVnHhV4BkPGJAAABlkYfv1AAAAGWaixDUE0ANmC6gV3_QTbzIMWjF1cisj2a2aEDJn79859kJr64PBoFaGJoVXfMktoKrj-ZB7qcgcK7KVs95TAPdVkWNbE8Eo37iwtVGY5CoxOz2mYrCD0NrMWM",
#             "domain": ".linkedin.com",
#             "path": "/",
#         })
#         load_cookies(driver, COOKIES_PATH)
#         driver.refresh()
#         time.sleep(5)
#         driver.get("https://www.linkedin.com/feed/")
#         time.sleep(5)
#         if "login" in driver.current_url or "checkpoint" in driver.current_url:
#             logger.warning("[LOGIN] Переадресовали на login — cookies не сработали.")
#         else:
#             logger.info("[LOGIN] Cookies работают, входим в LinkedIn.")

#         if "login" in driver.current_url or "checkpoint" in driver.current_url:
#             logger.warning("[LOGIN] Cookies невалидны — пробуем логин по email/паролю...")
#             driver.get(LINKEDIN_LOGIN_URL)
#             wait = WebDriverWait(driver, 10)

#             email_input = wait.until(EC.presence_of_element_located((By.ID, "username")))
#             password_input = wait.until(EC.presence_of_element_located((By.ID, "password")))
#             email_input.send_keys(EMAIL)
#             password_input.send_keys(PASSWORD)
#             password_input.send_keys(Keys.RETURN)

#             time.sleep(5)
#             save_cookies(driver, COOKIES_PATH)
#         else:
#             logger.info("[LOGIN] Авторизация по cookies успешна.")

#     except Exception as e:
#         logger.error(f"[LOGIN] Ошибка входа: {e}")
#         driver.quit()
#         raise

#     return driver
