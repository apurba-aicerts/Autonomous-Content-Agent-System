import asyncio
import aiohttp
import json
import time
import praw
import logging
from datetime import datetime
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from prawcore.exceptions import NotFound, Forbidden, ResponseException
import re
import os
from config import ensure_data_directory

# ------------------- LOGGING -------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ------------------- CONFIG -------------------
def load_config():
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("config.json file not found!")
        return None
    except json.JSONDecodeError:
        logger.error("Invalid JSON in config.json!")
        return None

# ------------------- FILTERING -------------------
SKIP_PATTERNS = [
    '/admin/', '/wp-admin/', '/privacy/', '/terms/', '/legal/',
    '/contact/', '/about-us/', '/sitemap', '/feed/', '/rss/',
    '.pdf', '.jpg', '.png', '.gif', '.mp4', '.zip', '.doc'
]

def should_skip_url(url):
    """Filter out URLs that are unlikely to contain useful content."""
    url_lower = url.lower()
    return any(pattern in url_lower for pattern in SKIP_PATTERNS)

# ------------------- ASYNC SITEMAP CRAWLER -------------------
async def fetch_sitemap_urls_async(session, sitemap_url):
    """Fetch and parse sitemap to extract URLs."""
    urls = []
    try:
        logger.info(f"Fetching sitemap: {sitemap_url}")
        async with session.get(sitemap_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                content = await response.text()
                root = ET.fromstring(content)
                
                # Try with namespace first
                for url_elem in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}url"):
                    loc_elem = url_elem.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
                    if loc_elem is not None and not should_skip_url(loc_elem.text):
                        urls.append(loc_elem.text)
                
                # Fallback without namespace
                if not urls:
                    for loc in root.findall(".//loc"):
                        if loc.text and not should_skip_url(loc.text):
                            urls.append(loc.text)
                            
    except Exception as e:
        logger.error(f"Failed to fetch sitemap {sitemap_url}: {e}")
    
    logger.info(f"Extracted {len(urls)} URLs from {sitemap_url}")
    return urls

async def extract_title_async(session, url, semaphore):
    """Extract title from a single URL with concurrency control."""
    async with semaphore:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as response:
                if response.status == 200:
                    # Check content type
                    content_type = response.headers.get('content-type', '').lower()
                    if 'text/html' not in content_type:
                        return None
                    
                    # Read content in chunks and stop early if we find title
                    content = ""
                    async for chunk in response.content.iter_chunked(1024):
                        content += chunk.decode('utf-8', errors='ignore')
                        # Stop reading if we have the head section
                        if '</head>' in content.lower() or len(content) > 50000:
                            break
                    
                    # Extract title
                    soup = BeautifulSoup(content, "html.parser")
                    title_tag = soup.find("title")
                    if title_tag:
                        title = title_tag.get_text().strip()
                        if title:
                            return title
                    
                    # Fallback to meta title
                    meta_title = soup.find("meta", property="og:title")
                    if meta_title and meta_title.get("content"):
                        return meta_title["content"].strip()
                        
        except asyncio.TimeoutError:
            logger.warning(f"Timeout for {url}")
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
        
        return None

async def process_titles_batch(session, urls, batch_size=50, progress_callback=None):
    """Process URLs in batches with progress reporting."""
    semaphore = asyncio.Semaphore(batch_size)
    titles = []
    failed_urls = []
    
    total_urls = len(urls)
    processed = 0
    
    # Process in batches to avoid overwhelming the system
    for i in range(0, total_urls, batch_size):
        batch = urls[i:i + batch_size]
        
        # Create tasks for this batch
        tasks = [extract_title_async(session, url, semaphore) for url in batch]
        
        # Process batch
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for j, result in enumerate(batch_results):
            url = batch[j]
            if isinstance(result, Exception):
                failed_urls.append(url)
            elif result:
                titles.append(result)
            else:
                failed_urls.append(url)
            
            processed += 1
            if progress_callback and processed % 20 == 0:
                progress_callback(processed, total_urls)
    
    return titles, failed_urls

async def retry_failed_urls(session, failed_urls, max_concurrent=10):
    """Retry failed URLs with lower concurrency."""
    if not failed_urls:
        return []
    
    logger.info(f"Retrying {len(failed_urls)} failed URLs...")
    semaphore = asyncio.Semaphore(max_concurrent)
    
    tasks = [extract_title_async(session, url, semaphore) for url in failed_urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    titles = [result for result in results if isinstance(result, str) and result]
    return titles

async def run_sitemap_agent_async(config):
    """Async version of sitemap agent with massive performance improvements."""
    own_sitemap_url = config.get("own_sitemap_url")
    competitor_sitemaps = config.get("competitor_sitemaps", [])
    
    if not own_sitemap_url:
        logger.error("'own_sitemap_url' not found in config.json")
        return {}
    
    # Configure session with connection pooling
    connector = aiohttp.TCPConnector(
        limit=100,  # Total connection pool size
        limit_per_host=20,  # Max connections per host
        ttl_dns_cache=300,
        use_dns_cache=True,
    )
    
    timeout = aiohttp.ClientTimeout(total=30)
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; AICartsContentAgent/2.0)'}
    
    sitemap_data = {}
    
    async with aiohttp.ClientSession(
        connector=connector, 
        timeout=timeout, 
        headers=headers
    ) as session:
        
        # Fetch all sitemaps concurrently
        all_sitemaps = [own_sitemap_url] + competitor_sitemaps
        sitemap_tasks = [fetch_sitemap_urls_async(session, url) for url in all_sitemaps]
        sitemap_results = await asyncio.gather(*sitemap_tasks)
        
        # Separate own vs competitor URLs
        own_urls = sitemap_results[0] if sitemap_results else []
        competitor_urls = []
        for i in range(1, len(sitemap_results)):
            competitor_urls.extend(sitemap_results[i])
        
        # Remove duplicates
        own_urls = list(set(own_urls))
        competitor_urls = list(set(competitor_urls))
        
        logger.info(f"Total URLs to process: {len(own_urls)} (own), {len(competitor_urls)} (competitors)")
        
        # Progress callback
        def progress_callback(processed, total):
            percentage = (processed / total) * 100
            logger.info(f"Progress: {processed}/{total} ({percentage:.1f}%)")
        
        # Process own titles
        logger.info("Processing AI Certs titles...")
        start_time = time.time()
        own_titles, own_failed = await process_titles_batch(
            session, own_urls, batch_size=50, progress_callback=progress_callback
        )
        
        # Retry failed ones
        if own_failed:
            retry_titles = await retry_failed_urls(session, own_failed)
            own_titles.extend(retry_titles)
        
        elapsed = time.time() - start_time
        logger.info(f"Own titles completed in {elapsed:.1f}s: {len(own_titles)} titles")
        
        # Process competitor titles
        logger.info("Processing competitor titles...")
        start_time = time.time()
        competitor_titles, competitor_failed = await process_titles_batch(
            session, competitor_urls, batch_size=50, progress_callback=progress_callback
        )
        
        # Retry failed ones
        if competitor_failed:
            retry_titles = await retry_failed_urls(session, competitor_failed)
            competitor_titles.extend(retry_titles)
        
        elapsed = time.time() - start_time
        logger.info(f"Competitor titles completed in {elapsed:.1f}s: {len(competitor_titles)} titles")
        
        # Prepare results
        sitemap_data = {
            "ai_certs_titles": own_titles,
            "competitor_titles": competitor_titles
        }
    
    # Save results to data directory
    output_file = os.path.join("data", "sitemaps_data.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(sitemap_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Async sitemap crawling completed! Data saved to {output_file}")
    return sitemap_data

# ------------------- ASYNC REDDIT SCRAPER -------------------
async def fetch_subreddit_posts_async(reddit, subreddit_name, posts_limit):
    """Fetch posts from a single subreddit."""
    try:
        logger.info(f"Fetching top {posts_limit} posts from r/{subreddit_name}...")
        subreddit = reddit.subreddit(subreddit_name)
        
        # Verify subreddit exists
        _ = subreddit.display_name
        
        posts = []
        posts_fetched = 0
        
        for post in subreddit.top(time_filter="week", limit=posts_limit):
            post_data = {
                "title": post.title,
                "score": post.score,
                "comments": post.num_comments,
                "url": post.url,
                "source": f"r/{subreddit_name}",
                "created_utc": datetime.fromtimestamp(post.created_utc).strftime("%Y-%m-%d %H:%M:%S"),
            }
            posts.append(post_data)
            posts_fetched += 1
        
        logger.info(f"Fetched {posts_fetched} posts from r/{subreddit_name}")
        return posts
        
    except NotFound:
        logger.warning(f"Subreddit r/{subreddit_name} not found or is private")
        return []
    except Forbidden:
        logger.warning(f"Access forbidden to r/{subreddit_name}")
        return []
    except ResponseException as e:
        logger.error(f"API error for r/{subreddit_name}: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error for r/{subreddit_name}: {e}")
        return []

async def run_reddit_agent_async(config):
    """Async version of Reddit agent with parallel subreddit processing."""
    reddit_config = config.get("reddit", {})
    subreddits = reddit_config.get("reddit_subreddits", ["MachineLearning", "artificial"])
    posts_limit = reddit_config.get("posts_limit", 50)
    
    try:
        reddit = praw.Reddit(
            client_id=reddit_config["client_id"],
            client_secret=reddit_config["client_secret"],
            user_agent=reddit_config["user_agent"]
        )
        logger.info("Successfully initialized Reddit API connection")
    except KeyError as e:
        logger.error(f"Missing Reddit config key: {e}")
        return []
    
    # Process all subreddits concurrently using asyncio with blocking calls
    loop = asyncio.get_event_loop()
    tasks = []
    
    for subreddit_name in subreddits:
        # Run Reddit API calls in thread pool since PRAW is synchronous
        task = loop.run_in_executor(
            None, 
            lambda sub=subreddit_name: asyncio.run(fetch_subreddit_posts_async(reddit, sub, posts_limit))
        )
        tasks.append(task)
    
    # Wait for all subreddit tasks to complete
    subreddit_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Flatten results
    all_posts = []
    for result in subreddit_results:
        if isinstance(result, list):
            all_posts.extend(result)
        elif isinstance(result, Exception):
            logger.error(f"Subreddit processing failed: {result}")
    
    # Save results to data directory
    output_file = os.path.join("data", "social_trends_raw.json")
    if all_posts:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_posts, f, indent=2, ensure_ascii=False)
        logger.info(f"Reddit scraping completed! {len(all_posts)} posts saved to {output_file}")
    
    return all_posts

# ------------------- MAIN ASYNC ORCHESTRATOR -------------------
async def main_async():
    """Main async orchestrator with parallel execution."""
    logger.info("=== OPTIMIZED DATA COLLECTION AGENT STARTED ===")
    start_time = time.time()
    
    # Ensure data directory exists
    ensure_data_directory()
    
    config = load_config()
    if config is None:
        return
    
    # Run sitemap and Reddit agents concurrently
    logger.info("Starting parallel data collection...")
    
    sitemap_task = asyncio.create_task(run_sitemap_agent_async(config))
    reddit_task = asyncio.create_task(run_reddit_agent_async(config))
    
    # Wait for both to complete
    sitemap_data, reddit_data = await asyncio.gather(sitemap_task, reddit_task)
    
    # Performance metrics
    total_time = time.time() - start_time
    logger.info("=== OPTIMIZED DATA COLLECTION AGENT COMPLETED ===")
    logger.info(f"Total execution time: {total_time:.1f} seconds")
    logger.info(f"Sitemap titles collected: {len(sitemap_data.get('ai_certs_titles', []))} (own), {len(sitemap_data.get('competitor_titles', []))} (competitors)")
    logger.info(f"Reddit posts collected: {len(reddit_data)}")
    
    # Performance improvement calculation
    if total_time > 0:
        estimated_old_time = 30 * 60  # 30 minutes
        speedup = estimated_old_time / total_time
        logger.info(f"Estimated speedup: {speedup:.1f}x faster than original version")

def main():
    """Synchronous entry point."""
    asyncio.run(main_async())

def run_data_collection():
    """Wrapper function for orchestrator integration."""
    logger.info("Starting data collection process...")
    try:
        main()
        logger.info("Data collection completed successfully")
        return True
    except Exception as e:
        logger.error(f"Data collection failed: {e}")
        raise

if __name__ == "__main__":
    main()