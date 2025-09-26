import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import json
import time
import praw
import logging
from prawcore.exceptions import NotFound, Forbidden, ResponseException
from datetime import datetime

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

# ------------------- SITEMAP CRAWLER -------------------
def fetch_sitemap_urls(sitemap_url):
    urls = []
    try:
        logger.info(f"Fetching sitemap: {sitemap_url}")
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; AICartsContentAgent/1.0)'}
        r = requests.get(sitemap_url, timeout=10, headers=headers)
        r.raise_for_status()
        root = ET.fromstring(r.text)

        # Try with namespace first
        for url_elem in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}url"):
            loc_elem = url_elem.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
            if loc_elem is not None:
                urls.append(loc_elem.text)

        # Fallback without namespace
        if not urls:
            for loc in root.findall(".//loc"):
                urls.append(loc.text)

    except Exception as e:
        logger.error(f"Failed to fetch or parse sitemap {sitemap_url}: {e}")
    return urls


def fetch_page_titles(url_list):
    titles = []
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; AICartsContentAgent/1.0)'}

    logger.info(f"Extracting titles from {len(url_list)} pages...")

    for i, url in enumerate(url_list):
        try:
            r = requests.get(url, timeout=5, headers=headers)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                title_tag = soup.find("title")
                if title_tag:
                    titles.append(title_tag.text.strip())

            if (i + 1) % 50 == 0:
                logger.info(f"Processed {i + 1}/{len(url_list)} URLs...")

            if i > 0 and i % 20 == 0:
                time.sleep(1)

        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")

    return titles


def run_sitemap_agent(config):
    own_sitemap_url = config.get("own_sitemap_url")
    competitor_sitemaps = config.get("competitor_sitemaps", [])

    if not own_sitemap_url:
        logger.error("'own_sitemap_url' not found in config.json")
        return {}

    sitemap_data = {}

    # Process own sitemap
    logger.info("Processing AI Certs sitemap...")
    urls = fetch_sitemap_urls(own_sitemap_url)
    logger.info(f"Found {len(urls)} URLs.")
    titles = fetch_page_titles(urls)
    logger.info(f"Extracted {len(titles)} titles.")
    sitemap_data["ai_certs_titles"] = titles

    # Process competitor sitemaps
    all_competitor_titles = []
    for sitemap_url in competitor_sitemaps:
        logger.info(f"Processing competitor sitemap: {sitemap_url}")
        urls = fetch_sitemap_urls(sitemap_url)
        logger.info(f"Found {len(urls)} URLs.")
        titles = fetch_page_titles(urls)
        logger.info(f"Extracted {len(titles)} titles.")
        all_competitor_titles.extend(titles)

    sitemap_data["competitor_titles"] = all_competitor_titles

    # Save
    with open("sitemaps_data.json", "w", encoding="utf-8") as f:
        json.dump(sitemap_data, f, indent=2, ensure_ascii=False)

    logger.info("Sitemap crawling completed! Data saved to sitemaps_data.json")
    return sitemap_data

# ------------------- REDDIT SCRAPER -------------------
def run_reddit_agent(config):
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

    all_posts = []

    for subreddit_name in subreddits:
        try:
            logger.info(f"Fetching top {posts_limit} posts from r/{subreddit_name}...")
            subreddit = reddit.subreddit(subreddit_name)
            _ = subreddit.display_name

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
                all_posts.append(post_data)
                posts_fetched += 1

            logger.info(f"Fetched {posts_fetched} posts from r/{subreddit_name}")
            time.sleep(1)

        except NotFound:
            logger.warning(f"Subreddit r/{subreddit_name} not found or is private")
        except Forbidden:
            logger.warning(f"Access forbidden to r/{subreddit_name}")
        except ResponseException as e:
            logger.error(f"API error for r/{subreddit_name}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error for r/{subreddit_name}: {e}")

    if all_posts:
        with open("social_trends_raw.json", "w", encoding="utf-8") as f:
            json.dump(all_posts, f, indent=2, ensure_ascii=False)
        logger.info(f"Reddit scraping completed! {len(all_posts)} posts saved to social_trends_raw.json")

    return all_posts

# ------------------- MAIN -------------------
def main():
    logger.info("=== DATA COLLECTION AGENT STARTED ===")

    config = load_config()
    if config is None:
        return

    sitemap_data = run_sitemap_agent(config)
    reddit_data = run_reddit_agent(config)

    logger.info("=== DATA COLLECTION AGENT COMPLETED ===")
    logger.info(f"Sitemaps titles collected: {len(sitemap_data.get('ai_certs_titles', []))} (own), {len(sitemap_data.get('competitor_titles', []))} (competitors)")
    logger.info(f"Reddit posts collected: {len(reddit_data)}")

if __name__ == "__main__":
    main()
