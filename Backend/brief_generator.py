import logging
from openai import OpenAI
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()
logger = logging.getLogger(__name__)


# ==========================================================
# 🎯 Structured Models
# ==========================================================
class BriefSchema(BaseModel):
    audience: str
    job_to_be_done: str
    angle: str
    promise: str
    cta: str
    key_talking_points: List[str]


class BriefItem(BaseModel):
    source_type: str
    topic: str
    priority: str
    brief: BriefSchema

class BriefList(BaseModel):
    briefs: List[BriefItem]


# ==========================================================
# 🧠 Content Brief Generator
# ==========================================================
class ContentBriefGenerator:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    # -------------------------------
    # 🔹 LLM Call with structured response & retries
    # -------------------------------
    def _make_llm_call(
        self, prompt: str, response_model, max_retries: int = 3
    ) -> Optional[BaseModel]:
        for attempt in range(max_retries):
            try:
                response = self.client.responses.parse(
                    model="gpt-4o-2024-08-06",
                    input=[
                        {
                            "role": "system",
                            "content": "You are a professional content strategist who writes structured, insightful briefs."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    text_format=response_model,
                )
                parsed = getattr(response, "output_parsed", None)
                if parsed is not None:
                    return parsed
                logger.warning(f"Retry {attempt + 1}/{max_retries}: empty or invalid LLM output")
            except Exception as e:
                logger.warning(f"Retry {attempt + 1}/{max_retries}: API error - {e}")
        logger.error("Failed to generate brief after all retries")
        return None

    # -------------------------------
    # 🔹 Generate grouped briefs for a list of topics
    # -------------------------------
    def _generate_briefs_for_group(
        self, topics: List[str], source_type: str, priority: str
    ) -> List[Dict[str, Any]]:
        if not topics:
            return []

        prompt = f"""
You are a senior content strategist.

Group the following topics into 3–7 logical clusters.
For each cluster, generate one structured content brief.

Each brief should include:
- audience
- job_to_be_done
- angle
- promise
- cta
- key_talking_points (3–6 concise points)

Topics:
{chr(10).join(f"- {t}" for t in topics)}
Source Type: {source_type}
Priority: {priority}
Return a JSON object with key "briefs", whose value is a list of briefs.
"""



        result = self._make_llm_call(prompt, response_model=BriefList)
        if result is None:
            logger.error(f"Failed to generate structured briefs for {source_type}")
            return []

        return [b.model_dump() for b in result.briefs]


    # -------------------------------
    # 🔹 Main entry point
    # -------------------------------
    def generate_content_briefs(
        self, content_gaps: List[Dict[str, Any]], trending_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        # Extract topics
        content_gap_topics = [t["gap_topic"] for t in content_gaps]
        trending_topics = [
            t["topic_cluster"]
            for t in trending_data.get("trending_topics", [])
            if t.get("relevance_score", 0)
            >= trending_data.get("elbow_threshold", 0)
        ]

        # Generate for Content Gaps
        logger.info("Generating grouped briefs for Content Gaps...")
        gap_briefs = self._generate_briefs_for_group(
            content_gap_topics, source_type="Content Gap", priority="High"
        )

        # Generate for Trending Topics
        logger.info("Generating grouped briefs for Trending Topics...")
        trend_briefs = self._generate_briefs_for_group(
            trending_topics, source_type="Trending Topic", priority="Medium"
        )

        all_briefs = gap_briefs + trend_briefs
        logger.info(f"✅ Generated {len(all_briefs)} structured content briefs in total.")
        return all_briefs


# ==========================================================
# 🧪 Example usage
# ==========================================================
if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    trending_input = {
        "trending_topics": [
            {"topic_cluster": "AI Applications and Ethics", "relevance_score": 86.39},
            {"topic_cluster": "Data Science Careers and Education", "relevance_score": 59.34},
            {"topic_cluster": "Career Advice and Personal Development", "relevance_score": 51.3},
        ],
        "elbow_threshold": 51.3,
    }

    content_gaps_input = [
        {"gap_topic": "Excel Courses"},
        {"gap_topic": "AWS Courses"},
        {"gap_topic": "Java Courses"},
        {"gap_topic": "Web Design Courses"},
        {"gap_topic": "Web Development Courses"},
    ]

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    generator = ContentBriefGenerator(api_key=OPENAI_API_KEY)
    result = generator.generate_content_briefs(content_gaps_input, trending_input)

    print(json.dumps(result, indent=2))
