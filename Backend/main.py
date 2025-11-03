# from fastapi import FastAPI, BackgroundTasks
# from pydantic import BaseModel
# import uuid
# import json
# import os
# from typing import List
# from content_pipeline import (
#     run_phase_1_and_2_parallel,
#     run_phase_3_and_4_parallel,
#     run_phase_5,
#     tracker
# )

# app = FastAPI(title="Content Strategy Optimizer API")

# # Store pipeline progress (in-memory)
# TASKS = {}

# # -----------------------------
# # Request Schema
# # -----------------------------
# class PipelineRequest(BaseModel):
#     our_url: str
#     competitors: List[str]
#     keywords: List[str]


# # -----------------------------
# # Background Pipeline Runner
# # -----------------------------
# def run_full_pipeline(req_data: dict, task_id: str):
#     try:
#         TASKS[task_id] = {"status": "running", "progress": tracker.phases}

#         # ---- Phase 1 & 2 ----
#         our_details, all_competitor_details, social_data = run_phase_1_and_2_parallel()

#         # ---- Phase 3 & 4 ----
#         content_gaps_combined, trending_input = run_phase_3_and_4_parallel(
#             our_details, all_competitor_details, social_data
#         )

#         # ---- Phase 5 ----
#         result = run_phase_5(content_gaps_combined, trending_input)

#         summary = {
#             "own_pages": len(our_details),
#             "competitors_analyzed": len(all_competitor_details),
#             "social_posts_mined": len(social_data),
#             "trending_clusters": len(trending_input),
#             "content_gaps": len(content_gaps_combined),
#             "briefs_generated": len(result),
#         }

#         TASKS[task_id] = {
#             "status": "completed",
#             "summary": summary,
#             "output_files": {
#                 "sitemaps": "data/sitemaps_data.json",
#                 "social_trends": "data/social_trends_raw.json",
#                 "trend_clusters": "data/trending_topics_report.json",
#                 "content_gaps": "data/content_gaps_report.json",
#                 "briefs": "data/content_briefs.json"
#             }
#         }

#     except Exception as e:
#         TASKS[task_id] = {"status": "failed", "error": str(e)}


# # -----------------------------
# # API ROUTES
# # -----------------------------
# @app.post("/pipeline/run")
# async def start_pipeline(request: PipelineRequest, background_tasks: BackgroundTasks):
#     """Run the full content strategy pipeline asynchronously"""
#     task_id = str(uuid.uuid4())
#     TASKS[task_id] = {"status": "starting"}

#     background_tasks.add_task(run_full_pipeline, request.dict(), task_id)
#     return {"task_id": task_id, "status": "started"}


# @app.get("/pipeline/status/{task_id}")
# def get_pipeline_status(task_id: str):
#     """Get current status or result of a pipeline run"""
#     if task_id not in TASKS:
#         return {"error": "Invalid task_id"}
#     return TASKS[task_id]


# @app.get("/")
# def home():
#     return {"message": "Content Strategy Optimizer API is running 🚀"}


# # -----------------------------
# # Run locally
# # -----------------------------
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)


from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import logging
from content_pipeline import (
    run_phase_1_and_2_parallel,
    run_phase_3_and_4_parallel,
    run_phase_5
)

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
# API Endpoint
# -----------------------------
@app.post("/pipeline/run")
def run_full_pipeline(request: PipelineRequest):
    """
    Runs the full content strategy pipeline (all phases) synchronously.
    Returns structured results directly in the response.
    """
    try:
        logger.info("🚀 Starting full content pipeline...")
        logger.info(f"Our URL: {request.our_url}")
        logger.info(f"Competitors: {request.competitors}")
        logger.info(f"Keywords: {request.keywords}")

        # ---- Phase 1 & 2 ----
        our_details, all_competitor_details, social_data = run_phase_1_and_2_parallel()

        # ---- Phase 3 & 4 ----
        content_gaps_combined, trending_input = run_phase_3_and_4_parallel(
            our_details, all_competitor_details, social_data
        )

        # ---- Phase 5 ----
        final_briefs = run_phase_5(content_gaps_combined, trending_input)

        # ---- Prepare output ----
        result = {
            "summary": {
                "own_pages": len(our_details),
                "competitors_analyzed": len(all_competitor_details),
                "social_posts_mined": len(social_data),
                "trending_clusters": len(trending_input),
                "content_gaps": len(content_gaps_combined),
                "briefs_generated": len(final_briefs),
            },
            "data": {
                "content_gaps": content_gaps_combined,
                "trending_topics": trending_input,
                "briefs": final_briefs
            }
        }

        logger.info("✅ Pipeline completed successfully.")
        return result

    except Exception as e:
        logger.exception("❌ Pipeline execution failed.")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def home():
    return {"message": "Content Strategy Optimizer API is running 🚀"}
