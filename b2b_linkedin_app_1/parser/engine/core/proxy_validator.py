import requests
from typing import List
import logging

logger = logging.getLogger(__name__)

def validate_proxies(proxies: List[str], timeout: int = 5) -> List[str]:
    test_url = "https://httpbin.org/ip"
    working_proxies = []

    logger.info(f"[PROXY VALIDATION] Start validating {len(proxies)} proxies...")

    for idx, proxy in enumerate(proxies, 1):
        try:
            ip, port, user, pwd = proxy.split(":")
            proxy_dict = {
                "http": f"http://{user}:{pwd}@{ip}:{port}",
                "https": f"http://{user}:{pwd}@{ip}:{port}",
            }
            logger.debug(f"[VALIDATION] Testing proxy {idx}/{len(proxies)}: {ip}:{port}")
            response = requests.get(test_url, proxies=proxy_dict, timeout=timeout, verify=False)
            if response.status_code == 200:
                ip_returned = response.json().get("origin", "Unknown")
                logger.info(f"[VALID PROXY] {proxy} → IP returned: {ip_returned}")
                working_proxies.append(proxy)
            else:
                logger.warning(f"[INVALID STATUS] {proxy} → status: {response.status_code}")
        except Exception as e:
            logger.warning(f"[INVALID PROXY] {proxy} → {e}")
            continue

    logger.info(f"[PROXY VALIDATION] {len(working_proxies)} of {len(proxies)} proxies are valid.")
    return working_proxies
