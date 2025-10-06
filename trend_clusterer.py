import json
import logging
import os
from datetime import datetime
from openai import OpenAI
from pydantic import BaseModel
from typing import List
from config import get_config, ensure_data_directory

logger = logging.getLogger(__name__)

# Configuration constants
WINDOW_DAYS = 14
WEIGHTS = {
    "engagement": 0.4,    # 40% - User interaction importance
    "freshness": 0.35,    # 35% - Recency importance  
    "frequency": 0.25     # 25% - Topic frequency importance
}

# Pydantic models for structured LLM output
class Cluster(BaseModel):
    cluster_name: str
    titles: List[str]

class ClusteredOutput(BaseModel):
    clusters: List[Cluster]

def make_llm_call(prompt, response_model, max_retries=3):
    """Standardized LLM call with retry logic."""
    client = OpenAI()
    
    for attempt in range(max_retries):
        try:
            response = client.responses.parse(
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

def safe_date_parse(post):
    """Safely parse various date formats from post data"""
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

def calculate_freshness_score(posts, current_time):
    """Calculate freshness score based on post timestamps"""
    if not posts:
        return 0
    
    freshness_scores = []
    for post in posts:
        post_date = safe_date_parse(post)
        if post_date:
            days_ago = (current_time - post_date).days
            # Score decreases linearly over time window
            post_freshness = max(((WINDOW_DAYS - days_ago) / WINDOW_DAYS) * 100, 0)
            freshness_scores.append(post_freshness)
    
    return sum(freshness_scores) / len(freshness_scores) if freshness_scores else 50

def calculate_engagement_score(posts):
    """Calculate raw engagement score from post metrics"""
    if not posts:
        return 0
    
    total_engagement = 0
    for post in posts:
        # Handle different engagement field names
        upvotes = post.get('score', post.get('upvotes', 0))
        comments = post.get('num_comments', post.get('comments', 0))
        
        # Weighted engagement: upvotes worth more than comments
        engagement = (upvotes * 0.7) + (comments * 0.3)
        total_engagement += engagement
    
    return total_engagement

def load_social_data(session_dir=None):
    """Load raw social media data from file."""
    input_file = os.path.join("data", "social_trends_raw.json")
    if session_dir:
        input_file = os.path.join(session_dir, "social_trends_raw.json")

    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Loaded social data from {input_file}")
        return data
    except FileNotFoundError:
        logger.error(f"Required file not found: {input_file}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {input_file}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading {input_file}: {e}")
        raise

def extract_titles_and_posts(raw_data):
    """Extract titles and create post lookup dictionary"""
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

def perform_clustering(titles):
    """Use LLM to cluster similar titles into topic groups"""
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
    result = make_llm_call(prompt, ClusteredOutput)
    
    if result is None:
        logger.error("Failed to perform clustering")
        return None
    
    # Convert to dict format
    clusters_data = []
    for cluster in result.clusters:
        cluster_dict = cluster.model_dump() if hasattr(cluster, "model_dump") else cluster.dict()
        clusters_data.append(cluster_dict)
    
    logger.info(f"Successfully clustered into {len(clusters_data)} topic groups")
    return clusters_data

def calculate_relevance_scores(clusters_data, posts_by_title):
    """Calculate relevance scores for each cluster"""
    cluster_metrics = []
    current_time = datetime.now()
    
    # First pass: calculate raw metrics
    for cluster in clusters_data:
        cluster_name = cluster["cluster_name"]
        cluster_titles = cluster["titles"]
        
        # Get posts for this cluster
        cluster_posts = []
        for title in cluster_titles:
            if title in posts_by_title:
                cluster_posts.append(posts_by_title[title])
        
        if not cluster_posts:
            continue
        
        # Calculate metrics
        frequency = len(cluster_posts)
        raw_engagement = calculate_engagement_score(cluster_posts)
        freshness_score = calculate_freshness_score(cluster_posts, current_time)
        
        cluster_metrics.append({
            "topic_cluster": cluster_name,
            "frequency": frequency,
            "raw_engagement": raw_engagement,
            "freshness_score": freshness_score,
            "post_count": len(cluster_posts)
        })
    
    # Find max values for normalization
    max_engagement = max((c["raw_engagement"] for c in cluster_metrics), default=1)
    max_frequency = max((c["frequency"] for c in cluster_metrics), default=1)
    
    logger.info(f"Normalization factors - Max engagement: {max_engagement}, Max frequency: {max_frequency}")
    
    # Second pass: normalize and calculate final relevance scores
    trending_topics = []
    for c in cluster_metrics:
        # Normalize engagement and frequency to 0-100 scale
        engagement_score = (c["raw_engagement"] / max_engagement) * 100 if max_engagement else 0
        normalized_frequency = (c["frequency"] / max_frequency) * 100 if max_frequency else 0
        
        # Calculate weighted relevance score
        relevance_score = (
            engagement_score * WEIGHTS["engagement"] +
            c["freshness_score"] * WEIGHTS["freshness"] +
            normalized_frequency * WEIGHTS["frequency"]
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
    
    # Sort by relevance score (highest first) and add rankings
    trending_topics.sort(key=lambda x: x["relevance_score"], reverse=True)
    for i, topic in enumerate(trending_topics, 1):
        topic["rank"] = i
    
    return trending_topics, cluster_metrics

def generate_report(trending_topics, cluster_metrics, total_titles):
    """Generate comprehensive trending topics report"""
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
            "time_window_days": WINDOW_DAYS
        },
        "scoring_weights": WEIGHTS,
        "trending_topics": trending_topics
    }
    
    return report

def save_clustering_results(clusters_data, session_dir=None):
    """Save raw clustering results"""
    output_file = os.path.join("data", "social_trends_clusters.json")
    if session_dir:
        output_file = os.path.join(session_dir, "social_trends_clusters.json")
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(clusters_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Clustering results saved to {output_file}")
        return True
    except Exception as e:
        logger.error(f"Failed to save clustering results: {e}")
        return False

def save_trending_report(report, session_dir=None):
    """Save trending topics report"""
    output_file = os.path.join("data", "trending_topics_report.json")
    if session_dir:
        output_file = os.path.join(session_dir, "trending_topics_report.json")
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"Trending topics report saved to {output_file}")
        return True
    except Exception as e:
        logger.error(f"Failed to save trending report: {e}")
        return False

def validate_inputs(session_dir=None):
    """Validate that required input files exist"""
    input_file = os.path.join("data", "social_trends_raw.json")
    if session_dir:
        input_file = os.path.join(session_dir, "social_trends_raw.json")
    if not os.path.exists(input_file):
        logger.error(f"Required input file missing: {input_file}")
        return False
    
    # Validate file content
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if not data or not isinstance(data, list):
            logger.error("Invalid raw data format - expected list of posts")
            return False
        
        valid_posts = 0
        for post in data:
            if isinstance(post, dict) and "title" in post:
                valid_posts += 1
        
        if valid_posts == 0:
            logger.error("No valid posts found in data")
            return False
        
        logger.info(f"Input validation passed - found {valid_posts} valid posts out of {len(data)} total")
        return True
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in input file: {e}")
        return False
    except Exception as e:
        logger.error(f"Error validating inputs: {e}")
        return False

def print_summary(report):
    """Print analysis summary"""
    trending_topics = report["trending_topics"]
    summary = report["summary"]
    
    logger.info("="*50)
    logger.info("TRENDING TOPICS ANALYSIS SUMMARY")
    logger.info("="*50)
    
    logger.info(f"Total clusters identified: {summary['total_clusters']}")
    logger.info(f"Total posts analyzed: {summary['total_posts_analyzed']}")
    logger.info(f"Total engagement: {summary['total_engagement']:,}")
    logger.info(f"Analysis time window: {summary['time_window_days']} days")
    
    logger.info("\nTop 5 trending topics:")
    for topic in trending_topics[:5]:
        logger.info(f"  {topic['rank']}. {topic['topic_cluster']} (Score: {topic['relevance_score']})")

def run_trend_analysis(session_dir=None):
    """Main function to run trend clustering and analysis"""
    logger.info("Starting trend analysis process...")
    
    # Ensure data directory exists
    ensure_data_directory(session_dir=session_dir)
    
    # Validate inputs
    if not validate_inputs(session_dir=session_dir):
        logger.error("Input validation failed - stopping trend analysis")
        raise ValueError("Input validation failed")
    
    try:
        # Load raw social data
        raw_data = load_social_data(session_dir=session_dir)
        
        # Extract titles and create lookup
        titles, posts_by_title = extract_titles_and_posts(raw_data)
        
        if not titles:
            logger.error("No valid titles found to process")
            raise ValueError("No valid titles found")
        
        # Perform clustering
        clusters_data = perform_clustering(titles)
        if not clusters_data:
            raise Exception("Clustering failed")
        
        # Calculate relevance scores and rankings
        trending_topics, cluster_metrics = calculate_relevance_scores(clusters_data, posts_by_title)
        
        # Generate comprehensive report
        report = generate_report(trending_topics, cluster_metrics, len(titles))
        
        # Save outputs
        if not save_clustering_results(clusters_data, session_dir):
            raise Exception("Failed to save clustering results")
        
        if not save_trending_report(report, session_dir):
            raise Exception("Failed to save trending report")
        
        # Print summary
        print_summary(report)
        
        logger.info("Trend analysis completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Trend analysis failed: {e}")
        raise

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        run_trend_analysis()
        logger.info("Trend analysis module executed successfully")
    except Exception as e:
        logger.error(f"Trend analysis module failed: {e}")
        exit(1)