#!/usr/bin/env python3
"""
Content Agent System - Streamlit GUI
Multi-user session-isolated interface for content intelligence pipeline
"""

import streamlit as st
import asyncio
import json
import os
import shutil
import time
import threading
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import io
import requests
from queue import Queue

# Import your existing agents
from config import validate_config, ensure_data_directory
from sitemap_agent import run_sitemap_agent
from social_trend_miner import run_social_trend_miner
from gap_analyzer import run_gap_analysis
from trend_clusterer import run_trend_analysis
from brief_generator import run_brief_generation

# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

def init_session_state():
    """Initialize session state variables"""
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())[:8]
    if 'competitor_urls' not in st.session_state:
        st.session_state.competitor_urls = ['']
    if 'pipeline_running' not in st.session_state:
        st.session_state.pipeline_running = False
    if 'pipeline_status' not in st.session_state:
        st.session_state.pipeline_status = {
            'phase1': 'pending',
            'phase2': 'pending', 
            'phase3': 'pending',
            'progress': 0
        }
    if 'results_ready' not in st.session_state:
        st.session_state.results_ready = False
    if 'session_dir' not in st.session_state:
        st.session_state.session_dir = f"data/session_{st.session_state.session_id}"
    if 'last_activity' not in st.session_state:
        st.session_state.last_activity = datetime.now()
    if 'error_message' not in st.session_state:
        st.session_state.error_message = None
    if 'status_queue' not in st.session_state:
        st.session_state.status_queue = Queue()

def get_session_dir():
    """Get current session directory"""
    return st.session_state.session_dir

def cleanup_old_sessions():
    """Remove session directories older than 1 hour"""
    data_dir = Path("data")
    if not data_dir.exists():
        return
    
    cutoff_time = datetime.now() - timedelta(hours=1)
    
    for session_dir in data_dir.glob("session_*"):
        if session_dir.is_dir():
            try:
                # Check directory modification time
                mtime = datetime.fromtimestamp(session_dir.stat().st_mtime)
                if mtime < cutoff_time:
                    shutil.rmtree(session_dir)
            except Exception:
                pass  # Ignore cleanup errors

def ensure_session_directory():
    """Create session-specific data directory"""
    session_dir = Path(get_session_dir())
    session_dir.mkdir(parents=True, exist_ok=True)
    return str(session_dir)

def clear_session_results():
    """Clear current session results"""
    session_dir = Path(get_session_dir())
    if session_dir.exists():
        shutil.rmtree(session_dir)
    ensure_session_directory()
    st.session_state.results_ready = False
    st.session_state.pipeline_status = {
        'phase1': 'pending',
        'phase2': 'pending',
        'phase3': 'pending',
        'progress': 0
    }

# ============================================================================
# URL VALIDATION
# ============================================================================

def validate_sitemap_url(url: str) -> tuple[bool, str]:
    """Validate sitemap URL accessibility"""
    if not url.strip():
        return False, "URL cannot be empty"
    
    if not url.startswith(('http://', 'https://')):
        return False, "URL must start with http:// or https://"
    
    try:
        response = requests.head(url, timeout=5, allow_redirects=True)
        if response.status_code == 200:
            return True, "Valid"
        else:
            return False, f"HTTP {response.status_code}"
    except requests.RequestException as e:
        return False, f"Connection error: {str(e)[:50]}"

# ============================================================================
# PIPELINE EXECUTION WITH THREAD-SAFE STATUS UPDATES
# ============================================================================

def send_status_update(status_queue: Queue, phase: str, status: str):
    """Thread-safe status update via queue"""
    status_queue.put({
        'type': 'phase_update',
        'phase': phase,
        'status': status
    })

def send_error_update(status_queue: Queue, message: str):
    """Thread-safe error message via queue"""
    status_queue.put({
        'type': 'error',
        'message': message
    })

def send_completion_update(status_queue: Queue, success: bool):
    """Thread-safe completion notification via queue"""
    status_queue.put({
        'type': 'completion',
        'success': success
    })

async def run_pipeline_async(competitor_urls: List[str], session_dir: str, status_queue: Queue):
    """Run the pipeline asynchronously with session isolation"""
    
    try:
        # Load base config
        with open('config.json', 'r') as f:
            base_config = json.load(f)
        
        # Create session config
        session_config = base_config.copy()
        session_config['competitor_sitemaps'] = [url for url in competitor_urls if url.strip()]
        
        # Save session config
        session_config_path = os.path.join(session_dir, 'config.json')
        with open(session_config_path, 'w') as f:
            json.dump(session_config, f, indent=2)
        
        # Phase 1: Data Collection
        send_status_update(status_queue, 'phase1', 'running')
        
        phase1_results = await asyncio.gather(
            run_sitemap_agent(session_dir=session_dir),
            run_social_trend_miner(session_dir=session_dir),
            return_exceptions=True
        )
        
        # # Move Phase 1 outputs to session directory
        # for file in ['sitemaps_data.json', 'social_trends_raw.json']:
        #     src = f"data/{file}"
        #     dst = os.path.join(session_dir, file)
        #     if os.path.exists(src):
        #         shutil.move(src, dst)
        
        # Check Phase 1 results
        if any(isinstance(r, Exception) or r is False for r in phase1_results):
            send_status_update(status_queue, 'phase1', 'failed')
            send_error_update(status_queue, "Phase 1 failed. Check logs for details.")
            send_completion_update(status_queue, False)
            return False
        
        send_status_update(status_queue, 'phase1', 'completed')
        
        # Phase 2: Analysis
        send_status_update(status_queue, 'phase2', 'running')
        
        # Copy input files for analysis agents
        # for file in ['sitemaps_data.json', 'social_trends_raw.json']:
        #     src = os.path.join(session_dir, file)
        #     link = f"data/{file}"
        #     if os.path.exists(link):
        #         os.remove(link)
        #     if os.path.exists(src):
        #         shutil.copy(src, link)
        
        # Run Phase 2 agents
        loop = asyncio.get_event_loop()
        # phase2_results = await asyncio.gather(
        #     loop.run_in_executor(None, run_gap_analysis),
        #     loop.run_in_executor(None, run_trend_analysis),
        #     return_exceptions=True
        # )

        phase2_results = await asyncio.gather(
        loop.run_in_executor(None, lambda: run_gap_analysis(session_dir=session_dir)),
        loop.run_in_executor(None, lambda: run_trend_analysis(session_dir=session_dir)),
        return_exceptions=True
    )

        
        # # Move Phase 2 outputs
        # for file in ['content_gaps_report.json', 'trending_topics_report.json']:
        #     src = f"data/{file}"
        #     dst = os.path.join(session_dir, file)
        #     if os.path.exists(src):
        #         shutil.move(src, dst)
        
        if any(isinstance(r, Exception) or r is False for r in phase2_results):
            send_status_update(status_queue, 'phase2', 'failed')
            send_error_update(status_queue, "Phase 2 failed. Partial results available.")
            send_completion_update(status_queue, False)
            return False
        
        send_status_update(status_queue, 'phase2', 'completed')
        
        # Phase 3: Brief Generation
        send_status_update(status_queue, 'phase3', 'running')
        
        # # Copy Phase 2 outputs for Phase 3
        # for file in ['content_gaps_report.json', 'trending_topics_report.json']:
        #     src = os.path.join(session_dir, file)
        #     link = f"data/{file}"
        #     if os.path.exists(src):
        #         shutil.copy(src, link)
        
        result = run_brief_generation(session_dir=session_dir)
        
        # Move Phase 3 output
        src = "data/content_briefs.json"
        dst = os.path.join(session_dir, "content_briefs.json")
        if os.path.exists(src):
            shutil.move(src, dst)
        
        if result is False:
            send_status_update(status_queue, 'phase3', 'failed')
            send_error_update(status_queue, "Phase 3 failed.")
            send_completion_update(status_queue, False)
            return False
        
        send_status_update(status_queue, 'phase3', 'completed')
        send_completion_update(status_queue, True)
        return True
        
    except Exception as e:
        send_error_update(status_queue, f"Pipeline error: {str(e)}")
        send_completion_update(status_queue, False)
        return False

def run_pipeline_thread(competitor_urls: List[str], session_dir: str, status_queue: Queue):
    """Run pipeline in background thread"""
    try:
        asyncio.run(run_pipeline_async(competitor_urls, session_dir, status_queue))
    except Exception as e:
        send_error_update(status_queue, f"Pipeline execution error: {str(e)}")
        send_completion_update(status_queue, False)

def process_status_updates():
    """Process status updates from queue and update session state"""
    queue = st.session_state.status_queue
    updates_processed = False
    
    while not queue.empty():
        update = queue.get()
        updates_processed = True
        
        if update['type'] == 'phase_update':
            phase = update['phase']
            status = update['status']
            st.session_state.pipeline_status[phase] = status
            
            # Calculate progress
            phase_weights = {'phase1': 33, 'phase2': 33, 'phase3': 34}
            total_progress = 0
            
            for p, weight in phase_weights.items():
                if st.session_state.pipeline_status[p] == 'completed':
                    total_progress += weight
                elif st.session_state.pipeline_status[p] == 'running':
                    total_progress += weight // 2
            
            st.session_state.pipeline_status['progress'] = total_progress
            
        elif update['type'] == 'error':
            st.session_state.error_message = update['message']
            
        elif update['type'] == 'completion':
            st.session_state.pipeline_running = False
            if update['success']:
                st.session_state.results_ready = True
    
    return updates_processed

# ============================================================================
# RESULTS LOADING
# ============================================================================

# def load_json_file(filename: str) -> Optional[Dict]:
#     """Load JSON file from session directory"""
#     filepath = os.path.join(get_session_dir(), filename)
#     if os.path.exists(filepath):
#         try:
#             with open(filepath, 'r') as f:
#                 return json.load(f)
#         except Exception:
#             return None
#     return None

def load_json_file(filename: str) -> Optional[Dict]:
    """Load JSON file from session directory"""
    filepath = os.path.join(get_session_dir(), filename)
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"JSON decode error in {filename}: {e}")
            return None
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            return None
    else:
        print(f"File not found: {filepath}")
    return None

def create_results_zip() -> io.BytesIO:
    """Create ZIP file with all results"""
    zip_buffer = io.BytesIO()
    session_dir = Path(get_session_dir())
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for json_file in session_dir.glob('*.json'):
            zip_file.write(json_file, json_file.name)
        
        # Add pipeline log if exists
        log_file = session_dir / 'pipeline.log'
        if log_file.exists():
            zip_file.write(log_file, 'pipeline.log')
    
    zip_buffer.seek(0)
    return zip_buffer

def get_pipeline_logs() -> str:
    """Get last 1000 characters of pipeline logs"""
    log_file = os.path.join(get_session_dir(), 'pipeline.log')
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                content = f.read()
                return content[-1000:] if len(content) > 1000 else content
        except Exception:
            return "Log file not accessible"
    return "No logs available yet"

# ============================================================================
# STREAMLIT UI
# ============================================================================

def main():
    st.set_page_config(
        page_title="Content Agent System",
        page_icon="🚀",
        layout="wide"
    )
    
    # Initialize session and cleanup
    init_session_state()
    cleanup_old_sessions()
    st.session_state.last_activity = datetime.now()
    
    # Process any status updates from background thread
    process_status_updates()
    
    # Header
    st.title("🚀 Content Agent System")
    st.markdown("*Autonomous content marketing intelligence platform*")
    st.divider()
    
    # ========================================================================
    # SECTION 1: CONFIGURATION
    # ========================================================================
    
    st.header("⚙️ Configuration")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader("Competitor Sitemap URLs")
        
        # Display competitor URL inputs
        for idx in range(len(st.session_state.competitor_urls)):
            col_input, col_btn = st.columns([5, 1])
            
            with col_input:
                url = st.text_input(
                    f"Competitor {idx + 1}",
                    value=st.session_state.competitor_urls[idx],
                    key=f"competitor_url_{idx}",
                    disabled=st.session_state.pipeline_running
                )
                st.session_state.competitor_urls[idx] = url
            
            with col_btn:
                if len(st.session_state.competitor_urls) > 1:
                    if st.button("❌", key=f"remove_{idx}", disabled=st.session_state.pipeline_running):
                        st.session_state.competitor_urls.pop(idx)
                        st.rerun()
    
    with col2:
        st.markdown("###")  # Spacing
        if st.button("➕ Add Competitor", disabled=st.session_state.pipeline_running):
            st.session_state.competitor_urls.append('')
            st.rerun()
    
    st.divider()
    
    # Run Pipeline Button
    col_btn1, col_btn2, col_btn3 = st.columns([2, 2, 6])
    
    with col_btn1:
        if st.button(
            "▶️ Run Pipeline",
            disabled=st.session_state.pipeline_running,
            type="primary",
            use_container_width=True
        ):
            # Validate URLs
            valid_urls = [url for url in st.session_state.competitor_urls if url.strip()]
            
            if not valid_urls:
                st.error("Please add at least one competitor sitemap URL")
            else:
                # Validate each URL
                all_valid = True
                for url in valid_urls:
                    is_valid, message = validate_sitemap_url(url)
                    if not is_valid:
                        st.error(f"Invalid URL {url}: {message}")
                        all_valid = False
                
                if all_valid:
                    # Clear previous results and start pipeline
                    clear_session_results()
                    ensure_session_directory()
                    st.session_state.pipeline_running = True
                    st.session_state.error_message = None
                    
                    # Start pipeline in background thread
                    thread = threading.Thread(
                        target=run_pipeline_thread,
                        args=(valid_urls, get_session_dir(), st.session_state.status_queue)
                    )
                    thread.daemon = True
                    thread.start()
                    
                    st.rerun()
    
    with col_btn2:
        if st.button("🗑️ Clear Results", disabled=st.session_state.pipeline_running):
            clear_session_results()
            st.rerun()
    
    # ========================================================================
    # SECTION 2: EXECUTION MONITOR
    # ========================================================================
    
    if st.session_state.pipeline_running or st.session_state.results_ready:
        st.divider()
        st.header("⏳ Execution Status")
        
        # Progress bar
        progress = st.session_state.pipeline_status['progress']
        st.progress(progress / 100)
        st.markdown(f"**Overall Progress: {progress}%**")
        
        # Phase indicators
        col1, col2, col3 = st.columns(3)
        
        status_icons = {
            'pending': '⏸️',
            'running': '⏳',
            'completed': '✅',
            'failed': '❌'
        }
        
        with col1:
            status = st.session_state.pipeline_status['phase1']
            st.metric(
                "Phase 1: Data Collection",
                status_icons[status] + " " + status.title()
            )
        
        with col2:
            status = st.session_state.pipeline_status['phase2']
            st.metric(
                "Phase 2: Analysis",
                status_icons[status] + " " + status.title()
            )
        
        with col3:
            status = st.session_state.pipeline_status['phase3']
            st.metric(
                "Phase 3: Brief Generation",
                status_icons[status] + " " + status.title()
            )
        
        # Error message
        if st.session_state.error_message:
            st.error(st.session_state.error_message)
        
        # Logs
        with st.expander("📋 View Detailed Logs"):
            logs = get_pipeline_logs()
            st.code(logs, language=None)
        
        # Completion handling
        if st.session_state.results_ready and not st.session_state.pipeline_running:
            st.success("✅ Pipeline completed successfully!")
            st.balloons()
        
        # Auto-refresh while running
        if st.session_state.pipeline_running:
            time.sleep(2)
            st.rerun()
    
    # ========================================================================
    # SECTION 3: RESULTS
    # ========================================================================
    
    if st.session_state.results_ready:
        st.divider()
        st.header("📊 Results")
        
        # Download button
        zip_buffer = create_results_zip()
        st.download_button(
            label="📥 Download All Results (ZIP)",
            data=zip_buffer,
            file_name=f"content_agent_results_{st.session_state.session_id}.zip",
            mime="application/zip"
        )
        
        # Results tabs
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📄 Sitemaps",
            "📱 Social Trends", 
            "🔍 Content Gaps",
            "🔥 Trending Topics",
            "📋 Content Briefs"
        ])
        
        # Tab 1: Sitemaps
        with tab1:
            data = load_json_file('sitemaps_data.json')
            if data:
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Own Site Titles", len(data.get('ai_certs_titles', [])))
                with col2:
                    st.metric("Competitor Titles", len(data.get('competitor_titles', [])))
                
                with st.expander("View Own Site Titles (First 50)"):
                    titles = data.get('ai_certs_titles', [])[:50]
                    for title in titles:
                        st.write(f"- {title}")
                
                with st.expander("View Competitor Titles (First 50)"):
                    titles = data.get('competitor_titles', [])[:50]
                    for title in titles:
                        st.write(f"- {title}")
            else:
                st.info("No sitemap data available")
        
        # Tab 2: Social Trends
        with tab2:
            data = load_json_file('social_trends_raw.json')
            if data and isinstance(data, list):
                st.metric("Posts Analyzed", len(data))
                st.dataframe(data, use_container_width=True)
            else:
                st.info("No social trends data available")
        
        # Tab 3: Content Gaps
        with tab3:
            data = load_json_file('content_gaps_report.json')
            if data:
                gaps = data.get('content_gaps', [])
                st.metric("Content Gaps Detected", len(gaps))
                
                for gap in gaps:
                    with st.expander(f"**{gap.get('gap_topic', 'Unknown')}**"):
                        st.write(f"**Competitor Coverage:** {gap.get('competitor_coverage', 0)} sources")
                        if 'reasoning' in gap:
                            st.write(gap['reasoning'])
            else:
                st.info("No content gaps data available")
        
        # Tab 4: Trending Topics
        with tab4:
            data = load_json_file('trending_topics_report.json')
            if data:
                topics = data.get('trending_topics', [])
                st.metric("Trending Topics Identified", len(topics))
                
                # Create table
                table_data = []
                for topic in topics:
                    metrics = topic.get('metrics', {})
                    table_data.append({
                        'Rank': topic.get('rank', 0),
                        'Topic': topic.get('topic_cluster', ''),
                        'Relevance Score': f"{topic.get('relevance_score', 0):.1f}",
                        'Engagement': f"{metrics.get('engagement_score', 0):.1f}",
                        'Freshness': f"{metrics.get('freshness_score', 0):.1f}",
                        'Frequency': metrics.get('frequency', 0)
                    })
                
                st.dataframe(table_data, use_container_width=True)
            else:
                st.info("No trending topics data available")
        
        # Tab 5: Content Briefs
        with tab5:
            data = load_json_file('content_briefs.json')
            if data and isinstance(data, list):
                st.metric("Content Briefs Generated", len(data))
                
                for idx, brief_data in enumerate(data):
                    brief = brief_data.get('brief', {})
                    with st.expander(
                        f"**{brief_data.get('topic', 'Unknown Topic')}** "
                        f"[{brief_data.get('priority', 'Medium')} Priority]"
                    ):
                        st.write(f"**Source:** {brief_data.get('source_type', 'Unknown')}")
                        st.write(f"**Audience:** {brief.get('audience', 'N/A')}")
                        st.write(f"**Job to be Done:** {brief.get('job_to_be_done', 'N/A')}")
                        st.write(f"**Angle:** {brief.get('angle', 'N/A')}")
                        st.write(f"**Promise:** {brief.get('promise', 'N/A')}")
                        st.write(f"**Call to Action:** {brief.get('cta', 'N/A')}")
                        
                        st.write("**Key Talking Points:**")
                        for point in brief.get('key_talking_points', []):
                            st.write(f"- {point}")
            else:
                st.info("No content briefs available")
    
    # ========================================================================
    # FOOTER
    # ========================================================================
    
    st.divider()
    st.caption(f"Content Agent System v1.0 | Built with Streamlit | Session: {st.session_state.session_id}")

if __name__ == "__main__":
    main()