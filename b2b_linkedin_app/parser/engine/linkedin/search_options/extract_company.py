import logging
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webdriver import WebDriver
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)

def extract_company_from_search_card(soup: BeautifulSoup) -> str:
    """
    Extract company directly from search card before visiting profile
    """
    try:
        # Strategy 1: Look for company names in search card
        company_selectors = [
            'div.entity-result__primary-subtitle',
            'div.entity-result__secondary-subtitle', 
            '.entity-result__summary .t-12',
            '.entity-result__summary .t-14',
        ]
        
        for selector in company_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                
                # Parse company from text
                company = parse_company_from_text(text)
                if company and company != "Unknown":
                    logger.info(f"[CARD_COMPANY] Extracted from search card: {company}")
                    return company
        
        # Strategy 2: Look for company patterns in all text
        all_text = soup.get_text()
        company_patterns = [
            r'(?:at|@)\s+([A-Z][a-zA-Z\s&.-]+?)(?:\s|$|,|\.|;)',
            r'(?:CEO|CTO|CFO|Founder|Director)\s+(?:at|@)\s+([A-Z][a-zA-Z\s&.-]+?)(?:\s|$|,|\.|;)',
        ]
        
        for pattern in company_patterns:
            matches = re.findall(pattern, all_text, re.IGNORECASE)
            for match in matches:
                company = match.strip()
                if is_valid_company_name(company):
                    logger.info(f"[CARD_COMPANY] Extracted from card text: {company}")
                    return company
                    
    except Exception as e:
        logger.warning(f"[CARD_COMPANY] Error extracting from card: {e}")
    
    return "Unknown"

def extract_company_from_profile(driver: WebDriver, profile_url: str) -> str:
    """
    Enhanced company extraction with multiple parsing strategies
    """
    if not profile_url:
        logger.warning("[FALLBACK] No profile URL provided — skipping fallback")
        return "Unknown"

    try:
        logger.info(f"[FALLBACK] Opening profile page: {profile_url}")
        driver.get(profile_url)

        try:
            WebDriverWait(driver, 15).until(
                lambda d: d.find_element(By.CLASS_NAME, "text-body-medium") or
                         d.find_element(By.CLASS_NAME, "text-heading-xlarge") or
                         d.find_element(By.TAG_NAME, "main")
            )
        except Exception as wait_err:
            logger.warning(f"[FALLBACK] Timeout waiting for profile elements: {wait_err}")

        current_url = driver.current_url
        if "/search/results/" in current_url or "/checkpoint/" in current_url:
            logger.warning(f"[FALLBACK] Redirected to: {current_url} — skipping")
            return "Unknown"

        html_content = driver.page_source
        soup = BeautifulSoup(html_content, "html.parser")

        # Strategy 1: Extract from headline/title area
        company = extract_from_headline(soup)
        if company and company != "Unknown":
            return company

        # Strategy 2: Extract from experience section
        company = extract_from_experience_section(soup)
        if company and company != "Unknown":
            return company

        # Strategy 3: Extract from current position indicators
        company = extract_from_current_position(soup)
        if company and company != "Unknown":
            return company

        # Strategy 4: Extract from any text containing company indicators
        company = extract_from_page_text(soup)
        if company and company != "Unknown":
            return company

        logger.info("[FALLBACK] Company not found in profile using any method.")
        return "Unknown"

    except Exception as e:
        logger.warning(f"[FALLBACK] Error while opening profile: {e}")
        return "Unknown"

    finally:
        try:
            logger.info("[FALLBACK] Going back to search results page...")
            driver.back()
            time.sleep(2.5)

            #Confirm we are back on the search page with cards
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-chameleon-result-urn]'))
            )
            logger.info("[FALLBACK] Successfully returned to search results page")
        except Exception as e:
            logger.error(f"[FALLBACK] Failed to return to search results: {e}")
            raise RuntimeError("Lost LinkedIn search page after fallback — stopping to prevent misalignment")


def extract_from_headline(soup: BeautifulSoup) -> str:
    """
    Extract company from headline/title area with multiple selectors
    """
    try:
        # Multiple possible headline selectors
        headline_selectors = [
            "div.text-body-medium.break-words",
            "h1.text-heading-xlarge",
            "div.text-heading-medium",
            "div.pv-text-details__left-panel h1",
            ".pv-top-card--list-bullet li",
        ]

        for selector in headline_selectors:
            headline_elem = soup.select_one(selector)
            if headline_elem:
                text = headline_elem.get_text(strip=True)
                company = parse_company_from_text(text)
                if company:
                    logger.info(f"[HEADLINE] Extracted from headline: {company}")
                    return company

    except Exception as e:
        logger.warning(f"[HEADLINE] Error extracting from headline: {e}")
    
    return "Unknown"

def extract_from_experience_section(soup: BeautifulSoup) -> str:
    """
    Extract company from experience section with better parsing
    """
    try:
        # Look for experience sections
        experience_selectors = [
            'section[data-section="experience"]',
            'section:has(h2:contains("Experience"))',
            'div[id*="experience"]',
        ]

        for selector in experience_selectors:
            section = soup.select_one(selector)
            if section:
                # Look for the first job entry
                job_entries = section.find_all(['li', 'div'], class_=lambda x: x and ('experience' in str(x).lower() or 'position' in str(x).lower()))
                
                for entry in job_entries[:3]:  # Check first 3 entries
                    # Look for company name in various formats
                    spans = entry.find_all("span", attrs={"aria-hidden": "true"})
                    for span in spans:
                        text = span.get_text(strip=True)
                        
                        # Parse company from experience text
                        if "·" in text:
                            company = text.split("·")[0].strip()
                            if is_valid_company_name(company):
                                logger.info(f"[EXPERIENCE] Extracted company from experience: {company}")
                                return company
                        elif text and is_valid_company_name(text):
                            logger.info(f"[EXPERIENCE] Extracted possible company: {text}")
                            return text

    except Exception as e:
        logger.warning(f"[EXPERIENCE] Error extracting from experience: {e}")
    
    return "Unknown"

def extract_from_current_position(soup: BeautifulSoup) -> str:
    """
    Extract company from current position indicators
    """
    try:
        # Look for current position indicators
        current_position_selectors = [
            '.pv-entity__summary-info h3 span[aria-hidden="true"]',
            '.pv-entity__company-summary-info h3 span',
            'h4 span[aria-hidden="true"]',
        ]

        for selector in current_position_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                if is_valid_company_name(text):
                    logger.info(f"[CURRENT_POS] Extracted from current position: {text}")
                    return text

    except Exception as e:
        logger.warning(f"[CURRENT_POS] Error extracting from current position: {e}")
    
    return "Unknown"

def extract_from_page_text(soup: BeautifulSoup) -> str:
    """
    Extract company from general page text using patterns
    """
    try:
        # Get all text from the page
        page_text = soup.get_text()
        
        # Look for company patterns in text
        company_patterns = [
            r'(?:CEO|CTO|CFO|Founder|Director|Manager)\s+(?:at|@)\s+([A-Z][a-zA-Z\s&.-]+?)(?:\s|$|,|\.|;)',
            r'(?:works?|working)\s+(?:at|for)\s+([A-Z][a-zA-Z\s&.-]+?)(?:\s|$|,|\.|;)',
            r'Company:\s*([A-Z][a-zA-Z\s&.-]+?)(?:\s|$|,|\.|;)',
        ]

        for pattern in company_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            for match in matches:
                company = match.strip()
                if is_valid_company_name(company):
                    logger.info(f"[PAGE_TEXT] Extracted from page text: {company}")
                    return company

    except Exception as e:
        logger.warning(f"[PAGE_TEXT] Error extracting from page text: {e}")
    
    return "Unknown"

def parse_company_from_text(text: str) -> str:
    """
    Parse company name from various text formats
    """
    try:
        # Clean the text
        text = text.strip()
        
        # Try different separators
        separators = [" at ", "@", "|", " - ", " · "]
        
        for sep in separators:
            if sep in text:
                parts = text.rsplit(sep, 1)
                if len(parts) > 1:
                    company = parts[-1].strip()
                    if is_valid_company_name(company):
                        return company

        # If no separators found, check if the whole text is a company name
        if is_valid_company_name(text):
            return text

    except Exception as e:
        logger.warning(f"[PARSE_COMPANY] Error parsing company from text: {e}")
    
    return "Unknown"

def is_valid_company_name(company: str) -> bool:
    """
    Improved validation that's less strict about job titles in company names
    """
    if not company or len(company.strip()) < 2:
        return False
    
    # Remove extra whitespace
    company = company.strip()
    
    # Skip if it's too long (probably not a company name)
    if len(company) > 100:
        return False
    
    # Skip obvious non-company phrases
    pure_non_company_phrases = [
        'experience', 'education', 'skills', 'about', 'contact',
        'see more', 'view profile', 'connect', 'message', 'linkedin',
        'unknown', 'n/a', 'none', 'not specified'
    ]
    
    if company.lower() in pure_non_company_phrases:
        return False
    
    # Skip if it's just a single job title word (but allow compound names)
    single_job_titles = [
        'manager', 'director', 'analyst', 'specialist', 'coordinator',
        'assistant', 'associate', 'intern', 'consultant', 'engineer',
        'developer', 'designer', 'architect', 'lead', 'senior', 'junior',
        'president', 'officer', 'supervisor', 'representative'
    ]
    
    # Only reject if it's EXACTLY one of these words (not part of a company name)
    if company.lower() in single_job_titles:
        return False
    
    return True