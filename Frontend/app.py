import streamlit as st
import requests
import pandas as pd
import json
from typing import List
from pathlib import Path

# -----------------------------
# CONFIG
# -----------------------------
API_URL = "http://localhost:8000/pipeline/run"
TEST_FILE_PATH = Path(r"C:\AI Certs\Autonomous-Content-Agent-System\Backend\data\test_data.json")

st.set_page_config(page_title="Content Strategy Optimizer", layout="wide")

# Initialize session state for modal
if 'selected_brief_idx' not in st.session_state:
    st.session_state.selected_brief_idx = None

# -----------------------------
# CUSTOM CSS
# -----------------------------
st.markdown("""
<style>
/* --- DARK THEME FIX --- */
@media (prefers-color-scheme: dark) {
    .modal-content {
        background: #1e1e1e !important;
        color: #f3f4f6 !important;
    }
    .modal-title, .brief-value, .brief-label {
        color: #f3f4f6 !important;
    }
    .priority-badge {
        filter: brightness(1.2);
    }
    .talking-points li {
        border-bottom: 1px solid #333 !important;
    }
    .talking-points li:before {
        color: #60a5fa !important;
    }
    .brief-section {
        border-color: #333 !important;
    }
    .modal-close-btn:hover {
        background: #2d2d2d !important;
    }
}
            
/* Hide default streamlit button styling */
.stButton button {
    background: none;
    border: none;
    padding: 0;
    margin: 0;
    width: 100%;
    height: 100%;
}

.stButton button:hover {
    background: none;
    border: none;
}

.stButton button:focus {
    outline: none;
    box-shadow: none;
}

/* Card Grid */
.cards-container {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 1.5rem;
    margin: 2rem 0;
}

/* Individual Card */
.brief-card {
    background: rgba(249, 250, 251, 0.95);
    border-radius: 12px;
    padding: 1.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    transition: all 0.25s ease;
    cursor: pointer;
    position: relative;
    border: 1px solid rgba(229, 231, 235, 0.8);
    border-left: 3px solid;
    min-height: 160px;
    display: flex;
    flex-direction: column;
}

.brief-card.priority-high {
    border-left-color: #EF4444;
}

.brief-card.priority-medium {
    border-left-color: #F59E0B;
}

.brief-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 10px 20px rgba(0,0,0,0.08);
    border-left-width: 4px;
    background: rgba(255, 255, 255, 0.98);
}

/* Priority Badge */
.priority-badge {
    position: absolute;
    top: 12px;
    right: 12px;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.priority-high {
    background: #FEE2E2;
    color: #991B1B;
}

.priority-medium {
    background: #FEF3C7;
    color: #92400E;
}

/* Source Icon */
.source-icon {
    width: 40px;
    height: 40px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.4rem;
    margin-bottom: 1rem;
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(139, 92, 246, 0.1) 100%);
    border: 1px solid rgba(99, 102, 241, 0.2);
}

/* Card Title */
.card-title {
    font-size: 1.05rem;
    font-weight: 600;
    color: #111827;
    margin: 0.5rem 0;
    line-height: 1.4;
    flex-grow: 1;
}

/* Card Meta */
.card-meta {
    font-size: 0.8rem;
    color: #6B7280;
    margin-top: auto;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-weight: 500;
}

/* Modal Styles */
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(4px);
    z-index: 999999;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2rem;
    animation: fadeIn 0.2s ease;
}

.modal-content {
    background: white;
    border-radius: 16px;
    max-width: 800px;
    max-height: 85vh;
    overflow-y: auto;
    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
    animation: slideUp 0.3s ease;
    position: relative;
}

.modal-header {
    padding: 2rem 2rem 1rem 2rem;
    border-bottom: 1px solid #e5e7eb;
    position: sticky;
    top: 0;
    background: white;
    z-index: 10;
    border-radius: 16px 16px 0 0;
}

.modal-body {
    padding: 2rem;
}

.modal-title {
    font-size: 1.75rem;
    font-weight: 700;
    color: #1a1a1a;
    margin-bottom: 1rem;
    line-height: 1.3;
    padding-right: 3rem;
}

/* Brief Details */
.brief-section {
    margin-bottom: 1.5rem;
}

.brief-label {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    color: #6b7280;
    margin-bottom: 0.5rem;
    letter-spacing: 0.5px;
}

.brief-value {
    font-size: 1rem;
    color: #1a1a1a;
    line-height: 1.6;
}

.talking-points {
    list-style: none;
    padding: 0;
    margin: 0;
}

.talking-points li {
    padding: 0.75rem 0;
    border-bottom: 1px solid #f3f4f6;
    display: flex;
    gap: 0.75rem;
}

.talking-points li:last-child {
    border-bottom: none;
}

.talking-points li:before {
    content: "▸";
    color: #4B9EFF;
    font-weight: bold;
    flex-shrink: 0;
}

/* Animations */
@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

@keyframes slideUp {
    from { 
        opacity: 0;
        transform: translateY(20px);
    }
    to { 
        opacity: 1;
        transform: translateY(0);
    }
}

/* Empty State */
.empty-state {
    text-align: center;
    padding: 4rem 2rem;
    color: #6b7280;
}

.empty-state-icon {
    font-size: 4rem;
    margin-bottom: 1rem;
}

/* Close button in modal */
.modal-close-btn {
    position: absolute;
    top: 1.5rem;
    right: 1.5rem;
    background: none;
    border: none;
    font-size: 1.5rem;
    color: #6b7280;
    cursor: pointer;
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    transition: all 0.2s ease;
}

.modal-close-btn:hover {
    background: #f3f4f6;
    color: #1a1a1a;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def get_source_icon(source_type):
    """Return emoji icon based on source type"""
    icons = {
        "Trending Topic": "🔥",
        "Content Gap": "🕳️",
        "Competitor": "🎯",
        "Own Content": "📝"
    }
    return icons.get(source_type, "📄")

def get_source_class(source_type):
    """Return CSS class for source type"""
    classes = {
        "Trending Topic": "source-trending",
        "Content Gap": "source-gap",
        "Competitor": "source-competitor",
        "Own Content": "source-own"
    }
    return classes.get(source_type, "source-trending")

def close_modal():
    """Close the modal"""
    st.session_state.selected_brief_idx = None

# -----------------------------
# HEADER
# -----------------------------
st.title("🧭 Content Strategy Optimizer")
st.caption("AI-powered tool for competitive content analysis & creative brief generation")

st.markdown("---")

# -----------------------------
# INPUT FORM
# -----------------------------
with st.form("input_form"):
    st.subheader("⚙️ Configuration")

    our_url = st.text_input("Your Website URL", "https://www.aicerts.ai/")
    competitors_input = st.text_area(
        "Competitor URLs (one per line)",
        "https://www.coursera.org\nhttps://www.udemy.com"
    )
    keywords = st.text_input("Keywords (comma separated)", "AI, Machine Learning, Data Science")

    use_test_file = st.checkbox("🧪 Use Local Test File (Skip API Call)", value=True)

    submitted = st.form_submit_button("🚀 Run Pipeline")

# -----------------------------
# EXECUTION
# -----------------------------
if submitted:
    # Reset modal state on new submission
    st.session_state.selected_brief_idx = None
    
    with st.spinner("Running pipeline... This may take a few minutes ⏳"):
        try:
            # Prepare payload
            payload = {
                "our_url": our_url.strip(),
                "competitors": [c.strip() for c in competitors_input.split("\n") if c.strip()],
                "keywords": [k.strip() for k in keywords.split(",") if k.strip()]
            }

            # -----------------------------
            # TEST MODE (Load local JSON)
            # -----------------------------
            if use_test_file:
                if not TEST_FILE_PATH.exists():
                    st.error(f"❌ Test file not found: {TEST_FILE_PATH}")
                    st.stop()

                st.info(f"🧩 Loading local test data from `{TEST_FILE_PATH}`...")
                with open(TEST_FILE_PATH, "r", encoding="utf-8") as f:
                    result = json.load(f)
            else:
                # -----------------------------
                # API MODE (Hit FastAPI endpoint)
                # -----------------------------
                response = requests.post(API_URL, json=payload)
                if response.status_code != 200:
                    st.error(f"❌ API Error: {response.text}")
                    st.stop()
                result = response.json()

            # Store result in session state
            st.session_state.result = result

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.stop()

# Display results if available
if 'result' in st.session_state:
    result = st.session_state.result
    
    # -----------------------------
    # SUMMARY SECTION
    # -----------------------------
    st.success("✅ Pipeline completed successfully!")

    st.markdown("### 📊 Summary")
    col1, col2, col3 = st.columns(3)
    col1.metric("Own Pages", result["summary"]["own_pages"])
    col2.metric("Competitors", result["summary"]["competitors_analyzed"])
    col3.metric("Briefs Generated", result["summary"]["briefs_generated"])

    st.markdown("---")

    # -----------------------------
    # CONTENT BRIEFS (CARD VIEW)
    # -----------------------------
    st.markdown("## 🧾 Content Briefs")

    briefs = result["data"]["briefs"]

    if not briefs:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-state-icon">📭</div>
            <div>No content briefs available</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Create grid of cards using markdown containers with clickable buttons
        cols_per_row = 3
        for i in range(0, len(briefs), cols_per_row):
            cols = st.columns(cols_per_row)
            
            for j, col in enumerate(cols):
                idx = i + j
                if idx < len(briefs):
                    brief = briefs[idx]
                    topic = brief.get("topic", "Untitled Topic")
                    source = brief.get("source_type", "Unknown")
                    priority = brief.get("priority", "Medium")
                    
                    priority_class = f"priority-{priority.lower()}"
                    source_icon = get_source_icon(source)
                    source_class = get_source_class(source)
                    
                    with col:
                        # Create card with markdown and button
                        priority_class_name = f"priority-{priority.lower()}"
                        st.markdown(f"""
                        <div class="brief-card {priority_class_name}" style="margin-bottom: 0.5rem;">
                            <div class="priority-badge {priority_class_name}">{priority}</div>
                            <div class="source-icon">{source_icon}</div>
                            <div class="card-title">{topic}</div>
                            <div class="card-meta">
                                <span>📂 {source}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Add invisible button on top
                        if st.button("View Details", key=f"card_{idx}", use_container_width=True):
                            st.session_state.selected_brief_idx = idx
                            st.rerun()

        # Display modal if a brief is selected
        if st.session_state.selected_brief_idx is not None:
            idx = st.session_state.selected_brief_idx
            if 0 <= idx < len(briefs):
                brief = briefs[idx]
                b = brief.get("brief", {})
                topic = brief.get("topic", "Untitled Topic")
                source = brief.get("source_type", "Unknown")
                priority = brief.get("priority", "Medium")
                priority_class = f"priority-{priority.lower()}"
                
                audience = b.get("audience", "N/A")
                job = b.get("job_to_be_done", "N/A")
                angle = b.get("angle", "N/A")
                promise = b.get("promise", "N/A")
                cta = b.get("cta", "")
                points = b.get("key_talking_points", [])
                
                # Build talking points HTML
                points_html = ""
                if points:
                    points_items = "".join([f"<li>{p}</li>" for p in points])
                    points_html = f"""
                    <div class="brief-section">
                        <div class="brief-label">🗣️ Key Talking Points</div>
                        <ul class="talking-points">
                            {points_items}
                        </ul>
                    </div>
                    """
                
                # Build CTA HTML
                cta_html = ""
                if cta:
                    cta_html = f"""
                    <div class="brief-section">
                        <div class="brief-label">📌 Call to Action</div>
                        <div class="brief-value">{cta}</div>
                    </div>
                    """
                
                # Create modal using st.dialog (Streamlit's native modal)
                @st.dialog(topic, width="large")
                def show_brief_modal():
                    st.markdown(f"""
                    <div style="display: flex; gap: 1rem; align-items: center; margin-bottom: 1.5rem;">
                        <span class="priority-badge {priority_class}">{priority}</span>
                        <span style="color: #6b7280; font-size: 0.9rem;">📂 {source}</span>
                    </div>
                    
                    <div class="brief-section">
                        <div class="brief-label">🎯 Target Audience</div>
                        <div class="brief-value">{audience}</div>
                    </div>
                    
                    <div class="brief-section">
                        <div class="brief-label">🧩 Job to be Done</div>
                        <div class="brief-value">{job}</div>
                    </div>
                    
                    <div class="brief-section">
                        <div class="brief-label">💡 Angle</div>
                        <div class="brief-value">{angle}</div>
                    </div>
                    
                    <div class="brief-section">
                        <div class="brief-label">✨ Promise</div>
                        <div class="brief-value">{promise}</div>
                    </div>
                    
                    {cta_html}
                    {points_html}
                    """, unsafe_allow_html=True)
                    
                    if st.button("Close", type="primary", use_container_width=True):
                        st.session_state.selected_brief_idx = None
                        st.rerun()
                
                show_brief_modal()

    # -----------------------------
    # TRENDING TOPICS
    # -----------------------------
    with st.expander("🔥 Trending Topics", expanded=False):
        trending_block = result["data"]["trending_topics"]
        trending_data = trending_block.get("trending_topics", [])

        if not trending_data:
            st.info("No trending topics available.")
        else:
            topics_flat = []
            for t in trending_data:
                row = {
                    "Rank": t.get("rank"),
                    "Topic Cluster": t.get("topic_cluster"),
                    "Relevance Score": t.get("relevance_score"),
                    "Freshness Score": t["metrics"].get("freshness_score"),
                    "Engagement Score": t["metrics"].get("engagement_score"),
                    "Frequency": t["metrics"].get("frequency"),
                    "Total Engagement": t["metrics"].get("total_engagement"),
                }
                topics_flat.append(row)

            topics_df = pd.DataFrame(topics_flat).sort_values(by="Rank")
            st.dataframe(topics_df, use_container_width=True)

            st.caption(
                f"📅 Analysis Timestamp: {trending_block['analysis_timestamp']} | "
                f"Elbow Threshold: {trending_block['elbow_threshold']}"
            )

    # -----------------------------
    # CONTENT GAPS
    # -----------------------------
    with st.expander("🕳️ Content Gaps", expanded=False):
        content_gaps = result["data"].get("content_gaps", [])
        if not content_gaps:
            st.info("No content gaps found.")
        else:
            gaps_df = pd.DataFrame(content_gaps)
            st.dataframe(gaps_df, use_container_width=True)