import logging
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webdriver import WebDriver
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# def extract_company_from_profile(driver: WebDriver, profile_url: str) -> str:
#     if not profile_url:
#         logger.warning("[FALLBACK] No profile URL provided — skipping fallback")
#         return "Unknown"

#     try:
#         logger.info(f"[FALLBACK] Opening profile page: {profile_url}")
#         driver.get(profile_url)

#         # Вместо тупого sleep ждем появления заголовка профиля
#         try:
#             WebDriverWait(driver, 15).until(
#                 EC.presence_of_element_located((By.CLASS_NAME, "text-body-medium"))
#             )
#         except Exception as wait_err:
#             logger.warning(f"[FALLBACK] Timeout waiting for profile headline: {wait_err}")

#         current_url = driver.current_url
#         if "/search/results/" in current_url or "/checkpoint/" in current_url:
#             logger.warning(f"[FALLBACK] Redirected to: {current_url} — skipping")
#             return "Unknown"

#         html_content = driver.page_source
#         soup = BeautifulSoup(html_content, "html.parser")

#         # Сохраняем страницу для дебага
#         try:
#             filename = profile_url.rstrip('/').split('/')[-1]
#             with open(f"profile_debug_{filename}.html", "w", encoding="utf-8") as f:
#                 f.write(soup.prettify())
#         except Exception as write_err:
#             logger.warning(f"[FALLBACK] Failed to write profile HTML: {write_err}")

#         # === 1. Headline-based parsing ===
#         headline_elem = (
#             soup.find("div", class_="text-body-medium break-words") or
#             soup.find("h1", class_="text-heading-xlarge") or
#             soup.find("div", class_="text-heading-medium")
#         )

#         if headline_elem:
#             text = headline_elem.get_text(strip=True)
#             if " at " in text:
#                 company = text.rsplit(" at ", 1)[-1].strip()
#                 logger.info(f"[FALLBACK] Extracted from headline (at): {company}")
#                 return company
#             elif "@" in text:
#                 company = text.rsplit("@", 1)[-1].strip()
#                 logger.info(f"[FALLBACK] Extracted from headline (@): {company}")
#                 return company
#             elif "|" in text:
#                 company = text.rsplit("|", 1)[-1].strip()
#                 logger.info(f"[FALLBACK] Extracted from headline (|): {company}")
#                 return company

#         # === 2. Experience Section Parsing ===
#         experience_sections = soup.find_all("section")
#         for sec in experience_sections:
#             heading = sec.find("h2")
#             if heading and "Experience" in heading.get_text():
#                 job_block = sec.find("li")
#                 if job_block:
#                     company_container = job_block.find("div", class_="display-flex align-items-center mr1 hoverable-link-text t-bold")
#                     if company_container:
#                         name_span = company_container.find("span", attrs={"aria-hidden": "true"})
#                         if name_span:
#                             company = name_span.get_text(strip=True)
#                             logger.info(f"[FALLBACK] Extracted correct company name from experience block: {company}")
#                             return company
#                 break

#         logger.info("[FALLBACK] Company not found in profile.")
#         return "Unknown"

#     except Exception as e:
#         logger.warning(f"[FALLBACK] Error while opening profile: {e}")
#         return "Unknown"

#     finally:
#         try:
#             logger.info("[FALLBACK] Going back to search results page...")
#             driver.back()
#             time.sleep(2)
#         except Exception as e:
#             logger.warning(f"[FALLBACK] Failed to go back after profile visit: {e}")

def extract_company_from_profile(driver: WebDriver, profile_url: str) -> str:
    if not profile_url:
        logger.warning("[FALLBACK] No profile URL provided — skipping fallback")
        return "Unknown"

    try:
        logger.info(f"[FALLBACK] Opening profile page: {profile_url}")
        driver.get(profile_url)

        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, "text-body-medium"))
            )
        except Exception as wait_err:
            logger.warning(f"[FALLBACK] Timeout waiting for profile headline: {wait_err}")

        current_url = driver.current_url
        if "/search/results/" in current_url or "/checkpoint/" in current_url:
            logger.warning(f"[FALLBACK] Redirected to: {current_url} — skipping")
            return "Unknown"

        html_content = driver.page_source
        soup = BeautifulSoup(html_content, "html.parser")

        # === 1. Headline-based parsing ===
        headline_elem = (
            soup.find("div", class_="text-body-medium break-words") or
            soup.find("h1", class_="text-heading-xlarge") or
            soup.find("div", class_="text-heading-medium")
        )

        if headline_elem:
            text = headline_elem.get_text(strip=True)
            if " at " in text:
                company = text.rsplit(" at ", 1)[-1].strip()
                logger.info(f"[FALLBACK] Extracted from headline (at): {company}")
                return company
            elif "@" in text:
                company = text.rsplit("@", 1)[-1].strip()
                logger.info(f"[FALLBACK] Extracted from headline (@): {company}")
                return company
            elif "|" in text:
                company = text.rsplit("|", 1)[-1].strip()
                logger.info(f"[FALLBACK] Extracted from headline (|): {company}")
                return company

        # === 2. Experience Section Parsing ===
        experience_sections = soup.find_all("section")
        for sec in experience_sections:
            heading = sec.find("h2")
            if heading and "Experience" in heading.get_text():
                job_block = sec.find("li")
                if job_block:
                    # Правильный поиск через <span aria-hidden="true">
                    spans = job_block.find_all("span", attrs={"aria-hidden": "true"})
                    for span in spans:
                        text = span.get_text(strip=True)
                        if "·" in text:
                            company = text.split("·")[0].strip()
                            logger.info(f"[FALLBACK] Extracted company name from experience block: {company}")
                            return company
                        elif text and len(text.split()) <= 5:  # fallback: если строка короткая
                            logger.info(f"[FALLBACK] Extracted possible company name: {text}")
                            return text
                break

        logger.info("[FALLBACK] Company not found in profile.")
        return "Unknown"

    except Exception as e:
        logger.warning(f"[FALLBACK] Error while opening profile: {e}")
        return "Unknown"

    finally:
        try:
            logger.info("[FALLBACK] Going back to search results page...")
            driver.back()
            time.sleep(2)
        except Exception as e:
            logger.warning(f"[FALLBACK] Failed to go back after profile visit: {e}")
