import os
import sqlite3
import pandas as pd
import re
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from torch.nn.functional import softmax
from tqdm import tqdm
import joblib
import random
import scipy as sp

# Import delete_irrelevant function from your analysis module
from analysis.mood_analyser import delete_irrelevant

# Initialize tokenizer and model once
tokenizer = AutoTokenizer.from_pretrained("blanchefort/rubert-base-cased-sentiment")
model = AutoModelForSequenceClassification.from_pretrained("blanchefort/rubert-base-cased-sentiment")


def classify(text):
    if not isinstance(text, str) or not text.strip():
        return "neutral"
    encoded = tokenizer(text, return_tensors='pt', truncation=True, padding=True)
    with torch.no_grad():
        logits = model(**encoded).logits
    pred_class = torch.argmax(softmax(logits, dim=1)).item()
    # Map index to label:
    labels = ["negative", "neutral", "positive"]
    return labels[pred_class]



def clean_text(text):
    if not isinstance(text, str):
        return ""
    # Simple cleaning: remove URLs, tags, extra spaces
    text = re.sub(r'<.*?>|@\w+|https?://\S+|www\.\S+', '', text)
    return re.sub(r'\s+', ' ', text).strip()


# Enable tqdm progress_apply
tqdm.pandas()

# Path to Instagram comments DB
insta_path = "data/instagram_comments.db"

# Clean irrelevant comments from DB (your function)
delete_irrelevant(insta_path)

if os.path.exists(insta_path):
    conn = sqlite3.connect(insta_path)
    insta_comments = pd.read_sql("SELECT * FROM comments", conn)
    conn.close()

    # Add metadata columns
    insta_comments['source'] = 'instagram'
    insta_comments['article_id'] = 'insta_' + insta_comments['id'].astype(str)

    # Keep only relevant columns, rename if needed
    insta_comments = insta_comments[['article_id', 'source', 'comment']]

    # Clean comments
    insta_comments['clean_comment'] = insta_comments['comment'].apply(clean_text)

    # Classify sentiment with progress bar
    insta_comments['sentiment'] = insta_comments['clean_comment'].progress_apply(classify)
else:
    insta_comments = pd.DataFrame(columns=['article_id', 'source', 'comment', 'clean_comment', 'sentiment'])

# Save to CSV
insta_comments.to_csv('insta_comments.csv', index=False)

print("Sentiment analysis completed. Results saved to insta_comments.csv")
