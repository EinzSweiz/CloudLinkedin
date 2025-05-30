import re
import logging

logger = logging.getLogger(__name__)

def extract_name(soup) -> str:
    name_elem = soup.find('span', {'dir': 'ltr'})
    if not name_elem:
        logger.debug("[NAME] No name element found — returning default 'LinkedIn Member'")
        return "LinkedIn Member"

    raw_name = name_elem.get_text(" ", strip=True)
    logger.debug("[NAME] Raw name extracted: %s", raw_name)

    # Удалим все "View .* profile"
    cleaned = re.sub(r'View\s+.*?\s+profile', '', raw_name, flags=re.IGNORECASE)
    if raw_name != cleaned:
        logger.debug("[NAME] Removed profile text: %s → %s", raw_name, cleaned)
    raw_name = cleaned

    # Удалим дубли (если текст повторяется)
    words = raw_name.split()
    mid = len(words) // 2
    if words[:mid] == words[mid:]:
        logger.debug("[NAME] Detected duplicated name segments: %s", raw_name)
        raw_name = " ".join(words[:mid])

    logger.debug("[NAME] Final cleaned name: %s", raw_name.strip())
    return raw_name.strip()
