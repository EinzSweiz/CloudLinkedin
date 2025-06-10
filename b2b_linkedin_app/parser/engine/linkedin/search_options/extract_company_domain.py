# Improved extract_company_domain.py
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import logging
import re

logger = logging.getLogger(__name__)

def extract_domain(driver, company_name: str) -> str | None:
    """
    Enhanced domain extraction with multiple fallback strategies
    """
    domain = None
    
    try:
        # Strategy 1: Direct company page approach
        company_slug = company_name.lower().replace(" ", "-").replace(",", "").replace("&", "").replace("|", "")
        company_url = f"https://www.linkedin.com/company/{company_slug}/about/"
        
        logger.info(f"[COMPANY_DOMAIN] Navigating to: {company_url}")
        driver.get(company_url)
        time.sleep(3)
        
        # Check if we hit a premium wall or redirect
        current_url = driver.current_url
        if "premium" in current_url or "unavailable" in current_url:
            logger.warning(f"[COMPANY_DOMAIN] Hit premium wall for {company_name}, trying alternative methods")
            return try_alternative_domain_search(driver, company_name)
        
        # Look for website link with multiple selectors
        domain_selectors = [
            '//a[contains(@href, "http") and not(contains(@href, "linkedin")) and contains(@class, "link-without-visited-state")]',
            '//a[contains(@href, "http") and not(contains(@href, "linkedin"))]',
            '//a[starts-with(@href, "http") and not(contains(@href, "linkedin.com"))]',
        ]
        
        for selector in domain_selectors:
            try:
                link = driver.find_element(By.XPATH, selector)
                potential_domain = link.get_attribute("href")
                if is_valid_domain(potential_domain):
                    domain = clean_domain(potential_domain)
                    logger.info(f"[COMPANY_DOMAIN] Found domain: {domain}")
                    break
            except NoSuchElementException:
                continue
        
        if not domain:
            # Strategy 2: Parse page content for website mentions
            domain = extract_domain_from_page_content(driver)
            
    except Exception as e:
        logger.error(f"[COMPANY_DOMAIN] Error for {company_name}: {e}")
        return try_alternative_domain_search(driver, company_name)
    
    finally:
        try:
            logger.info("[COMPANY_DOMAIN] Going back to search results...")
            driver.back()
            time.sleep(2)
        except Exception as e:
            logger.warning(f"[COMPANY_DOMAIN] Failed to go back: {e}")
    
    return domain

def try_alternative_domain_search(driver, company_name: str) -> str | None:
    """
    Alternative domain search strategies when direct approach fails
    """
    try:
        # Strategy 1: Google search for company website
        search_query = f"site:linkedin.com {company_name} website"
        google_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
        
        logger.info(f"[ALTERNATIVE] Trying Google search for {company_name}")
        driver.get(google_url)
        time.sleep(2)
        
        # Look for website links in search results
        try:
            results = driver.find_elements(By.CSS_SELECTOR, 'a[href*="http"]:not([href*="linkedin"]):not([href*="google"])')
            for result in results[:3]:  # Check first 3 results
                href = result.get_attribute("href")
                if is_valid_domain(href):
                    return clean_domain(href)
        except:
            pass
            
        # Strategy 2: Use company name patterns to guess domain
        return guess_domain_from_company_name(company_name)
        
    except Exception as e:
        logger.warning(f"[ALTERNATIVE] Failed alternative search for {company_name}: {e}")
        return None

def extract_domain_from_page_content(driver) -> str | None:
    """
    Extract domain by parsing page content for website mentions
    """
    try:
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Look for common website patterns in text
        text = soup.get_text()
        
        # Regex patterns for websites
        website_patterns = [
            r'(?:www\.)?([a-zA-Z0-9-]+\.(?:com|org|net|io|co|fr|de|uk))',
            r'(?:Website:|Site:|URL:)\s*(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,})',
        ]
        
        for pattern in website_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                domain = f"https://www.{match}" if not match.startswith('http') else match
                if is_valid_domain(domain):
                    logger.info(f"[CONTENT_PARSE] Found domain in content: {domain}")
                    return clean_domain(domain)
                    
    except Exception as e:
        logger.warning(f"[CONTENT_PARSE] Failed to parse page content: {e}")
    
    return None

def guess_domain_from_company_name(company_name: str) -> str | None:
    """
    Guess domain based on company name patterns
    """
    try:
        # Clean company name
        clean_name = re.sub(r'[^a-zA-Z0-9\s]', '', company_name.lower())
        clean_name = clean_name.replace(' ', '')
        
        # Common domain patterns
        possible_domains = [
            f"https://www.{clean_name}.com",
            f"https://www.{clean_name}.fr",  # For French companies
            f"https://www.{clean_name}.io",
            f"https://{clean_name}.com",
        ]
        
        # Return first guess (you could validate these with HTTP requests)
        for domain in possible_domains:
            logger.info(f"[GUESS] Guessing domain: {domain}")
            return domain
            
    except Exception as e:
        logger.warning(f"[GUESS] Failed to guess domain for {company_name}: {e}")
    
    return None

def is_valid_domain(url: str) -> bool:
    """
    Check if URL is a valid domain (not LinkedIn, social media, etc.)
    """
    if not url:
        return False
        
    invalid_patterns = [
        'linkedin.com', 'facebook.com', 'twitter.com', 'instagram.com',
        'youtube.com', 'google.com', 'premium', 'unavailable'
    ]
    
    url_lower = url.lower()
    return not any(pattern in url_lower for pattern in invalid_patterns)

def clean_domain(url: str) -> str:
    """
    Clean and normalize domain URL
    """
    if not url.startswith('http'):
        url = f"https://{url}"
    
    # Remove tracking parameters
    if '?' in url:
        url = url.split('?')[0]
    
    return url.rstrip('/')