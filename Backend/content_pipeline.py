
import json
from datetime import datetime, time
import os
from dotenv import load_dotenv
import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from functools import partial
# import time
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
        self.start_time = datetime.now()
    
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
    
    # def _print_progress(self):
    #     elapsed = datetime.now() - self.start_time
    #     print(f"\n{'='*70}")
    #     print(f"⏱️  Elapsed Time: {elapsed:.1f}s")
    #     print(f"{'='*70}")
    #     for phase, data in self.phases.items():
    #         status_icon = "✅" if data["status"] == "completed" else "⏳" if data["status"] == "running" else "⏸️"
    #         if data["total"] > 0:
    #             pct = (data["completed"] / data["total"]) * 100
    #             bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
    #             print(f"{status_icon} {phase:20s} [{bar}] {data['completed']}/{data['total']} ({pct:.0f}%)")
    #         else:
    #             print(f"{status_icon} {phase:20s} [{data['status']}]")
    #     print(f"{'='*70}\n")
    
    def _print_progress(self):
        elapsed = (datetime.now() - self.start_time).total_seconds()
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
def scrape_site(url: str, scraper: WebScraper, keywords: List[str], start_date:str, end_date:str, is_own: bool = False) -> tuple:
    """Scrape a single site (own or competitor)"""
    try:
        site_type = "own site" if is_own else "competitor"
        print(f"🔍 Starting scrape: {url} ({site_type})")
        
        details = scraper.scrape(
            homepage_url=url,
            start_date=start_date,
            end_date=end_date,
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
def run_phase_1_and_2_parallel(our_url: str = "https://www.aicerts.ai/", 
                               competitors: List[str] = None,
                               keywords: List[str] = None):
    """Run sitemap scraping and social mining in parallel"""
    
    print("\n" + "="*70)
    print("🚀 PHASE 1 & 2: PARALLEL DATA COLLECTION")
    print("="*70)
    from datetime import datetime, timedelta
    # yesterday = datetime.now() - timedelta(days=1)
    # yesterday_str = yesterday.strftime("%Y-%m-%d")

    # Calculate date range
    yesterday = datetime.now() - timedelta(days=1)
    yesterday_str = yesterday.strftime("%Y-%m-%d")

    # Our site → last 30 days
    start_30_days = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    end_today = yesterday.strftime("%Y-%m-%d")

    # Competitor sites → only yesterday
    comp_start = yesterday_str
    comp_end = yesterday_str


    # Normalize to full-day range
    # start_date = datetime.combine(yesterday.date(), time.min)   # 00:00:00
    # end_date = datetime.combine(yesterday.date(), time.max)     # 23:59:59
    # Setup
    scraper = WebScraper(
        delay=0.1,
        timeout=10,
        max_pages=15,
        max_depth=1,
        max_concurrent=15
    )
    
    # our_url = "https://www.aicerts.ai/"
    # competitors = [
    #     "https://www.mygreatlearning.com",
    #     "https://www.coursera.org",
    #     "https://www.udemy.com",
    #     "https://www.simplilearn.com"
    # ]
    # keywords = ['course', 'certification', 'program']
    
    # Update progress
    tracker.update("sitemap_scraping", total=len(competitors) + 1, completed=0, status="running")
    tracker.update("social_mining", total=1, completed=0, status="running")
    
    # Use ThreadPoolExecutor for I/O-bound operations
    with ThreadPoolExecutor(max_workers=6) as executor:
        # Submit all scraping jobs
        future_to_url = {}
        
        # Submit our own site
        future = executor.submit(scrape_site, our_url, scraper, keywords, start_30_days, yesterday_str, True)
        future_to_url[future] = ("own", our_url)
        
        # Submit all competitor sites
        for comp_url in competitors:
            future = executor.submit(scrape_site, comp_url, scraper, keywords, yesterday_str, yesterday_str, False)
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
                
                keywords_social = keywords if keywords else ["AI", "artificial intelligence", "machine learning", "deep learning"]
                start_date = yesterday #datetime(2025, 10, 24)
                end_date = yesterday #datetime(2025, 10, 30)
                
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
# def run_phase_5(content_gaps_combined, trending_input):
#     """Generate content briefs"""
    
#     print("\n" + "="*70)
#     print("🚀 PHASE 5: CONTENT BRIEF GENERATION")
#     print("="*70)
    
#     tracker.update("brief_generation", total=1, completed=0, status="running")
    
#     generator = ContentBriefGenerator(api_key=OPENAI_API_KEY)
#     result = generator.generate_content_briefs(content_gaps_combined, trending_input)
    
#     with open("data/content_briefs.json", "w", encoding="utf-8") as f:
#         json.dump(result, f, indent=2, ensure_ascii=False)
    
#     tracker.update("brief_generation", completed=1, status="completed")
#     print(f"✅ Saved {len(result)} generated briefs.")
    
#     return result

def run_phase_5(content_gaps_combined, trending_input):
    """Generate content briefs (Phase 5) and save them to DB"""

    print("\n" + "="*70)
    print("🚀 PHASE 5: CONTENT BRIEF GENERATION")
    print("="*70)

    tracker.update("brief_generation", total=1, completed=0, status="running")

    generator = ContentBriefGenerator(api_key=OPENAI_API_KEY)

    # -----------------------------
    # 1️⃣ Generate Content Briefs
    # -----------------------------
    result = generator.generate_content_briefs(
        content_gaps_combined,
        trending_input
    )

    print(f"📦 Generated {len(result)} briefs.")

    # -----------------------------
    # 2️⃣ Save Each Brief to DB
    # -----------------------------
    from models import save_brief   # ⚠️ update import path
    # (where you pasted the script with Brief + BriefTalkingPoint)

    saved_ids = []
    for item in result:
        brief_id = save_brief(item)
        saved_ids.append(brief_id)

    print(f"💾 Saved {len(saved_ids)} briefs to database.")

    # -----------------------------
    # 3️⃣ Save JSON file (optional)
    # -----------------------------
    try:
        with open("data/content_briefs.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print("📂 content_briefs.json saved.")
    except Exception as e:
        print("❌ Error saving JSON:", e)

    # -----------------------------
    # 4️⃣ Update tracker & return
    # -----------------------------
    tracker.update("brief_generation", completed=1, status="completed")
    print("✅ Phase 5 completed.")

    return {
        "saved_brief_ids": saved_ids,
        "briefs": result
    }

# -----------------------------
# MAIN EXECUTION
# -----------------------------
if __name__ == "__main__":
    start_time = datetime.now()
    
    print("\n" + "="*70)
    print("🚀 CONTENT STRATEGY OPTIMIZER - PARALLEL EXECUTION")
    print("="*70)
    our_url = "https://www.aicerts.ai/"
    competitors = [
        "https://www.mygreatlearning.com",
        "https://www.coursera.org",
        "https://www.udemy.com",
        "https://www.simplilearn.com",
        "https://www.skillsoft.com"
    ]
    try:
        # Phase 1 & 2: Parallel data collection
        our_details, all_competitor_details, social_data = run_phase_1_and_2_parallel(our_url, competitors)
        
        # Phase 3 & 4: Parallel analysis
        content_gaps_combined, trending_input = run_phase_3_and_4_parallel(
            our_details, all_competitor_details, social_data
        )
        
        # Phase 5: Brief generation
        result = run_phase_5(content_gaps_combined, trending_input)
        
        # Final summary
        total_time = datetime.now() - start_time
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