import sqlite3
import time
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

BASE_URL = "https://podrobno.uz"

# --- Setup Selenium ---
options = Options()
# options.add_argument("--headless")  # Uncomment to run headless
options.add_argument("--window-size=1920,1080")
driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 7)

# --- Setup SQLite ---
conn = sqlite3.connect("data/podrobno_articles.db")
conn.execute("PRAGMA encoding = 'UTF-8';")
cursor = conn.cursor()

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
    comment TEXT,
    FOREIGN KEY(article_id) REFERENCES articles(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS emotions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER,
    emotion TEXT,
    count INTEGER,
    FOREIGN KEY(article_id) REFERENCES articles(id)
)
""")
conn.commit()

try:
    driver.get(BASE_URL)
    wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "h2.sh-title a, a[href^='/cat/']")))

    article_links = driver.find_elements(By.CSS_SELECTOR, "h2.sh-title a, a[href^='/cat/']")
    article_urls = list({urljoin(BASE_URL, a.get_attribute("href")) for a in article_links if a.get_attribute("href")})

    print(f"Found {len(article_urls)} articles")

    for idx, url in enumerate(article_urls):
        print(f"\n[{idx+1}/{len(article_urls)}] Scraping: {url}")
        driver.get(url)
        time.sleep(1)

        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.post-title")))
            title = driver.find_element(By.CSS_SELECTOR, "h1.post-title").text.strip()
        except TimeoutException:
            print("   Title not found.")
            title = ""

        try:
            content_div = driver.find_element(By.CSS_SELECTOR, "div.detail-text")
            content = content_div.text.strip()
        except NoSuchElementException:
            print("   Content not found.")
            content = ""

        cursor.execute("INSERT OR IGNORE INTO articles (url, title, content) VALUES (?, ?, ?)", (url, title, content))
        conn.commit()

        cursor.execute("SELECT id FROM articles WHERE url = ?", (url,))
        article_id = cursor.fetchone()[0]

        # --- Comments ---
        cursor.execute("DELETE FROM comments WHERE article_id = ?", (article_id,))
        comment_blocks = driver.find_elements(By.CSS_SELECTOR, "div.comment-content p")
        print(f"   Found {len(comment_blocks)} comments")

        for comment_block in comment_blocks:
            comment = comment_block.text.strip()
            if comment:
                cursor.execute("INSERT INTO comments (article_id, comment) VALUES (?, ?)", (article_id, comment))

        # --- Emotions ---
        cursor.execute("DELETE FROM emotions WHERE article_id = ?", (article_id,))
        emotion_blocks = driver.find_elements(By.CSS_SELECTOR, "div.pc-emotions-item")
        print(f"   Found {len(emotion_blocks)} emotional reactions")

        for emotion_block in emotion_blocks:
            try:
                emotion_name = emotion_block.get_attribute("title").strip()
                emotion_count = emotion_block.find_element(By.CSS_SELECTOR, ".pc-emotions-item-counter").text.strip()
                count = int(emotion_count) if emotion_count.isdigit() else 0
                cursor.execute("INSERT INTO emotions (article_id, emotion, count) VALUES (?, ?, ?)", (article_id, emotion_name, count))
            except Exception as e:
                print(f"   Emotion error: {e}")

        conn.commit()

finally:
    driver.quit()
    conn.close()
def run():
    # Re-execute the same logic as if running the script directly
    import __main__
    if __main__.__file__.endswith("main.py"):
        # Only run this if called from main pipeline
        exec(open(__file__, encoding="utf-8").read())

if __name__ == "__main__":
    run()
