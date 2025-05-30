import random
from typing import List
import logging

logger = logging.getLogger(__name__)

user_agents_list = [
    # Google Chrome (Windows)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",

    # Mozilla Firefox (Windows)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0",

    # Microsoft Edge (Windows)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.2365.92",

    # Safari (macOS)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",

    # Opera (Windows)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 OPR/111.0.0.0",

    # Brave (Windows)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Brave/122.0.0.0"
]


class UserAgent:
    def __init__(self, user_agent_list: List[str] = user_agents_list):
        self.active_user_agent = ''
        self.user_agents_list = user_agent_list
        logger.info(f"[USER-AGENT INIT] Loaded {len(self.user_agents_list)} user agents")

    def get_random_user_agent(self) -> str:
        available_user_agent = [ua for ua in self.user_agents_list if ua != self.active_user_agent]

        if available_user_agent:
            self.active_user_agent = random.choice(available_user_agent)
            logger.info(f"[USER-AGENT SELECTED] {self.active_user_agent[:80]}...")  # сократим вывод
        else:
            logger.warning("[USER-AGENT WARNING] Нет доступных user-agents отличных от активного")

        return self.active_user_agent
    
user_agents = UserAgent()