import random
import logging
from typing import List
from parser.engine.core.proxy_validator import validate_proxies

logger = logging.getLogger(__name__)

proxies_list = [
    "198.23.239.134:6540:ctdolui:erj1et0a04ov",
    "207.244.217.165:6712:ctdolui:erj1et0a04ov",
    "107.172.163.27:6543:ctdolui:erj1et0a04ov",
    "161.123.152.115:6360:ctdolui:erj1et0a04ov",
    "23.94.138.75:6349:ctdolui:erj1et0a04ov",
    "216.10.27.159:6837:ctdolui:erj1et0a04ov",
    "136.0.207.84:6661:ctdolui:erj1et0a04ov",
    "64.64.118.149:6732:ctdolui:erj1et0a04ov",
    "142.147.128.93:6593:ctdolui:erj1et0a04ov",
    "154.36.110.199:6853:ctdolui:erj1et0a04ov"
]

class Proxy:
    def __init__(self, proxy_list: List[str] = proxies_list, validate: bool = False):
        self.active_proxy = ''
        self.proxies_list = validate_proxies(proxy_list) if validate else proxy_list
        logger.info(f"[PROXY INIT] Total loaded: {len(self.proxies_list)} proxies")

    def get_random_proxy(self):
        available_proxies = [p for p in self.proxies_list if p != self.active_proxy]

        if available_proxies:
            self.active_proxy = random.choice(available_proxies)
            logger.info(f"[PROXY SELECTED] {self.active_proxy}")
        else:
            logger.warning("[PROXY WARNING] No new proxies available")

        ip, port, user, pwd = self.active_proxy.split(":")
        return ip, port, user, pwd

proxies = Proxy()
