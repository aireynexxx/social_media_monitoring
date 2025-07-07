import argparse
from analysis.mood_analyser import load_data, analyze
from llm.report_generator import generate_report

def run_pipeline(skip_scraping=True):
    if not skip_scraping:
        from scrapers import gazeta_scraper, podrobno_scraper
        print(" Scraping data...")
        gazeta_scraper.run()
        podrobno_scraper.run()

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
