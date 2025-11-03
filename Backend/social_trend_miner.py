#social_trend_miner.py for reddit
import json
import logging
from datetime import datetime
import praw
from prawcore.exceptions import NotFound, Forbidden, ResponseException
from concurrent.futures import ThreadPoolExecutor, as_completed

# -----------------------------
# LOGGING CONFIGURATION
# -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("RedditTrendMiner")


# -----------------------------
# CLASS: RedditTrendMiner
# -----------------------------
class RedditTrendMiner:
    def __init__(self, client_id: str, client_secret: str, user_agent: str, max_workers: int = 10):
        """
        Initialize RedditTrendMiner with Reddit API credentials.
        """
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        self.max_workers = max_workers
        logger.info("✅ RedditTrendMiner initialized successfully")

    # -------------------------
    # SEARCH SUBREDDITS BY KEYWORD
    # -------------------------
    def search_subreddits_by_keyword(self, keyword: str, limit: int = 10):
        subs = []
        try:
            for sub in self.reddit.subreddits.search(keyword, limit=limit):
                subs.append(sub.display_name)
        except Exception as e:
            logger.error(f"Error searching subreddits for '{keyword}': {e}")
        return subs

    # -------------------------
    # FETCH POSTS FROM SUBREDDIT
    # -------------------------
    def fetch_subreddit_posts(self, subreddit_name: str, start_date: datetime, end_date: datetime, posts_limit: int = 50):
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            _ = subreddit.display_name  # Verify subreddit exists

            start_ts = int(start_date.timestamp())
            end_ts = int(end_date.timestamp())

            posts = []
            for post in subreddit.new(limit=posts_limit):
                # if start_ts <= post.created_utc <= end_ts:
                posts.append({
                    "id": post.id,
                    "title": post.title,
                    "selftext": post.selftext,
                    "score": post.score,
                    "ups": post.ups,
                    "downs": post.downs,
                    "comments": post.num_comments,
                    "created_utc": datetime.fromtimestamp(post.created_utc).strftime("%Y-%m-%d %H:%M:%S"),
                    "subreddit": str(post.subreddit),
                    "url": f"https://www.reddit.com{post.permalink}"
                })

            logger.info(f"Fetched {len(posts)} posts from r/{subreddit_name}")
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

    # -------------------------
    # RUN METHOD (PARALLEL)
    # -------------------------
    def run(self, keywords, start_date, end_date, posts_limit=50, top_subs=5, output_file="social_trends_raw.json"):
        """
        Run trend mining across multiple subreddits in parallel.
        """
        all_posts = []
        subreddit_tasks = []

        # Step 1: Collect all subreddits for all keywords
        for keyword in keywords:
            subs = self.search_subreddits_by_keyword(keyword, limit=top_subs)
            logger.info(f"Subreddits for '{keyword}': {subs}")
            for sub in subs:
                subreddit_tasks.append((sub, start_date, end_date, posts_limit))

        # Step 2: Parallel fetching using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_sub = {
                executor.submit(self.fetch_subreddit_posts, sub, s, e, limit): sub
                for (sub, s, e, limit) in subreddit_tasks
            }

            for future in as_completed(future_to_sub):
                sub_name = future_to_sub[future]
                try:
                    posts = future.result()
                    all_posts.extend(posts)
                except Exception as e:
                    logger.error(f"Error processing r/{sub_name}: {e}")

        # Step 3: Save all results
        # with open(output_file, "w", encoding="utf-8") as f:
        #     json.dump(all_posts, f, indent=2, ensure_ascii=False)

        # logger.info(f"✅ Saved {len(all_posts)} posts to {output_file}")
        return all_posts


# -----------------------------
# EXAMPLE USAGE
# -----------------------------
if __name__ == "__main__":
    miner = RedditTrendMiner(
        client_id="ydYRJCnXguV_6gTnnNjmww",
        client_secret="I-dyOgNW3dFKu8jWjemWDd6hPqvkFw",
        user_agent="AICertsContentAgent/1.0",
        max_workers=10  # adjust threads here
    )

    keywords = ["Machine Learning", "AI", "DataScience"]
    start_date = datetime(2025, 10, 24)
    end_date = datetime(2025, 10, 31)

    data = miner.run(keywords, start_date, end_date, posts_limit=10, top_subs=3)
    # print(json.dumps(data, indent=2))
