# parser/engine/linkedin/search_profiles.py (Updated version)
import time
import logging
import random
from typing import List, Dict
from urllib.parse import quote
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from django.conf import settings

# Import the new manual captcha login
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
from parser.engine.linkedin.login import get_logged_driver

logger = logging.getLogger(__name__)
LINKEDIN_SEARCH_URL = "https://www.linkedin.com/search/results/people/?keywords={keywords}&geoUrn={location_code}"
HUNTER_API_KEY = settings.HUNTER_API_KEY

def search_linkedin_profiles(
    keywords: List[str],
    location: str = "France",
    limit: int = 50,
    start_page: int = 1,
    end_page: int = 10 
) -> List[Dict]:
    """
    Enhanced LinkedIn profile search with manual captcha handling
    """
    logger.info(f"[SEARCH] Starting LinkedIn search with manual captcha support")
    logger.info(f"[SEARCH] Keywords: {keywords}, Location: {location}, Pages: {start_page}-{end_page}")
    
    # Use the new login function with manual captcha support
    try:
        driver = get_logged_driver()  # This now has VNC captcha support
        logger.info(f"[SEARCH] ✅ Successfully logged in with VNC captcha support")
    except Exception as e:
        logger.error(f"[SEARCH] ❌ Failed to login: {e}")
        return []

    try:
        location_code = LOCATION_CODES.get(location.lower())
        if not location_code:
            logger.warning(f"[LOCATION] Unknown location '{location}', defaulting to France.")
            location_code = LOCATION_CODES["france"]

        keyword_str = quote(" ".join(keywords), safe="")
        geo_urn_param = quote(f'["{location_code}"]', safe="")
        final_url = LINKEDIN_SEARCH_URL.format(keywords=keyword_str, location_code=geo_urn_param)

        logger.info(f"[SEARCH] Navigating to search URL: {final_url}")
        driver.get(final_url)
        time.sleep(random.uniform(3, 6))
        
        # Check if we got redirected to login/captcha again
        current_url = driver.current_url
        if "login" in current_url or "checkpoint" in current_url:
            logger.warning(f"[SEARCH] Redirected to login page during search - this shouldn't happen after manual captcha")
            return []
        
        # Skip to start page if needed
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
        visited_domains = {}

        while len(profiles) < limit and current_page <= end_page:
            logger.info(f"[SEARCH] Parsing page {current_page}: {driver.current_url}")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(3, 6))

            cards = driver.find_elements(By.CSS_SELECTOR, 'div[data-chameleon-result-urn]')
            logger.info(f"[SEARCH] Found {len(cards)} cards on page {current_page}")
            
            if not cards:
                logger.warning(f"[SEARCH] No cards found on page {current_page}")
                break

            for i in range(len(cards)):
                try:
                    time.sleep(random.uniform(1.0, 2.5))

                    # Re-fetch cards to avoid stale element references
                    cards = driver.find_elements(By.CSS_SELECTOR, 'div[data-chameleon-result-urn]')
                    if i >= len(cards):
                        logger.warning(f"[SEARCH] Card index {i} out of range, skipping")
                        continue
                        
                    card = cards[i]
                    card_html = card.get_attribute('outerHTML')
                    soup = BeautifulSoup(card_html, 'html.parser')
                    
                    name = extract_name(soup)
                    position = extract_position(soup)
                    profile_url = extract_profile_url_from_card(soup)

                    if not profile_url:
                        logger.debug(f"[SEARCH] No profile URL found for {name}, skipping")
                        continue

                    # Extract company with fallback to profile visit
                    company = extract_company_from_profile(driver, profile_url)

                    # Debug unknown positions
                    if position == "Unknown":
                        debug_filename = f"debug_card_{name.replace(' ', '_')}_{int(time.time())}.html"
                        with open(debug_filename, "w", encoding="utf-8") as f:
                            f.write(card_html)
                        logger.debug(f"[DEBUG] Saved unknown-position card: {debug_filename}")

                    # Get domain (with caching)
                    if company in visited_domains:
                        domain = visited_domains[company]
                    else:
                        domain = extract_domain(driver, company)
                        visited_domains[company] = domain

                    # Extract email
                    email = None
                    if domain:
                        name_parts = name.split()
                        first_name = name_parts[0] if len(name_parts) > 0 else ""
                        last_name = name_parts[-1] if len(name_parts) > 1 else ""
                        email = extract_personal_email(
                            first_name=first_name, 
                            last_name=last_name, 
                            domain=domain, 
                            api_key=HUNTER_API_KEY
                        )

                    profile_data = {
                        "name": name,
                        "position": position,
                        "company": company,
                        "email": email,
                        "profile_url": profile_url,
                    }
                    
                    profiles.append(profile_data)
                    logger.info(f"[PROFILE] Extracted #{len(profiles)}: {name} @ {company}")

                    if len(profiles) >= limit:
                        break

                except Exception as e:
                    logger.warning(f"[PROFILE PARSE] Skipped card {i} due to error: {e}")
                    continue

            if len(profiles) >= limit:
                break

            # Navigate to next page
            try:
                next_button = driver.find_element(By.XPATH, '//button[@aria-label="Next"]')
                driver.execute_script(scroll_script)
                time.sleep(random.uniform(3, 6))
                
                if next_button.is_enabled():
                    logger.info(f"[NAVIGATION] Moving to page {current_page + 1}")
                    next_button.click()
                    time.sleep(random.uniform(3, 6))
                    current_page += 1
                else:
                    logger.info("[NAVIGATION] Next button disabled - reached last page")
                    break
            except Exception as e:
                logger.warning(f"[NAVIGATION] No next button found or error clicking: {e}")
                break

        logger.info(f"[RESULT] Completed search. Found {len(profiles)} profiles total.")
        return profiles

    except Exception as e:
        logger.error(f"[SEARCH] Fatal error during search: {e}")
        return []
    finally:
        try:
            driver.quit()
            logger.info(f"[CLEANUP] Browser closed successfully")
        except Exception as e:
            logger.warning(f"[CLEANUP] Error closing browser: {e}")