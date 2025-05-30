# import re
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# def extract_profile_url(urn: str) -> str | None:
#     """
#     Extracts a clean LinkedIn profile URL from a URN like 'urn:li:member:123456789'.
#     If the format is invalid (e.g., 'headless'), returns None.
#     """
#     if not urn or "headless" in urn.lower():
#         logger.warning("[PROFILE_URL] Invalid or headless URN: %s", urn)
#         return None

#     match = re.search(r"urn:li:member:(\d+)", urn)
#     if match:
#         profile_id = match.group(1)
#         profile_url = f"https://www.linkedin.com/in/{profile_id}"
#         logger.debug("[PROFILE_URL] Extracted: %s", profile_url)
#         return profile_url
#     else:
#         logger.warning("[PROFILE_URL] Failed to extract from URN: %s", urn)
#         return None


def extract_profile_url_from_card(soup: BeautifulSoup) -> str | None:
    """
    Надёжно извлекает ссылку на профиль из карточки результата поиска.
    """
    try:
        link = soup.find("a", href=True)
        if not link:
            return None

        href = link["href"]

        # Пропускаем нерелевантные ссылки
        if "/in/" not in href:
            return None

        # Безопасная сборка ссылки
        if href.startswith("http"):
            profile_url = href.split("?")[0].rstrip("/")
        else:
            profile_url = f"https://www.linkedin.com{href.split('?')[0].rstrip('/')}"

        logger.info(f"[PROFILE_URL] Extracted from card href: {profile_url}")
        return profile_url

    except Exception as e:
        logger.warning(f"[PROFILE_URL] Error parsing href from card: {e}")
        return None