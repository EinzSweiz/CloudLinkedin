import pickle
import os
import logging
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time

logger = logging.getLogger(__name__)
COOKIES_PATH = "/app/cookies/linkedin_cookies.pkl"
IMPORTANT_COOKIES = {
    "li_at", "JSESSIONID", "lidc", "bcookie", "bscookie", "lang", "li_rm"
}

def save_cookies(driver: WebDriver, path: str = COOKIES_PATH):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as file:
            pickle.dump(driver.get_cookies(), file)
            logger.info(f"[COOKIES] Cookies saved successfully to: {path}")
    except Exception as e:
        logger.error(f"[COOKIES] Failed to save cookies: {e}")

def load_cookies(driver: WebDriver, path: str = COOKIES_PATH) -> bool:
    try:
        if not os.path.exists(path):
            logger.warning(f"[COOKIES] File not found: {path}")
            return False

        with open(path, 'rb') as file:
            cookies = pickle.load(file)

        # ❌ FIX: Remove broken get_timeouts() call
        # Replace with manual default timeout
        original_timeout = 60

        # Use shorter timeout for initial page load
        driver.set_page_load_timeout(30)

        try:
            logger.info("[COOKIES] Loading LinkedIn base page...")
            driver.get("https://www.linkedin.com")

            WebDriverWait(driver, 20).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            logger.warning("[COOKIES] Page load timeout, continuing anyway...")
        except Exception as e:
            logger.warning(f"[COOKIES] Page load issue: {e}, continuing...")
        finally:
            driver.set_page_load_timeout(original_timeout)

        current_domain = driver.execute_script("return document.domain")
        logger.info(f"[COOKIES] Loading cookies for domain: {current_domain}")

        valid_cookies_added = 0
        for cookie in cookies:
            if not isinstance(cookie, dict):
                logger.warning(f"[COOKIES] Skipped invalid cookie format: {type(cookie)}")
                continue

            cookie_name = cookie.get("name")
            if cookie_name not in IMPORTANT_COOKIES:
                continue

            try:
                clean_cookie = {
                    "name": str(cookie_name),
                    "value": str(cookie["value"]),
                    "domain": current_domain
                }
                if "path" in cookie:
                    clean_cookie["path"] = cookie["path"]
                if "secure" in cookie:
                    clean_cookie["secure"] = cookie["secure"]
                if "httpOnly" in cookie:
                    clean_cookie["httpOnly"] = cookie["httpOnly"]

                driver.add_cookie(clean_cookie)
                valid_cookies_added += 1
                logger.debug(f"[COOKIES] Added: {cookie_name}")
            except Exception as e:
                logger.warning(f"[COOKIES] Failed to add {cookie_name}: {e}")

        logger.info(f"[COOKIES] Added {valid_cookies_added} valid cookies")

        driver.set_page_load_timeout(30)
        try:
            logger.info("[COOKIES] Testing cookies by navigating to feed...")
            driver.get("https://www.linkedin.com/feed/")
            WebDriverWait(driver, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            logger.warning("[COOKIES] Feed page load timeout, checking URL anyway...")
        except Exception as e:
            logger.warning(f"[COOKIES] Feed page load issue: {e}, checking URL anyway...")
        finally:
            driver.set_page_load_timeout(original_timeout)

        time.sleep(2)
        current_url = driver.current_url
        if "login" in current_url or "checkpoint" in current_url:
            logger.warning(f"[COOKIES] Cookies invalid — redirected to: {current_url}")
            return False

        logger.info("[COOKIES] Cookies are valid and working!")
        return True

    except Exception as e:
        logger.error(f"[COOKIES] Failed to load cookies: {e}")
        return False
