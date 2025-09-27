#!/usr/bin/env python3
"""
CONTENT AGENT SYSTEM - MAIN PIPELINE ORCHESTRATOR

Purpose: Execute the complete content agent workflow in modular fashion
Architecture: Function-based imports with parallel execution and retry logic
Author: AI Content Team
Date: September 2025
"""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Import module functions
from config import validate_config, ensure_data_directory
from sitemap_agent import run_sitemap_agent
from social_trend_miner import run_social_trend_miner
from gap_analyzer import run_gap_analysis
from trend_clusterer import run_trend_analysis
from brief_generator import run_brief_generation

# Configuration
EXPECTED_OUTPUTS = {
    "phase1": ["data/sitemaps_data.json", "data/social_trends_raw.json"],
    "phase2": ["data/content_gaps_report.json", "data/trending_topics_report.json"], 
    "phase3": ["data/content_briefs.json"]
}

def setup_logging():
    """Configure logging for the main pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('data/pipeline.log', mode='a', encoding='utf-8')
        ]
    )
    return logging.getLogger(__name__)

def print_banner():
    """Print startup banner with timestamp"""
    print("=" * 70)
    print("🚀 CONTENT AGENT SYSTEM - PIPELINE ORCHESTRATOR")
    print("=" * 70)
    print(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 Working directory: {os.getcwd()}")
    print()

def print_phase_header(phase_num, phase_name, description):
    """Print phase execution header"""
    print(f"\n{'='*50}")
    print(f"🔄 PHASE {phase_num}: {phase_name}")
    print(f"{'='*50}")
    print(f"📋 {description}")
    print(f"⏰ Started at: {datetime.now().strftime('%H:%M:%S')}")
    print()

def validate_phase_outputs(phase_name, expected_files):
    """Validate that expected output files were created and contain valid data."""
    logger = logging.getLogger(__name__)
    logger.info(f"Validating {phase_name} outputs...")
    
    missing_files = []
    invalid_files = []
    
    for file_path in expected_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
        else:
            try:
                # Check file size
                file_size = os.path.getsize(file_path)
                if file_size == 0:
                    invalid_files.append(f"{file_path} (empty)")
                else:
                    logger.info(f"✅ {file_path} - Valid ({file_size:,} bytes)")
            except Exception as e:
                invalid_files.append(f"{file_path} (error: {e})")
    
    if missing_files:
        logger.error(f"Missing output files: {', '.join(missing_files)}")
        return False
    
    if invalid_files:
        logger.error(f"Invalid output files: {', '.join(invalid_files)}")
        return False
    
    logger.info(f"✅ All {phase_name} outputs validated successfully")
    return True

async def run_parallel_phase(agents, phase_name, expected_outputs):
    """Run agents in parallel with retry logic."""
    logger = logging.getLogger(__name__)
    
    # Run agents in parallel
    logger.info(f"Starting {phase_name} agents in parallel...")
    results = await asyncio.gather(*[agent() for agent in agents], return_exceptions=True)
    
    # Check results and identify failures
    failed_agents = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Agent {i+1} failed with exception: {result}")
            failed_agents.append(i)
        elif result is False:
            logger.error(f"Agent {i+1} returned failure")
            failed_agents.append(i)
        else:
            logger.info(f"Agent {i+1} completed successfully")
    
    # Retry failed agents once
    if failed_agents:
        logger.warning(f"Retrying {len(failed_agents)} failed agents...")
        for agent_idx in failed_agents:
            logger.info(f"Retrying agent {agent_idx+1}...")
            try:
                retry_result = await agents[agent_idx]()
                if retry_result is False:
                    logger.error(f"Agent {agent_idx+1} failed on retry - aborting pipeline")
                    return False
                else:
                    logger.info(f"Agent {agent_idx+1} succeeded on retry")
            except Exception as e:
                logger.error(f"Agent {agent_idx+1} failed on retry with exception: {e} - aborting pipeline")
                return False
    
    # Validate outputs
    return validate_phase_outputs(phase_name, expected_outputs)

def run_sync_agent(agent_func, agent_name):
    """Run synchronous agent with error handling."""
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Executing {agent_name}...")
        result = agent_func()
        if result is False:
            logger.error(f"{agent_name} returned failure")
            return False
        else:
            logger.info(f"{agent_name} completed successfully")
            return True
    except Exception as e:
        logger.error(f"{agent_name} failed with exception: {e}")
        return False

def print_pipeline_summary(start_time, success=True):
    """Print final pipeline execution summary"""
    logger = logging.getLogger(__name__)
    total_time = time.time() - start_time
    
    print(f"\n{'='*70}")
    if success:
        print("🎉 PIPELINE EXECUTION COMPLETED SUCCESSFULLY")
        logger.info("Pipeline completed successfully")
    else:
        print("💥 PIPELINE EXECUTION FAILED")
        logger.error("Pipeline execution failed")
    print(f"{'='*70}")
    
    print(f"⏱️ Total execution time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
    print(f"📅 Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if success:
        print("\nGenerated files:")
        all_outputs = EXPECTED_OUTPUTS["phase1"] + EXPECTED_OUTPUTS["phase2"] + EXPECTED_OUTPUTS["phase3"]
        for output_file in all_outputs:
            if os.path.exists(output_file):
                file_size = os.path.getsize(output_file)
                print(f"   - {output_file} ({file_size:,} bytes)")
            else:
                print(f"   - {output_file} (missing)")
        
        print(f"\nNext steps:")
        print(f"   • Review data/content_briefs.json for actionable content ideas")
        print(f"   • Use the generated insights to create targeted content")
        print(f"   • Run the pipeline again to get fresh trends and gaps")
    
    print(f"{'='*70}")

async def main():
    """Main pipeline orchestrator function."""
    pipeline_start_time = time.time()
    
    # Setup logging and print banner
    logger = setup_logging()
    print_banner()
    
    # Phase 0: Pre-flight validation
    print("🔍 Pre-flight validation")
    print("=" * 50)
    logger.info("Starting pipeline pre-flight validation...")
    
    # Validate configuration
    try:
        if not validate_config():
            logger.error("Configuration validation failed - aborting pipeline")
            print_pipeline_summary(pipeline_start_time, success=False)
            return False
    except Exception as e:
        logger.error(f"Configuration validation error: {e}")
        print_pipeline_summary(pipeline_start_time, success=False)
        return False
    
    # Ensure data directory exists
    try:
        ensure_data_directory()
        logger.info("Data directory validated/created")
    except Exception as e:
        logger.error(f"Failed to create data directory: {e}")
        print_pipeline_summary(pipeline_start_time, success=False)
        return False
    
    print("✅ Pre-flight validation completed successfully\n")
    logger.info("Pre-flight validation completed")
    
    try:
        # Phase 1: Parallel Data Collection
        print_phase_header(1, "DATA COLLECTION (PARALLEL)", "Sitemap crawling and Reddit scraping")
        
        phase1_agents = [run_sitemap_agent, run_social_trend_miner]
        if not await run_parallel_phase(phase1_agents, "Data Collection", EXPECTED_OUTPUTS["phase1"]):
            logger.error("Phase 1 failed - aborting pipeline")
            print_pipeline_summary(pipeline_start_time, success=False)
            return False
        
        # Phase 2: Parallel Analysis
        print_phase_header(2, "ANALYSIS (PARALLEL)", "Gap analysis and trend clustering")
        
        # Wrap sync functions for async execution
        async def run_gap_async():
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, run_gap_analysis)
        
        async def run_trend_async():
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, run_trend_analysis)
        
        phase2_agents = [run_gap_async, run_trend_async]
        if not await run_parallel_phase(phase2_agents, "Analysis", EXPECTED_OUTPUTS["phase2"]):
            logger.error("Phase 2 failed - aborting pipeline")
            print_pipeline_summary(pipeline_start_time, success=False)
            return False
        
        # Phase 3: Sequential Brief Generation
        print_phase_header(3, "BRIEF GENERATION (SEQUENTIAL)", "Creating actionable content briefs")
        
        if not run_sync_agent(run_brief_generation, "Brief Generation"):
            logger.error("Phase 3 failed - aborting pipeline")
            print_pipeline_summary(pipeline_start_time, success=False)
            return False
        
        # Validate final outputs
        if not validate_phase_outputs("Brief Generation", EXPECTED_OUTPUTS["phase3"]):
            logger.error("Phase 3 output validation failed - aborting pipeline")
            print_pipeline_summary(pipeline_start_time, success=False)
            return False
        
        # Success!
        print_pipeline_summary(pipeline_start_time, success=True)
        return True
        
    except KeyboardInterrupt:
        logger.warning("Pipeline interrupted by user (Ctrl+C)")
        print("\n⚠️ Pipeline interrupted by user (Ctrl+C)")
        print_pipeline_summary(pipeline_start_time, success=False)
        return False
    except Exception as e:
        logger.error(f"Unexpected pipeline error: {e}")
        print(f"\n❌ Unexpected pipeline error: {e}")
        print_pipeline_summary(pipeline_start_time, success=False)
        return False

def run_pipeline():
    """Entry point for the pipeline."""
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Fatal pipeline error: {e}")
        print(f"Fatal pipeline error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_pipeline()