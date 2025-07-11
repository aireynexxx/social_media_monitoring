import argparse
import subprocess
from analysis.mood_analyser import load_data, analyze
from llm.report_generator import generate_report

def run_pipeline(skip_scraping=True):
    if not skip_scraping:
        print(" Scraping Podrobno...")
        subprocess.run(["python", "scrapers/podrobno_scraper.py"], check=True)

        print(" Scraping Instagram...")
        subprocess.run(["python", "scrapers/instagram_scraper.py"], check=True)

        print(" Scraping Gazeta...")
        subprocess.run(["python", "scrapers/gazeta_scraper.py"], check=True)

    print(" Analyzing mood...")
    articles, comments, emotions = load_data()
    analyze(articles, comments, emotions)

    print(" Generating report...")
    generate_report()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scrape", action="store_true", help="Run scrapers before analysis")
    args = parser.parse_args()

    run_pipeline(skip_scraping=not args.scrape)
