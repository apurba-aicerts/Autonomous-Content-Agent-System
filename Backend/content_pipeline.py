# # import json
# # from datetime import datetime

# # # from Backend.sitemap_agent import WebScraper
# # # from Backend.social_trend_miner import RedditTrendMiner
# # # from Backend.gap_analyzer import ContentGapFinder
# # # from Backend.trend_clusterer import TrendAnalyzer
# # # from Backend.brief_generator import ContentBriefGenerator

# # from sitemap_agent import WebScraper
# # from social_trend_miner import RedditTrendMiner
# # from gap_analyzer import ContentGapFinder
# # from trend_clusterer import TrendAnalyzer
# # from brief_generator import ContentBriefGenerator

# # import os
# # from dotenv import load_dotenv
# # load_dotenv()

# # # -----------------------------
# # OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# # client_id = os.getenv("client_id")
# # client_secret = os.getenv("client_secret")  
# # user_agent = os.getenv("user_agent")
# # # -----------------------------
# # # PHASE 1: Data Collection
# # scraper = WebScraper(
# #         delay=0.1,          # Short delay for rate limiting
# #         timeout=10,
# #         max_pages=15,
# #         max_depth=1,
# #         max_concurrent=15   # 15 concurrent requests
# #     )
# # our_details = scraper.scrape(
# #         homepage_url="https://www.aicerts.ai/",#"https://www.mygreatlearning.com",
# #         start_date="2025-01-01",
# #         end_date="2025-12-31",
# #         keywords=['course', 'certification', 'program']
# #     )
# # competitor_details = scraper.scrape(
# #         homepage_url="https://www.mygreatlearning.com",
# #         start_date="2025-01-01",
# #         end_date="2025-12-31",
# #         keywords=['course', 'certification', 'program']
# #     )
# # all_details = {"our_pages": our_details, "competitor_pages": competitor_details}
# # # Save all results
# # with open("data/sitemaps_data.json", "w", encoding="utf-8") as f:
# #     json.dump(all_details, f, indent=2, ensure_ascii=False)
# # print(f"✅ Saved sitemap sitemaps_data.json with {len(our_details)} own pages and {len(competitor_details)} competitor pages.")

# # own_titles = [page['title'] for page in our_details]
# # competitor_titles = [page['title'] for page in competitor_details]

# # miner = RedditTrendMiner(
# #         client_id=client_id,
# #         client_secret=client_secret,
# #         user_agent=user_agent,
# #         max_workers=10  # adjust threads here
# #     )

# # keywords = ["MachineLearning", "AI", "DataScience"]
# # start_date = datetime(2025, 10, 24)
# # end_date = datetime(2025, 10, 30)

# # social_data = miner.run(keywords, start_date, end_date, posts_limit=100, top_subs=3)
# # with open("data/social_trends_raw.json", "w", encoding="utf-8") as f:
# #     json.dump(social_data, f, indent=2, ensure_ascii=False)
# # print(f"✅ Saved {len(social_data)} social posts to social_trends_raw.json")


# # # PHASE 2: Analysis
# # analyzer = TrendAnalyzer(api_key=OPENAI_API_KEY)
# # trending_input = analyzer.run_from_data(social_data, apply_elbow=True, show_plot=False)

# # with open("data/trending_topics_report.json", "w", encoding="utf-8") as f:
# #     json.dump(trending_input, f, indent=2, ensure_ascii=False)
# # print(f"✅ Saved {len(trending_input)} social posts to trending_topics_report.json")


# # finder = ContentGapFinder(api_key=OPENAI_API_KEY)
# # content_gaps_input = finder.find_gaps(own_titles, competitor_titles)

# # with open("data/content_gaps_report.json", "w", encoding="utf-8") as f:
# #     json.dump(content_gaps_input, f, indent=2, ensure_ascii=False)
# # print(f"✅ Saved {len(content_gaps_input)} social posts to content_gaps_report.json")


# # # PHASE 3: Content Brief Generation Example
# # generator = ContentBriefGenerator(api_key=OPENAI_API_KEY)
# # result = generator.generate_content_briefs(content_gaps_input, trending_input)

# # with open("data/content_briefs.json", "w", encoding="utf-8") as f:
# #     json.dump(result, f, indent=2, ensure_ascii=False)
# # print(f"✅ Saved {len(result)} social posts to content_briefs.json")

# # print(json.dumps(result, indent=2))

# """
# =============================================================
#                      ORCHESTRATOR (main.py)
# =============================================================
# Coordinates all agents: WebScraper, RedditTrendMiner, 
# TrendAnalyzer, ContentGapFinder, and ContentBriefGenerator.
# Phases:
#   1. Data Collection (Parallel)
#   2. Analysis (Parallel)
#   3. Strategy Generation (Sequential)
# =============================================================
# """

# import json
# import os
# import logging
# from datetime import datetime
# from concurrent.futures import ThreadPoolExecutor, as_completed
# from dotenv import load_dotenv

# # Local imports
# from sitemap_agent import WebScraper
# from social_trend_miner import RedditTrendMiner
# from gap_analyzer import ContentGapFinder
# from trend_clusterer import TrendAnalyzer
# from brief_generator import ContentBriefGenerator


# # ============================================================
# # CONFIGURATION
# # ============================================================
# load_dotenv()
# os.makedirs("data", exist_ok=True)

# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s | %(levelname)s | %(message)s",
#     handlers=[
#         logging.FileHandler("data/orchestrator.log"),
#         logging.StreamHandler()
#     ]
# )

# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# client_id = os.getenv("client_id")
# client_secret = os.getenv("client_secret")
# user_agent = os.getenv("user_agent")

# # ============================================================
# # RETRY DECORATOR
# # ============================================================
# def retry(max_attempts=3):
#     def decorator(func):
#         def wrapper(*args, **kwargs):
#             for attempt in range(1, max_attempts + 1):
#                 try:
#                     return func(*args, **kwargs)
#                 except Exception as e:
#                     logging.warning(f"Attempt {attempt} failed for {func.__name__}: {e}")
#                     if attempt == max_attempts:
#                         logging.error(f"Max retries reached for {func.__name__}")
#                         raise
#         return wrapper
#     return decorator


# # ============================================================
# # PHASE 1: DATA COLLECTION
# # ============================================================
# @retry()
# def run_sitemap_scraper():
#     logging.info("Starting sitemap scraping...")
#     scraper = WebScraper(delay=0.1, timeout=10, max_pages=15, max_depth=1, max_concurrent=15)

#     our_details = scraper.scrape(
#         homepage_url="https://www.aicerts.ai/",
#         start_date="2025-01-01",
#         end_date="2025-12-31",
#         keywords=['course', 'certification', 'program']
#     )
#     competitor_details = scraper.scrape(
#         homepage_url="https://www.mygreatlearning.com",
#         start_date="2025-01-01",
#         end_date="2025-12-31",
#         keywords=['course', 'certification', 'program']
#     )

#     result = {"our_pages": our_details, "competitor_pages": competitor_details}
#     with open("data/sitemaps_data.json", "w", encoding="utf-8") as f:
#         json.dump(result, f, indent=2, ensure_ascii=False)
#     logging.info(f"✅ Saved sitemap_data.json with {len(our_details)} our pages and {len(competitor_details)} competitor pages.")

#     return result


# @retry()
# def run_reddit_miner():
#     logging.info("Starting Reddit trend mining...")
#     miner = RedditTrendMiner(
#         client_id=client_id,
#         client_secret=client_secret,
#         user_agent=user_agent,
#         max_workers=10
#     )

#     keywords = ["Machine Learning", "AI", "DataScience"]
#     start_date = datetime(2025, 10, 24)
#     end_date = datetime(2025, 10, 31)

#     data = miner.run(keywords, start_date, end_date, posts_limit=10, top_subs=3)
#     with open("data/social_trends_raw.json", "w", encoding="utf-8") as f:
#         json.dump(data, f, indent=2, ensure_ascii=False)
#     logging.info(f"✅ Saved {len(data)} Reddit posts to social_trends_raw.json.")

#     return data


# def phase1_data_collection():
#     logging.info("===== PHASE 1: DATA COLLECTION START =====")
#     with ThreadPoolExecutor(max_workers=2) as executor:
#         futures = {
#             executor.submit(run_sitemap_scraper): "sitemap",
#             executor.submit(run_reddit_miner): "reddit"
#         }
#         results = {}
#         for future in as_completed(futures):
#             task_name = futures[future]
#             try:
#                 results[task_name] = future.result()
#             except Exception as e:
#                 logging.error(f"{task_name} task failed: {e}")
#     logging.info("===== PHASE 1: DATA COLLECTION COMPLETE =====")
#     return results


# # ============================================================
# # PHASE 2: ANALYSIS
# # ============================================================
# @retry()
# def run_trend_analysis(social_data):
#     logging.info("Starting trend analysis...")
#     analyzer = TrendAnalyzer(api_key=OPENAI_API_KEY)
#     result = analyzer.run_from_data(social_data, apply_elbow=True, show_plot=False)

#     with open("data/trending_topics_report.json", "w", encoding="utf-8") as f:
#         json.dump(result, f, indent=2, ensure_ascii=False)
#     logging.info(f"✅ Saved {len(result)} trending topics to trending_topics_report.json.")

#     return result


# @retry()
# def run_gap_analysis(own_titles, competitor_titles):
#     logging.info("Starting content gap analysis...")
#     finder = ContentGapFinder(api_key=OPENAI_API_KEY)
#     result = finder.find_gaps(own_titles, competitor_titles)

#     with open("data/content_gaps_report.json", "w", encoding="utf-8") as f:
#         json.dump(result, f, indent=2, ensure_ascii=False)
#     logging.info(f"✅ Saved {len(result)} content gaps to content_gaps_report.json.")

#     return result


# def phase2_analysis(phase1_results):
#     logging.info("===== PHASE 2: ANALYSIS START =====")

#     sitemap_data = phase1_results.get("sitemap", {})
#     social_data = phase1_results.get("reddit", [])

#     own_titles = [p['title'] for p in sitemap_data.get("our_pages", [])]
#     competitor_titles = [p['title'] for p in sitemap_data.get("competitor_pages", [])]

#     with ThreadPoolExecutor(max_workers=2) as executor:
#         futures = {
#             executor.submit(run_trend_analysis, social_data): "trend_analysis",
#             executor.submit(run_gap_analysis, own_titles, competitor_titles): "gap_analysis"
#         }
#         results = {}
#         for future in as_completed(futures):
#             task_name = futures[future]
#             try:
#                 results[task_name] = future.result()
#             except Exception as e:
#                 logging.error(f"{task_name} task failed: {e}")
#     logging.info("===== PHASE 2: ANALYSIS COMPLETE =====")
#     return results


# # ============================================================
# # PHASE 3: STRATEGY GENERATION
# # ============================================================
# @retry()
# def phase3_strategy(analysis_results):
#     logging.info("===== PHASE 3: STRATEGY GENERATION START =====")

#     generator = ContentBriefGenerator(api_key=OPENAI_API_KEY)
#     content_gaps = analysis_results.get("gap_analysis", [])
#     trending_topics = analysis_results.get("trend_analysis", [])

#     result = generator.generate_content_briefs(content_gaps, trending_topics)

#     with open("data/content_briefs.json", "w", encoding="utf-8") as f:
#         json.dump(result, f, indent=2, ensure_ascii=False)
#     logging.info(f"✅ Saved {len(result)} content briefs to content_briefs.json.")

#     logging.info("===== PHASE 3: STRATEGY GENERATION COMPLETE =====")
#     return result


# # ============================================================
# # MAIN EXECUTION
# # ============================================================
# if __name__ == "__main__":
#     logging.info("🚀 Starting Orchestrator Workflow")
#     try:
#         phase1_results = phase1_data_collection()
#         analysis_results = phase2_analysis(phase1_results)
#         final_output = phase3_strategy(analysis_results)
#         logging.info("🎯 Workflow completed successfully.")
#         print(json.dumps(final_output, indent=2))
#     except Exception as e:
#         logging.error(f"Workflow failed: {e}")

# import json
# from datetime import datetime
# import os
# from dotenv import load_dotenv

# from sitemap_agent import WebScraper
# from social_trend_miner import RedditTrendMiner
# from gap_analyzer import ContentGapFinder
# from trend_clusterer import TrendAnalyzer
# from brief_generator import ContentBriefGenerator

# # -----------------------------
# # Load Environment Variables
# # -----------------------------
# load_dotenv()
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# client_id = os.getenv("client_id")
# client_secret = os.getenv("client_secret")
# user_agent = os.getenv("user_agent")

# # Ensure data folder exists
# os.makedirs("data", exist_ok=True)

# # -----------------------------
# # PHASE 1: DATA COLLECTION
# # -----------------------------
# scraper = WebScraper(
#     delay=0.1,
#     timeout=10,
#     max_pages=15,
#     max_depth=1,
#     max_concurrent=15
# )

# # 1️⃣ Scrape our own site
# our_details = scraper.scrape(
#     homepage_url="https://www.aicerts.ai/",
#     start_date="2025-01-01",
#     end_date="2025-12-31",
#     keywords=['course', 'certification', 'program']
# )
# own_titles = [page['title'] for page in our_details]

# # 2️⃣ Scrape multiple competitors
# competitors = [
#     "https://www.mygreatlearning.com",
#     "https://www.coursera.org",
#     "https://www.udemy.com",
#     "https://www.simplilearn.com"
# ]

# all_competitor_details = {}
# for url in competitors:
#     print(f"🔍 Scraping competitor: {url}")
#     comp_data = scraper.scrape(
#         homepage_url=url,
#         start_date="2025-01-01",
#         end_date="2025-12-31",
#         keywords=['course', 'certification', 'program']
#     )
#     all_competitor_details[url] = comp_data

# # Save combined sitemap data
# all_details = {
#     "our_pages": our_details,
#     "competitor_pages": all_competitor_details
# }
# with open("data/sitemaps_data.json", "w", encoding="utf-8") as f:
#     json.dump(all_details, f, indent=2, ensure_ascii=False)
# print(f"✅ Saved sitemap data for {len(competitors)} competitors.")


# # -----------------------------
# # PHASE 2: SOCIAL TREND MINING
# # -----------------------------
# miner = RedditTrendMiner(
#     client_id=client_id,
#     client_secret=client_secret,
#     user_agent=user_agent,
#     max_workers=10
# )
# keywords = ["MachineLearning", "AI", "DataScience"]
# start_date = datetime(2025, 10, 24)
# end_date = datetime(2025, 10, 30)

# social_data = miner.run(keywords, start_date, end_date, posts_limit=50, top_subs=3)
# with open("data/social_trends_raw.json", "w", encoding="utf-8") as f:
#     json.dump(social_data, f, indent=2, ensure_ascii=False)
# print(f"✅ Saved {len(social_data)} social posts to social_trends_raw.json")


# # -----------------------------
# # PHASE 3: TREND ANALYSIS
# # -----------------------------
# analyzer = TrendAnalyzer(api_key=OPENAI_API_KEY)
# trending_input = analyzer.run_from_data(social_data, apply_elbow=True, show_plot=False)

# with open("data/trending_topics_report.json", "w", encoding="utf-8") as f:
#     json.dump(trending_input, f, indent=2, ensure_ascii=False)
# print(f"✅ Saved {len(trending_input)} trending clusters to trending_topics_report.json")


# # -----------------------------
# # PHASE 4: CONTENT GAP ANALYSIS
# # -----------------------------
# finder = ContentGapFinder(api_key=OPENAI_API_KEY)
# content_gaps_combined = []

# for comp_url, comp_pages in all_competitor_details.items():
#     comp_titles = [page['title'] for page in comp_pages]
#     print(f"⚙️ Finding content gaps vs {comp_url}")
    
#     gaps = finder.find_gaps(own_titles, comp_titles)
#     for g in gaps:
#         g["competitor"] = comp_url  # annotate for traceability
    
#     content_gaps_combined.extend(gaps)

# # Save all gaps together
# with open("data/content_gaps_report.json", "w", encoding="utf-8") as f:
#     json.dump(content_gaps_combined, f, indent=2, ensure_ascii=False)
# print(f"✅ Saved {len(content_gaps_combined)} total content gaps across competitors.")


# # -----------------------------
# # PHASE 5: CONTENT BRIEF GENERATION
# # -----------------------------
# generator = ContentBriefGenerator(api_key=OPENAI_API_KEY)
# result = generator.generate_content_briefs(content_gaps_combined, trending_input)

# with open("data/content_briefs.json", "w", encoding="utf-8") as f:
#     json.dump(result, f, indent=2, ensure_ascii=False)
# print(f"✅ Saved {len(result)} generated briefs to content_briefs.json")

# # Optional: Print summary
# print(json.dumps(result, indent=2))
import json
from datetime import datetime
import os
from dotenv import load_dotenv
import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from functools import partial
import time
from typing import Dict, List, Any
import threading

from sitemap_agent import WebScraper
from social_trend_miner import RedditTrendMiner
from gap_analyzer import ContentGapFinder
from trend_clusterer import TrendAnalyzer
from brief_generator import ContentBriefGenerator

# -----------------------------
# Progress Tracker
# -----------------------------
class ProgressTracker:
    def __init__(self):
        self.lock = threading.Lock()
        self.phases = {
            "sitemap_scraping": {"total": 0, "completed": 0, "status": "pending"},
            "social_mining": {"total": 0, "completed": 0, "status": "pending"},
            "trend_analysis": {"total": 0, "completed": 0, "status": "pending"},
            "gap_analysis": {"total": 0, "completed": 0, "status": "pending"},
            "brief_generation": {"total": 0, "completed": 0, "status": "pending"}
        }
        self.start_time = time.time()
    
    def update(self, phase: str, completed: int = None, total: int = None, status: str = None):
        with self.lock:
            if total is not None:
                self.phases[phase]["total"] = total
            if completed is not None:
                self.phases[phase]["completed"] = completed
            if status is not None:
                self.phases[phase]["status"] = status
            self._print_progress()
    
    def increment(self, phase: str):
        with self.lock:
            self.phases[phase]["completed"] += 1
            self._print_progress()
    
    def _print_progress(self):
        elapsed = time.time() - self.start_time
        print(f"\n{'='*70}")
        print(f"⏱️  Elapsed Time: {elapsed:.1f}s")
        print(f"{'='*70}")
        for phase, data in self.phases.items():
            status_icon = "✅" if data["status"] == "completed" else "⏳" if data["status"] == "running" else "⏸️"
            if data["total"] > 0:
                pct = (data["completed"] / data["total"]) * 100
                bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                print(f"{status_icon} {phase:20s} [{bar}] {data['completed']}/{data['total']} ({pct:.0f}%)")
            else:
                print(f"{status_icon} {phase:20s} [{data['status']}]")
        print(f"{'='*70}\n")

# -----------------------------
# Load Environment Variables
# -----------------------------
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client_id = os.getenv("client_id")
client_secret = os.getenv("client_secret")
user_agent = os.getenv("user_agent")

os.makedirs("data", exist_ok=True)

# Initialize progress tracker
tracker = ProgressTracker()

# -----------------------------
# Helper Functions
# -----------------------------
def scrape_site(url: str, scraper: WebScraper, keywords: List[str], is_own: bool = False) -> tuple:
    """Scrape a single site (own or competitor)"""
    try:
        site_type = "own site" if is_own else "competitor"
        print(f"🔍 Starting scrape: {url} ({site_type})")
        
        details = scraper.scrape(
            homepage_url=url,
            start_date="2025-01-01",
            end_date="2025-12-31",
            keywords=keywords
        )
        
        print(f"✅ Completed scrape: {url} ({len(details)} pages)")
        tracker.increment("sitemap_scraping")
        
        return (url, details, None)
    except Exception as e:
        print(f"❌ Error scraping {url}: {str(e)}")
        tracker.increment("sitemap_scraping")
        return (url, [], str(e))


def analyze_gap_for_competitor(comp_url: str, comp_pages: List[Dict], 
                               own_titles: List[str], api_key: str) -> List[Dict]:
    """Analyze content gaps for a single competitor"""
    try:
        print(f"⚙️  Finding content gaps vs {comp_url}")
        finder = ContentGapFinder(api_key=api_key)
        comp_titles = [page['title'] for page in comp_pages]
        
        gaps = finder.find_gaps(own_titles, comp_titles)
        for g in gaps:
            g["competitor"] = comp_url
        
        print(f"✅ Found {len(gaps)} gaps for {comp_url}")
        tracker.increment("gap_analysis")
        
        return gaps
    except Exception as e:
        print(f"❌ Error analyzing gaps for {comp_url}: {str(e)}")
        tracker.increment("gap_analysis")
        return []


# -----------------------------
# PHASE 1 & 2: PARALLEL DATA COLLECTION
# -----------------------------
def run_phase_1_and_2_parallel():
    """Run sitemap scraping and social mining in parallel"""
    
    print("\n" + "="*70)
    print("🚀 PHASE 1 & 2: PARALLEL DATA COLLECTION")
    print("="*70)
    
    # Setup
    scraper = WebScraper(
        delay=0.1,
        timeout=10,
        max_pages=15,
        max_depth=1,
        max_concurrent=15
    )
    
    our_url = "https://www.aicerts.ai/"
    competitors = [
        "https://www.mygreatlearning.com",
        "https://www.coursera.org",
        "https://www.udemy.com",
        "https://www.simplilearn.com"
    ]
    keywords = ['course', 'certification', 'program']
    
    # Update progress
    tracker.update("sitemap_scraping", total=len(competitors) + 1, completed=0, status="running")
    tracker.update("social_mining", total=1, completed=0, status="running")
    
    # Use ThreadPoolExecutor for I/O-bound operations
    with ThreadPoolExecutor(max_workers=6) as executor:
        # Submit all scraping jobs
        future_to_url = {}
        
        # Submit our own site
        future = executor.submit(scrape_site, our_url, scraper, keywords, True)
        future_to_url[future] = ("own", our_url)
        
        # Submit all competitor sites
        for comp_url in competitors:
            future = executor.submit(scrape_site, comp_url, scraper, keywords, False)
            future_to_url[future] = ("competitor", comp_url)
        
        # Submit social mining job in parallel
        def mine_social_trends():
            try:
                tracker.update("social_mining", status="running")
                print("🔍 Starting social trend mining...")
                
                miner = RedditTrendMiner(
                    client_id=client_id,
                    client_secret=client_secret,
                    user_agent=user_agent,
                    max_workers=10
                )
                
                keywords_social = ["MachineLearning", "AI", "DataScience"]
                start_date = datetime(2025, 10, 24)
                end_date = datetime(2025, 10, 30)
                
                social_data = miner.run(keywords_social, start_date, end_date, 
                                       posts_limit=50, top_subs=3)
                
                print(f"✅ Completed social mining: {len(social_data)} posts")
                tracker.update("social_mining", completed=1, status="completed")
                
                return social_data
            except Exception as e:
                print(f"❌ Error in social mining: {str(e)}")
                tracker.update("social_mining", completed=1, status="completed")
                return []
        
        social_future = executor.submit(mine_social_trends)
        
        # Collect scraping results
        our_details = []
        all_competitor_details = {}
        
        for future in as_completed(future_to_url):
            site_type, url = future_to_url[future]
            url_result, details, error = future.result()
            
            if site_type == "own":
                our_details = details
            else:
                all_competitor_details[url_result] = details
        
        # Wait for social mining to complete
        social_data = social_future.result()
    
    tracker.update("sitemap_scraping", status="completed")
    
    # Save sitemap data
    all_details = {
        "our_pages": our_details,
        "competitor_pages": all_competitor_details
    }
    with open("data/sitemaps_data.json", "w", encoding="utf-8") as f:
        json.dump(all_details, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved sitemap data for {len(competitors)} competitors.")
    
    # Save social data
    with open("data/social_trends_raw.json", "w", encoding="utf-8") as f:
        json.dump(social_data, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved {len(social_data)} social posts.")
    
    return our_details, all_competitor_details, social_data


# -----------------------------
# PHASE 3 & 4: PARALLEL ANALYSIS
# -----------------------------
def run_phase_3_and_4_parallel(our_details, all_competitor_details, social_data):
    """Run trend analysis and gap analysis in parallel"""
    
    print("\n" + "="*70)
    print("🚀 PHASE 3 & 4: PARALLEL ANALYSIS")
    print("="*70)
    
    tracker.update("trend_analysis", total=1, completed=0, status="running")
    tracker.update("gap_analysis", total=len(all_competitor_details), completed=0, status="running")
    
    own_titles = [page['title'] for page in our_details]
    
    with ThreadPoolExecutor(max_workers=len(all_competitor_details) + 1) as executor:
        # Submit trend analysis
        def analyze_trends():
            try:
                print("⚙️  Starting trend analysis...")
                analyzer = TrendAnalyzer(api_key=OPENAI_API_KEY)
                trending_input = analyzer.run_from_data(social_data, apply_elbow=True, show_plot=False)
                
                print(f"✅ Completed trend analysis: {len(trending_input)} clusters")
                tracker.update("trend_analysis", completed=1, status="completed")
                
                return trending_input
            except Exception as e:
                print(f"❌ Error in trend analysis: {str(e)}")
                tracker.update("trend_analysis", completed=1, status="completed")
                return []
        
        trend_future = executor.submit(analyze_trends)
        
        # Submit gap analysis for all competitors in parallel
        gap_futures = []
        for comp_url, comp_pages in all_competitor_details.items():
            future = executor.submit(
                analyze_gap_for_competitor,
                comp_url, comp_pages, own_titles, OPENAI_API_KEY
            )
            gap_futures.append(future)
        
        # Collect results
        trending_input = trend_future.result()
        
        content_gaps_combined = []
        for future in as_completed(gap_futures):
            gaps = future.result()
            content_gaps_combined.extend(gaps)
    
    tracker.update("gap_analysis", status="completed")
    
    # Save results
    with open("data/trending_topics_report.json", "w", encoding="utf-8") as f:
        json.dump(trending_input, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved {len(trending_input)} trending clusters.")
    
    with open("data/content_gaps_report.json", "w", encoding="utf-8") as f:
        json.dump(content_gaps_combined, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved {len(content_gaps_combined)} total content gaps.")
    
    return content_gaps_combined, trending_input


# -----------------------------
# PHASE 5: CONTENT BRIEF GENERATION
# -----------------------------
def run_phase_5(content_gaps_combined, trending_input):
    """Generate content briefs"""
    
    print("\n" + "="*70)
    print("🚀 PHASE 5: CONTENT BRIEF GENERATION")
    print("="*70)
    
    tracker.update("brief_generation", total=1, completed=0, status="running")
    
    generator = ContentBriefGenerator(api_key=OPENAI_API_KEY)
    result = generator.generate_content_briefs(content_gaps_combined, trending_input)
    
    with open("data/content_briefs.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    tracker.update("brief_generation", completed=1, status="completed")
    print(f"✅ Saved {len(result)} generated briefs.")
    
    return result


# -----------------------------
# MAIN EXECUTION
# -----------------------------
if __name__ == "__main__":
    start_time = time.time()
    
    print("\n" + "="*70)
    print("🚀 CONTENT STRATEGY OPTIMIZER - PARALLEL EXECUTION")
    print("="*70)
    
    try:
        # Phase 1 & 2: Parallel data collection
        our_details, all_competitor_details, social_data = run_phase_1_and_2_parallel()
        
        # Phase 3 & 4: Parallel analysis
        content_gaps_combined, trending_input = run_phase_3_and_4_parallel(
            our_details, all_competitor_details, social_data
        )
        
        # Phase 5: Brief generation
        result = run_phase_5(content_gaps_combined, trending_input)
        
        # Final summary
        total_time = time.time() - start_time
        print("\n" + "="*70)
        print("🎉 PIPELINE COMPLETED SUCCESSFULLY")
        print("="*70)
        print(f"⏱️  Total Execution Time: {total_time:.2f}s ({total_time/60:.2f} minutes)")
        print(f"📊 Results:")
        print(f"   - Own pages scraped: {len(our_details)}")
        print(f"   - Competitors analyzed: {len(all_competitor_details)}")
        print(f"   - Social posts mined: {len(social_data)}")
        print(f"   - Trending clusters: {len(trending_input)}")
        print(f"   - Content gaps found: {len(content_gaps_combined)}")
        print(f"   - Content briefs generated: {len(result)}")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ Pipeline failed with error: {str(e)}")
        import traceback
        traceback.print_exc()