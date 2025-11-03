import logging
import json
from openai import OpenAI
from pydantic import BaseModel
from typing import List
from dotenv import load_dotenv
import os   
load_dotenv()
# -----------------------------
# LOGGING SETUP
# -----------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ContentGapFinder")


# -----------------------------
# Pydantic Response Models
# -----------------------------
class GapItem(BaseModel):
    gap_topic: str
    competitor_coverage: int
    # gap_description: str  # <-- Added detailed explanation


class Gaps(BaseModel):
    gaps: List[GapItem]


# -----------------------------
# MAIN CLASS
# -----------------------------
class ContentGapFinder:
    def __init__(self, api_key: str):
        """Initialize OpenAI client with credentials."""
        self.client = OpenAI(api_key=api_key)
        logger.info("✅ ContentGapFinder initialized successfully")

    def make_llm_call(self, ai_titles, competitor_titles, max_retries=3):
        """Compare two title lists and identify missing topics using LLM."""
        user_prompt = f"""
    Compare the following lists of webpage titles:
    - Our Titles: {json.dumps(ai_titles, indent=2)}
    - Competitor Titles: {json.dumps(competitor_titles, indent=2)}

    Identify key content gaps — topics that competitors cover but we do not.
    For each gap:
    1. Provide a clear descriptive and  human-readable title.
    2. Estimate how many competitor titles mention or relate to it (competitor_coverage).
    """

        for attempt in range(max_retries):
            try:
                response = self.client.responses.parse(
                    model="gpt-4o-2024-08-06",
                    input=[
                        {"role": "system", "content": "You are a content analyst. Identify missing topic coverage between two lists of page titles."},
                        {"role": "user", "content": user_prompt},
                    ],
                    text_format=Gaps,
                    temperature=0,
                )
                parsed = getattr(response, "output_parsed", None)
                # print(parsed.model_dump())
                if parsed is not None:

                    return parsed.model_dump()["gaps"]
                logger.warning(f"Attempt {attempt + 1}/{max_retries}: Empty response, retrying...")
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{max_retries}: API error: {e}")

        logger.error("❌ Failed to retrieve valid LLM response after all retries.")
        return []

    def find_gaps(self, ai_titles, competitor_titles):
        """High-level method to run analysis and return gaps."""
        logger.info(f"Running gap analysis between {len(ai_titles)} own titles and {len(competitor_titles)} competitor titles...")

        result = self.make_llm_call(ai_titles, competitor_titles)
        return result
        print(result)
        gaps = [
            {"gap_topic": g.gap_topic, "competitor_coverage": g.competitor_coverage}
            for g in result
        ]
        logger.info(f"✅ Identified {len(gaps)} content gaps.")
        return gaps


# -----------------------------
# EXAMPLE USAGE
# -----------------------------
if __name__ == "__main__":
    ai_titles = [{'title': 'Certification Process - AICERTs - Empower with AI Certifications',
  'description': 'AI CERTs: Globally recognized, industry-aligned certification. Expert-led, ethical, and continuously improving for AI excellence.',
  'url': 'https://www.aicerts.ai/certification-process/',
  'date': '2025-07-07'},
 {'title': 'AI Foundation Course by AICerts | Learn AI from Experts',
  'description': 'Master the future with AICerts’ AI Foundation Course! Learn AI basics, get hands-on skills & earn your certification. Start your AI journey today',
  'url': 'https://www.aicerts.ai/certifications/essentials/ai-foundation/',
  'date': '2025-07-07'}]

    competitor_titles = [{'title': 'Free Excel Courses with Certificates Online (2025)',
  'description': 'Learn formulas, pivot tables, data analysis and more with our Free Excel courses with Certification to enhance your skills & open new career opportunities today!',
  'url': 'https://www.mygreatlearning.com/microsoft-excel/free-courses',
  'date': '2025-08-08'},
 {'title': 'Free Web Development Courses Online with Certificates (2025)',
  'description': 'Discover top-rated free web development courses with certificates. Master coding, web design, and responsive skills in front-end and back-end development.',
  'url': 'https://www.mygreatlearning.com/web-development/free-courses',
  'date': '2025-08-08'}]
    
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    finder = ContentGapFinder(api_key=OPENAI_API_KEY)
    gaps = finder.find_gaps(ai_titles, competitor_titles)
    # print(gaps)
    print(json.dumps(gaps, indent=2))
