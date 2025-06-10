from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import logging
import datetime
import re

logger = logging.getLogger(__name__)

def extract_domain(driver, company_name: str) -> str | None:
    domain = None
    try:
        company_slug = company_name.lower().replace(" ", "-").replace(",", "")
        company_url = f"https://www.linkedin.com/company/{company_slug}/about/"
        logger.info(f"[COMPANY_DOMAIN] Navigating directly to: {company_url}")

        driver.get(company_url)
        time.sleep(5)  # можно заменить на WebDriverWait

        # Пробуем найти ссылку на сайт компании
        try:
            link = driver.find_element(
                By.XPATH,
                '//a[starts-with(@href, "http") and contains(@class, "link-without-visited-state")]'
            )
            domain = link.get_attribute("href")
            logger.info(f"[COMPANY_DOMAIN] Found domain: {domain}")
        except NoSuchElementException:
            logger.warning(f"[COMPANY_DOMAIN] No domain link found for: {company_name}")

    except Exception as e:
        logger.error(f"[COMPANY_DOMAIN] Unexpected error for {company_name}: {e}")
        return None

    finally:
        # ⬅️ Возвращаемся назад (очень важно для сохранения контекста)
        try:
            logger.info("[COMPANY_DOMAIN] Going back to search results...")
            driver.back()
            time.sleep(3)
        except Exception as e:
            logger.warning(f"[COMPANY_DOMAIN] Failed to go back after company visit: {e}")

    return domain.strip() if domain else None
