# post_summarizer.py

import sqlite3
import pandas as pd
import random
import os
import ollama
from tqdm import tqdm

# === CONFIG ===
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTAGRAM_DB = os.path.join(BASE_DIR, "data", "instagram_comments.db")
OUTPUT_DB = os.path.join(BASE_DIR, "data", "instagram_summaries.db")
PROMPT_DIR = os.path.join(BASE_DIR, "prompts")
MAX_COMMENTS = 50
OLLAMA_MODEL = "llama3.1:8b"

# === ENSURE PROMPT DIR EXISTS ===
os.makedirs(PROMPT_DIR, exist_ok=True)

# === OLLAMA CHAT FUNCTION ===
def call_llm(prompt: str, model: str = OLLAMA_MODEL) -> str:
    try:
        response = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": "Ты — аналитик социальных сетей. Делай краткие обзоры на русском языке."},
                {"role": "user", "content": prompt}
            ]
        )
        return response['message']['content'].strip()
    except Exception as e:
        print("⚠️ Ошибка при вызове Ollama:", e)
        return "[ERROR: Не удалось получить ответ от модели]"

def summarize():
    # === VERIFY DB EXISTS ===
    if not os.path.exists(INSTAGRAM_DB):
        raise FileNotFoundError(f"Файл базы данных не найден: {INSTAGRAM_DB}")

    # === LOAD DATA ===
    print('Connecting to Instagram Database...')
    conn = sqlite3.connect(INSTAGRAM_DB)
    df = pd.read_sql("SELECT * FROM comments", conn)
    conn.close()

    # === GROUP BY POST ===
    post_groups = df.groupby("post_url")

    # === PREP OUTPUT DB ===
    print('Connecting to Summary Database...')
    # === CLEAN OUTPUT DB IF EXISTS ===
    if os.path.exists(OUTPUT_DB):
        print(f"🗑️ Deleting existing database: {OUTPUT_DB}")
        os.remove(OUTPUT_DB)
    out_conn = sqlite3.connect(OUTPUT_DB)
    out_cursor = out_conn.cursor()
    out_cursor.execute("""
    CREATE TABLE IF NOT EXISTS post_summaries (
        post_url TEXT PRIMARY KEY,
        caption TEXT,
        comment_count INTEGER,
        summary TEXT
    );
    """)
    out_conn.commit()

    # === LOOP THROUGH POSTS ===
    print('Starting Summary Loop...')
    for post_url, group in tqdm(post_groups, desc="Summarizing posts"):
        caption = group["post_caption"].iloc[0]
        comments = group["comment"].dropna().astype(str).tolist()
        comment_count = len(comments)

        # Limit comments to prevent overloading context window
        if len(comments) > MAX_COMMENTS:
            random.seed(42)
            comments = random.sample(comments, MAX_COMMENTS)

        # === BUILD PROMPT ===
        prompt = f"""Пост:
    {caption.strip()}
    
    Комментарии ({comment_count}):
    """
        for i, comment in enumerate(comments, 1):
            prompt += f"{i}. {comment.strip()}\n"

        prompt += """
    
    Задача:
    На основе содержания поста и комментариев составь краткий аналитический обзор на русском языке. Укажи:
    - Основную тему поста
    - Общее настроение и реакцию людей
    - Конкретные примеры или тенденции, если они есть
    
    Будьте прямолинейны и прямолинейны в своих выводах и заключениях.
    """

        # === SAVE PROMPT FOR DEBUGGING ===
        prompt_path = os.path.join(PROMPT_DIR, f"prompt_{hash(post_url)}.txt")
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(prompt.strip())

        # === CALL OLLAMA CHAT ===
        summary = call_llm(prompt)

        # === STORE RESULT ===
        out_cursor.execute("""
            INSERT OR REPLACE INTO post_summaries (post_url, caption, comment_count, summary)
            VALUES (?, ?, ?, ?)
        """, (post_url, caption, comment_count, summary))
        out_conn.commit()

    out_conn.close()
    print("✅ Все посты успешно проанализированы. Результаты сохранены в:", OUTPUT_DB)
