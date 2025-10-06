import asyncio
import json
import time
import praw
import logging
from datetime import datetime
from prawcore.exceptions import NotFound, Forbidden, ResponseException
import os
from config import ensure_data_directory

logger = logging.getLogger(__name__)

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

# def load_config():
#     """Load configuration from config.json"""
#     try:
#         with open("config.json", "r", encoding="utf-8") as f:
#             return json.load(f)
#     except FileNotFoundError:
#         logger.error("config.json file not found!")
#         return None
#     except json.JSONDecodeError:
#         logger.error("Invalid JSON in config.json!")
#         return None

def load_config(session_dir=None):
    """Load configuration from config.json"""
    config_path = "config.json"
    if session_dir:
        config_path = os.path.join(session_dir, "config.json")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"{config_path} file not found!")
        return None
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in {config_path}!")
        return None


async def run_social_trend_miner(session_dir=None):
    """Main social trend miner agent function."""
    logger.info("Starting social trend miner agent...")
    
    try:
        config = load_config(session_dir=session_dir)
        if config is None:
            logger.error("Failed to load configuration")
            return False
        
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
            return False
        
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
        output_file = os.path.join(session_dir, "social_trends_raw.json")
        if all_posts:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(all_posts, f, indent=2, ensure_ascii=False)
            logger.info(f"Social trend miner completed successfully! {len(all_posts)} posts saved to {output_file}")
            return True
        else:
            logger.error("No posts collected from Reddit")
            return False
        
    except Exception as e:
        logger.error(f"Social trend miner agent failed: {e}")
        return False

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    asyncio.run(run_social_trend_miner())