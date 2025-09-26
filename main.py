#!/usr/bin/env python3
"""
CONTENT AGENT SYSTEM - MAIN PIPELINE ORCHESTRATOR

Purpose: Execute the complete content agent workflow in the correct sequence
Architecture: 3-phase pipeline with validation and error handling
Author: AI Content Team
Date: September 2025
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding issue
if os.name == 'nt':  # Windows
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# ==================== CONFIGURATION ====================
REQUIRED_CONFIG_KEYS = {
    "reddit": ["client_id", "client_secret", "user_agent", "reddit_subreddits", "posts_limit"],
    "own_sitemap_url": str,
    "competitor_sitemaps": list
}

REQUIRED_AGENTS = [
    "data_collection.py",
    "Gap_AGENT.py", 
    "Clustering_AGENT.py",
    "Brief_Agent.py"
]

EXPECTED_OUTPUTS = {
    "phase1": ["sitemaps_data.json", "social_trends_raw.json"],
    "phase2": ["content_gaps_report.json", "trending_topics_report.json"], 
    "phase3": ["content_briefs.json"]
}

# Rate limiting configuration
API_RATE_LIMITS = {
    "openai_requests_per_minute": 50,
    "delay_between_agents": 2,  # seconds
    "retry_attempts": 3,
    "retry_delay": 5  # seconds
}

# ==================== UTILITY FUNCTIONS ====================

def print_banner():
    """Print startup banner with timestamp"""
    print("=" * 70)
    print("🚀 CONTENT AGENT SYSTEM - PIPELINE ORCHESTRATOR")
    print("=" * 70)
    print(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 Working directory: {os.getcwd()}")
    print()

def print_phase_header(phase_num, phase_name, agents):
    """Print phase execution header"""
    print(f"\n{'='*50}")
    print(f"🔄 PHASE {phase_num}: {phase_name}")
    print(f"{'='*50}")
    print(f"📋 Agents to execute: {', '.join(agents)}")
    print(f"⏰ Started at: {datetime.now().strftime('%H:%M:%S')}")
    print()

def validate_config(config_path="config.json"):
    """Validate configuration file exists and has required structure"""
    print("🔍 Validating configuration...")
    
    if not os.path.exists(config_path):
        print(f"❌ Error: {config_path} not found")
        return None
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in {config_path}: {e}")
        return None
    
    # Validate reddit configuration
    if "reddit" not in config:
        print("❌ Error: 'reddit' section missing from config")
        return None
    
    for key in REQUIRED_CONFIG_KEYS["reddit"]:
        if key not in config["reddit"]:
            print(f"❌ Error: Missing reddit config key: {key}")
            return None
    
    # Validate sitemap configuration
    if "own_sitemap_url" not in config:
        print("❌ Error: 'own_sitemap_url' missing from config")
        return None
    
    if "competitor_sitemaps" not in config or not isinstance(config["competitor_sitemaps"], list):
        print("❌ Error: 'competitor_sitemaps' missing or not a list")
        return None
    
    print("✅ Configuration validation passed")
    return config

def validate_agent_files():
    """Check that all required agent files exist"""
    print("🔍 Validating agent files...")
    
    missing_agents = []
    for agent in REQUIRED_AGENTS:
        if not os.path.exists(agent):
            missing_agents.append(agent)
    
    if missing_agents:
        print(f"❌ Error: Missing agent files: {', '.join(missing_agents)}")
        return False
    
    print(f"✅ All {len(REQUIRED_AGENTS)} agent files found")
    return True

def validate_phase_outputs(phase_name, expected_files):
    """Validate that expected output files were created"""
    print(f"🔍 Validating {phase_name} outputs...")
    
    missing_files = []
    invalid_files = []
    
    for file_path in expected_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
        else:
            # Validate JSON structure
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if not data:  # Empty data
                        invalid_files.append(f"{file_path} (empty)")
                    else:
                        print(f"✅ {file_path} - Valid")
            except json.JSONDecodeError:
                invalid_files.append(f"{file_path} (invalid JSON)")
            except Exception as e:
                invalid_files.append(f"{file_path} (error: {e})")
    
    if missing_files:
        print(f"❌ Missing output files: {', '.join(missing_files)}")
        return False
    
    if invalid_files:
        print(f"❌ Invalid output files: {', '.join(invalid_files)}")
        return False
    
    print(f"✅ All {phase_name} outputs validated successfully")
    return True

def run_agent_with_retry(agent_script, max_retries=API_RATE_LIMITS["retry_attempts"]):
    """Execute an agent script with retry logic"""
    for attempt in range(1, max_retries + 1):
        try:
            print(f"🤖 Executing {agent_script} (attempt {attempt}/{max_retries})...")
            start_time = time.time()
            
            # Run the agent script
            result = subprocess.run(
                [sys.executable, agent_script],
                capture_output=True,
                text=True,
                timeout=1800  # 30 minute timeout
            )
            
            execution_time = time.time() - start_time
            
            if result.returncode == 0:
                print(f"✅ {agent_script} completed successfully in {execution_time:.1f}s")
                if result.stdout:
                    print(f"📄 Output:\n{result.stdout}")
                return True
            else:
                print(f"❌ {agent_script} failed with return code {result.returncode}")
                if result.stderr:
                    print(f"🔴 Error output:\n{result.stderr}")
                if result.stdout:
                    print(f"📄 Standard output:\n{result.stdout}")
                
                if attempt < max_retries:
                    print(f"⏳ Retrying in {API_RATE_LIMITS['retry_delay']} seconds...")
                    time.sleep(API_RATE_LIMITS["retry_delay"])
                
        except subprocess.TimeoutExpired:
            print(f"⏰ {agent_script} timed out after 30 minutes")
            if attempt < max_retries:
                print(f"⏳ Retrying in {API_RATE_LIMITS['retry_delay']} seconds...")
                time.sleep(API_RATE_LIMITS["retry_delay"])
        except Exception as e:
            print(f"💥 Unexpected error running {agent_script}: {e}")
            if attempt < max_retries:
                print(f"⏳ Retrying in {API_RATE_LIMITS['retry_delay']} seconds...")
                time.sleep(API_RATE_LIMITS["retry_delay"])
    
    print(f"❌ {agent_script} failed after {max_retries} attempts")
    return False

async def run_agents_parallel(agent_scripts):
    """Run multiple agents in parallel"""
    print(f"🔄 Running {len(agent_scripts)} agents in parallel...")
    
    # Create tasks for parallel execution
    tasks = []
    for agent in agent_scripts:
        task = asyncio.create_task(
            asyncio.to_thread(run_agent_with_retry, agent)
        )
        tasks.append((agent, task))
    
    # Wait for all tasks and check results
    results = {}
    for agent, task in tasks:
        try:
            success = await task
            results[agent] = success
        except Exception as e:
            print(f"💥 Error in parallel execution of {agent}: {e}")
            results[agent] = False
    
    # Check if all agents succeeded
    failed_agents = [agent for agent, success in results.items() if not success]
    
    if failed_agents:
        print(f"❌ Failed agents: {', '.join(failed_agents)}")
        return False
    
    print(f"✅ All {len(agent_scripts)} agents completed successfully")
    return True

def run_agent_sequential(agent_script):
    """Run a single agent sequentially"""
    print(f"🔄 Running {agent_script} sequentially...")
    
    success = run_agent_with_retry(agent_script)
    if not success:
        print(f"❌ Sequential execution of {agent_script} failed")
        return False
    
    print(f"✅ {agent_script} completed successfully")
    return True

def print_pipeline_summary(start_time, success=True):
    """Print final pipeline execution summary"""
    total_time = time.time() - start_time
    
    print(f"\n{'='*70}")
    if success:
        print("🎉 PIPELINE EXECUTION COMPLETED SUCCESSFULLY")
    else:
        print("💥 PIPELINE EXECUTION FAILED")
    print(f"{'='*70}")
    
    print(f"⏱️  Total execution time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
    print(f"📅 Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if success:
        print("\n📁 Generated files:")
        all_outputs = EXPECTED_OUTPUTS["phase1"] + EXPECTED_OUTPUTS["phase2"] + EXPECTED_OUTPUTS["phase3"]
        for output_file in all_outputs:
            if os.path.exists(output_file):
                file_size = os.path.getsize(output_file)
                print(f"   ✅ {output_file} ({file_size:,} bytes)")
            else:
                print(f"   ❌ {output_file} (missing)")
        
        print(f"\n🚀 Next steps:")
        print(f"   • Review content_briefs.json for actionable content ideas")
        print(f"   • Use python Reformat_agent.py --url <URL> to repurpose existing content")
        print(f"   • Run the pipeline again to get fresh trends and gaps")
    
    print(f"{'='*70}")

# ==================== MAIN PIPELINE EXECUTION ====================

async def main():
    """Main pipeline orchestrator"""
    pipeline_start_time = time.time()
    
    # Print startup banner
    print_banner()
    
    # Phase 0: Pre-flight validation
    print("🔍 PHASE 0: PRE-FLIGHT VALIDATION")
    print("=" * 50)
    
    # Validate configuration
    config = validate_config()
    if not config:
        print("❌ Pipeline aborted due to configuration errors")
        sys.exit(1)
    
    # Validate agent files
    if not validate_agent_files():
        print("❌ Pipeline aborted due to missing agent files")
        sys.exit(1)
    
    print("✅ Pre-flight validation completed\n")
    
    try:
        # Phase 1: Data Collection (Parallel)
        print_phase_header(1, "DATA COLLECTION", ["data_collection.py"])
        
        # Note: data_collection.py handles both sitemap and Reddit collection internally
        phase1_success = await run_agents_parallel(["data_collection.py"])
        
        if not phase1_success:
            print("❌ Phase 1 failed - aborting pipeline")
            return False
        
        # Validate Phase 1 outputs
        if not validate_phase_outputs("Phase 1", EXPECTED_OUTPUTS["phase1"]):
            print("❌ Phase 1 output validation failed - aborting pipeline")
            return False
        
        # Inter-phase delay for rate limiting
        print(f"⏳ Inter-phase delay: {API_RATE_LIMITS['delay_between_agents']} seconds...")
        time.sleep(API_RATE_LIMITS["delay_between_agents"])
        
        # Phase 2: Analysis & Synthesis (Parallel)
        print_phase_header(2, "ANALYSIS & SYNTHESIS", ["Gap_AGENT.py", "Clustering_AGENT.py"])
        
        phase2_success = await run_agents_parallel(["Gap_AGENT.py", "Clustering_AGENT.py"])
        
        if not phase2_success:
            print("❌ Phase 2 failed - aborting pipeline")
            return False
        
        # Validate Phase 2 outputs
        if not validate_phase_outputs("Phase 2", EXPECTED_OUTPUTS["phase2"]):
            print("❌ Phase 2 output validation failed - aborting pipeline")
            return False
        
        # Inter-phase delay for rate limiting
        print(f"⏳ Inter-phase delay: {API_RATE_LIMITS['delay_between_agents']} seconds...")
        time.sleep(API_RATE_LIMITS["delay_between_agents"])
        
        # Phase 3: Content Brief Generation (Sequential)
        print_phase_header(3, "CONTENT BRIEF GENERATION", ["Brief_Agent.py"])
        
        phase3_success = run_agent_sequential("Brief_Agent.py")
        
        if not phase3_success:
            print("❌ Phase 3 failed - aborting pipeline")
            return False
        
        # Validate Phase 3 outputs
        if not validate_phase_outputs("Phase 3", EXPECTED_OUTPUTS["phase3"]):
            print("❌ Phase 3 output validation failed - aborting pipeline")
            return False
        
        # Success!
        print_pipeline_summary(pipeline_start_time, success=True)
        return True
        
    except KeyboardInterrupt:
        print("\n⚠️  Pipeline interrupted by user (Ctrl+C)")
        print_pipeline_summary(pipeline_start_time, success=False)
        return False
    except Exception as e:
        print(f"\n💥 Unexpected pipeline error: {e}")
        print_pipeline_summary(pipeline_start_time, success=False)
        return False

def run_pipeline():
    """Synchronous entry point for the pipeline"""
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"💥 Fatal pipeline error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_pipeline()