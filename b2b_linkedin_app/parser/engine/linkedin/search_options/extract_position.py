from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import logging
import re

logger = logging.getLogger(__name__)

def extract_position(soup: BeautifulSoup) -> str:
    try:
        # This looks for divs that have "t-14" and "t-black" in the class list
        divs = soup.find_all('div', class_='t-14')
        for div in divs:
            classes = div.get("class", [])
            if "t-black" in classes:
                position = div.get_text(strip=True)
                
                # Clean and shorten the position
                cleaned_position = clean_position_text(position)
                
                if cleaned_position and cleaned_position != "Unknown":
                    logger.debug("[POSITION] Found via soup: %s", cleaned_position)
                    return cleaned_position
                    
    except Exception as e:
        logger.debug("[POSITION] Error during parsing: %s", e)

    return "Unknown"

def clean_position_text(position: str) -> str:
    """
    Clean and shorten position text to keep it concise
    """
    if not position:
        return "Unknown"
    
    # Remove extra whitespace
    position = position.strip()
    
    # Skip if too short
    if len(position) < 3:
        return "Unknown"
    
    # Truncate if too long (keep first part only)
    if len(position) > 80:
        # Try to cut at a logical break point
        logical_breaks = [" at ", " | ", " - ", " · ", " in ", " for "]
        for break_point in logical_breaks:
            if break_point in position:
                position = position.split(break_point)[0].strip()
                break
        
        # If still too long, cut at 80 characters
        if len(position) > 80:
            position = position[:80].strip()
    
    # Clean up common patterns that make positions too verbose
    position = clean_verbose_patterns(position)
    
    # Remove redundant phrases
    position = remove_redundant_phrases(position)
    
    return position.strip()

def clean_verbose_patterns(position: str) -> str:
    """
    Remove verbose patterns that make positions too long
    """
    # Remove location info in parentheses
    position = re.sub(r'\s*\([^)]*\)', '', position)
    
    # Remove "Full-time", "Part-time", etc.
    position = re.sub(r'\b(Full-time|Part-time|Contract|Freelance|Remote)\b', '', position, flags=re.IGNORECASE)
    
    # Clean up multiple separators
    position = re.sub(r'\s*[|·-]\s*$', '', position)  # Remove trailing separators
    position = re.sub(r'^\s*[|·-]\s*', '', position)  # Remove leading separators
    
    # Remove "Currently" prefix
    position = re.sub(r'^\s*Currently\s+', '', position, flags=re.IGNORECASE)
    
    return position

def remove_redundant_phrases(position: str) -> str:
    """
    Remove redundant or unnecessary phrases
    """
    redundant_phrases = [
        "LinkedIn Member",
        "View profile",
        "Connect",
        "Message",
        "See contact info",
        "Follow",
        "More",
    ]
    
    for phrase in redundant_phrases:
        position = position.replace(phrase, "")
    
    # Clean up extra spaces
    position = re.sub(r'\s+', ' ', position)
    
    return position

# Alternative: Even more aggressive shortening
def extract_position_short(soup: BeautifulSoup) -> str:
    """
    Alternative version that extracts only the core job title
    """
    try:
        divs = soup.find_all('div', class_='t-14')
        for div in divs:
            classes = div.get("class", [])
            if "t-black" in classes:
                position = div.get_text(strip=True)
                
                # Get only the core title (before first separator)
                core_title = extract_core_title(position)
                
                if core_title and len(core_title) > 2:
                    logger.debug("[POSITION] Core title extracted: %s", core_title)
                    return core_title
                    
    except Exception as e:
        logger.debug("[POSITION] Error during parsing: %s", e)

    return "Unknown"

def extract_core_title(position: str) -> str:
    """
    Extract just the core job title (before company info)
    """
    if not position:
        return "Unknown"
    
    # Split on common separators and take the first meaningful part
    separators = [" at ", " | ", " - ", " · ", " in ", " for ", " @"]
    
    for sep in separators:
        if sep in position:
            core = position.split(sep)[0].strip()
            if len(core) > 2:
                return core
    
    # If no separators, return first 50 characters
    if len(position) > 50:
        return position[:50].strip()
    
    return position.strip()