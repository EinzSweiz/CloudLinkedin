import time
import logging
import random
from typing import List, Dict, Optional
from urllib.parse import quote
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from django.conf import settings
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from parser.engine.linkedin.search_options.extract_name import extract_name
from parser.engine.linkedin.search_options.extract_company import extract_company_from_profile, extract_company_from_search_card
from parser.engine.linkedin.search_options.extract_position import extract_position
from parser.engine.linkedin.search_options.exract_profile_url import extract_profile_url_from_card
from parser.engine.linkedin.search_options.extract_email import extract_personal_email
from parser.engine.linkedin.search_options.extract_company_domain import extract_domain
from parser.engine.linkedin.search_options.location_codes import LOCATION_CODES
from parser.engine.linkedin.search_options.safety_scripts import scroll_script
from parser.engine.linkedin.login import get_logged_driver, save_captcha_session_for_transfer, check_captcha_success, recover_solved_session

# Import WebSocket broadcaster
try:
    from parser_controler.utils import WebSocketBroadcaster
except ImportError:
    class WebSocketBroadcaster:
        def __init__(self, *args): pass
        def send_update(self, *args, **kwargs): pass
        def send_log(self, *args, **kwargs): pass

logger = logging.getLogger(__name__)
LINKEDIN_SEARCH_URL = "https://www.linkedin.com/search/results/people/?keywords={keywords}&geoUrn={location_code}"
HUNTER_API_KEY = settings.HUNTER_API_KEY

def safe_page_load(driver, url, max_retries=3, timeout=30):
    for attempt in range(max_retries):
        try:
            logger.info(f"[LOAD] Attempt {attempt + 1}/{max_retries}: Loading {url}")
            
            # Set timeouts
            driver.set_page_load_timeout(timeout)
            
            # Load page
            driver.get(url)

            # Wait for page to be ready
            WebDriverWait(driver, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            # Additional wait for dynamic content
            WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.TAG_NAME, "body"))
                        )
            
            # Verify page loaded correctly
            current_url = driver.current_url
            if "error" in current_url.lower() or "unavailable" in current_url.lower():
                raise Exception(f"Page error detected: {current_url}")
                
            logger.info(f"[LOAD] ✅ Successfully loaded: {current_url}")
            return True
            
        except TimeoutException:
            logger.warning(f"[LOAD] Timeout on attempt {attempt + 1}: {url}")
            if attempt < max_retries - 1:
                # Refresh browser state
                try:
                    driver.execute_script("window.stop();")
                    time.sleep(2)
                except:
                    pass
                time.sleep(random.uniform(5, 10))
            continue
            
        except WebDriverException as e:
            logger.warning(f"[LOAD] WebDriver error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(random.uniform(5, 10))
            continue
            
        except Exception as e:
            logger.error(f"[LOAD] Unexpected error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(random.uniform(5, 10))
            continue
    
    logger.error(f"[LOAD] ❌ Failed to load {url} after {max_retries} attempts")
    return False

def wait_and_validate_search_page(driver, broadcaster=None, email=None):
    """Enhanced search page validation with VNC challenge resolution"""
    try:
        logger.info("[VALIDATE] Waiting for search results to load...")
        if broadcaster:
            broadcaster.send_log('INFO', 'VALIDATE', 'Waiting for search results to load...')
            
        # Wait for page to be ready
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # Check for LinkedIn security challenges FIRST
        current_url = driver.current_url
        logger.info(f"[VALIDATE] Current URL: {current_url}")
        
        if "uas/login" in current_url or "checkpoint" in current_url or "challenge" in current_url:
            logger.warning("[VALIDATE] LinkedIn security challenge detected during search")
            if broadcaster:
                broadcaster.send_log('WARNING', 'VALIDATE', 'LinkedIn security challenge detected - starting VNC resolution...')
            
            # Get email for VNC if not provided
            if not email:
                try:
                    from parser.engine.core.acount_credits_operator import Credential
                    credential = Credential()
                    creds = credential.get_credentials()
                    email = creds.get("email") if creds else "unknown@email.com"
                except:
                    email = "unknown@email.com"
            
            # Save session data for VNC transfer
            if save_captcha_session_for_transfer(driver, email):
                logger.info("Session data saved for VNC challenge resolution")
                if broadcaster:
                    broadcaster.send_log('INFO', 'VNC', 'Session data saved for VNC transfer')
            
            # Use VNC to solve the challenge
            try:
                from parser.engine.core.captcha_handler import FullyAutomatedCaptchaHandler
                from parser.engine.core.acount_credits_operator import Credential
                
                credential = Credential()
                creds = credential.get_credentials()
                
                if creds and email:
                    captcha_handler = FullyAutomatedCaptchaHandler(
                        auto_open_browser=True,
                        timeout=900  # 15 minutes
                    )
                    
                    cred_id = creds.get("cred_id", email)
                    
                    logger.info("🚀 Starting VNC challenge resolution for search page...")
                    if broadcaster:
                        broadcaster.send_log('INFO', 'VNC', 'Starting VNC challenge resolution...')
                    
                    captcha_result = captcha_handler.solve_captcha(email, cred_id)
                    
                    if captcha_result:
                        logger.info("✅ VNC challenge container started!")
                        if broadcaster:
                            broadcaster.send_log('INFO', 'VNC', 'VNC container started - waiting for challenge resolution...')
                        
                        # Monitor for success
                        success_data = check_captcha_success(email, timeout=900)
                        
                        if success_data:
                            logger.info("🎉 VNC challenge solved successfully!")
                            if broadcaster:
                                broadcaster.send_log('INFO', 'VNC', 'Challenge solved successfully!')
                            
                            # Recover session
                            if recover_solved_session(driver, email, success_data):
                                logger.info("✅ Session recovery completed!")
                                if broadcaster:
                                    broadcaster.send_log('INFO', 'VNC', 'Session recovery completed')
                                
                                # Try to navigate back to search or refresh current page
                                try:
                                    # If we're still on a challenge page, try to navigate back to search
                                    if "search/results" not in driver.current_url:
                                        # Try to reconstruct search URL or navigate to general search
                                        if "search/results" in current_url:
                                            driver.get(current_url)
                                        else:
                                            driver.get("https://www.linkedin.com/search/results/people/")
                                        time.sleep(5)
                                    
                                    # Recursive call to validate the search page again
                                    return wait_and_validate_search_page(driver, broadcaster, email)
                                    
                                except Exception as nav_error:
                                    logger.error(f"Error navigating back to search: {nav_error}")
                                    if broadcaster:
                                        broadcaster.send_log('ERROR', 'VNC', f'Navigation error: {str(nav_error)}')
                                    return False
                            else:
                                logger.error("❌ Session recovery failed")
                                if broadcaster:
                                    broadcaster.send_log('ERROR', 'VNC', 'Session recovery failed')
                                return False
                        else:
                            logger.error("❌ VNC challenge resolution failed or timed out")
                            if broadcaster:
                                broadcaster.send_log('ERROR', 'VNC', 'Challenge resolution failed or timed out')
                            return False
                    else:
                        logger.error("❌ Failed to start VNC challenge container")
                        if broadcaster:
                            broadcaster.send_log('ERROR', 'VNC', 'Failed to start VNC container')
                        return False
                else:
                    logger.error("❌ No credentials available for VNC challenge resolution")
                    if broadcaster:
                        broadcaster.send_log('ERROR', 'VNC', 'No credentials available')
                    return False
                    
            except Exception as vnc_error:
                logger.error(f"❌ VNC challenge handling failed: {vnc_error}")
                if broadcaster:
                    broadcaster.send_log('ERROR', 'VNC', f'VNC handling failed: {str(vnc_error)}')
                return False
        
        # Continue with normal validation if no challenge detected
        if "/search/results/" not in current_url:
            raise Exception(f"Not on search results page: {current_url}")
            
        # Wait for search results container
        search_container = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.search-results-container'))
        )
        
        # Wait for actual profile cards
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-chameleon-result-urn]'))
        )
        
        # Check for no results
        no_results_selectors = [
            '.search-no-results',
            '[data-test-id="search-no-results"]',
            'text*="No results found"'
        ]
        
        for selector in no_results_selectors:
            try:
                if driver.find_elements(By.CSS_SELECTOR, selector):
                    logger.warning("[VALIDATE] No search results found")
                    if broadcaster:
                        broadcaster.send_log('WARNING', 'VALIDATE', 'No search results found for this query')
                    return False
            except:
                continue
        
        # Count results
        cards = driver.find_elements(By.CSS_SELECTOR, 'div[data-chameleon-result-urn]')
        logger.info(f"[VALIDATE] ✅ Search page validated. Found {len(cards)} profile cards")
        
        if broadcaster:
            broadcaster.send_log('INFO', 'VALIDATE', f'Search page loaded successfully with {len(cards)} profiles')
        
        return True
        
    except Exception as e:
        logger.error(f"[VALIDATE] Search page validation failed: {e}")
        if broadcaster:
            broadcaster.send_log('ERROR', 'VALIDATE', f'Search page validation failed: {str(e)}')
        return False

def collect_cards_from_page(driver, broadcaster=None):
    try:
        # Wait for page stability
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # Scroll to load all content
        logger.info("[COLLECT] Scrolling to load all content...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        
        # Wait for content to load after scroll
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-chameleon-result-urn]'))
        )
        
        driver.execute_script("window.scrollTo(0, 0);")
        
        # Wait for scroll to complete
        WebDriverWait(driver, 3).until(
            lambda d: d.execute_script("return window.pageYOffset") == 0
        )
        
        # Find cards with retry
        cards = []
        for attempt in range(3):
            cards = driver.find_elements(By.CSS_SELECTOR, 'div[data-chameleon-result-urn]')
            if cards:
                break
            logger.warning(f"[COLLECT] No cards found on attempt {attempt + 1}, retrying...")
            time.sleep(2)
        
        if not cards:
            logger.warning(f"[COLLECT] No cards found on current page")
            if broadcaster:
                broadcaster.send_log('WARNING', 'COLLECT', 'No profile cards found on current page')
            return []
            
        logger.info(f"[COLLECT] Found {len(cards)} cards on this page")
        if broadcaster:
            broadcaster.send_log('INFO', 'COLLECT', f'Found {len(cards)} profile cards on page')
        
        card_data_list = []
        
        for i, card in enumerate(cards):
            try:
                logger.info(f"[COLLECT] Collecting data from card {i+1}/{len(cards)}")
                
                if broadcaster:
                    broadcaster.send_update(
                        action='collecting_card',
                        message=f'Extracting data from profile {i+1}/{len(cards)}',
                        data={'current_card': i+1, 'total_cards': len(cards)}
                    )
                
                # Extract HTML immediately to avoid stale element issues
                card_html = card.get_attribute('outerHTML')
                soup = BeautifulSoup(card_html, 'html.parser')
                
                # Extract basic info from search card ONLY
                name = extract_name(soup)
                position = extract_position(soup)
                profile_url = extract_profile_url_from_card(soup)
                company = extract_company_from_search_card(soup)
                
                if not profile_url:
                    logger.debug(f"[COLLECT] No profile URL for {name}, skipping")
                    continue

                # Store card data for later processing
                card_data = {
                    "name": name,
                    "position": position,
                    "company": company,
                    "profile_url": profile_url,
                }
                
                card_data_list.append(card_data)
                logger.info(f"[COLLECT] Collected #{len(card_data_list)}: {name} @ {company}")
                
                if broadcaster:
                    broadcaster.send_log('INFO', 'COLLECT', f'Collected: {name} @ {company}')
                
                # Small delay between cards
                time.sleep(random.uniform(0.3, 0.8))
                
            except Exception as card_error:
                logger.warning(f"[COLLECT] Error collecting card {i}: {card_error}")
                if broadcaster:
                    broadcaster.send_log('ERROR', 'COLLECT', f'Failed to extract card {i+1}: {str(card_error)}')
                continue

        return card_data_list
        
    except Exception as e:
        logger.error(f"[COLLECT] Fatal error: {e}")
        if broadcaster:
            broadcaster.send_log('ERROR', 'COLLECT', f'Fatal collection error: {str(e)}')
        return []

def enhance_profiles_with_domains_and_emails(driver, card_data_list, visited_domains, broadcaster=None, email=None):
    """
    PHASE 2: Enhance collected profiles with domains and emails
    Enhanced with WebSocket updates and VNC support
    """
    enhanced_profiles = []
    
    if broadcaster:
        broadcaster.send_update(
            action='enhancement_started',
            message=f'Starting email enhancement for {len(card_data_list)} profiles...',
            data={'total_to_enhance': len(card_data_list)}
        )
    
    for i, card_data in enumerate(card_data_list):
        try:
            logger.info(f"[ENHANCE] Processing profile {i+1}/{len(card_data_list)}: {card_data['name']}")
            
            if broadcaster:
                broadcaster.send_update(
                    action='enhancing_profile',
                    message=f'Getting email for {card_data["name"]} @ {card_data["company"]}',
                    data={'current': i+1, 'total': len(card_data_list), 'name': card_data['name']}
                )
            
            company = card_data["company"]
            
            # Get domain (with caching to avoid repeat lookups)
            domain = None
            if company in visited_domains:
                domain = visited_domains[company]
                logger.info(f"[ENHANCE] Using cached domain for {company}: {domain}")
                if broadcaster:
                    broadcaster.send_log('INFO', 'DOMAIN', f'Using cached domain for {company}: {domain}')
            elif company != "Unknown":
                logger.info(f"[ENHANCE] Getting domain for {company}...")
                if broadcaster:
                    broadcaster.send_log('INFO', 'DOMAIN', f'Looking up domain for {company}...')
                
                # Store current search URL to return to later
                search_url = driver.current_url
                
                try:
                    domain = extract_domain(driver, company)
                    visited_domains[company] = domain
                    
                    if broadcaster:
                        broadcaster.send_log('INFO', 'DOMAIN', f'Found domain for {company}: {domain}')
                    
                    # CRITICAL: Return to search page after domain extraction
                    logger.info(f"[ENHANCE] Returning to search page: {search_url}")
                    safe_page_load(driver, search_url, max_retries=2, timeout=20)
                    
                    # Wait for search page to load with VNC support
                    wait_and_validate_search_page(driver, broadcaster, email)
                    
                except Exception as domain_error:
                    logger.warning(f"[ENHANCE] Domain extraction failed for {company}: {domain_error}")
                    if broadcaster:
                        broadcaster.send_log('ERROR', 'DOMAIN', f'Domain lookup failed for {company}: {str(domain_error)}')
                    domain = None
                    
                    # Ensure we're back on search page even if domain extraction failed
                    try:
                        safe_page_load(driver, search_url, max_retries=2, timeout=20)
                    except:
                        pass

            # Extract email if we have a domain
            email_found = None
            if domain:
                try:
                    if broadcaster:
                        broadcaster.send_log('INFO', 'EMAIL', f'Searching email for {card_data["name"]} @ {domain}')
                    
                    name_parts = card_data["name"].split()
                    first_name = name_parts[0] if len(name_parts) > 0 else ""
                    last_name = name_parts[-1] if len(name_parts) > 1 else ""
                    
                    email_found = extract_personal_email(
                        first_name=first_name, 
                        last_name=last_name, 
                        domain=domain, 
                        api_key=HUNTER_API_KEY,
                        company=company
                    )
                    
                    if email_found:
                        if broadcaster:
                            broadcaster.send_log('INFO', 'EMAIL', f'✅ Found email: {email_found}')
                    else:
                        if broadcaster:
                            broadcaster.send_log('WARNING', 'EMAIL', f'❌ No email found for {card_data["name"]}')
                            
                except Exception as email_error:
                    logger.warning(f"[ENHANCE] Email extraction failed: {email_error}")
                    if broadcaster:
                        broadcaster.send_log('ERROR', 'EMAIL', f'Email extraction failed: {str(email_error)}')

            # Create enhanced profile
            enhanced_profile = {
                "name": card_data["name"],
                "position": card_data["position"],
                "company": company,
                "email": email_found,
                "profile_url": card_data["profile_url"],
                "domain": domain
            }
            
            enhanced_profiles.append(enhanced_profile)
            logger.info(f"[ENHANCE] Enhanced #{len(enhanced_profiles)}: {card_data['name']} @ {company} (email: {'✓' if email_found else '✗'})")
            
            if broadcaster:
                broadcaster.send_update(
                    action='profile_enhanced',
                    message=f'Enhanced profile {i+1}/{len(card_data_list)}: {card_data["name"]}',
                    data={
                        'enhanced_count': len(enhanced_profiles),
                        'total': len(card_data_list),
                        'has_email': bool(email_found),
                        'progress_percentage': round((i+1) / len(card_data_list) * 100, 1)
                    }
                )
            
            # Delay between enhancements to avoid rate limiting
            time.sleep(random.uniform(1.0, 2.0))
            
        except Exception as e:
            logger.error(f"[ENHANCE] Error enhancing profile {card_data['name']}: {e}")
            if broadcaster:
                broadcaster.send_log('ERROR', 'ENHANCE', f'Enhancement failed for {card_data["name"]}: {str(e)}')
            
            # Still add basic profile even if enhancement fails
            basic_profile = {
                "name": card_data["name"],
                "position": card_data["position"],
                "company": card_data["company"],
                "email": None,
                "profile_url": card_data["profile_url"],
                "domain": None
            }
            enhanced_profiles.append(basic_profile)

    return enhanced_profiles

def navigate_to_next_page(driver, broadcaster=None, email=None):
    """
    Enhanced next page navigation with VNC support
    """
    try:
        # Ensure we're still on search results
        current_url = driver.current_url
        if "/search/results/" not in current_url:
            logger.error(f"[NAVIGATION] Not on search page: {current_url}")
            if broadcaster:
                broadcaster.send_log('ERROR', 'NAVIGATION', f'Not on search page: {current_url}')
            return False
            
        if broadcaster:
            broadcaster.send_log('INFO', 'NAVIGATION', 'Looking for next page button...')
            
        # Scroll to make sure all content is loaded and next button is visible
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".artdeco-pagination, button[aria-label='Next']"))
                )
        
        # Try multiple selectors for next button
        next_selectors = [
            '//button[@aria-label="Next"]',
            '//button[contains(@class, "artdeco-pagination__button--next")]',
            '//a[@aria-label="Next"]'
        ]
        
        for selector in next_selectors:
            try:
                next_button = driver.find_element(By.XPATH, selector)
                if next_button.is_enabled() and next_button.is_displayed():
                    logger.info(f"[NAVIGATION] Clicking next button")
                    if broadcaster:
                        broadcaster.send_log('INFO', 'NAVIGATION', 'Found next button, navigating to next page...')
                    
                    driver.execute_script("arguments[0].click();", next_button)
                    WebDriverWait(driver, 10).until(
                                            lambda d: d.current_url != current_url
                                        )
                    
                    # Verify we moved to next page WITH VNC support
                    if wait_and_validate_search_page(driver, broadcaster, email):
                        logger.info(f"[NAVIGATION] Successfully moved to next page")
                        if broadcaster:
                            broadcaster.send_log('INFO', 'NAVIGATION', 'Successfully navigated to next page')
                        return True
                    else:
                        logger.warning("[NAVIGATION] Failed to validate next page")
                        return False
                    
            except Exception as e:
                logger.debug(f"[NAVIGATION] Selector {selector} failed: {e}")
                continue
                
        logger.info("[NAVIGATION] No next button found - probably last page")
        if broadcaster:
            broadcaster.send_log('INFO', 'NAVIGATION', 'No next button found - reached last page')
        return False
        
    except Exception as e:
        logger.warning(f"[NAVIGATION] Navigation error: {e}")
        if broadcaster:
            broadcaster.send_log('ERROR', 'NAVIGATION', f'Navigation error: {str(e)}')
        return False

def search_linkedin_profiles(
    keywords: List[str],
    location: str = "France",
    limit: int = 50,
    start_page: int = 1,
    end_page: int = 10,
    parser_request_id: Optional[int] = None
) -> List[Dict]:
    """
    Enhanced LinkedIn search with VNC challenge resolution
    """
    logger.info(f"[SEARCH] Starting LinkedIn search with VNC support")
    logger.info(f"[SEARCH] Keywords: {keywords}, Location: {location}, Pages: {start_page}-{end_page}")
    
    # Initialize WebSocket broadcaster
    broadcaster = WebSocketBroadcaster(parser_request_id) if parser_request_id else None
    
    if broadcaster:
        broadcaster.send_log('INFO', 'SEARCH', f'Starting LinkedIn search for {keywords} in {location}')
        broadcaster.send_update(
            action='search_started',
            message=f'Initializing LinkedIn search for {keywords}',
            data={'keywords': keywords, 'location': location, 'pages': f'{start_page}-{end_page}'}
        )
    
    driver = None
    current_email = None  # Track the current logged-in email
    
    try:
        driver = get_logged_driver()
        logger.info(f"[SEARCH] ✅ Successfully logged in")
        
        # Get the current user's email for VNC purposes
        try:
            from parser.engine.core.acount_credits_operator import Credential
            credential = Credential()
            creds = credential.get_credentials()
            current_email = creds.get("email") if creds else None
            logger.info(f"[SEARCH] Current logged-in email: {current_email}")
        except Exception as e:
            logger.warning(f"[SEARCH] Could not get current email: {e}")
            current_email = "unknown@email.com"  # Fallback
        
        if broadcaster:
            broadcaster.send_log('INFO', 'LOGIN', 'Successfully logged into LinkedIn')
            
        # Add a stabilization period after login
        logger.info("[SEARCH] Stabilizing session after login...")
        time.sleep(random.uniform(3, 6))
        
    except Exception as e:
        logger.error(f"[SEARCH] ❌ Failed to login: {e}")
        if broadcaster:
            broadcaster.send_log('ERROR', 'LOGIN', f'LinkedIn login failed: {str(e)}')
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
        if broadcaster:
            broadcaster.send_log('INFO', 'SEARCH', f'Navigating to LinkedIn search page')
        
        # Use safe page loading
        if not safe_page_load(driver, final_url, max_retries=3, timeout=30):
            logger.error("[SEARCH] Failed to load search page")
            if broadcaster:
                broadcaster.send_log('ERROR', 'SEARCH', 'Failed to load LinkedIn search page')
            return []
        
        # Validate search page WITH VNC support
        if not wait_and_validate_search_page(driver, broadcaster, current_email):
            logger.error("[SEARCH] Search page validation failed")
            return []

        # Skip to start page if needed
        current_page = 1
        while current_page < start_page:
            if broadcaster:
                broadcaster.send_update(
                    action='skipping_to_start',
                    message=f'Skipping to start page {start_page} (currently on page {current_page})',
                    data={'current_page': current_page, 'target_page': start_page}
                )
            if not navigate_to_next_page(driver, broadcaster, current_email):
                logger.warning(f"[SEARCH] Failed to reach start page {start_page}")
                return []
            current_page += 1

        # PHASE 1: Collect all card data from all pages
        if broadcaster:
            broadcaster.send_update(
                action='phase_1_started',
                message='Phase 1: Collecting profile cards from LinkedIn pages...',
                data={'phase': 'collection', 'pages_to_process': end_page - start_page + 1}
            )

        all_card_data = []
        visited_domains = {}

        while len(all_card_data) < limit and current_page <= end_page:
            logger.info(f"[SEARCH] Collecting data from page {current_page}: {driver.current_url}")
            
            if broadcaster:
                broadcaster.send_update(
                    action='page_processing',
                    message=f'Processing page {current_page} of {end_page}',
                    data={'current_page': current_page, 'total_pages': end_page, 'profiles_collected': len(all_card_data)}
                )
            
            # Collect all cards from current page
            page_card_data = collect_cards_from_page(driver, broadcaster)
            
            if not page_card_data:
                logger.warning(f"[SEARCH] No cards collected from page {current_page}, stopping")
                if broadcaster:
                    broadcaster.send_log('WARNING', 'SEARCH', f'No profiles found on page {current_page} - stopping')
                break
                
            all_card_data.extend(page_card_data)
            logger.info(f"[SEARCH] Collected {len(page_card_data)} cards from page {current_page}. Total: {len(all_card_data)}")
            
            if broadcaster:
                broadcaster.send_update(
                    action='cards_collected',
                    message=f'Found {len(page_card_data)} profiles on page {current_page}',
                    data={
                        'page_cards': len(page_card_data),
                        'total_collected': len(all_card_data),
                        'current_page': current_page
                    }
                )

            if len(all_card_data) >= limit:
                logger.info(f"[SEARCH] Reached limit of {limit} profiles")
                if broadcaster:
                    broadcaster.send_log('INFO', 'SEARCH', f'Reached profile limit of {limit}')
                break

            # Navigate to next page
            if current_page < end_page:
                if navigate_to_next_page(driver, broadcaster, current_email):
                    current_page += 1
                else:
                    logger.info(f"[SEARCH] No more pages available")
                    break
            else:
                logger.info(f"[SEARCH] Reached end page {end_page}")
                break

        # Trim to limit
        if len(all_card_data) > limit:
            all_card_data = all_card_data[:limit]

        logger.info(f"[SEARCH] ✅ PHASE 1 COMPLETE: Collected {len(all_card_data)} profiles from {current_page} pages")
        
        if broadcaster:
            broadcaster.send_update(
                action='phase_1_completed',
                message=f'Phase 1 complete: Collected {len(all_card_data)} profiles from {current_page} pages',
                data={'profiles_collected': len(all_card_data), 'pages_processed': current_page}
            )

        # PHASE 2: Enhance with domains and emails
        logger.info(f"[SEARCH] PHASE 2: Enhancing profiles with domains and emails...")
        
        if broadcaster:
            broadcaster.send_update(
                action='phase_2_started',
                message='Phase 2: Enhancing profiles with emails and domains...',
                data={'phase': 'enhancement', 'profiles_to_enhance': len(all_card_data)}
            )
        
        enhanced_profiles = enhance_profiles_with_domains_and_emails(driver, all_card_data, visited_domains, broadcaster, current_email)

        logger.info(f"[RESULT] COMPLETED: Found {len(enhanced_profiles)} profiles total.")
        
        if broadcaster:
            emails_found = sum(1 for profile in enhanced_profiles if profile.get('email'))
            broadcaster.send_update(
                action='search_completed',
                message=f'Search completed! Found {len(enhanced_profiles)} profiles, {emails_found} with emails',
                data={
                    'total_profiles': len(enhanced_profiles),
                    'emails_found': emails_found,
                    'success_rate': round((emails_found / len(enhanced_profiles) * 100), 1) if enhanced_profiles else 0
                }
            )
        
        return enhanced_profiles

    except Exception as e:
        logger.error(f"[SEARCH] Fatal error during search: {e}")
        if broadcaster:
            broadcaster.send_log('ERROR', 'SEARCH', f'Fatal search error: {str(e)}')
        return []
    finally:
        try:
            if driver:
                driver.quit()
                logger.info(f"[CLEANUP] Browser closed successfully")
                if broadcaster:
                    broadcaster.send_log('INFO', 'CLEANUP', 'Browser session closed')
        except Exception as e:
            logger.warning(f"[CLEANUP] Error closing browser: {e}")