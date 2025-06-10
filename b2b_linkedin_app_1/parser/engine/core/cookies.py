import pickle
import os
import logging
from selenium.webdriver.remote.webdriver import WebDriver
import time

logger = logging.getLogger(__name__)
COOKIES_PATH = "/app/cookies/linkedin_cookies.pkl"
IMPORTANT_COOKIES = {
    "li_at", "JSESSIONID", "lidc", "bcookie", "bscookie", "lang", "li_rm"
}

def save_cookies(driver: WebDriver, path: str = COOKIES_PATH):
    try:
        with open(path, 'wb') as file:
            pickle.dump(driver.get_cookies(), file)
            logger.info("[COOKIES] Cookies saved successfully.")
    except Exception as e:
        logger.error(f"[COOKIES] Failed to save cookies: {e}")

def load_cookies(driver: WebDriver, path: str = COOKIES_PATH) -> bool:
    try:
        if not os.path.exists(path):
            logger.warning(f"[COOKIES] File not found: {path}")
            return False

        with open(path, 'rb') as file:
            cookies = pickle.load(file)

        driver.get("https://www.linkedin.com")
        driver.execute_script("return document.readyState")
        current_domain = driver.execute_script("return document.domain")
        logger.info(f"[COOKIES] Loaded cookies for domain: {current_domain}")

        for cookie in cookies:
            if not isinstance(cookie, dict):
                logger.warning(f"[COOKIES] Skipped invalid cookie format: {cookie}")
                continue
            if cookie.get("name") not in IMPORTANT_COOKIES:
                continue

            cookie.pop("expiry", None)
            cookie["domain"] = current_domain
            cookie["name"] = str(cookie["name"])
            cookie["value"] = str(cookie["value"])

            try:
                driver.add_cookie(cookie)
                logger.debug(f"[COOKIES] Added: {cookie['name']}")
            except Exception as e:
                logger.warning(f"[COOKIES] Failed to add {cookie['name']}: {e}")

        # 🧠 Проверяем валидность: если редиректит на login → cookies невалидны
        driver.get("https://www.linkedin.com/feed/")
        time.sleep(3)
        current_url = driver.current_url

        if "login" in current_url or "checkpoint" in current_url:
            logger.warning(f"[COOKIES] Cookies invalid — redirected to: {current_url}")
            return False

        logger.info("[COOKIES] Cookies are valid.")
        return True

    except Exception as e:
        logger.error(f"[COOKIES] Failed to load cookies: {e}")
        return False
