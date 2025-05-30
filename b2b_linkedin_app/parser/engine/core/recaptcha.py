import requests
import time

API_KEY = 'rucaptcha_key'

def solve_recaptcha(site_key, page_url):
    resp = requests.post("http://rucaptcha.com/in.php", data={
        "key": API_KEY,
        "method": "userrecaptcha",
        "googlekey": site_key,
        "pageurl": page_url,
        "json": 1
    }).json()
    
    captcha_id = resp["request"]

    # ждём капчу
    for _ in range(20):
        time.sleep(5)
        result = requests.get("http://rucaptcha.com/res.php", params={
            "key": API_KEY,
            "action": "get",
            "id": captcha_id,
            "json": 1
        }).json()

        if result["status"] == 1:
            return result["request"]
    
    raise Exception("Captcha solving failed")
