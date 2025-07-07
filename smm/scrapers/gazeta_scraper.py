#GazetaUz Scraper
import sqlite3
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from urllib.parse import urljoin
import time

BASE_URL = "https://www.gazeta.uz"

options = Options()
# options.add_argument("--headless")  # Uncomment to run headless
options.add_argument("--window-size=1920,1080")

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 5)

conn = sqlite3.connect("data/gazeta_articles.db")
conn.execute("PRAGMA encoding = 'UTF-8';")
cursor = conn.cursor()

# Create tables if they don't exist
cursor.execute("""
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE,
    title TEXT,
    content TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER,
    user TEXT,
    comment TEXT,
    upvotes INTEGER,
    downvotes INTEGER,
    FOREIGN KEY(article_id) REFERENCES articles(id)
)
""")

conn.commit()

max_pages = 5  # Set max pages you want to scrape
current_page = 1

try:
    driver.get(f"{BASE_URL}/ru/list/news/")
    wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a[href^='/ru/'][href*='/2025/']")))

    while current_page <= max_pages:
        print(f"\nScraping listing page {current_page}...")

        # Find article links on listing page
        article_elements = driver.find_elements(By.CSS_SELECTOR, "a[href^='/ru/'][href*='/2025/']")
        article_urls = []
        for elem in article_elements:
            href = elem.get_attribute('href')
            full_url = urljoin(BASE_URL, href)
            if full_url not in article_urls:
                article_urls.append(full_url)

        print(f"Found {len(article_urls)} articles on page {current_page}")

        for idx, url in enumerate(article_urls):
            print(f"  [{idx+1}/{len(article_urls)}] Scraping article: {url}")
            driver.get(url)

            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1#article_title")))
                title = driver.find_element(By.CSS_SELECTOR, "h1#article_title").text
            except TimeoutException:
                print("    ERROR: Article title not found.")
                title = ""

            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "p[dir='ltr']")))
                paragraphs = driver.find_elements(By.CSS_SELECTOR, "p[dir='ltr']")
                content = "\n".join(p.text for p in paragraphs if p.text.strip())
            except TimeoutException:
                content = ""

            # Save article info (ignore duplicates)
            cursor.execute("""
                INSERT OR IGNORE INTO articles (url, title, content) VALUES (?, ?, ?)
            """, (url, title, content))
            conn.commit()

            # Get article id to link comments
            cursor.execute("SELECT id FROM articles WHERE url = ?", (url,))
            article_id = cursor.fetchone()[0]

            # Remove old comments before adding new ones
            cursor.execute("DELETE FROM comments WHERE article_id = ?", (article_id,))
            conn.commit()

            # Extract comments
            comments = driver.find_elements(By.CSS_SELECTOR, "div.comment-body")
            print(f"    Found {len(comments)} comments")

            for comment in comments:
                try:
                    user = comment.find_element(By.CSS_SELECTOR, "h4.comment-user").text
                    comment_text = comment.find_element(By.CSS_SELECTOR, "p").text
                    upvotes = comment.find_element(By.CSS_SELECTOR, "span.up-votes-count").text
                    downvotes = comment.find_element(By.CSS_SELECTOR, "span.down-votes-count").text
                except Exception as e:
                    print(f"    Skipping a comment due to error: {e}")
                    continue

                cursor.execute("""
                    INSERT INTO comments (article_id, user, comment, upvotes, downvotes)
                    VALUES (?, ?, ?, ?, ?)
                """, (article_id, user, comment_text, int(upvotes), int(downvotes)))

            conn.commit()

            # Go back to listing page after each article
            driver.back()
            wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a[href^='/ru/'][href*='/2025/']")))

        # Try to click the Next button on listing page
        try:
            next_button = driver.find_element(By.CSS_SELECTOR, "a.next")
            print("Clicking Next page...")
            next_button.click()
            current_page += 1
            wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a[href^='/ru/'][href*='/2025/']")))
        except NoSuchElementException:
            print("No more pages. Stopping.")
            break

    print("\nScraping finished.")

finally:
    driver.quit()
    conn.close()
