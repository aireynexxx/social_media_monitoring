# 📰 Social Media & News Mood Analyzer

A Python project that automatically scrapes Instagram and major Uzbek news sources (Gazeta.uz, Podrobno.uz), analyzes public sentiment from comments, summarizes posts/articles, and generates a final analytical report using an LLM.

---

## 📦 Features

- ✅ Scrapes Instagram posts and comments  
- ✅ Scrapes articles and comments from **Gazeta.uz** and **Podrobno.uz**  
- ✅ Performs sentiment and mood analysis on comments  
- ✅ Summarizes posts and articles using a local LLM  
- ✅ Generates a structured, multi-source report with analysis  
- ✅ Modular and configurable via command-line options  

---

## 🛠️ Installation

1. **Clone the repository**

```bash
git clone https://github.com/your-username/social-media-analyzer.git
cd social-media-analyzer
```

2. **Create a virtual environment**

```bash
python -m venv venv
source venv/bin/activate  # on Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

---

## 🚀 Usage

Run the pipeline with one or more options:

```bash
python main.py [--scrape] [--analyze]
```

### Options:
- `--scrape`: Run all scrapers (Instagram, Gazeta, Podrobno)
- `--analyze`: Perform mood analysis, summarization, and report generation

### Examples:
```bash
# Just generate report from existing data
python main.py

# Scrape and analyze everything
python main.py --scrape --analyze

# Only scrape new data
python main.py --scrape
```

---

## 📁 Project Structure

```
social_media_monitoring/
├── scrapers/
│   ├── instagram_scraper.py
│   ├── gazeta_scraper.py
│   └── podrobno_scraper.py
├── analysis/
│   ├── mood_analyser.py
│   ├── insta_post_summarizer.py
│   ├── article_summarizer.py
│   └── insta_comment_labeler.py
├── llm/
│   └── report_generator.py
├── data/
│   ├── *.db (SQLite databases)
├── main.py
└── requirements.txt
```

---

## 💡 Tech Stack

- Python 3.10+
- SQLite (for local data storage)
- Pandas / NumPy
- Selenium (for Instagram scraping)
- Local LLM (via Ollama, e.g. Mistral or Gemma)
- LangChain (optional, for pipeline composition)

---

## 📄 Output

Generates a structured LLM-based report summarizing:
- Mood trends
- Frequent topics
- Article/post summaries
- Public sentiment breakdown

---

## 🧠 Example Use Cases

- Social media monitoring
- Media bias and emotion analysis
- Political or news trend research
- Public relations impact assessment

---

## 📬 Contact

Created by Diana Shadibaeva and Tyson Watson – contributions and feedback welcome!
