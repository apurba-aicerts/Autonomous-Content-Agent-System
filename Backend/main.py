from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import logging
from datetime import datetime

from content_pipeline import (
    run_phase_1_and_2_parallel,
    run_phase_3_and_4_parallel,
    run_phase_5
)

# ⬇️ UPDATE THIS IMPORT TO MATCH YOUR PROJECT PATH
from models import get_briefs_today  


# -----------------------------
# Logging Setup
# -----------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ContentStrategyAPI")

# -----------------------------
# FastAPI App
# -----------------------------
app = FastAPI(title="Content Strategy Optimizer API", version="1.0")

# -----------------------------
# Input Schema
# -----------------------------
class PipelineRequest(BaseModel):
    our_url: str
    competitors: List[str]
    keywords: List[str]


# -----------------------------
# RUN PIPELINE ENDPOINT
# -----------------------------
@app.post("/pipeline/run")
def run_full_pipeline(request: PipelineRequest):
    """
    Runs the full content strategy pipeline (all phases) synchronously.
    Saves briefs to database.
    """
    try:
        logger.info("🚀 Starting full content pipeline...")
        logger.info(f"Our URL: {request.our_url}")
        logger.info(f"Competitors: {request.competitors}")
        logger.info(f"Keywords: {request.keywords}")

        # ---- Phase 1 & 2 ----
        our_details, all_competitor_details, social_data = run_phase_1_and_2_parallel(request.our_url, 
                                                                                      request.competitors, 
                                                                                      request.keywords)

        # ---- Phase 3 & 4 ----
        content_gaps_combined, trending_input = run_phase_3_and_4_parallel(
            our_details, all_competitor_details, social_data
        )

        # ---- Phase 5 ---- (DB Save happens inside)
        brief_result = run_phase_5(content_gaps_combined, trending_input)

        saved_ids = brief_result["saved_brief_ids"]
        briefs_data = brief_result["briefs"]

        # ---- Prepare response ----
        result = {
            "summary": {
                "own_pages": len(our_details),
                "competitors_analyzed": len(all_competitor_details),
                "social_posts_mined": len(social_data),
                "trending_clusters": len(trending_input),
                "content_gaps": len(content_gaps_combined),
                "briefs_generated": len(saved_ids),
            },
            "data": {
                "brief_ids_saved": saved_ids,
                "content_gaps": content_gaps_combined,
                "trending_topics": trending_input,
                "briefs": briefs_data
            }
        }

        logger.info("✅ Pipeline completed successfully.")
        return result

    except Exception as e:
        logger.exception("❌ Pipeline execution failed.")
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------
# NEW API: GET TODAY'S BRIEFS (UPDATED FORMAT)
# -----------------------------
@app.get("/briefs/today")
def get_briefs_for_today():
    """
    Fetch all briefs generated today (00:00 to 23:59 UTC).
    Returns data in the same format as /pipeline/run for consistency.
    """
    try:
        today = datetime.utcnow().date()
        briefs_data = get_briefs_today(today)
        
        # Transform to match pipeline response format
        result = {
            "summary": {
                "own_pages": 0,  # Not applicable for today's briefs
                "competitors_analyzed": 0,  # Not applicable
                "social_posts_mined": 0,  # Not applicable
                "trending_clusters": 0,  # Not applicable
                "content_gaps": 0,  # Not applicable
                "briefs_generated": len(briefs_data),
            },
            "data": {
                "brief_ids_saved": [b["id"] for b in briefs_data],
                "content_gaps": [],  # Empty for today's briefs
                "trending_topics": {},  # Empty for today's briefs
                "briefs": briefs_data
            }
        }
        
        logger.info(f"✅ Retrieved {len(briefs_data)} briefs for {today}")
        return result
        
    except Exception as e:
        logger.exception("❌ Failed to retrieve today's briefs.")
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------
# HOME
# -----------------------------
@app.get("/")
def home():
    return {"message": "Content Strategy Optimizer API is running 🚀"}