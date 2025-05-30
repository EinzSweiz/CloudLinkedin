import json
import logging
import random
from datetime import datetime

logger = logging.getLogger(__name__)

class Credential:
    def __init__(self, json_path: str = 'credentials.json'):
        self.json_path = json_path
        self.credits_list = self.load_credentials()
        self.active_credentials = None
        logger.info(f"[CREDENTIALS INIT] Loaded {len(self.credits_list)} credentials")

    def load_credentials(self) -> list[dict]:
        try:
            with open(self.json_path, 'r', encoding='utf-8') as file:
                creds = json.load(file)
                if isinstance(creds, list) and all(isinstance(item, dict) for item in creds):
                    return creds
                else:
                    logger.error("Invalid JSON format: expected list of dicts.")
                    return []
        except Exception as e:
            logger.error(f"Error loading credentials from {self.json_path}: {e}")
            return []

    def save_credentials(self):
        try:
            with open(self.json_path, 'w', encoding='utf-8') as file:
                json.dump(self.credits_list, file, indent=2, ensure_ascii=False)
                logger.info("[CREDENTIALS SAVED] Updated credentials with status and last_used")
        except Exception as e:
            logger.error(f"Failed to save credentials to {self.json_path}: {e}")

    def get_credentials(self) -> dict:
        valid_cred = [c for c in self.credits_list if c.get("status", "valid") == "valid"]

        if not valid_cred:
            logger.warning("[CREDENTIAL] No valid credentials available")
            return {}

        self.active_credentials = random.choice(valid_cred)
        self.active_credentials["last_used"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"[CREDENTIAL SELECTED] {self.active_credentials['email']}")
        self.save_credentials()
        return self.active_credentials

    def mark_invalid(self, reason="checkpoint"):
        if self.active_credentials:
            self.active_credentials["status"] = "invalid"
            self.active_credentials["fail_reason"] = reason
            logger.warning(f"[CREDENTIAL MARKED INVALID] {self.active_credentials['email']} → {reason}")
            self.save_credentials()
