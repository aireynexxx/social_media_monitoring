# instagram_scraper.py

import sqlite3
import os
import time
import random
import re
from selenium import webdriver
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

USERNAME = input('Instagram Username: ')
PASSWORD = input('Instagram Password: ')

TARGET_PROFILES = ['repost.uz', 'uznews', 'upl_uz', 'podrobno.uz']
##,

DB_PATH = 'data/instagram_comments.db'
if os.path.exists(DB_PATH):
    print(f"🗑️ Deleting existing database: {DB_PATH}")
    os.remove(DB_PATH)

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA encoding = 'UTF-8';")
cursor = conn.cursor()

# Create table
cursor.execute("""
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_name TEXT,
    post_url TEXT,
    post_caption TEXT,
    username TEXT,
    comment TEXT
)
""")
conn.commit()

# Set up browser
options = uc.ChromeOptions()
options.add_argument('--no-sandbox')
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-gpu')
options.add_argument(f'--window-size={random.randint(1024, 1600)},{random.randint(768, 900)}')

driver = uc.Chrome(options=options)
wait = WebDriverWait(driver, 8)

def human_typing(element, text):
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.2))

def login():
    driver.get("https://www.instagram.com/accounts/login/")
    wait.until(EC.presence_of_element_located((By.NAME, "username")))
    human_typing(driver.find_element(By.NAME, "username"), USERNAME)
    human_typing(driver.find_element(By.NAME, "password"), PASSWORD)
    driver.find_element(By.NAME, "password").send_keys(Keys.RETURN)
    time.sleep(random.uniform(10, 12))

def is_emojis(text):
    # Remove all emoji-like unicode symbols and whitespace
    cleaned = re.sub(r'[^\w\s]', '', text)  # Remove symbols/punctuation
    cleaned = re.sub(r'\s+', '', cleaned)  # Remove whitespace
    return cleaned == ''

def less_than_twelve(text):
    return len(text) <= 12

def is_mention_only(text):
    return re.fullmatch(r"(?:@\w+\s*)+", text.strip()) is not None

def scrape_posts(username):
    driver.get(f"https://www.instagram.com/{username}/")
    time.sleep(random.uniform(3, 6))

    for y in range(1000, 6000, 1000):
        driver.execute_script(f"window.scrollTo(0, {y});")
        time.sleep(random.uniform(4, 8))

    posts = driver.find_elements(By.CSS_SELECTOR, "a[href*='/p/']")
    post_links = [post.get_attribute('href') for post in posts]
    print(f"Found {len(post_links)} posts for @{username}")

    for link in post_links:
        driver.get(link)
        time.sleep(random.uniform(2, 6))

        try:
            caption = driver.find_element(By.CSS_SELECTOR, 'h1._ap3a').text
        except:
            caption = ""

        # Load more comments
        while True:
            try:
                load_more = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "svg[aria-label='Load more comments']")))
                driver.execute_script("arguments[0].scrollIntoView(true);", load_more)
                time.sleep(random.uniform(3, 6))
                load_more.click()
            except (TimeoutException, ElementClickInterceptedException):
                break

        try:
            comment_elements = driver.find_elements(By.CSS_SELECTOR, "ul ul span._ap3a")
            print(f"    Found {len(comment_elements)} comments on post")

            for comment in comment_elements:
                try:
                    parent = comment.find_element(By.XPATH, "./ancestor::li[1]")
                    username_elem = parent.find_element(By.XPATH, ".//h3//a[starts-with(@href, '/')]")
                    commenter = username_elem.text
                except:
                    commenter = "(unknown)"
                if is_emojis(comment.text) or less_than_twelve(comment.text) or is_mention_only(comment.text):
                    continue

                comment_text = comment.text.strip()

                # Insert comment into DB (sentiment is filled in later by mood_analyser)
                cursor.execute("""
                    INSERT INTO comments (account_name, post_url, post_caption, username, comment)
                    VALUES (?, ?, ?, ?, ?)
                """, (username, link, caption, commenter, comment_text))

            conn.commit()

        except Exception as e:
            print(f"    Failed to extract comments: {e}")

def run():
    login()
    for account in TARGET_PROFILES:
        scrape_posts(account)
        time.sleep(random.randint(2, 6))
    driver.quit()
    conn.close()

if __name__ == "__main__":
    run()
