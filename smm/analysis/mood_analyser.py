# mood_analyser.py

import sqlite3
import pandas as pd
import numpy as np
import re
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from torch.nn.functional import softmax
from tqdm import tqdm
import joblib
import random
import os

def delete_irrelevant( db_path='instagram_comments.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    keywords = [
        # English
        "uzbekistan", "tashkent", "government", "mirziyoyev", "reform", "tax", "taxes",
        "economy", "salary", "price", "healthcare", "education", "internet", "protest",
        "explosion", "accident", "fire", "rights", "law", "election", "police", "corruption",
        "job", "jobs", "employee", "employment", "tariffs", "tarif",

        # Russian
        "Узбекистан", "Ташкент", "правительство", "Мирзиёев", "реформа", "налог", "налоги",
        "экономика", "зарплата", "цена", "здравоохранение", "образование", "интернет", "протест",
        "взрыв", "авария", "пожар", "права", "закон", "выборы", "полиция", "коррупция",
        "работа", "рабочие места", "работник", "занятость", "тарифы", "тариф",

        # Uzbek (Latin script)
        "o'zbekiston", "toshkent", "hukumat", "mirziyoyev", "islohot", "soliq", "soliqlar",
        "iqtisod", "maosh", "narx", "sog'liqni saqlash", "ta'lim", "internet", "norozilik",
        "portlash", "avariya", "yong'in", "huquqlar", "qonun", "saylov", "politsiya",
        "korruptsiya", "ish", "xodim", "bandlik", "tariflar", "tarif",
    ]

    like_clauses = " OR ".join([f"post_caption LIKE ?" for _ in keywords])
    params = [f"%{kw}%" for kw in keywords]

    query = f"""
    DELETE FROM comments
    WHERE NOT ({like_clauses})
    """
    cursor.execute(query, params)
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()

    print(f'Deleted {deleted_count} posts.')



def clean_text(text):
    if not isinstance(text, str):
        return ""
    text = re.sub(r'<.*?>|@\w+|https?://\S+|www\.\S+', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def load_data():
    # --- Podrobno ---
    pod_articles = pd.read_sql("SELECT * FROM articles", sqlite3.connect("data/podrobno_articles.db"))
    pod_emotions = pd.read_sql("SELECT * FROM emotions", sqlite3.connect("data/podrobno_articles.db"))
    pod_articles['source'] = 'podrobno'
    pod_articles['article_id'] = pod_articles['id'].astype(str) + 'podrobno'
    pod_emotions['article_id'] = pod_emotions['article_id'].astype(str) + 'podrobno'

    # --- Gazeta ---
    gaz_articles = pd.read_sql("SELECT * FROM articles", sqlite3.connect("data/gazeta_articles.db"))
    gaz_comments = pd.read_sql("SELECT * FROM comments", sqlite3.connect("data/gazeta_articles.db"))
    gaz_articles['source'] = 'gazeta'
    gaz_articles['article_id'] = gaz_articles['id'].astype(str) + 'gazeta'
    gaz_comments['article_id'] = gaz_comments['article_id'].astype(str) + 'gazeta'

    # --- Instagram ---
    insta_path = "data/instagram_comments.db"

    delete_irrelevant(insta_path)

    if os.path.exists(insta_path):
        insta_comments = pd.read_sql("SELECT * FROM comments", sqlite3.connect(insta_path))
        insta_comments['source'] = 'instagram'
        insta_comments['article_id'] = 'insta_' + insta_comments['id'].astype(str)
        insta_comments = insta_comments.rename(columns={'comment': 'comment'})
        insta_comments = insta_comments[['article_id', 'source', 'comment']]  # Keep it uniform
    else:
        insta_comments = pd.DataFrame(columns=['article_id', 'source', 'comment'])

    # --- Combine ---
    articles = pd.concat([gaz_articles, pod_articles], ignore_index=True)
    comments = pd.concat([gaz_comments[['article_id', 'comment']], insta_comments], ignore_index=True)
    emotions = pod_emotions.copy()

    return articles, comments, emotions

def analyze(articles, comments, emotions):
    comments['clean_comment'] = comments['comment'].apply(clean_text)

    tokenizer = AutoTokenizer.from_pretrained("blanchefort/rubert-base-cased-sentiment")
    model = AutoModelForSequenceClassification.from_pretrained("blanchefort/rubert-base-cased-sentiment")

    def classify(text):
        if not text.strip():
            return "neutral"
        encoded = tokenizer(text, return_tensors='pt', truncation=True, padding=True)
        with torch.no_grad():
            logits = model(**encoded).logits
        stars = torch.argmax(softmax(logits, dim=1)) + 1
        return "negative" if stars <= 2 else "neutral" if stars == 3 else "positive"

    tqdm.pandas()
    comments['sentiment'] = comments['clean_comment'].progress_apply(classify)

    counts = comments.groupby('article_id')['sentiment'].value_counts().unstack(fill_value=0)

    def get_mood(row):
        pos = row.get("positive", 0)
        neu = row.get("neutral", 0)
        neg = row.get("negative", 0)
        if pos > max(neg, neu):
            return "positive"
        if neg > max(pos, neu):
            return "negative"
        return "neutral"

    counts['mood'] = counts.apply(get_mood, axis=1)
    articles = articles.merge(counts['mood'], left_on="article_id", right_index=True, how="left")

    # --- Add emoji-based sentiment override (Podrobno only) ---
    emoji_sentiment_map = {
        'Нравится': 'positive', 'Восхищение': 'positive', 'Радость': 'positive',
        'Удивление': 'neutral',
        'Подавленность': 'negative', 'Грусть': 'negative',
        'Разочарование': 'negative', 'Не нравится': 'negative'
    }
    emotions['sentiment'] = emotions['emotion'].map(emoji_sentiment_map)
    emotions_summary = emotions.groupby(['article_id', 'sentiment'])['count'].sum().unstack(fill_value=0).reset_index()
    emotions_summary['dominant_sentiment'] = emotions_summary[['positive', 'neutral', 'negative']].idxmax(axis=1)

    for _, row in emotions_summary.iterrows():
        articles.loc[articles['article_id'] == row['article_id'], 'mood'] = row['dominant_sentiment']

    articles['mood'] = articles['mood'].fillna("no comment")

    # === Instagram Summaries Block ===
    insta_summary_path = "data/instagram_summaries.db"
    if os.path.exists(insta_summary_path):
        insta_summary_conn = sqlite3.connect(insta_summary_path)
        insta_summary_df = pd.read_sql("SELECT * FROM post_summaries", insta_summary_conn)
        insta_summary_conn.close()

        insta_summary_texts = insta_summary_df["summary"].dropna().tolist()
        random.seed(42)
        random.shuffle(insta_summary_texts)
        insta_summaries = "\n\n".join(f"- {s.strip()}" for s in insta_summary_texts[:5]) if insta_summary_texts else "Нет Instagram-сводок."
    else:
        insta_summaries = "Instagram-данные отсутствуют."

    # === Article Summaries Block ===
    article_summary_path = "data/article_summaries.db"
    if os.path.exists(article_summary_path):
        article_summary_conn = sqlite3.connect(article_summary_path)
        article_summary_df = pd.read_sql("SELECT * FROM summaries", article_summary_conn)
        article_summary_conn.close()

        article_summary_texts = article_summary_df["summary"].dropna().tolist()
        random.seed(42)
        random.shuffle(article_summary_texts)
        article_summaries = "\n\n".join(f"- {s.strip()}" for s in article_summary_texts[:5]) if article_summary_texts else "Нет сводок по статьям."
    else:
        article_summaries = "Сводки по статьям отсутствуют."

    # === Comment Sentiment Block ===
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    SENTIMENT_DB = os.path.join(BASE_DIR, "data", "instagram_avg_sentiment.db")

    # Connect and load the average sentiment table
    conn = sqlite3.connect(SENTIMENT_DB)
    avg_df = pd.read_sql_query("SELECT * FROM average_sentiment", conn)
    conn.close()

    average_sentiment_text = "\n".join(f"Этот пост: {row['post_caption']}, вызвал такую реакцию: {row['average_sentiment']}"
    for _, row in avg_df.iterrows())





    # --- Save intermediate outputs ---
    joblib.dump(articles, "articles_df.pkl")
    joblib.dump(comments, "comments_df.pkl")
    joblib.dump(emotions_summary, "sentiment_insta_summary_emotions.pkl")

    # === Generate Prompt for LLM ===
    mood_counts = articles['mood'].value_counts().to_dict()
    sampled_comments = comments['clean_comment'].dropna().tolist()
    random.seed(42)
    sampled_comments = random.sample(sampled_comments, min(10, len(sampled_comments)))

    if 'dominant_sentiment' in emotions_summary.columns:
        top_emotions = emotions_summary['dominant_sentiment'].value_counts().head(5).index.tolist()
    else:
        top_emotions = ['(эмоции не определены)']

    prompt = f"""
Вы — аналитик Узбекского СМИ про Узбекистан, изучающий общественное мнение по поводу новостей и комментариев читателей на русском языке, поэтому используйте только русский язык.

Напишите **аналитический отчет на русском языке** для представителей государства на основе следующих данных.

{average_sentiment_text}

Задача:
Составьте профессиональный и связный отчет на **русском** языке, в котором вы проанализируете общее настроение населения по отношению к текущим новостям. Упомяните эмоциональные тенденции, общие темы и возможные причины недовольства или поддержки. При необходимости переформулируйте или редко процитируйте уместные пользовательские комментарии.
    """.strip()

    with open("reports/prompt.txt", "w", encoding="utf-8") as f:
        f.write(prompt)

'''
Сводка:
- Количество проанализированных статей: {len(articles)}
- Распределение настроения (по статьям):
    - Позитивное: {mood_counts.get('positive', 0)}
    - Нейтральное: {mood_counts.get('neutral', 0)}
    - Негативное: {mood_counts.get('negative', 0)}
    
Краткие аналитические сводки по постам Instagram:
{insta_summaries}

Краткие аналитические сводки по статьям СМИ:
{article_summaries}
'''