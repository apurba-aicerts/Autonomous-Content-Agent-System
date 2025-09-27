#!/usr/bin/env python3
"""
COMBINED TREND CLUSTERING & RANKING AGENT

Purpose: Analyze raw social data, identify topic clusters, and rank them by relevance.
Input: social_trends_raw.json
Output: trending_topics_report.json with clustered and ranked topics
"""

import json
import re
from datetime import datetime
from openai import OpenAI

# ==================== CONFIGURATION ====================
WINDOW_DAYS = 14
WEIGHTS = {
    "engagement": 0.4,    # 40% - User interaction importance
    "freshness": 0.35,    # 35% - Recency importance  
    "frequency": 0.25     # 25% - Topic frequency importance
}

# OpenAI settings
OPENAI_MODEL = "gpt-4o-mini"
TEMPERATURE = 0.2
MAX_TOKENS = 4000

from pydantic import BaseModel
from typing import List

class Cluster(BaseModel):
    cluster_name: str
    titles: List[str]

class ClusteredOutput(BaseModel):
    clusters: List[Cluster]

# ==================== UTILITY FUNCTIONS ====================

def clean_json_response(response_text):
    """Clean and extract JSON from LLM response that might be wrapped in markdown"""
    response_text = re.sub(r'```json\s*', '', response_text)
    response_text = re.sub(r'```\s*$', '', response_text)
    return response_text.strip()

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

# ==================== MAIN AGENT CLASS ====================

class TrendClusteringAgent:
    def __init__(self):
        self.client = OpenAI()
        self.current_time = datetime.now()
        
    def load_raw_data(self, filename="social_trends_raw.json"):
        """Load and validate raw social media data"""
        try:
            with open(filename, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            
            if not raw_data or not isinstance(raw_data, list):
                raise ValueError("Invalid raw data format - expected list of posts")
            
            print(f"✅ Loaded {len(raw_data)} posts from {filename}")
            return raw_data
            
        except FileNotFoundError:
            print(f"❌ Error: {filename} not found")
            return None
        except json.JSONDecodeError:
            print(f"❌ Error: Invalid JSON in {filename}")
            return None
    
    def extract_titles_and_posts(self, raw_data):
        """Extract titles and create post lookup dictionary"""
        titles = []
        posts_by_title = {}
        
        for post in raw_data:
            if isinstance(post, dict) and "title" in post:
                title = post["title"]
                titles.append(title)
                posts_by_title[title] = post
            else:
                print(f"⚠️  Warning: Skipping invalid post structure")
        
        print(f"📊 Extracted {len(titles)} valid titles for clustering")
        return titles, posts_by_title
    

    def perform_clustering(self, titles):
        """Use LLM to cluster similar titles into topic groups with structured output"""
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

        try:
            print("🤖 Calling OpenAI API for structured clustering...")

            response = self.client.responses.parse(
                model=OPENAI_MODEL,
                input=[{"role": "user", "content": prompt}],
                text_format=ClusteredOutput
            )

            clusters_data = [cluster.dict() for cluster in response.output_parsed.clusters]
            print(f"✅ Successfully parsed {len(clusters_data)} clusters (structured output)")
            return clusters_data

        except Exception as e:
            print(f"❌ Clustering error: {e}")
            return None


    def calculate_relevance_scores(self, clusters_data, posts_by_title):
        """Calculate relevance scores for each cluster"""
        cluster_metrics = []
        
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
            freshness_score = calculate_freshness_score(cluster_posts, self.current_time)
            
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
        
        print(f"📈 Normalization factors - Max engagement: {max_engagement}, Max frequency: {max_frequency}")
        
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
    
    def generate_report(self, trending_topics, cluster_metrics, total_titles):
        """Generate comprehensive trending topics report"""
        total_posts = sum(c["post_count"] for c in cluster_metrics)
        total_engagement = sum(c["raw_engagement"] for c in cluster_metrics)
        
        report = {
            "analysis_timestamp": self.current_time.isoformat(),
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
    
    def save_outputs(self, clusters_data, report):
        """Save clustering results and final report"""
        try:
            # Save raw clusters
            with open("social_trends_clusters.json", "w", encoding="utf-8") as f:
                json.dump(clusters_data, f, indent=2, ensure_ascii=False)
            print("✅ Clusters saved to social_trends_clusters.json")
            
            # Save final report
            with open("trending_topics_report.json", "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print("✅ Final report saved to trending_topics_report.json")
            
            return True
        except Exception as e:
            print(f"❌ Error saving files: {e}")
            return False
    
    def print_summary(self, report):
        """Print comprehensive analysis summary"""
        trending_topics = report["trending_topics"]
        summary = report["summary"]
        
        print(f"\n{'='*60}")
        print(f"🔥 TRENDING TOPICS ANALYSIS COMPLETE")
        print(f"{'='*60}")
        
        print(f"\n📊 SUMMARY STATISTICS:")
        print(f"   • Total clusters identified: {summary['total_clusters']}")
        print(f"   • Total posts analyzed: {summary['total_posts_analyzed']}")
        print(f"   • Original titles: {summary['original_titles']}")
        print(f"   • Total engagement: {summary['total_engagement']:,}")
        print(f"   • Analysis time window: {summary['time_window_days']} days")
        
        print(f"\n⚖️  SCORING WEIGHTS:")
        for weight, value in report["scoring_weights"].items():
            print(f"   • {weight.title()}: {value*100}%")
        
        print(f"\n🏆 TOP 10 TRENDING TOPICS:")
        print("-" * 60)
        for topic in trending_topics[:10]:
            print(f"{topic['rank']:2d}. {topic['topic_cluster']}")
            print(f"     Relevance Score: {topic['relevance_score']}")
            print(f"     Posts: {topic['metrics']['frequency']} | "
                  f"Engagement: {topic['metrics']['total_engagement']:,} | "
                  f"Freshness: {topic['metrics']['freshness_score']:.1f}%")
            print()
    
    def run(self, input_file="social_trends_raw.json"):
        """Main execution function - runs the complete pipeline"""
        print("🚀 Starting Combined Trend Clustering & Ranking Agent...")
        print(f"   Input: {input_file}")
        print(f"   Model: {OPENAI_MODEL}")
        print(f"   Time window: {WINDOW_DAYS} days")
        
        # Step 1: Load raw data
        raw_data = self.load_raw_data(input_file)
        if not raw_data:
            return False
        
        # Step 2: Extract titles and create lookup
        titles, posts_by_title = self.extract_titles_and_posts(raw_data)
        if not titles:
            print("❌ No valid titles found to process")
            return False
        
        # Step 3: Perform clustering
        clusters_data = self.perform_clustering(titles)
        if not clusters_data:
            return False
        
        # Step 4: Calculate relevance scores and rankings
        trending_topics, cluster_metrics = self.calculate_relevance_scores(clusters_data, posts_by_title)
        
        # Step 5: Generate comprehensive report
        report = self.generate_report(trending_topics, cluster_metrics, len(titles))
        
        # Step 6: Save outputs
        if not self.save_outputs(clusters_data, report):
            return False
        
        # Step 7: Print summary
        self.print_summary(report)
        
        print(f"\n✅ Analysis complete! Check trending_topics_report.json for detailed results.")
        return True

# ==================== EXECUTION ====================

if __name__ == "__main__":
    # Initialize and run the agent
    agent = TrendClusteringAgent()
    success = agent.run()
    
    if not success:
        print("❌ Analysis failed. Please check your input data and try again.")
        exit(1)
    else:
        print("🎉 All done! Your trending topics are ready.")