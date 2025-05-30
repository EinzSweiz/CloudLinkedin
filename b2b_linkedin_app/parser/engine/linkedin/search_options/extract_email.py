import requests
import logging

logger = logging.getLogger(__name__)

def extract_personal_email(first_name: str, last_name: str, domain: str, api_key: str) -> str | None:
    url = (
        f"https://api.hunter.io/v2/email-finder"
        f"?domain={domain}&first_name={first_name}&last_name={last_name}&api_key={api_key}"
    )
    try:
        response = requests.get(url)
        if response.status_code != 200:
            logger.warning(f"[EMAIL-FINDER] Hunter API returned {response.status_code} for {first_name} {last_name} @ {domain}")
            return None

        data = response.json()
        email = data.get("data", {}).get("email")
        confidence = data.get("data", {}).get("score", 0)

        if email:
            logger.info(f"[EMAIL-FINDER] Found email {email} (score: {confidence}) for {first_name} {last_name}")
            return email
        else:
            logger.info(f"[EMAIL-FINDER] No email found for {first_name} {last_name} @ {domain}")
            return None

    except Exception as e:
        logger.error(f"[EMAIL-FINDER] Exception: {e}")
        return None