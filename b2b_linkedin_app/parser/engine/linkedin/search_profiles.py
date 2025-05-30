import time
import logging
import random
from typing import List, Dict
from urllib.parse import quote
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from django.conf import settings

from parser.engine.linkedin.login import get_logged_driver
from parser.engine.linkedin.search_options.extract_name import extract_name
from parser.engine.linkedin.search_options.extract_company import extract_company_from_profile
from parser.engine.linkedin.search_options.extract_position import extract_position
from parser.engine.linkedin.search_options.exract_profile_url import extract_profile_url_from_card
from parser.engine.linkedin.search_options.extract_email import extract_personal_email
from parser.engine.linkedin.search_options.extract_company_domain import extract_domain
from parser.engine.linkedin.search_options.location_codes import LOCATION_CODES
from parser.engine.linkedin.search_options.safety_scripts import scroll_script
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)
LINKEDIN_SEARCH_URL = settings.LINKEDIN_SEARCH_URL
HUNTER_API_KEY = settings.HUNTER_API_KEY

def search_linkedin_profiles(
    keywords: List[str],
    location: str = "France",
    limit: int = 50,
    start_page: int = 1,
    end_page: int = 10 
) -> List[Dict]:
    driver = get_logged_driver()

    location_code = LOCATION_CODES.get(location.lower())
    if not location_code:
        logger.warning(f"[LOCATION] Unknown location '{location}', defaulting to France.")
        location_code = LOCATION_CODES["france"]

    keyword_str = quote(" ".join(keywords), safe="")
    geo_urn_param = quote(f'["{location_code}"]', safe="")
    final_url = LINKEDIN_SEARCH_URL.format(keywords=keyword_str, location_code=geo_urn_param)

    logger.info(f"[DEBUG] Final URL after login: {final_url}")
    driver.get(final_url)
    time.sleep(random.uniform(3, 6))
    
    current_page = 1
    while current_page < start_page:
        try:
            logger.info(f"[SKIP] Skipping to page {start_page} (current: {current_page})")

            wait = WebDriverWait(driver, 10)
            next_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[@aria-label="Next"]')))

            driver.execute_script(scroll_script)
            time.sleep(random.uniform(2, 4))

            next_button.click()
            current_page += 1
            time.sleep(random.uniform(2, 4))
        except Exception as e:
            logger.warning(f"[SKIP] Failed to skip to page {start_page}: {e}")
            return []

    profiles = []
    seen = set()

    while len(profiles) < limit and current_page <= end_page:
        logger.info(f"[SEARCH] Parsing page {current_page}: {driver.current_url}")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.uniform(3, 6))

        cards = driver.find_elements(By.CSS_SELECTOR, 'div[data-chameleon-result-urn]')
        logger.info(f"[SEARCH] Found {len(cards)} cards on page")
        visited_domains = {}
        for i in range(len(cards)):
            try:
                time.sleep(random.uniform(1.0, 2.5))

                # 🔄 Каждый раз пересоздаём cards
                cards = driver.find_elements(By.CSS_SELECTOR, 'div[data-chameleon-result-urn]')
                card = cards[i]  # теперь это свежий элемент

                card_html = card.get_attribute('outerHTML')
                soup = BeautifulSoup(card_html, 'html.parser')
                
                name = extract_name(soup)
                position = extract_position(soup)
                profile_url = extract_profile_url_from_card(soup)

                if not profile_url:
                    continue

                # 🔄 Переход по профилю
                company = extract_company_from_profile(driver, profile_url)

                if position == "Unknown":
                    with open(f"debug_card_{name.replace(' ', '_')}.html", "w", encoding="utf-8") as f:
                        f.write(card_html)
                    logger.debug(f"[DEBUG] Saved unknown-position card: {name}")

                if company in visited_domains:
                    domain = visited_domains[company]
                else:
                    domain = extract_domain(driver, company)
                    visited_domains[company] = domain

                name_parts = name.split()
                first_name = name_parts[0] if len(name_parts) > 0 else ""
                last_name = name_parts[-1] if len(name_parts) > 1 else ""
                email = extract_personal_email(
                    first_name=first_name, 
                    last_name=last_name, 
                    domain=domain, 
                    api_key=HUNTER_API_KEY
                )

                profiles.append({
                    "name": name,
                    "position": position,
                    "company": company,
                    "email": email,
                    "profile_url": profile_url,
                })

                if len(profiles) >= limit:
                    break

            except Exception as e:
                logger.warning(f"[PROFILE PARSE] Skipped one card due to error: {e}")
                continue

        # Навигация на следующую страницу
        try:
            next_button = driver.find_element(By.XPATH, '//button[@aria-label="Next"]')
            driver.execute_script(scroll_script)
            time.sleep(random.uniform(3, 6))
            if next_button.is_enabled():
                logger.info("[NAVIGATION] Clicking Next button...")
                time.sleep(random.uniform(1, 3))
                next_button.click()
                time.sleep(random.uniform(3, 6))
                current_page += 1
            else:
                logger.warning("[NAVIGATION] Next button is not enabled. Exiting pagination.")
                break
        except Exception as e:
            logger.warning(f"[NAVIGATION] No Next button found or failed to click: {e}")
            break

    driver.quit()
    logger.info(f"[RESULT] Parsed {len(profiles)} profiles.")
    return profiles


# import time
# import logging
# import random
# from typing import List, Dict
# from urllib.parse import quote
# from selenium.webdriver.common.by import By
# from bs4 import BeautifulSoup
# from django.conf import settings

# from parser.engine.linkedin.login import get_logged_driver
# from parser.engine.linkedin.search_options.extract_name import extract_name
# from parser.engine.linkedin.search_options.extract_company import extract_company
# from parser.engine.linkedin.search_options.extract_position import extract_position
# from parser.engine.linkedin.search_options.exract_profile_url import extract_profile_url
# from parser.engine.linkedin.search_options.extract_email import extract_personal_email
# from parser.engine.linkedin.search_options.extract_company_email import extract_company_domain
# from parser.engine.linkedin.search_options.location_codes import LOCATION_CODES
# from parser.engine.linkedin.search_options.safety_scripts import scroll_script
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC

# logger = logging.getLogger(__name__)
# LINKEDIN_SEARCH_URL = settings.LINKEDIN_SEARCH_URL
# HUNTER_API_KEY = settings.HUNTER_API_KEY

# def search_linkedin_profiles(
#     keywords: List[str],
#     location: str = "France",
#     limit: int = 50,
#     start_page: int = 1,
#     end_page: int = 10 
# ) -> List[Dict]:
#     driver = get_logged_driver()

#     location_code = LOCATION_CODES.get(location.lower())
#     if not location_code:
#         logger.warning(f"[LOCATION] Unknown location '{location}', defaulting to France.")
#         location_code = LOCATION_CODES["france"]

#     keyword_str = "%20".join(keywords)
#     location_param = quote(f'["{location_code}"]')
#     final_url = LINKEDIN_SEARCH_URL.format(keywords=keyword_str, location_code=location_param)

#     logger.info(f"[DEBUG] Final URL after login: {final_url}")
#     driver.get(final_url)
#     time.sleep(random.uniform(3, 6))
    
#     current_page = 1
#     while current_page < start_page:
#         try:
#             logger.info(f"[SKIP] Skipping to page {start_page} (current: {current_page})")

#             wait = WebDriverWait(driver, 10)
#             next_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[@aria-label="Next"]')))

#             driver.execute_script(scroll_script)
#             time.sleep(random.uniform(2, 4))

#             next_button.click()
#             current_page += 1
#             time.sleep(random.uniform(2, 4))
#         except Exception as e:
#             logger.warning(f"[SKIP] Failed to skip to page {start_page}: {e}")
#             return []

#     profiles = []
#     seen = set()

#     while len(profiles) < limit and current_page <= end_page:
#         logger.info(f"[SEARCH] Parsing page {current_page}: {driver.current_url}")
#         driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
#         time.sleep(random.uniform(3, 6))

#         cards = driver.find_elements(By.CSS_SELECTOR, 'div[data-chameleon-result-urn]')
#         logger.info(f"[SEARCH] Found {len(cards)} cards on page")

#         for card in cards:
#             try:
#                 time.sleep(random.uniform(0.5, 1.2))
#                 # soup = BeautifulSoup(card.get_attribute('outerHTML'), 'html.parser')
#                 card_html = card.get_attribute('outerHTML')
#                 card_urn = card.get_attribute("data-chameleon-result-urn") 
#                 soup = BeautifulSoup(card_html, 'html.parser')
#                 name = extract_name(soup)
#                 company = extract_company(soup)
#                 position = extract_position(soup)
#                 profile_url = extract_profile_url(card_urn)
#                 if position == "Unknown":
#                     with open(f"debug_card_{name.replace(' ', '_')}.html", "w", encoding="utf-8") as f:
#                         f.write(soup.prettify())
#                     logger.debug(f"[DEBUG] Saved unknown-position card: {name}")
#                 if not profile_url or profile_url in seen:
#                     continue
#                 name_parts = name.split()
#                 first_name = name_parts[0] if len(name_parts) > 0 else ""
#                 last_name = name_parts[-1] if len(name_parts) > 1 else ""
#                 domain = extract_company_domain(driver, company)
#                 email = extract_personal_email(first_name=first_name, last_name=last_name, domain=domain, api_key=HUNTER_API_KEY)


#                 seen.add(profile_url)

#                 profiles.append({
#                     "name": name,
#                     "position": position,
#                     "company": company,
#                     "email": email,
#                     "profile_url": profile_url,
#                 })

#                 if len(profiles) >= limit:
#                     break

#             except Exception as e:
#                 logger.warning(f"[PROFILE PARSE] Skipped one card due to error: {e}")
#                 continue

#         # Навигация на следующую страницу
#         try:
#             next_button = driver.find_element(By.XPATH, '//button[@aria-label="Next"]')
#             driver.execute_script(scroll_script)
#             time.sleep(random.uniform(3, 6))
#             if next_button.is_enabled():
#                 logger.info("[NAVIGATION] Clicking Next button...")
#                 time.sleep(random.uniform(1, 3))
#                 next_button.click()
#                 time.sleep(random.uniform(3, 6))
#                 current_page += 1
#             else:
#                 logger.warning("[NAVIGATION] Next button is not enabled. Exiting pagination.")
#                 break
#         except Exception as e:
#             logger.warning(f"[NAVIGATION] No Next button found or failed to click: {e}")
#             break

#     driver.quit()
#     logger.info(f"[RESULT] Parsed {len(profiles)} profiles.")
#     return profiles

