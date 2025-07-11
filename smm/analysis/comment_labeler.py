# comment_labeler.py

import sqlite3
import pandas as pd
import random
import os
import ollama
from tqdm import tqdm

# === CONFIG ===
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_DB = os.path.join(BASE_DIR, "data", "instagram_comments.db")
SUMMARY_DB = os.path.join(BASE_DIR, "data", "instagram_summaries.db")
OUTPUT_DB = os.path.join(BASE_DIR, "data", "instagram_comments_tagged.db")
OLLAMA_MODEL = "llama3.1:8b"

# === LLM CALL FUNCTION TO DETECT TOPIC ===
def call_topic_classifier(caption, comments):
    prompt = f"""
Ты — аналитик социальных сетей. На основе текста поста и комментариев определи, к какой теме он относится. Темы могут быть: политика, миграция, безопасность, экономика, культура, образование, здравоохранение, технологии, международные отношения, и т.д.

Пост:
"""
    prompt += caption.strip() + "\n\nКомментарии:\n"
    for i, c in enumerate(comments[:10], 1):
        prompt += f"{i}. {c.strip()}\n"
    prompt += "\nУкажи 1-2 темы через запятую. Без пояснений."

    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": "Ты категоризатор тем."},
                {"role": "user", "content": prompt}
            ]
        )
        return [t.strip().lower() for t in response['message']['content'].split(',') if t.strip()]
    except Exception as e:
        print("⚠️ Ошибка при классификации темы:", e)
        return ["прочее"]

# === PREP OUTPUT DB ===
'''if os.path.exists(OUTPUT_DB):
    print(f"🗑️ Deleting existing database: {OUTPUT_DB}")
    os.remove(OUTPUT_DB)'''

print("📥 Loading Instagram Comments DB...")
conn = sqlite3.connect(INPUT_DB)
df = pd.read_sql("SELECT * FROM comments", conn)
conn.close()

# === GROUP BY POST AND TAG ===
print("🏷️ Classifying topics for each post and tagging comments...")
post_groups = df.groupby("post_url")
all_tagged_rows = []

for post_url, group in tqdm(post_groups, desc="Tagging topics"):
    caption = group["post_caption"].iloc[0]
    comments = group["comment"].dropna().astype(str).tolist()
    topics = call_topic_classifier(caption, comments)

    for _, row in group.iterrows():
        row_dict = row.to_dict()
        row_dict["topics"] = ", ".join(topics)
        all_tagged_rows.append(row_dict)

# === SAVE TO NEW DB ===
print("💾 Saving tagged comments...")
tagged_df = pd.DataFrame(all_tagged_rows)
conn_out = sqlite3.connect(OUTPUT_DB)
tagged_df.to_sql("comments", conn_out, index=False, if_exists="replace")
conn_out.close()

print("✅ Комментарии размечены темами и сохранены в:", OUTPUT_DB)
