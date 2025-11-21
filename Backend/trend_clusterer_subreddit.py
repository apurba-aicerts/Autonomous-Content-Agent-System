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
                    model="gpt-4o",
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
    # Subreddit-wise Processing (Optional)
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
            clusters_data.append(cluster_dict)
        
        logger.info(f"Created {len(clusters_data)} clusters from r/{subreddit_name}")
        return clusters_data

    @staticmethod
    def merge_clusters_globally(all_subreddit_clusters):
        """
        Merge clusters with identical names across subreddits.
        
        Args:
            all_subreddit_clusters (list): List of all cluster dicts from all subreddits
            
        Returns:
            list: Merged clusters with combined titles
        """
        merged = {}
        
        for cluster in all_subreddit_clusters:
            cluster_name = cluster["cluster_name"]
            titles = cluster["titles"]
            
            if cluster_name not in merged:
                merged[cluster_name] = {
                    "cluster_name": cluster_name,
                    "titles": []
                }
            
            merged[cluster_name]["titles"].extend(titles)
        
        # Convert to list
        merged_clusters = []
        for cluster_name, data in merged.items():
            merged_clusters.append({
                "cluster_name": cluster_name,
                "titles": data["titles"]
            })
        
        logger.info(f"Merged into {len(merged_clusters)} unique global clusters")
        return merged_clusters

    # ===============================
    # Core Analysis Steps
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
You are a research assistant specializing in thematic analysis of social media content for marketing intelligence.

Task: Analyze the provided post titles and organize them into meaningful topic clusters with highly informative, detail-rich cluster names.

Core Objective:
Create cluster names that serve as comprehensive summaries, enabling anyone to understand the cluster's complete scope without reading individual titles. Marketing teams should immediately grasp what specific technologies, models, companies, events, or topics are being discussed.

Instructions:
1. Identify common themes, technologies, methodologies, research areas, or discussion topics across the titles.
2. Group semantically similar titles together into coherent clusters.
3. Create information-dense cluster names (5-15 words) that capture ALL key specific details within the cluster.
4. Ensure each title is assigned to exactly one cluster.
5. Aim for 5-15 clusters depending on the diversity and granularity of the content.
6. Prioritize substantive thematic groupings over superficial keyword matches.

Cluster Naming Requirements (CRITICAL):
Cluster names MUST include specific, concrete identifiers that appear in the titles:

1. **Specific Model Names**: Never say "AI models" - say "Gemini 3, Claude on Azure, Qwen2.5-Omni"
2. **Specific Companies/Platforms**: Never say "tech companies" - say "Google, Microsoft Azure, Anthropic"
3. **Specific Technologies/Frameworks**: Never say "ML frameworks" - say "ONNX Runtime, CUDA, PyTorch, JetBrains PSI"
4. **Specific Job Roles/Companies**: Never say "data science jobs" - say "Marsh McLennan DS Internship, Expedia ML Scientist, Senior DS Interviews"
5. **Specific Events/Announcements**: Never say "recent developments" - say "Cloudflare Outage November 2025, Gemini 3 Launch, Tsinghua ICLR Paper Withdrawal"
6. **Specific Techniques/Methods**: Never say "training methods" - say "Post-training, Fine-tuning Multimodal LLMs, ONNX+CUDA GPU Acceleration"
7. **Specific Research Venues**: Never say "academic publishing" - say "arXiv Upload Timing, ACL/EMNLP Workshop Publications, ICLR Submissions"
8. **Specific Applications**: Never say "AI applications" - say "ECG Biosignal Synthesis, Invoice/Contract Data Extraction, Clean Water Access Solutions"

Cluster Name Construction Guidelines:
- Length: 5-15 words (prioritize completeness over brevity)
- Include ALL key specific nouns from the cluster (model names, company names, technologies, events)
- Use commas or "and" to list multiple specific items: "Gemini 3, Claude Azure Integration, and Qwen2.5-Omni Multimodal Fine-tuning"
- Be explicit: "Microsoft-Anthropic Partnership Bringing Claude to Azure" not "New AI Partnerships"
- Capture concrete details: "Marsh McLennan and Expedia DS/ML Interview Preparation and Career Transitions" not "Data Science Career Opportunities"
- If discussing techniques, name them: "LLM Post-training, Qwen2.5-Omni Multimodal Fine-tuning, and ONNX Runtime GPU Optimization"

Examples of Good vs Bad Cluster Names:
- ❌ BAD: "AI Model Development and Fine-Tuning"
- ✅ GOOD: "LLM Post-training and Qwen2.5-Omni Multimodal Fine-tuning with ONNX Runtime CUDA"

- ❌ BAD: "AI News and Developments"  
- ✅ GOOD: "Google Gemini 3 Launch, Microsoft-Anthropic Claude Azure Partnership, November 2025 Updates"

- ❌ BAD: "Career and Opportunities in AI"
- ✅ GOOD: "Marsh McLennan DS Internship, Expedia ML Scientist, Senior DS Interview Preparation, Backend to AI/ML Transitions"

- ❌ BAD: "AI Research and Papers"
- ✅ GOOD: "arXiv Upload Timing, ACL/EMNLP Workshop Publishing, Tsinghua ICLR Citation Integrity, OpenCodePapers Platform"

- ❌ BAD: "AI in Industry and Society"
- ✅ GOOD: "Anthropic CEO on AI Risk Disclosure, Google Sundar Pichai on AI Bubble and Job Automation, E-commerce Impact"

Exclusion Rule:
Completely exclude and do not cluster titles that are:
- Meaningless or nonsensical
- Meme-based or purely humorous content
- Pop culture references without technical substance
- Low-information or off-topic posts (e.g., "What if city was made of yarn?", "😬", "Pirate Booty")
- Random personal anecdotes unrelated to technical content

Do NOT create clusters for excluded content. Do NOT include such titles in any cluster. Simply omit them from the output entirely.

Output Format:
Return a JSON array of cluster objects. Each object should contain:
- "cluster_name": An information-dense, specific name capturing all key details (5-15 words)
- "titles": An array of post titles belonging to this cluster

Titles to Analyze:
{json.dumps(titles, indent=2)}

Critical Reminder: Marketing teams will use these cluster names for strategic planning. They need to see EXACTLY which models, companies, technologies, events, and roles are being discussed - not generic categories. Make every word in the cluster name count by being specific and concrete.
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
    def generate_report(cls, trending_topics, cluster_metrics, total_titles, elbow_threshold=None, clustering_mode="global"):
        """Generate comprehensive trending topics report."""
        current_time = datetime.now()
        total_posts = sum(c["post_count"] for c in cluster_metrics)
        total_engagement = sum(c["raw_engagement"] for c in cluster_metrics)

        report = {
            "analysis_timestamp": current_time.isoformat(),
            "summary": {
                "clustering_mode": clustering_mode,
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

    @classmethod
    def _get_default_report(cls):
        """Return default report structure when analysis fails or no data available."""
        current_time = datetime.now()
        return {
            "analysis_timestamp": current_time.isoformat(),
            "summary": {
                "clustering_mode": "global",
                "total_clusters": 0,
                "total_posts_analyzed": 0,
                "original_titles": 0,
                "total_engagement": 0,
                "time_window_days": cls.WINDOW_DAYS,
                "topics_after_filtering": 0
            },
            "scoring_weights": cls.WEIGHTS,
            "trending_topics": [],
            "elbow_threshold": 0.0
        }

    # ===============================
    # Main Entry Point
    # ===============================
    def run_from_data(self, raw_data: list, apply_elbow=True, show_plot=False, cluster_by_subreddit=False):
        """
        Run trend analysis with optional subreddit-wise clustering.
        
        Args:
            raw_data (list): List of post dictionaries
            apply_elbow (bool): Whether to apply elbow method filtering
            show_plot (bool): Whether to show the elbow plot
            cluster_by_subreddit (bool): Whether to cluster by subreddit (default: False)
            
        Returns:
            report (dict): Analysis report with filtered trending topics
        """
        try:
            logger.info(f"Starting trend analysis (cluster_by_subreddit={cluster_by_subreddit})...")

            # Validate input
            if not raw_data or not isinstance(raw_data, list):
                logger.warning("Input is empty or not a list. Returning default report.")
                return self._get_default_report()
            
            # Step 1: Create title-to-post mapping
            titles, posts_by_title = self.extract_titles_and_posts(raw_data)
            if not posts_by_title:
                logger.warning("No valid titles found. Returning default report.")
                return self._get_default_report()

            # Step 2: Perform clustering based on mode
            if cluster_by_subreddit:
                logger.info("Using subreddit-wise clustering mode")
                clustering_mode = "by_subreddit"
                
                # Group by subreddit
                subreddit_posts = self.group_posts_by_subreddit(raw_data)
                
                # Cluster each subreddit
                all_subreddit_clusters = []
                for subreddit_name, posts in subreddit_posts.items():
                    clusters = self.cluster_subreddit_posts(subreddit_name, posts)
                    all_subreddit_clusters.extend(clusters)
                
                if not all_subreddit_clusters:
                    logger.warning("No clusters generated. Returning default report.")
                    return self._get_default_report()
                
                # Merge clusters globally
                final_clusters = self.merge_clusters_globally(all_subreddit_clusters)
            else:
                logger.info("Using global clustering mode")
                clustering_mode = "global"
                
                # Cluster all titles at once
                final_clusters = self.perform_clustering(titles)
                
                if not final_clusters:
                    logger.warning("No clusters generated. Returning default report.")
                    return self._get_default_report()

            # Step 3: Save final clusters
            with open("data/social_trends_cluster.json", "w", encoding="utf-8") as f:
                json.dump(final_clusters, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ Saved {len(final_clusters)} final clusters")

            # Step 4: Calculate relevance scores
            trending_topics, cluster_metrics = self.calculate_relevance_scores(final_clusters, posts_by_title)
            
            if not trending_topics:
                logger.warning("No trending topics calculated. Returning default report.")
                return self._get_default_report()
            
            # Step 5: Apply elbow filtering
            elbow_threshold = None
            if apply_elbow:
                trending_topics, elbow_threshold = self.apply_elbow_filtering(
                    trending_topics, 
                    show_plot=show_plot
                )
            
            # Step 6: Generate final report
            report = self.generate_report(
                trending_topics, 
                cluster_metrics, 
                len(posts_by_title), 
                elbow_threshold,
                clustering_mode
            )

            logger.info("Trend analysis completed successfully.")
            return report

        except Exception as e:
            logger.error(f"Error during trend analysis: {e}")
            return self._get_default_report()


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
    start_date = datetime(2025, 11, 10)
    end_date = datetime(2025, 11, 10)
    # print(start_date, end_date)


    sample_data = miner.run(keywords, start_date, end_date, posts_limit=10, top_subs=3)
    print(json.dumps(sample_data, indent=2))

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    analyzer = TrendAnalyzer(api_key=OPENAI_API_KEY)
    
    # Run with global clustering (default)
    report = analyzer.run_from_data(sample_data, apply_elbow=True, show_plot=False)
    print(json.dumps(report, indent=2))
    
    # Or run with subreddit-wise clustering
    # report = analyzer.run_from_data(sample_data, apply_elbow=True, show_plot=False, cluster_by_subreddit=True)
    # print(json.dumps(report, indent=2))