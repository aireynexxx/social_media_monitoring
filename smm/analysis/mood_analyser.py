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

    # --- Combine ---
    articles = pd.concat([gaz_articles, pod_articles], ignore_index=True)
    comments = pd.concat([gaz_comments], ignore_index=True)
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

    # Save outputs
    joblib.dump(articles, "articles_df.pkl")
    joblib.dump(comments, "comments_df.pkl")
    joblib.dump(emotions_summary, "sentiment_summary_emotions.pkl")

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
Вы — аналитик Узбекского СМИ про Узбекистан, изучающий общественное мнение по поводу новостей и комментариев читателей на русском языке.

Напишите **аналитический отчет на русском языке** для представителей государства на основе следующих данных.

Сводка:
- Количество проанализированных статей: {len(articles)}
- Распределение настроения (по статьям):
    - Позитивное: {mood_counts.get('positive', 0)}
    - Нейтральное: {mood_counts.get('neutral', 0)}
    - Негативное: {mood_counts.get('negative', 0)}

- Наиболее часто встречающиеся эмоции (по реакциям): {", ".join(top_emotions)}

- Примеры комментариев пользователей:
{chr(10).join(f'- "{c}"' for c in sampled_comments)}

Задача:
Составьте профессиональный и связный отчет на русском языке, в котором вы проанализируете общее настроение населения по отношению к текущим новостям. Упомяните эмоциональные тенденции, общие темы и возможные причины недовольства или поддержки. При необходимости переформулируйте или процитируйте пользовательские комментарии.
    """.strip()

    with open("prompt.txt", "w", encoding="utf-8") as f:
        f.write(prompt)
