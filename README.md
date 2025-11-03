# Content Strategy Pipeline System

A comprehensive, production-ready autonomous content marketing intelligence platform that discovers trending topics, identifies content gaps, and generates actionable content briefs through parallel processing.

## Table of Contents
- [System Overview](#system-overview)
- [Architecture](#architecture)
- [Installation & Setup](#installation--setup)
- [Configuration](#configuration)
- [Running the System](#running-the-system)
- [Pipeline Phases](#pipeline-phases)
- [Output Files](#output-files)
- [Performance & Optimization](#performance--optimization)
- [Error Handling](#error-handling)
- [Troubleshooting](#troubleshooting)
- [API Requirements](#api-requirements)

## System Overview

### What This System Does

This system automates content strategy research by:

1. **Scraping competitor websites** to understand their content landscape
2. **Mining social media trends** from Reddit to identify hot topics
3. **Analyzing content gaps** between your content and competitors
4. **Clustering trending discussions** into actionable topic groups
5. **Generating content briefs** with audience, angle, and talking points

### Key Features

- **Parallel Processing**: Phases 1 & 2 run concurrently for 40-50% faster execution
- **Real-time Progress Tracking**: Visual progress bars for each phase
- **Robust Error Handling**: Automatic retries and graceful degradation
- **Structured Outputs**: JSON files with validated schemas
- **Multi-Competitor Support**: Analyze up to 5 competitors simultaneously
- **Scalable Architecture**: ThreadPoolExecutor for I/O-bound operations

### Performance Metrics

- **Total Pipeline Time**: 7-16 minutes (vs 13-26 minutes sequential)
- **Concurrent Agents**: 6 parallel workers in data collection
- **Sitemap Processing**: Up to 15 concurrent page fetches
- **Reddit Mining**: 10 concurrent subreddit threads

## Architecture

### System Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│           CONTENT PIPELINE (content_pipeline.py)        │
└─────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┴──────────────────┐
        │                                     │
        ▼                                     ▼
┌───────────────────┐              ┌───────────────────┐
│   PHASE 1 & 2     │              │  Progress Tracker │
│   (PARALLEL)      │◄─────────────┤   (Threading)     │
└───────┬───────────┘              └───────────────────┘
        │
   ┌────┴────┐
   │         │
   ▼         ▼
┌──────┐  ┌──────────────┐
│Sitemap│  │Social Trend  │
│Agent  │  │Miner         │
└───┬───┘  └──────┬───────┘
    │             │
    └──────┬──────┘
           │
    ┌──────▼──────┐
    │  PHASE 3 & 4 │
    │  (PARALLEL)  │
    └──────┬───────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌─────────┐  ┌──────────┐
│Gap      │  │Trend     │
│Analyzer │  │Clusterer │
└────┬────┘  └─────┬────┘
     │             │
     └──────┬──────┘
            │
     ┌──────▼──────┐
     │   PHASE 5    │
     │ (SEQUENTIAL) │
     └──────┬───────┘
            │
     ┌──────▼──────┐
     │Brief        │
     │Generator    │
     └──────┬──────┘
            │
     ┌──────▼──────┐
     │content_     │
     │briefs.json  │
     └─────────────┘
```

### Component Overview

| Component | Purpose | Execution Mode | Duration |
|-----------|---------|----------------|----------|
| `sitemap_agent.py` | Scrapes competitor sitemaps & extracts titles | Async parallel | 2-4 min |
| `social_trend_miner.py` | Mines Reddit posts for trending discussions | Parallel threads | 2-3 min |
| `gap_analyzer.py` | Identifies content gaps vs competitors | Parallel per competitor | 3-5 min |
| `trend_clusterer.py` | Clusters social posts into topic groups | Sequential | 2-4 min |
| `brief_generator.py` | Generates actionable content briefs | Sequential | 2-3 min |

## Installation & Setup

### Prerequisites

- Python 3.8+
- 4GB+ RAM (for concurrent processing)
- OpenAI API key with GPT-4 access
- Reddit API credentials (client_id, client_secret)

### Step 1: Clone & Install

```bash
# Clone repository
git clone <repository-url>
cd content-pipeline

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Environment Variables

Create a `.env` file in the root directory:

```bash
# OpenAI API (required)
OPENAI_API_KEY=sk-your-openai-api-key

# Reddit API (required)
client_id=your_reddit_client_id
client_secret=your_reddit_client_secret
user_agent=ContentAgent/1.0 by YourUsername
```

### Step 3: Verify Setup

```bash
# Create data directory
mkdir -p data

# Test imports
python -c "from content_pipeline import *; print('✅ Setup successful')"
```

## Configuration

The system is configured through `.env` file and hardcoded parameters in `content_pipeline.py`. Key parameters:

### Sitemap Scraping Configuration

```python
scraper = WebScraper(
    delay=0.1,          # Rate limiting delay (seconds)
    timeout=10,         # Request timeout
    max_pages=15,       # Pages to scrape per site
    max_depth=1,        # Sitemap recursion depth
    max_concurrent=15   # Concurrent page fetches
)
```

### Reddit Mining Configuration

```python
miner = RedditTrendMiner(
    max_workers=10  # Concurrent subreddit threads
)

keywords = ["MachineLearning", "AI", "DataScience"]
start_date = datetime(2025, 10, 24)
end_date = datetime(2025, 10, 30)
posts_limit = 50  # Posts per subreddit
top_subs = 3      # Top subreddits per keyword
```

### Target URLs

Modify in `content_pipeline.py`:

```python
our_url = "https://www.aicerts.ai/"

competitors = [
    "https://www.mygreatlearning.com",
    "https://www.coursera.org",
    "https://www.udemy.com",
    "https://www.simplilearn.com"
]

keywords = ['course', 'certification', 'program']
```

## Running the System

### Full Pipeline Execution

```bash
python content_pipeline.py
```

### Expected Output

```
======================================================================
⏱️  Elapsed Time: 0.1s
======================================================================
⏸️ sitemap_scraping     [░░░░░░░░░░░░░░░░░░░░] 0/5 (0%)
⏸️ social_mining        [░░░░░░░░░░░░░░░░░░░░] 0/1 (0%)
⏸️ trend_analysis       [pending]
⏸️ gap_analysis         [pending]
⏸️ brief_generation     [pending]
======================================================================

======================================================================
🚀 PHASE 1 & 2: PARALLEL DATA COLLECTION
======================================================================
🔍 Starting scrape: https://www.aicerts.ai/ (own site)
🔍 Starting social trend mining...
✅ Completed scrape: https://www.aicerts.ai/ (15 pages)
✅ Completed social mining: 150 posts

======================================================================
🚀 PHASE 3 & 4: PARALLEL ANALYSIS
======================================================================
⚙️  Starting trend analysis...
⚙️  Finding content gaps vs competitors...
✅ Completed trend analysis: 8 clusters
✅ Found 12 gaps for https://www.coursera.org

======================================================================
🚀 PHASE 5: CONTENT BRIEF GENERATION
======================================================================
✅ Saved 20 generated briefs.

======================================================================
🎉 PIPELINE COMPLETED SUCCESSFULLY
======================================================================
⏱️  Total Execution Time: 754.32s (12.57 minutes)
📊 Results:
   - Own pages scraped: 15
   - Competitors analyzed: 4
   - Social posts mined: 150
   - Trending clusters: 8
   - Content gaps found: 48
   - Content briefs generated: 20
======================================================================
```

### Individual Component Testing

```bash
# Test sitemap scraping only
python sitemap_agent.py

# Test Reddit mining only
python social_trend_miner.py

# Test gap analysis (requires sitemaps_data.json)
python gap_analyzer.py

# Test trend clustering (requires social_trends_raw.json)
python trend_clusterer.py

# Test brief generation (requires gaps + trends)
python brief_generator.py
```

## Agent Deep Dive

### Agent 1: Sitemap Agent (`sitemap_agent.py`)

**Purpose**: High-performance asynchronous web scraper that discovers and crawls website sitemaps to extract page metadata.

**How It Works**:

```
┌─────────────────────────────────────────────────────────┐
│              SITEMAP AGENT WORKFLOW                     │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────┐
│ 1. Sitemap Discovery│
│  - Try common paths │
│    /sitemap.xml     │
│    /sitemap_index   │
│  - Check robots.txt │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 2. XML Parsing      │
│  - Detect sitemap   │
│    index vs regular │
│  - Extract all URLs │
│  - Get lastmod dates│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 3. Recursive Crawl  │
│  - Handle sitemap   │
│    indexes          │
│  - Follow child     │
│    sitemaps         │
│  - Max depth: 1     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 4. URL Filtering    │
│  - Match keywords   │
│  - Date range check │
│  - Remove duplicates│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 5. Page Scraping    │
│  - Async fetch 15   │
│    pages at once    │
│  - Extract title    │
│  - Extract desc     │
│  - Extract date     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 6. Data Validation  │
│  - Verify date range│
│  - Deduplicate      │
│  - Sort by date     │
└──────────┬──────────┘
           │
           ▼
    sitemaps_data.json
```

**Key Technical Features**:
- **Async I/O**: Uses `aiohttp` with `TCPConnector` for concurrent requests
- **Namespace Handling**: Parses XML with/without namespace declarations
- **Rate Limiting**: Configurable delay between requests (default: 0.1s)
- **Error Recovery**: Individual page failures don't crash entire scrape
- **Smart Filtering**: Pre-filters URLs by sitemap dates before fetching

**Configuration Parameters**:
```python
scraper = WebScraper(
    delay=0.1,          # Delay between requests
    timeout=10,         # Request timeout in seconds
    max_pages=15,       # Maximum pages to scrape
    max_depth=1,        # Sitemap recursion depth
    max_concurrent=15   # Concurrent page fetches
)
```

**Output Schema**:
```json
{
  "our_pages": [
    {
      "title": "AI Foundation Course by AICerts",
      "description": "Master the future with AI Foundation Course...",
      "url": "https://www.aicerts.ai/certifications/ai-foundation/",
      "date": "2025-07-07"
    }
  ],
  "competitor_pages": {
    "https://www.mygreatlearning.com": [
      {
        "title": "Free Excel Courses with Certificates",
        "description": "Learn formulas, pivot tables...",
        "url": "https://www.mygreatlearning.com/excel/free-courses",
        "date": "2025-08-08"
      }
    ]
  }
}
```

---

### Agent 2: Social Trend Miner (`social_trend_miner.py`)

**Purpose**: Discovers trending discussions from Reddit by searching relevant subreddits and extracting posts with engagement metrics.

**How It Works**:

```
┌─────────────────────────────────────────────────────────┐
│           SOCIAL TREND MINER WORKFLOW                   │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────┐
│ 1. Keyword Input    │
│  - MachineLearning  │
│  - AI               │
│  - DataScience      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 2. Subreddit Search │
│  - Query Reddit API │
│  - Get top 3 subs   │
│    per keyword      │
│  - Handle private   │
│    subreddits       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 3. Parallel Fetch   │
│  - ThreadPoolExec   │
│    10 workers       │
│  - Fetch posts from │
│    all subreddits   │
│  - Handle API errors│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 4. Post Extraction  │
│  - Get new posts    │
│  - Extract title    │
│  - Get score (votes)│
│  - Get comments     │
│  - Get timestamp    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 5. Date Filtering   │
│  - Filter by range  │
│  - Sort by timestamp│
│  - Limit per sub    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 6. Data Aggregation │
│  - Combine all posts│
│  - Remove duplicates│
│  - Add metadata     │
└──────────┬──────────┘
           │
           ▼
  social_trends_raw.json
```

**Key Technical Features**:
- **PRAW Library**: Python Reddit API Wrapper for authentication
- **Parallel Processing**: ThreadPoolExecutor with 10 concurrent workers
- **Error Handling**: Graceful handling of NotFound, Forbidden, ResponseException
- **Engagement Metrics**: Captures upvotes, downvotes, comments for scoring
- **Subreddit Discovery**: Automatic search for relevant communities

**Configuration Parameters**:
```python
miner = RedditTrendMiner(
    client_id="your_client_id",
    client_secret="your_client_secret",
    user_agent="ContentAgent/1.0",
    max_workers=10  # Concurrent subreddit threads
)

# Search parameters
keywords = ["MachineLearning", "AI", "DataScience"]
start_date = datetime(2025, 10, 24)
end_date = datetime(2025, 10, 30)
posts_limit = 50  # Posts per subreddit
top_subs = 3      # Top subreddits per keyword
```

**Output Schema**:
```json
[
  {
    "id": "1abc2de",
    "title": "RAG vs Fine-tuning: Comprehensive comparison",
    "selftext": "I've been experimenting with both approaches...",
    "score": 1500,
    "ups": 1520,
    "downs": 20,
    "comments": 89,
    "created_utc": "2025-10-25 14:30:00",
    "subreddit": "MachineLearning",
    "url": "https://www.reddit.com/r/MachineLearning/comments/..."
  }
]
```

---

### Agent 3: Gap Analyzer (`gap_analyzer.py`)

**Purpose**: Identifies content topics that competitors cover but are missing from your content library using LLM-powered thematic analysis.

**How It Works**:

```
┌─────────────────────────────────────────────────────────┐
│              GAP ANALYZER WORKFLOW                      │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────┐
│ 1. Input Loading    │
│  - Load own titles  │
│  - Load competitor  │
│    titles           │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 2. Per-Competitor   │
│    Analysis         │
│  - Parallel threads │
│  - One thread per   │
│    competitor       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 3. LLM Comparison   │
│  - Send both title  │
│    lists to GPT-4   │
│  - Request thematic │
│    gap analysis     │
│  - Get structured   │
│    response         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 4. Gap Extraction   │
│  - Parse Pydantic   │
│    response         │
│  - Extract gap_topic│
│  - Count competitor │
│    coverage         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 5. Retry Logic      │
│  - Max 3 retries    │
│  - Handle API errors│
│  - Return empty on  │
│    final failure    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 6. Gap Aggregation  │
│  - Combine gaps from│
│    all competitors  │
│  - Annotate with    │
│    competitor URL   │
│  - Sort by coverage │
└──────────┬──────────┘
           │
           ▼
content_gaps_report.json
```

**Key Technical Features**:
- **LLM-Powered**: Uses GPT-4 for semantic understanding of content themes
- **Pydantic Validation**: Structured response parsing with `GapItem` model
- **Parallel Competitor Analysis**: Each competitor analyzed in separate thread
- **Retry Mechanism**: 3 attempts per LLM call with exponential backoff
- **Coverage Scoring**: Estimates how many competitor titles mention each gap

**LLM Prompt Strategy**:
```python
prompt = f"""
Compare the following lists of webpage titles:
- Our Titles: {json.dumps(ai_titles, indent=2)}
- Competitor Titles: {json.dumps(competitor_titles, indent=2)}

Identify key content gaps – topics that competitors cover but we do not.
For each gap:
1. Provide a clear descriptive and human-readable title.
2. Estimate how many competitor titles mention or relate to it (competitor_coverage).
"""
```

**Pydantic Schema**:
```python
class GapItem(BaseModel):
    gap_topic: str
    competitor_coverage: int

class Gaps(BaseModel):
    gaps: List[GapItem]
```

**Output Schema**:
```json
[
  {
    "gap_topic": "Excel Courses for Data Analysis",
    "competitor_coverage": 4,
    "competitor": "https://www.mygreatlearning.com"
  },
  {
    "gap_topic": "Web Development Bootcamps",
    "competitor_coverage": 3,
    "competitor": "https://www.udemy.com"
  }
]
```

---

### Agent 4: Trend Clusterer (`trend_clusterer.py`)

**Purpose**: Transforms raw social media posts into actionable topic clusters with data-driven relevance scores using multi-factor analysis.

**How It Works**:

```
┌─────────────────────────────────────────────────────────┐
│            TREND CLUSTERER WORKFLOW                     │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────┐
│ 1. Post Grouping    │
│  - Group by         │
│    subreddit        │
│  - Create title-to- │
│    post mapping     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 2. Subreddit-wise   │
│    Clustering       │
│  - LLM clusters per │
│    subreddit        │
│  - Identify themes  │
│  - Group similar    │
│    titles           │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 3. Global Merging   │
│  - Merge clusters   │
│    with same name   │
│  - Combine titles   │
│  - Track subreddits │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 4. Engagement Score │
│  - Calculate total  │
│    upvotes          │
│  - Calculate total  │
│    comments         │
│  - Normalize 0-100  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 5. Freshness Score  │
│  - Time since post  │
│  - 14-day window    │
│  - Decay function   │
│  - Normalize 0-100  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 6. Frequency Score  │
│  - Count posts in   │
│    cluster          │
│  - Normalize 0-100  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 7. Weighted Scoring │
│  Relevance =        │
│  E×0.4 + F×0.35 +   │
│  Freq×0.25          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 8. Elbow Filtering  │
│  - Calculate elbow  │
│    threshold        │
│  - Filter low-score │
│    topics           │
│  - Return top trends│
└──────────┬──────────┘
           │
           ▼
trending_topics_report.json
```

**Key Technical Features**:
- **Subreddit-Wise Clustering**: Processes each subreddit independently for better topic separation
- **Global Merging**: Combines identical clusters across subreddits
- **Multi-Factor Scoring**: Weighted combination of engagement, freshness, and frequency
- **Elbow Method**: Statistical filtering to identify truly trending topics
- **Time-Decay Function**: Recent posts weighted higher than older ones

**Scoring Algorithm Details**:

**1. Engagement Score** (40% weight)
```python
# Raw engagement = (upvotes × 0.7) + (comments × 0.3)
engagement_score = (raw_engagement / max_engagement) * 100
```

**2. Freshness Score** (35% weight)
```python
days_ago = (current_time - post_date).days
freshness_score = max(((14 - days_ago) / 14) * 100, 0)
# Posts older than 14 days get 0 freshness
```

**3. Frequency Score** (25% weight)
```python
frequency_score = (post_count / max_frequency) * 100
```

**4. Final Relevance Score**
```python
relevance_score = (
    engagement_score * 0.4 +
    freshness_score * 0.35 +
    frequency_score * 0.25
)
```

**Elbow Method**:
```python
def elbow_threshold_detection(values):
    """
    Finds the 'elbow' point in relevance scores using 
    maximum perpendicular distance from baseline.
    Returns threshold where scores drop significantly.
    """
    sorted_vals = np.sort(values)[::-1]  # Descending
    # Calculate distances from line (first to last point)
    distances = perpendicular_distance(sorted_vals)
    elbow_idx = np.argmax(distances)
    threshold = sorted_vals[elbow_idx]
    return threshold
```

**LLM Clustering Prompt**:
```python
prompt = f"""
You are a research assistant specializing in thematic analysis.

Task: Analyze these post titles from r/{subreddit_name} and group them 
into meaningful topic clusters.

Instructions:
1. Identify common themes, technologies, concepts
2. Group similar titles together
3. Create descriptive cluster names (2-5 words)
4. Ensure each title assigned to exactly one cluster
5. Aim for 5-15 clusters

Titles: {titles}
"""
```

**Output Schema**:
```json
{
  "analysis_timestamp": "2025-11-03T10:30:00",
  "summary": {
    "total_clusters": 8,
    "total_posts_analyzed": 150,
    "topics_after_filtering": 5
  },
  "scoring_weights": {
    "engagement": 0.4,
    "freshness": 0.35,
    "frequency": 0.25
  },
  "elbow_threshold": 51.3,
  "trending_topics": [
    {
      "topic_cluster": "RAG vs Fine-Tuning Debate",
      "relevance_score": 86.39,
      "rank": 1,
      "metrics": {
        "freshness_score": 88.0,
        "engagement_score": 95.0,
        "frequency": 12,
        "total_engagement": 18500
      }
    }
  ]
}
```

---

### Agent 5: Brief Generator (`brief_generator.py`)

**Purpose**: Transforms content gaps and trending topics into actionable content briefs with strategic recommendations.

**How It Works**:

```
┌─────────────────────────────────────────────────────────┐
│            BRIEF GENERATOR WORKFLOW                     │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────┐
│ 1. Input Loading    │
│  - Load content gaps│
│  - Load trending    │
│    topics (filtered)│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 2. Topic Extraction │
│  - Extract gap      │
│    topics           │
│  - Extract trend    │
│    clusters above   │
│    elbow threshold  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 3. Logical Grouping │
│  - Group similar    │
│    topics into 3-7  │
│    clusters         │
│  - Separate by      │
│    source type      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 4. LLM Brief Gen    │
│  - Generate one     │
│    brief per cluster│
│  - Structured prompt│
│  - Pydantic schema  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 5. Brief Structure  │
│  - audience         │
│  - job_to_be_done   │
│  - angle            │
│  - promise          │
│  - cta              │
│  - talking_points   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 6. Priority         │
│    Assignment       │
│  - Content Gap: High│
│  - Trending: Medium │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 7. Validation       │
│  - Pydantic schema  │
│  - Retry on fail    │
│  - Max 3 attempts   │
└──────────┬──────────┘
           │
           ▼
   content_briefs.json
```

**Key Technical Features**:
- **Topic Clustering**: Groups similar gaps/trends for comprehensive briefs
- **Structured Output**: Pydantic models ensure consistent brief format
- **Priority Assignment**: Content gaps marked "High", trends marked "Medium"
- **Batch Processing**: Generates briefs in groups for efficiency
- **Retry Logic**: 3 attempts per LLM call with error handling

**Pydantic Schema**:
```python
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
```

**LLM Prompt Strategy**:
```python
prompt = f"""
You are a senior content strategist.

Group the following topics into 3–7 logical clusters.
For each cluster, generate one structured content brief.

Each brief should include:
- audience: Target demographic
- job_to_be_done: What problem they're solving
- angle: Unique content positioning
- promise: Key value proposition
- cta: Clear call-to-action
- key_talking_points: 3–6 concise outline points

Topics:
{topics}
Source Type: {source_type}
Priority: {priority}
"""
```

**Output Schema**:
```json
[
  {
    "source_type": "Content Gap",
    "topic": "Excel and Data Analysis Training",
    "priority": "High",
    "brief": {
      "audience": "Business analysts and data professionals seeking to upskill",
      "job_to_be_done": "Master Excel for advanced data analysis and reporting",
      "angle": "Excel as the foundation for data-driven decision making",
      "promise": "Transform raw data into actionable insights in hours, not days",
      "cta": "Enroll in our Excel for Data Professionals certification",
      "key_talking_points": [
        "Power Query for automated data transformation",
        "Advanced formulas for statistical analysis",
        "Pivot tables and charts for executive reporting",
        "Data modeling best practices",
        "Excel automation with macros"
      ]
    }
  },
  {
    "source_type": "Trending Topic",
    "topic": "RAG vs Fine-Tuning in AI",
    "priority": "Medium",
    "brief": {
      "audience": "AI practitioners and ML engineers evaluating LLM strategies",
      "job_to_be_done": "Choose the right LLM customization approach for their use case",
      "angle": "Practical comparison with real-world implementation guidance",
      "promise": "Make informed LLM strategy decisions backed by hands-on examples",
      "cta": "Download our RAG vs Fine-Tuning decision framework",
      "key_talking_points": [
        "When to use RAG vs Fine-Tuning",
        "Cost-benefit analysis of each approach",
        "Hybrid strategies for complex use cases",
        "Performance benchmarks and case studies"
      ]
    }
  }
]
```

---

## Pipeline Phases

### Phase 1 & 2: Parallel Data Collection

Runs **Sitemap Agent** and **Social Trend Miner** concurrently using `ThreadPoolExecutor` with 6 workers.

**Combined Output**: 
- `data/sitemaps_data.json` (own + competitor pages)
- `data/social_trends_raw.json` (Reddit posts with engagement)

### Phase 3 & 4: Parallel Analysis

Runs **Gap Analyzer** and **Trend Clusterer** concurrently. Gap analyzer processes each competitor in parallel threads.

**Combined Output**:
- `data/content_gaps_report.json` (gaps vs all competitors)
- `data/trending_topics_report.json` (scored and filtered topics)
- `data/social_trends_cluster.json` (intermediate clustering data)

### Phase 5: Content Brief Generation

Runs **Brief Generator** sequentially, combining gaps and trends into actionable briefs.

**Final Output**:
- `data/content_briefs.json` (ready-to-use content strategy)

## Output Files

All outputs are saved in the `data/` directory:

| File | Description | Schema |
|------|-------------|--------|
| `sitemaps_data.json` | Scraped page titles from own & competitor sites | `{our_pages: [], competitor_pages: {}}` |
| `social_trends_raw.json` | Raw Reddit posts with engagement metrics | `[{title, score, comments, subreddit, ...}]` |
| `social_trends_cluster.json` | Subreddit-wise clustered topics | `[{cluster_name, titles, subreddit}]` |
| `content_gaps_report.json` | Content gaps vs competitors | `[{gap_topic, competitor_coverage, competitor}]` |
| `trending_topics_report.json` | Ranked trending topics with scores | `{trending_topics: [], elbow_threshold}` |
| `content_briefs.json` | Final actionable content briefs | `[{source_type, topic, priority, brief}]` |

## Performance & Optimization

### Parallel Processing Benefits

**Sequential Execution (Old System)**
- Phase 1: 5-8 minutes (serial scraping)
- Phase 2: 6-14 minutes (serial analysis)
- Total: 13-26 minutes

**Parallel Execution (Current System)**
- Phase 1 & 2: 2-5 minutes (concurrent scraping + mining)
- Phase 3 & 4: 3-7 minutes (concurrent gap + trend analysis)
- Phase 5: 2-4 minutes (sequential brief generation)
- Total: 7-16 minutes (**~45% faster**)

### Resource Utilization

```python
# Phase 1 & 2: ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=6) as executor:
    # Sitemap scraping + Reddit mining run concurrently
    # 1 worker for own site + 4 for competitors + 1 for Reddit
```

### Optimization Tips

1. **Adjust Concurrency**: Increase `max_workers` for faster processing
   ```python
   ThreadPoolExecutor(max_workers=10)  # More workers = faster
   ```

2. **Reduce Data Volume**: Lower `posts_limit` and `max_pages`
   ```python
   posts_limit=25  # Fewer posts = faster processing
   max_pages=10    # Fewer pages = faster scraping
   ```

3. **Competitor Selection**: Analyze 2-3 key competitors instead of 5
   ```python
   competitors = [
       "https://www.coursera.org",
       "https://www.udemy.com"
   ]  # Fewer competitors = faster gaps
   ```

## Error Handling

### Retry Logic

Each agent has built-in retry mechanisms:

```python
# Sitemap Agent: Per-request retry
async def _fetch_page_details(...):
    try:
        # Fetch page
    except asyncio.TimeoutError:
        logger.debug("Timeout, will retry")
        return None  # Triggers automatic retry

# Gap Analyzer: LLM call retry
def make_llm_call(self, ..., max_retries=3):
    for attempt in range(max_retries):
        try:
            response = self.client.responses.parse(...)
            return response
        except Exception as e:
            logger.warning(f"Retry {attempt+1}/{max_retries}")
```

### Error Recovery

**Parallel Execution Failures**
- Individual agent failures don't crash entire pipeline
- Failed agents increment progress tracker
- Partial results are saved for debugging

**API Rate Limits**
- Exponential backoff on Reddit API errors
- OpenAI retry logic with 3 attempts
- Graceful degradation with partial data

### Logging

```python
# Progress tracking with visual feedback
tracker.update("sitemap_scraping", completed=3, total=5, status="running")

# Error logging with context
logger.error(f"Gap analysis failed for {comp_url}: {str(e)}")

# Phase completion tracking
logger.info("✅ PHASE 1 & 2: PARALLEL DATA COLLECTION complete")
```

## Troubleshooting

### Common Issues

**Issue 1: "No module named 'openai'"**
```bash
# Solution: Install dependencies
pip install -r requirements.txt
```

**Issue 2: "OPENAI_API_KEY not found"**
```bash
# Solution: Create .env file with API key
echo "OPENAI_API_KEY=sk-your-key" >> .env
```

**Issue 3: "Sitemap not found"**
```bash
# Solution: Verify sitemap URL manually
curl https://www.yoursite.com/sitemap.xml
```

**Issue 4: "Reddit API 401 Unauthorized"**
```bash
# Solution: Verify Reddit credentials in .env
# client_id and client_secret must be correct
```

**Issue 5: Progress stuck at 0%**
```bash
# Solution: Check for network connectivity
ping www.google.com

# Verify target sites are accessible
curl -I https://www.aicerts.ai/
```

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Output Files

```bash
# Verify all files were created
ls -lh data/

# Inspect file contents
cat data/content_gaps_report.json | python -m json.tool | head -20
```

## API Requirements

### OpenAI API

**Model Used**: `gpt-4o-2024-08-06`
**Rate Limits**: 
- 60 requests/minute (tier 1)
- 200,000 tokens/minute

**Estimated Usage per Run**:
- Gap Analysis: ~10,000 tokens
- Trend Clustering: ~15,000 tokens
- Brief Generation: ~8,000 tokens
- **Total**: ~33,000 tokens (~$0.30/run)

### Reddit API

**Requirements**:
- Script-type application
- Rate limit: 60 requests/minute
- No OAuth required

**Setup**:
1. Go to https://www.reddit.com/prefs/apps
2. Click "create application"
3. Select "script"
4. Note `client_id` (under app name) and `client_secret`

### Network Requirements

- Stable internet connection
- Access to target sitemaps (no firewall blocks)
- Reddit API accessible (check if reddit.com is reachable)

---

## Support & Contributing

**Issue Reporting**: Create GitHub issue with logs from `data/orchestrator.log`

**Feature Requests**: Open discussion with use case description

**Pull Requests**: Follow existing code structure and add tests

---

**Version**: 2.0  
**Last Updated**: November 2025  
**License**: MIT