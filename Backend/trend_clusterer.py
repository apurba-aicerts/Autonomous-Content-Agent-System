# trend_clusterer.py
import json
import logging
from datetime import datetime
from openai import OpenAI
from pydantic import BaseModel
from typing import List
import numpy as np
import matplotlib.pyplot as plt

import os
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)


class Cluster(BaseModel):
    cluster_name: str
    titles: List[str]


class ClusteredOutput(BaseModel):
    clusters: List[Cluster]


class TrendAnalyzer:
    WINDOW_DAYS = 14
    WEIGHTS = {
        "engagement": 0.4,
        "freshness": 0.35,
        "frequency": 0.25
    }

    def __init__(self, api_key: str):
        """Initialize with OpenAI API key."""
        self.client = OpenAI(api_key=api_key)
        logger.info("TrendAnalyzer initialized with provided API key.")

    # ===============================
    # Elbow Method
    # ===============================
    @staticmethod
    def elbow_threshold_detection(values, show_plot=False):
        """
        Detect the elbow (knee) point in a list of real numbers using
        the max-perpendicular-distance method.

        Args:
            values (iterable of float): real numbers (not necessarily sorted)
            show_plot (bool): whether to display the plot

        Returns:
            threshold (float): value at the elbow point
            elbow_index (int): index in the sorted array (descending)
            sorted_values (np.ndarray): sorted values (descending)
            selected_indices (list[int]): indices in sorted array where values >= threshold
        """
        arr = np.array(values, dtype=float)
        if arr.size == 0:
            raise ValueError("Input list is empty")

        # Sort values descending for a "long-tail" shape
        sorted_vals = np.sort(arr)[::-1]
        xs = np.arange(len(sorted_vals))

        # Line between first and last points
        x0, y0 = xs[0], sorted_vals[0]
        x1, y1 = xs[-1], sorted_vals[-1]

        dx = x1 - x0
        dy = y1 - y0
        denom = np.hypot(dx, dy)

        # Compute perpendicular distances from each point to line
        distances = np.abs(dx * (sorted_vals - y0) - dy * (xs - x0)) / denom
        elbow_idx = int(np.argmax(distances))
        threshold = float(sorted_vals[elbow_idx])
        selected_indices = list(np.where(sorted_vals >= threshold)[0])

        # Plot if requested
        if show_plot:
            plt.figure(figsize=(8, 5))
            plt.plot(xs, sorted_vals, 'b.-', label="Sorted relevance scores")
            plt.plot([x0, x1], [y0, y1], 'k--', label="Baseline line")
            plt.scatter(elbow_idx, threshold, color='red', s=80, zorder=5, 
                       label=f"Elbow = {threshold:.2f}")
            plt.axhline(threshold, color='red', linestyle=':', label="Threshold")
            plt.title("Elbow Point Detection for Trending Topics")
            plt.xlabel("Rank (sorted by relevance)")
            plt.ylabel("Relevance Score")
            plt.legend()
            plt.grid(True, linestyle='--', alpha=0.5)
            plt.tight_layout()
            plt.show()

        return threshold, elbow_idx, sorted_vals, selected_indices

    # ===============================
    # Utility Methods
    # ===============================
    @staticmethod
    def safe_date_parse(post):
        """Safely parse various date formats from post data."""
        try:
            if "created_utc" in post and post["created_utc"]:
                return datetime.fromisoformat(post["created_utc"].replace("Z", "+00:00"))
            elif "timestamp" in post and post["timestamp"]:
                return datetime.fromisoformat(post["timestamp"].replace("Z", "+00:00"))
            elif "post_date" in post and post["post_date"]:
                return datetime.fromisoformat(post["post_date"])
            else:
                return None
        except (ValueError, TypeError):
            return None

    def make_llm_call(self, prompt, response_model, max_retries=3):
        """Standardized LLM call with retry logic."""
        for attempt in range(max_retries):
            try:
                response = self.client.responses.parse(
                    model="gpt-4o-2024-08-06",
                    input=[{"role": "user", "content": prompt}],
                    text_format=response_model,
                    temperature=0.2
                )

                parsed = getattr(response, "output_parsed", None)
                if parsed is not None:
                    return parsed

                logger.warning(f"Retry {attempt+1}/{max_retries}: no parsed output")

            except Exception as e:
                logger.warning(f"Retry {attempt+1}/{max_retries}: API error: {e}")

        logger.error("Failed to get valid LLM response after all retries")
        return None

    # ===============================
    # NEW: Subreddit-wise Processing
    # ===============================
    @staticmethod
    def group_posts_by_subreddit(raw_data):
        """Group posts by subreddit."""
        subreddit_posts = {}
        
        for post in raw_data:
            if not isinstance(post, dict) or "title" not in post:
                logger.warning("Skipping invalid post structure")
                continue
            
            subreddit = post.get("subreddit", "unknown")
            if subreddit not in subreddit_posts:
                subreddit_posts[subreddit] = []
            subreddit_posts[subreddit].append(post)
        
        logger.info(f"Grouped posts into {len(subreddit_posts)} subreddits")
        return subreddit_posts

    def cluster_subreddit_posts(self, subreddit_name, posts):
        """
        Perform clustering for a single subreddit.
        
        Args:
            subreddit_name (str): Name of the subreddit
            posts (list): List of posts from this subreddit
            
        Returns:
            list: Cluster data with subreddit metadata
        """
        titles = [post["title"] for post in posts]
        
        prompt = f"""
You are a research assistant specializing in thematic analysis of social media content.

Task: Analyze these post titles from r/{subreddit_name} and group them into meaningful topic clusters.

Instructions:
1. Identify common themes, technologies, concepts, or discussion topics
2. Group similar titles together into clusters
3. Create descriptive cluster names (2-5 words)
4. Ensure each title is assigned to exactly one cluster
5. Aim for 5-15 clusters depending on content diversity
6. Focus on substantive themes, not superficial similarities

Titles to analyze:
{json.dumps(titles, indent=2)}
"""
        
        logger.info(f"Clustering {len(titles)} posts from r/{subreddit_name}...")
        result = self.make_llm_call(prompt, ClusteredOutput)
        
        if result is None:
            logger.error(f"Failed to cluster posts from r/{subreddit_name}")
            return []
        
        clusters_data = []
        for cluster in result.clusters:
            cluster_dict = cluster.model_dump() if hasattr(cluster, "model_dump") else cluster.dict()
            cluster_dict["subreddit"] = subreddit_name
            clusters_data.append(cluster_dict)
        
        logger.info(f"Created {len(clusters_data)} clusters from r/{subreddit_name}")
        return clusters_data

    @staticmethod
    def merge_clusters_globally(all_subreddit_clusters, posts_by_title):
        """
        Merge clusters with identical names across subreddits.
        
        Args:
            all_subreddit_clusters (list): List of all cluster dicts from all subreddits
            posts_by_title (dict): Mapping of title to post data
            
        Returns:
            list: Merged clusters with combined titles and posts
        """
        merged = {}
        
        for cluster in all_subreddit_clusters:
            cluster_name = cluster["cluster_name"]
            titles = cluster["titles"]
            
            if cluster_name not in merged:
                merged[cluster_name] = {
                    "cluster_name": cluster_name,
                    "titles": [],
                    "subreddits": set()
                }
            
            merged[cluster_name]["titles"].extend(titles)
            merged[cluster_name]["subreddits"].add(cluster.get("subreddit", "unknown"))
        
        # Convert to list and clean up
        merged_clusters = []
        for cluster_name, data in merged.items():
            merged_clusters.append({
                "cluster_name": cluster_name,
                "titles": data["titles"]
            })
        
        logger.info(f"Merged into {len(merged_clusters)} unique global clusters")
        return merged_clusters

    # ===============================
    # Core Analysis Steps (Modified)
    # ===============================
    @staticmethod
    def extract_titles_and_posts(raw_data):
        """Extract titles and create post lookup dictionary."""
        titles = []
        posts_by_title = {}

        for post in raw_data:
            if isinstance(post, dict) and "title" in post:
                title = post["title"]
                titles.append(title)
                posts_by_title[title] = post
            else:
                logger.warning("Skipping invalid post structure")

        logger.info(f"Extracted {len(titles)} valid titles for clustering")
        return titles, posts_by_title

    def perform_clustering(self, titles):
        """Use LLM to cluster similar titles into topic groups."""
        prompt = f"""
You are a research assistant specializing in thematic analysis of social media content.

Task: Analyze these post titles and group them into meaningful topic clusters.

Instructions:
1. Identify common themes, technologies, concepts, or discussion topics
2. Group similar titles together into clusters
3. Create descriptive cluster names (2-5 words)
4. Ensure each title is assigned to exactly one cluster
5. Aim for 5-15 clusters depending on content diversity
6. Focus on substantive themes, not superficial similarities

Titles to analyze:
{json.dumps(titles, indent=2)}
"""
        logger.info("Performing topic clustering via LLM...")
        result = self.make_llm_call(prompt, ClusteredOutput)
        if result is None:
            logger.error("Failed to perform clustering")
            return None

        clusters_data = []
        for cluster in result.clusters:
            cluster_dict = cluster.model_dump() if hasattr(cluster, "model_dump") else cluster.dict()
            clusters_data.append(cluster_dict)

        logger.info(f"Successfully clustered into {len(clusters_data)} topic groups")
        return clusters_data

    @classmethod
    def calculate_freshness_score(cls, posts, current_time):
        """Calculate freshness score based on post timestamps."""
        if not posts:
            return 0

        freshness_scores = []
        for post in posts:
            post_date = cls.safe_date_parse(post)
            if post_date:
                days_ago = (current_time - post_date).days
                post_freshness = max(((cls.WINDOW_DAYS - days_ago) / cls.WINDOW_DAYS) * 100, 0)
                freshness_scores.append(post_freshness)

        return sum(freshness_scores) / len(freshness_scores) if freshness_scores else 50

    @staticmethod
    def calculate_engagement_score(posts):
        """Calculate raw engagement score from post metrics."""
        if not posts:
            return 0

        total_engagement = 0
        for post in posts:
            upvotes = post.get('score', post.get('upvotes', 0))
            comments = post.get('num_comments', post.get('comments', 0))
            engagement = (upvotes * 0.7) + (comments * 0.3)
            total_engagement += engagement

        return total_engagement

    @classmethod
    def calculate_relevance_scores(cls, clusters_data, posts_by_title):
        """Calculate relevance scores for each cluster."""
        cluster_metrics = []
        current_time = datetime.now()

        for cluster in clusters_data:
            cluster_name = cluster["cluster_name"]
            cluster_titles = cluster["titles"]

            cluster_posts = [posts_by_title[title] for title in cluster_titles if title in posts_by_title]

            if not cluster_posts:
                continue

            frequency = len(cluster_posts)
            raw_engagement = cls.calculate_engagement_score(cluster_posts)
            freshness_score = cls.calculate_freshness_score(cluster_posts, current_time)

            cluster_metrics.append({
                "topic_cluster": cluster_name,
                "frequency": frequency,
                "raw_engagement": raw_engagement,
                "freshness_score": freshness_score,
                "post_count": len(cluster_posts)
            })

        max_engagement = max((c["raw_engagement"] for c in cluster_metrics), default=1)
        max_frequency = max((c["frequency"] for c in cluster_metrics), default=1)

        trending_topics = []
        for c in cluster_metrics:
            engagement_score = (c["raw_engagement"] / max_engagement) * 100 if max_engagement else 0
            normalized_frequency = (c["frequency"] / max_frequency) * 100 if max_frequency else 0

            relevance_score = (
                engagement_score * cls.WEIGHTS["engagement"] +
                c["freshness_score"] * cls.WEIGHTS["freshness"] +
                normalized_frequency * cls.WEIGHTS["frequency"]
            )

            trending_topics.append({
                "topic_cluster": c["topic_cluster"],
                "relevance_score": round(relevance_score, 2),
                "metrics": {
                    "freshness_score": round(c["freshness_score"], 2),
                    "engagement_score": round(engagement_score, 2),
                    "frequency": c["frequency"],
                    "total_engagement": c["raw_engagement"]
                }
            })

        trending_topics.sort(key=lambda x: x["relevance_score"], reverse=True)
        for i, topic in enumerate(trending_topics, 1):
            topic["rank"] = i

        return trending_topics, cluster_metrics

    def apply_elbow_filtering(self, trending_topics, show_plot=False):
        """
        Apply elbow method to filter trending topics based on relevance scores.
        
        Args:
            trending_topics (list): List of topic dictionaries with relevance_score
            show_plot (bool): Whether to display the elbow plot
            
        Returns:
            filtered_topics (list): Topics with relevance_score >= threshold
            threshold (float): The computed threshold value
        """
        if not trending_topics:
            logger.warning("No trending topics to filter")
            return [], 0.0
        
        if len(trending_topics) < 3:
            logger.info("Too few topics for elbow method, returning all")
            return trending_topics, 0.0
        
        # Extract relevance scores
        relevance_scores = [topic["relevance_score"] for topic in trending_topics]
        
        # Apply elbow method
        threshold, elbow_idx, sorted_vals, selected_indices = self.elbow_threshold_detection(
            relevance_scores, 
            show_plot=show_plot
        )
        
        # Filter topics above threshold
        filtered_topics = [
            topic for topic in trending_topics 
            if topic["relevance_score"] >= threshold
        ]
        
        logger.info(f"Elbow threshold: {threshold:.2f}")
        logger.info(f"Topics above threshold: {len(filtered_topics)}/{len(trending_topics)}")
        
        return filtered_topics, threshold

    @classmethod
    def generate_report(cls, trending_topics, cluster_metrics, total_titles, elbow_threshold=None):
        """Generate comprehensive trending topics report."""
        current_time = datetime.now()
        total_posts = sum(c["post_count"] for c in cluster_metrics)
        total_engagement = sum(c["raw_engagement"] for c in cluster_metrics)

        report = {
            "analysis_timestamp": current_time.isoformat(),
            "summary": {
                "total_clusters": len(cluster_metrics),
                "total_posts_analyzed": total_posts,
                "original_titles": total_titles,
                "total_engagement": total_engagement,
                "time_window_days": cls.WINDOW_DAYS,
                "topics_after_filtering": len(trending_topics)
            },
            "scoring_weights": cls.WEIGHTS,
            "trending_topics": trending_topics
        }
        
        if elbow_threshold is not None:
            report["elbow_threshold"] = round(elbow_threshold, 2)

        return report

    # ===============================
    # Main Entry Point (MODIFIED)
    # ===============================
    def run_from_data(self, raw_data: list, apply_elbow=True, show_plot=False):
        """
        Run trend analysis with subreddit-wise clustering.
        
        Args:
            raw_data (list): List of post dictionaries
            apply_elbow (bool): Whether to apply elbow method filtering
            show_plot (bool): Whether to show the elbow plot
            
        Returns:
            report (dict): Analysis report with filtered trending topics
        """
        logger.info("Starting subreddit-wise trend analysis...")

        if not raw_data or not isinstance(raw_data, list):
            raise ValueError("Input must be a non-empty list of post dictionaries")

        # Step 1: Create title-to-post mapping
        _, posts_by_title = self.extract_titles_and_posts(raw_data)
        if not posts_by_title:
            raise ValueError("No valid titles found in input data")

        # Step 2: Group posts by subreddit
        subreddit_posts = self.group_posts_by_subreddit(raw_data)

        # Step 3: Cluster each subreddit independently
        all_subreddit_clusters = []
        for subreddit_name, posts in subreddit_posts.items():
            clusters = self.cluster_subreddit_posts(subreddit_name, posts)
            all_subreddit_clusters.extend(clusters)

        if not all_subreddit_clusters:
            raise Exception("No clusters generated from any subreddit")

        # Save subreddit-wise clusters for inspection
        with open("data/social_trends_cluster.json", "w", encoding="utf-8") as f:
            json.dump(all_subreddit_clusters, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ Saved {len(all_subreddit_clusters)} subreddit-wise clusters")

        # Step 4: Merge clusters globally (exact name match)
        merged_clusters = self.merge_clusters_globally(all_subreddit_clusters, posts_by_title)

        # Step 5: Calculate relevance scores globally
        trending_topics, cluster_metrics = self.calculate_relevance_scores(merged_clusters, posts_by_title)
        
        # Step 6: Apply elbow filtering
        elbow_threshold = None
        if apply_elbow:
            trending_topics, elbow_threshold = self.apply_elbow_filtering(
                trending_topics, 
                show_plot=show_plot
            )
        
        # Step 7: Generate final report
        report = self.generate_report(trending_topics, cluster_metrics, len(posts_by_title), elbow_threshold)

        logger.info("Subreddit-wise trend analysis completed successfully.")
        return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from social_trend_miner import RedditTrendMiner
    
    miner = RedditTrendMiner(
        client_id="ydYRJCnXguV_6gTnnNjmww",
        client_secret="I-dyOgNW3dFKu8jWjemWDd6hPqvkFw",
        user_agent="AICertsContentAgent/1.0",
        max_workers=10
    )

    keywords = ["MachineLearning", "AI", "DataScience"]
    start_date = datetime(2025, 10, 24)
    end_date = datetime(2025, 10, 30)

    sample_data = miner.run(keywords, start_date, end_date, posts_limit=50, top_subs=3)

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    analyzer = TrendAnalyzer(api_key=OPENAI_API_KEY)
    
    # Run with elbow method filtering and plot
    report = analyzer.run_from_data(sample_data, apply_elbow=True, show_plot=False)
    print(json.dumps(report, indent=2))