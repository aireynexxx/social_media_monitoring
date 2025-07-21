import os
import sqlite3
import pandas as pd
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from torch.nn.functional import softmax
from tqdm import tqdm

def insta_sentiment():
    # === CONFIG ===
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    INPUT_DB = os.path.join(BASE_DIR, "data", "instagram_comments.db")
    OUTPUT_DB = os.path.join(BASE_DIR, "data", "instagram_sentiment.db")
    AVG_DB = os.path.join(BASE_DIR, "data", "instagram_avg_sentiment.db")

    # Remove output DBs if they exist
    for db_path in [OUTPUT_DB, AVG_DB]:
        if os.path.exists(db_path):
            print(f"🗑️ Deleting existing database: {db_path}")
            os.remove(db_path)

    # Load tokenizer and model
    tokenizer = AutoTokenizer.from_pretrained("blanchefort/rubert-base-cased-sentiment")
    model = AutoModelForSequenceClassification.from_pretrained("blanchefort/rubert-base-cased-sentiment")

    # Connect to input DB and read data
    conn = sqlite3.connect(INPUT_DB)
    df = pd.read_sql_query("SELECT * FROM comments", conn)
    conn.close()

    # Sentiment label mapping
    label_map = {0: "negative", 1: "neutral", 2: "positive"}

    # Sentiment classification function
    def classify_sentiment(text):
        if not isinstance(text, str) or text.strip() == "":
            return "neutral"
        inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)
        with torch.no_grad():
            outputs = model(**inputs)
            probs = softmax(outputs.logits, dim=1)
            label = torch.argmax(probs).item()
            return label_map[label]

    # Apply sentiment analysis
    tqdm.pandas(desc="🔍 Analyzing sentiment")
    df["sentiment"] = df["comment"].progress_apply(classify_sentiment)

    # Save sentiment-labeled comments
    conn_out = sqlite3.connect(OUTPUT_DB)
    df.to_sql("comments_with_sentiment", conn_out, index=False, if_exists="replace")
    conn_out.close()
    print(f"✅ Sentiment-labeled data saved to {OUTPUT_DB}")

    # Compute majority sentiment per post
    majority_df = (
        df.groupby("post_caption")["sentiment"]
        .agg(lambda x: x.value_counts().idxmax())
        .reset_index()
        .rename(columns={"sentiment": "average_sentiment"})
    )

    # Save to new DB
    conn_avg = sqlite3.connect(AVG_DB)
    majority_df.to_sql("average_sentiment", conn_avg, index=False, if_exists="replace")
    conn_avg.close()
    print(f"📊 Majority sentiment per post saved to {AVG_DB}")

if __name__ == "__main__":
    insta_sentiment()