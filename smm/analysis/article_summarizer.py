import sqlite3
import pandas as pd
from tqdm import tqdm
import ollama
import os

# === Paths to the databases ===
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAZETA_DB = os.path.join(BASE_DIR, "data", "gazeta_articles.db")
PODROBNO_DB = os.path.join(BASE_DIR, "data", "podrobno_articles.db")
OUTPUT_DB = os.path.join(BASE_DIR, "data", "article_summaries.db")

# === Model and prompt template ===
MODEL = "llama3.1:8b"  # or whatever your Ollama model is
SYSTEM_PROMPT = "Ты — аналитик СМИ. Напиши краткое содержание и выяви главные темы статьи и комментариев."

SUMMARY_TEMPLATE = """
СТАТЬЯ:
{article}

КОММЕНТАРИИ:
{comments}

Сформулируй краткое содержание содержания статьи и основных реакций в комментариях. Ответ должен быть на русском языке.
"""

# === Load and normalize articles ===
def load_articles_and_comments(db_path, article_table, comment_table):
    conn = sqlite3.connect(db_path)
    articles = pd.read_sql(f"SELECT * FROM {article_table}", conn)
    comments = pd.read_sql(f"SELECT * FROM {comment_table}", conn)
    conn.close()

    if "content" in articles.columns:
        articles = articles.rename(columns={"content": "text"})

    return articles, comments

# === Generate summary using Ollama ===
def generate_summary(article, comments):
    top_comments = "\n".join(comments[:5]) if comments else "Нет комментариев."
    prompt = SUMMARY_TEMPLATE.format(article=article, comments=top_comments)

    response = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
    )

    return response["message"]["content"]

# === Main summarization routine ===
def summarize_articles():
    print("📥 Загружаем данные из обеих баз данных...")
    gazeta_articles, gazeta_comments = load_articles_and_comments(GAZETA_DB, "articles", "comments")
    podrobno_articles, podrobno_comments = load_articles_and_comments(PODROBNO_DB, "articles", "comments")

    print("🗃️ Подготовка базы данных итогов...")

    # Standardize and combine
    gazeta_articles["source"] = "gazeta"
    podrobno_articles["source"] = "podrobno"

    gazeta_comments["source"] = "gazeta"
    podrobno_comments["source"] = "podrobno"

    all_articles = pd.concat([gazeta_articles, podrobno_articles], ignore_index=True)
    all_comments = pd.concat([gazeta_comments, podrobno_comments], ignore_index=True)

    # Drop articles with no text
    all_articles = all_articles[all_articles["text"].str.strip().astype(bool)]

    # --- NEW: Filter out articles with no comments ---
    article_ids_with_comments = set(all_comments['article_id'].unique())
    all_articles = all_articles[all_articles['id'].isin(article_ids_with_comments)]

    print(f"🧠 Начинаем генерацию обзоров для {len(all_articles)} статей с комментариями...")
    summaries = []

    for _, article_row in tqdm(all_articles.iterrows(), total=len(all_articles), desc="Summarizing articles"):
        article_id = article_row["id"]
        source = article_row["source"]
        title = article_row["title"]
        article_text = article_row["text"]

        # Filter comments for this article
        article_comments = all_comments[
            (all_comments["article_id"] == article_id) & (all_comments["source"] == source)
        ]

        comment_texts = article_comments["comment"].dropna().tolist()

        try:
            summary = generate_summary(article_text, comment_texts)
        except Exception as e:
            summary = f"[ERROR] {str(e)}"

        summaries.append({
            "source": source,
            "article_id": article_id,
            "title": title,
            "summary": summary,
        })

    # Save to DB
    if os.path.exists(OUTPUT_DB):
        print(f"🗑️ Deleting existing database: {OUTPUT_DB}")
        os.remove(OUTPUT_DB)

    print(f"💾 Сохраняем в {OUTPUT_DB}...")
    conn_out = sqlite3.connect(OUTPUT_DB)
    pd.DataFrame(summaries).to_sql("summaries", conn_out, index=False)
    conn_out.close()

    print("✅ Обзоры статей успешно сохранены!")

# === Entry point ===
if __name__ == "__main__":
    summarize_articles()
