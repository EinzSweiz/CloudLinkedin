from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

# def extract_position(card: WebElement) -> str:
#     try:
#         elem = card.find_element(By.XPATH, './/div[contains(@class, "t-14") and contains(@class, "t-black")]')
#         position = elem.text.strip()
#         logger.debug("[POSITION] Found via Selenium: %s", position)
#         return position
#     except Exception as e:
#         logger.debug("[POSITION] Not found via Selenium — returning 'Unknown'. Error: %s", e)
#         return "Unknown"
def extract_position(soup: BeautifulSoup) -> str:
    try:
        # This looks for divs that have "t-14" and "t-black" in the class list
        divs = soup.find_all('div', class_='t-14')
        for div in divs:
            classes = div.get("class", [])
            if "t-black" in classes:
                position = div.get_text(strip=True)
                logger.debug("[POSITION] Found via soup: %s", position)
                return position
    except Exception as e:
        logger.debug("[POSITION] Error during parsing: %s", e)

    return "Unknown"

