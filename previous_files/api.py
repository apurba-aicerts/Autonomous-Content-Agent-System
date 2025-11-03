#!/usr/bin/env python3
"""
CONTENT AGENT SYSTEM - REST API

Purpose: Provide REST API interface for the content agent pipeline
Features: Async pipeline execution, status tracking, log streaming
Author: AI Content Team
Date: September 2025
"""

import asyncio
import logging
import os
import sys
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager

# Import your main pipeline function
from main import main as run_main_pipeline, setup_logging, EXPECTED_OUTPUTS

# Global storage for pipeline runs (in production, use Redis/Database)
pipeline_runs: Dict[str, Dict[str, Any]] = {}

class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class PipelineRunRequest(BaseModel):
    """Request model for starting a pipeline run"""
    run_id: Optional[str] = Field(default=None, description="Optional custom run ID")
    config_override: Optional[Dict[str, Any]] = Field(default=None, description="Configuration overrides")
    notify_webhook: Optional[str] = Field(default=None, description="Webhook URL for completion notification")

class PipelineRunResponse(BaseModel):
    """Response model for pipeline run status"""
    run_id: str
    status: PipelineStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None
    outputs: Optional[Dict[str, str]] = None
    logs_url: Optional[str] = None

class PipelineRunSummary(BaseModel):
    """Summary model for listing pipeline runs"""
    run_id: str
    status: PipelineStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    print("🚀 Content Agent API starting up...")
    setup_logging()
    
    # Cleanup old runs on startup
    cleanup_old_runs()
    
    yield
    
    # Shutdown
    print("🛑 Content Agent API shutting down...")
    cancel_all_running_pipelines()

app = FastAPI(
    title="Content Agent System API",
    description="REST API for executing and monitoring content agent pipeline",
    version="1.0.0",
    lifespan=lifespan
)

def cleanup_old_runs(max_age_hours: int = 24):
    """Clean up old pipeline runs from memory"""
    cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
    
    runs_to_remove = []
    for run_id, run_data in pipeline_runs.items():
        if run_data["started_at"] < cutoff_time:
            runs_to_remove.append(run_id)
    
    for run_id in runs_to_remove:
        del pipeline_runs[run_id]
    
    if runs_to_remove:
        print(f"🧹 Cleaned up {len(runs_to_remove)} old pipeline runs")

def cancel_all_running_pipelines():
    """Cancel all running pipelines on shutdown"""
    for run_id, run_data in pipeline_runs.items():
        if run_data["status"] == PipelineStatus.RUNNING:
            run_data["status"] = PipelineStatus.CANCELLED
            run_data["completed_at"] = datetime.now()

async def execute_pipeline_async(run_id: str):
    """Execute the pipeline asynchronously"""
    logger = logging.getLogger(__name__)
    run_data = pipeline_runs[run_id]
    
    try:
        logger.info(f"Starting pipeline run {run_id}")
        run_data["status"] = PipelineStatus.RUNNING
        
        # Run the main pipeline in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(None, run_main_pipeline)
        
        # Update run status
        run_data["completed_at"] = datetime.now()
        run_data["duration_seconds"] = (
            run_data["completed_at"] - run_data["started_at"]
        ).total_seconds()
        
        if success:
            run_data["status"] = PipelineStatus.COMPLETED
            run_data["outputs"] = get_pipeline_outputs()
            logger.info(f"Pipeline run {run_id} completed successfully")
        else:
            run_data["status"] = PipelineStatus.FAILED
            run_data["error_message"] = "Pipeline execution failed - check logs for details"
            logger.error(f"Pipeline run {run_id} failed")
            
    except Exception as e:
        logger.error(f"Pipeline run {run_id} error: {e}")
        run_data["status"] = PipelineStatus.FAILED
        run_data["error_message"] = str(e)
        run_data["completed_at"] = datetime.now()
        run_data["duration_seconds"] = (
            run_data["completed_at"] - run_data["started_at"]
        ).total_seconds()

def get_pipeline_outputs() -> Dict[str, str]:
    """Get information about pipeline output files"""
    outputs = {}
    
    all_expected = (
        EXPECTED_OUTPUTS["phase1"] + 
        EXPECTED_OUTPUTS["phase2"] + 
        EXPECTED_OUTPUTS["phase3"]
    )
    
    for output_file in all_expected:
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            outputs[output_file] = f"{file_size:,} bytes"
        else:
            outputs[output_file] = "missing"
    
    return outputs

@app.get("/", summary="Health Check")
async def root():
    """Health check endpoint"""
    return {
        "service": "Content Agent System API",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.post("/pipeline/run", response_model=PipelineRunResponse, summary="Start Pipeline Run")
async def start_pipeline_run(
    request: PipelineRunRequest,
    background_tasks: BackgroundTasks
):
    """Start a new pipeline run"""
    
    # Generate or use provided run ID
    run_id = request.run_id or str(uuid.uuid4())
    
    # Check if run ID already exists
    if run_id in pipeline_runs:
        raise HTTPException(
            status_code=400, 
            detail=f"Pipeline run with ID '{run_id}' already exists"
        )
    
    # Check if another pipeline is currently running
    active_runs = [
        r for r in pipeline_runs.values() 
        if r["status"] in [PipelineStatus.PENDING, PipelineStatus.RUNNING]
    ]
    
    if active_runs:
        raise HTTPException(
            status_code=409,
            detail="Another pipeline run is already active. Only one pipeline can run at a time."
        )
    
    # Initialize run data
    run_data = {
        "run_id": run_id,
        "status": PipelineStatus.PENDING,
        "started_at": datetime.now(),
        "completed_at": None,
        "duration_seconds": None,
        "error_message": None,
        "outputs": None,
        "config_override": request.config_override,
        "notify_webhook": request.notify_webhook
    }
    
    pipeline_runs[run_id] = run_data
    
    # Start pipeline execution in background
    background_tasks.add_task(execute_pipeline_async, run_id)
    
    return PipelineRunResponse(
        run_id=run_id,
        status=PipelineStatus.PENDING,
        started_at=run_data["started_at"],
        logs_url=f"/pipeline/{run_id}/logs"
    )

@app.get("/pipeline/runs", response_model=List[PipelineRunSummary], summary="List Pipeline Runs")
async def list_pipeline_runs(
    status: Optional[PipelineStatus] = None,
    limit: int = 50
):
    """List recent pipeline runs"""
    
    runs = list(pipeline_runs.values())
    
    # Filter by status if provided
    if status:
        runs = [r for r in runs if r["status"] == status]
    
    # Sort by start time (newest first)
    runs.sort(key=lambda x: x["started_at"], reverse=True)
    
    # Limit results
    runs = runs[:limit]
    
    return [
        PipelineRunSummary(
            run_id=run["run_id"],
            status=run["status"],
            started_at=run["started_at"],
            completed_at=run["completed_at"],
            duration_seconds=run["duration_seconds"]
        )
        for run in runs
    ]

@app.get("/pipeline/{run_id}", response_model=PipelineRunResponse, summary="Get Pipeline Run Status")
async def get_pipeline_run_status(run_id: str):
    """Get the status of a specific pipeline run"""
    
    if run_id not in pipeline_runs:
        raise HTTPException(status_code=404, detail=f"Pipeline run '{run_id}' not found")
    
    run_data = pipeline_runs[run_id]
    
    return PipelineRunResponse(
        run_id=run_data["run_id"],
        status=run_data["status"],
        started_at=run_data["started_at"],
        completed_at=run_data["completed_at"],
        duration_seconds=run_data["duration_seconds"],
        error_message=run_data["error_message"],
        outputs=run_data["outputs"],
        logs_url=f"/pipeline/{run_id}/logs"
    )

@app.delete("/pipeline/{run_id}", summary="Cancel Pipeline Run")
async def cancel_pipeline_run(run_id: str):
    """Cancel a running pipeline (if possible)"""
    
    if run_id not in pipeline_runs:
        raise HTTPException(status_code=404, detail=f"Pipeline run '{run_id}' not found")
    
    run_data = pipeline_runs[run_id]
    
    if run_data["status"] not in [PipelineStatus.PENDING, PipelineStatus.RUNNING]:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot cancel pipeline in '{run_data['status']}' status"
        )
    
    # Note: Actual cancellation of subprocess is complex, this just marks as cancelled
    run_data["status"] = PipelineStatus.CANCELLED
    run_data["completed_at"] = datetime.now()
    run_data["duration_seconds"] = (
        run_data["completed_at"] - run_data["started_at"]
    ).total_seconds()
    
    return {"message": f"Pipeline run '{run_id}' marked as cancelled"}

@app.get("/pipeline/{run_id}/logs", summary="Get Pipeline Logs")
async def get_pipeline_logs(run_id: str):
    """Stream pipeline logs"""
    
    if run_id not in pipeline_runs:
        raise HTTPException(status_code=404, detail=f"Pipeline run '{run_id}' not found")
    
    log_file = "data/pipeline.log"
    
    if not os.path.exists(log_file):
        raise HTTPException(status_code=404, detail="Log file not found")
    
    def generate_logs():
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    yield line
        except Exception as e:
            yield f"Error reading log file: {e}\n"
    
    return StreamingResponse(
        generate_logs(),
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename=pipeline_{run_id}.log"}
    )

@app.get("/pipeline/{run_id}/outputs", summary="Get Pipeline Output Files")
async def get_pipeline_outputs_info(run_id: str):
    """Get information about pipeline output files"""
    
    if run_id not in pipeline_runs:
        raise HTTPException(status_code=404, detail=f"Pipeline run '{run_id}' not found")
    
    run_data = pipeline_runs[run_id]
    
    if run_data["status"] != PipelineStatus.COMPLETED:
        raise HTTPException(
            status_code=400, 
            detail=f"Pipeline run is not completed (status: {run_data['status']})"
        )
    
    outputs = get_pipeline_outputs()
    
    return {
        "run_id": run_id,
        "outputs": outputs,
        "total_files": len([f for f, status in outputs.items() if status != "missing"]),
        "missing_files": len([f for f, status in outputs.items() if status == "missing"])
    }

@app.get("/system/status", summary="System Status")
async def get_system_status():
    """Get overall system status"""
    
    # Count runs by status
    status_counts = {}
    for status in PipelineStatus:
        status_counts[status.value] = len([
            r for r in pipeline_runs.values() if r["status"] == status
        ])
    
    # Check disk space for data directory
    data_dir = Path("data")
    total_size = 0
    file_count = 0
    
    if data_dir.exists():
        for file_path in data_dir.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
                file_count += 1
    
    return {
        "total_runs": len(pipeline_runs),
        "runs_by_status": status_counts,
        "data_directory": {
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "file_count": file_count
        },
        "system_time": datetime.now().isoformat()
    }

@app.post("/system/cleanup", summary="Cleanup Old Runs")
async def cleanup_system(max_age_hours: int = 24):
    """Clean up old pipeline runs"""
    
    initial_count = len(pipeline_runs)
    cleanup_old_runs(max_age_hours)
    final_count = len(pipeline_runs)
    
    return {
        "message": "Cleanup completed",
        "removed_runs": initial_count - final_count,
        "remaining_runs": final_count
    }

if __name__ == "__main__":
    print("🚀 Starting Content Agent System API...")
    print("📚 API documentation available at: http://localhost:8000/docs")
    
    uvicorn.run(
        "api:app",
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info",
        access_log=True
    )