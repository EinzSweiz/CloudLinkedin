import sys
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)
from parser.engine.linkedin.search_profiles import search_linkedin_profiles

if __name__ == "__main__":
    logging.info("[RUNNER] Script started.")
    profiles = search_linkedin_profiles(
        keywords=["Python", "Developer", "Backend"],
        location="Germany",
        limit=10,
        start_page=5,
        end_page=10,
    )
    for profile in profiles:
        logging.info(f"[PROFILE] {profile}")
