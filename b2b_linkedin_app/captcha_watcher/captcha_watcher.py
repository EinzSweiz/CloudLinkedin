import os
import time
from parser.engine.core.cookies import save_cookies
from parser.engine.core.acount_credits_operator import Credential
from selenium.webdriver.chrome.options import Options
import undetected_chromedriver as uc

WATCH_FILE = "./shared_volume/captcha_queue.txt"
PROCESSED_FILE = "./shared_volume/captcha_resolved.txt"

def resolve(email):
    creds = Credential().get_specific(email)
    if not creds:
        print(f"No credentials for {email}")
        return

    EMAIL = creds["email"]
    PASSWORD = creds["password"]
    cookie_path = f"./cookies/linkedin_cookies_{EMAIL}.pkl"

    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = uc.Chrome(options=options, version_main=136)
    driver.get("https://www.linkedin.com/login")
    input(f"Please solve CAPTCHA and login for {EMAIL}. Press ENTER when done...")
    save_cookies(driver, cookie_path)
    driver.quit()

    with open(PROCESSED_FILE, "a") as f:
        f.write(f"{EMAIL}\n")

def watch_loop():
    print("Watching for CAPTCHA requests...")
    processed = set()

    while True:
        if os.path.exists(WATCH_FILE):
            with open(WATCH_FILE, "r") as f:
                lines = [line.strip() for line in f.readlines()]
                for email in lines:
                    if email and email not in processed:
                        resolve(email)
                        processed.add(email)
        time.sleep(10)

if __name__ == "__main__":
    watch_loop()
