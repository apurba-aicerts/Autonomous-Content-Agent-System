# Content Agent System

A comprehensive guide for developers to understand, maintain, and extend the autonomous content marketing intelligence system.

## Table of Contents
- [Project Overview](#project-overview)
- [Business Context & Goals](#business-context--goals)
- [Technical Architecture](#technical-architecture)
- [Codebase Structure](#codebase-structure)
- [Data Flow & Pipeline](#data-flow--pipeline)
- [Installation & Environment Setup](#installation--environment-setup)
- [Configuration Management](#configuration-management)
- [Running the System](#running-the-system)
- [Code Deep Dive](#code-deep-dive)
- [Error Handling Strategy](#error-handling-strategy)
- [Performance Considerations](#performance-considerations)
- [Testing & Debugging](#testing--debugging)
- [Deployment & Operations](#deployment--operations)
- [Future Enhancements](#future-enhancements)
- [Troubleshooting Playbook](#troubleshooting-playbook)

## Project Overview

### What This System Does
This is an autonomous content marketing intelligence platform that solves the manual, time-intensive process of content ideation and competitive analysis. It systematically:

1. **Discovers trending topics** from social media discussions
2. **Identifies content gaps** by analyzing competitor coverage
3. **Generates actionable content briefs** with strategic recommendations
4. **Prioritizes opportunities** using data-driven scoring algorithms

### Target Users
- Marketing teams needing systematic content strategy
- Content creators seeking data-driven topic selection
- Product marketing managers analyzing competitive landscapes
- Marketing operations teams automating research workflows

### Key Value Propositions
- **Time Savings**: Reduces 20+ hours of manual research to 15 minutes of automated processing
- **Data-Driven Decisions**: Replaces gut-feel content selection with engagement-based metrics
- **Competitive Intelligence**: Provides systematic competitor content gap analysis
- **Scalable Process**: Handles multiple data sources and competitors simultaneously

## Business Context & Goals

### Problem Statement
Content marketing teams face three critical challenges:
1. **Manual Research Overhead**: Spending 60%+ of time on research vs. creation
2. **Reactive Content Strategy**: Missing trending topics due to slow manual discovery
3. **Competitive Blind Spots**: No systematic way to identify content gaps vs competitors

### Success Metrics
- **Research Time Reduction**: From 20+ hours to <1 hour per content planning cycle
- **Topic Relevance**: 80%+ of generated briefs should align with actual trending discussions
- **Content Gap Accuracy**: 90%+ of identified gaps should represent genuine competitive opportunities
- **Actionability**: Content briefs should be immediately usable without additional research

### Business Logic & Scoring Methodology
The system uses a weighted scoring algorithm for trend prioritization:

```
Relevance Score = (Engagement × 0.4) + (Freshness × 0.35) + (Frequency × 0.25)

Where:
- Engagement: Normalized user interactions (upvotes, comments)
- Freshness: Time-decay score (newer = higher score)
- Frequency: Topic mention frequency in data window
```

This weighting prioritizes topics with high user engagement while ensuring recency and discussion volume.

## Technical Architecture

### System Design Principles
1. **Modularity**: Each agent is independently testable and maintainable
2. **Async Processing**: Parallel execution where possible for performance
3. **Fail-Safe Design**: Graceful degradation with comprehensive error handling
4. **Data Validation**: Structured input/output validation at each stage
5. **Configuration-Driven**: All parameters externalized to config files

### Multi-Agent Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR (main.py)                      │
└─────────────────────────────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
         ┌──────────▼──────────┐  ┌─────────▼─────────┐
         │   PHASE 1: DATA     │  │   PHASE 1: DATA   │
         │  Sitemap Crawler    │  │  Social Scraper   │
         │  (data_collector)   │  │ (data_collector)  │
         └──────────┬──────────┘  └─────────┬─────────┘
                    │                       │
         ┌──────────▼──────────┐  ┌─────────▼─────────┐
         │ sitemaps_data.json  │  │social_trends_raw  │
         │                     │  │     .json         │
         └──────────┬──────────┘  └─────────┬─────────┘
                    │                       │
         ┌──────────▼──────────┐  ┌─────────▼─────────┐
         │   PHASE 2: ANALYSIS │  │ PHASE 2: ANALYSIS │
         │   Gap Analyzer      │  │ Trend Clusterer   │
         │  (gap_analyzer)     │  │(trend_clusterer)  │
         └──────────┬──────────┘  └─────────┬─────────┘
                    │                       │
         ┌──────────▼──────────┐  ┌─────────▼─────────┐
         │content_gaps_report  │  │trending_topics    │
         │      .json          │  │   _report.json    │
         └──────────┬──────────┘  └─────────┬─────────┘
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │   PHASE 3: STRATEGY   │
                    │   Brief Generator     │
                    │  (brief_generator)    │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │  content_briefs.json  │
                    │  (FINAL OUTPUT)       │
                    └───────────────────────┘
```

## Codebase Structure

### File Organization
```
content-agent-system/
├── main.py                 # Pipeline orchestrator
├── config.py               # Configuration management
├── config.json             # System configuration
├── data_collector.py       # Phase 1: Data collection agents
├── gap_analyzer.py         # Phase 2: Content gap analysis
├── trend_clusterer.py      # Phase 2: Social trend clustering  
├── brief_generator.py      # Phase 3: Content brief generation
├── data/                   # Output directory
│   ├── sitemaps_data.json
│   ├── social_trends_raw.json
│   ├── content_gaps_report.json
│   ├── trending_topics_report.json
│   └── content_briefs.json
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

### Dependency Overview
- **Core Libraries**: `asyncio`, `aiohttp`, `json`, `logging`, `os`
- **Web Scraping**: `BeautifulSoup4`, `requests`, `xml.etree.ElementTree`
- **Social API**: `praw` (Python Reddit API Wrapper)
- **AI Integration**: `openai` (OpenAI Python SDK)
- **Data Validation**: `pydantic` (Structured data models)
- **HTTP**: `aiohttp` (Async HTTP client for performance)

## Data Flow & Pipeline

### Phase 1: Data Collection (Parallel)
**Duration**: 2-5 minutes | **Concurrency**: Parallel execution

#### Sitemap Crawler Agent
```python
# Input: config.json -> own_sitemap_url, competitor_sitemaps
# Process: XML parsing -> URL extraction -> Title scraping
# Output: data/sitemaps_data.json

{
  "ai_certs_titles": ["AI Certification Guide", "Blockchain Basics"],
  "competitor_titles": ["ML for Business", "AI Ethics Framework"]
}
```

#### Social Trend Miner Agent  
```python
# Input: config.json -> reddit_subreddits, posts_limit
# Process: Reddit API -> Post extraction -> Engagement metrics
# Output: data/social_trends_raw.json

[
  {
    "title": "RAG vs Fine-tuning debate",
    "score": 1500,
    "comments": 89,
    "source": "r/MachineLearning",
    "created_utc": "2025-09-20 14:30:00"
  }
]
```

### Phase 2: Analysis & Synthesis (Parallel)
**Duration**: 3-7 minutes | **Concurrency**: Parallel execution

#### Gap Analyzer Agent
```python
# Input: data/sitemaps_data.json
# Process: LLM comparison -> Thematic gap identification
# Output: data/content_gaps_report.json

{
  "content_gaps": [
    {
      "gap_topic": "AI Governance for SMBs",
      "competitor_coverage": 4
    }
  ]
}
```

#### Trend Clusterer Agent
```python
# Input: data/social_trends_raw.json  
# Process: LLM clustering -> Relevance scoring -> Ranking
# Output: data/trending_topics_report.json

{
  "trending_topics": [
    {
      "topic_cluster": "RAG vs Fine-Tuning",
      "relevance_score": 92.5,
      "rank": 1,
      "metrics": {
        "freshness_score": 88,
        "engagement_score": 95, 
        "frequency": 12
      }
    }
  ]
}
```

### Phase 3: Strategy Generation (Sequential)
**Duration**: 2-4 minutes | **Concurrency**: Sequential execution

#### Brief Generator Agent
```python
# Input: content_gaps_report.json + trending_topics_report.json
# Process: Topic prioritization -> LLM brief generation
# Output: data/content_briefs.json

[
  {
    "source_type": "Content Gap",
    "topic": "AI Governance for SMBs",
    "priority": "High", 
    "brief": {
      "audience": "Small business owners adopting AI",
      "job_to_be_done": "Implement AI safely without enterprise resources",
      "angle": "Practical AI governance for resource-constrained teams",
      "promise": "Reduce AI implementation risks by 80% with simple processes",
      "cta": "Download our SMB AI Governance Checklist",
      "key_talking_points": [
        "Risk assessment frameworks for SMBs",
        "Cost-effective compliance strategies",
        "Vendor evaluation criteria"
      ]
    }
  }
]
```

## Installation & Environment Setup

### Prerequisites Checklist
- [ ] Python 3.8+ installed
- [ ] OpenAI API key with GPT-4 access
- [ ] Reddit application credentials (client_id, client_secret)
- [ ] Network access to target sitemaps
- [ ] Minimum 4GB RAM (for concurrent processing)

### Step-by-Step Setup

1. **Environment Preparation**
```bash
# Clone repository
git clone <repository-url>
cd content-agent-system

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

2. **API Credentials Setup**
```bash
# Set OpenAI API key (required)
export OPENAI_API_KEY="sk-your-openai-api-key"

# For Windows PowerShell:
$env:OPENAI_API_KEY="sk-your-openai-api-key"
```

3. **Reddit API Setup**
- Go to https://www.reddit.com/prefs/apps
- Create a "script" application
- Note the client_id and client_secret
- Update config.json with credentials

4. **Configuration File Setup**
```bash
# Copy and edit configuration
cp config.json.example config.json
# Edit config.json with your URLs and credentials
```

5. **Directory Structure Validation**
```bash
# Create data directory
mkdir -p data

# Verify write permissions
touch data/test.txt && rm data/test.txt
```

## Configuration Management

### config.json Structure & Parameters

```json
{
  "reddit": {
    "client_id": "your_reddit_client_id",
    "client_secret": "your_reddit_client_secret",
    "user_agent": "ContentAgent/1.0 by YourUsername",
    "reddit_subreddits": ["MachineLearning", "ArtificialIntelligence", "datascience"],
    "posts_limit": 50
  },
  "own_sitemap_url": "https://yourcompany.com/sitemap.xml",
  "competitor_sitemaps": [
    "https://competitor1.com/sitemap.xml",
    "https://competitor2.com/sitemap.xml"
  ]
}
```

### Configuration Parameters Explained

| Parameter | Type | Purpose | Impact | Constraints |
|-----------|------|---------|---------|-------------|
| `reddit.subreddits` | Array | Communities to monitor | More subreddits = broader trend coverage | Max ~10 for API limits |
| `posts_limit` | Integer | Posts per subreddit | Higher = more data, slower processing | 10-100 recommended |
| `own_sitemap_url` | String | Your website sitemap | Base for gap analysis | Must be accessible XML |
| `competitor_sitemaps` | Array | Competitor sitemaps | More competitors = better gap analysis | Max ~5 for processing time |

### Configuration Best Practices
- **Reddit Subreddits**: Choose communities relevant to your domain
- **Posts Limit**: Start with 25-50, increase based on processing time tolerance
- **Sitemap URLs**: Verify accessibility and XML format before adding
- **User Agent**: Use descriptive, contact-identifiable strings

## Running the System

### Full Pipeline Execution
```bash
# Run complete pipeline (recommended)
python main.py

# Expected output:
# ================================
# 🚀 CONTENT AGENT SYSTEM - PIPELINE ORCHESTRATOR  
# ================================
# 📅 Started at: 2025-09-27 10:30:00
# 
# Phase 1: DATA COLLECTION
# ✅ Data Collection completed in 3.2s
# 
# Phase 2: GAP ANALYSIS  
# ✅ Gap Analysis completed in 4.1s
# 
# Phase 3: TREND ANALYSIS
# ✅ Trend Analysis completed in 5.3s
# 
# Phase 4: CONTENT BRIEF GENERATION
# ✅ Brief Generation completed in 2.8s
# 
# 🎉 PIPELINE EXECUTION COMPLETED SUCCESSFULLY
# ⏱️ Total execution time: 15.4 seconds
```

### Individual Module Testing
```bash
# Test data collection only
python data_collector.py

# Test gap analysis (requires sitemaps_data.json)
python gap_analyzer.py

# Test trend clustering (requires social_trends_raw.json)
python trend_clusterer.py

# Test brief generation (requires gap + trend reports)
python brief_generator.py
```

### Execution Modes & Flags
```bash
# Dry run mode (validation only)
python main.py --dry-run

# Verbose logging
python main.py --verbose

# Skip specific phases
python main.py --skip-social  # Skip Reddit data collection
python main.py --skip-gaps    # Skip gap analysis
```

## Code Deep Dive

### main.py - Pipeline Orchestrator
**Purpose**: Coordinates execution, handles validation, manages error recovery

**Key Functions**:
```python
def run_phase_with_validation(phase_func, phase_name, expected_outputs):
    """Executes phase with comprehensive validation and error handling"""
    
def validate_phase_outputs(phase_name, expected_files):
    """Validates output files exist and contain valid data"""
    
def print_pipeline_summary(start_time, success=True):
    """Provides detailed execution summary and next steps"""
```

**Error Handling Strategy**:
- Pre-flight configuration validation
- Inter-phase output validation  
- Graceful failure with detailed error messages
- Execution time tracking and performance reporting

### data_collector.py - Data Collection Engine
**Purpose**: Async data collection from sitemaps and Reddit

**Performance Optimizations**:
```python
# Async sitemap processing with connection pooling
connector = aiohttp.TCPConnector(
    limit=100,           # Total connection pool
    limit_per_host=20,   # Per-host connections
    ttl_dns_cache=300,   # DNS cache TTL
)

# Concurrent title extraction with semaphore
semaphore = asyncio.Semaphore(50)  # Control concurrency
```

**Key Implementation Details**:
- **Sitemap Processing**: XML parsing → URL extraction → Title scraping
- **Reddit Integration**: PRAW wrapper with error handling for private/deleted subreddits
- **Content Filtering**: Skips non-content pages (admin, legal, media files)
- **Retry Logic**: Exponential backoff for failed requests

### gap_analyzer.py - Competitive Intelligence Engine
**Purpose**: Identifies content gaps through LLM-powered analysis

**Core Algorithm**:
```python
def identify_gaps_batch(ai_titles, competitor_batch):
    """Process competitor titles in batches to identify content gaps"""
    prompt = f"""
    Compare these title sets and identify topics present in competitor titles 
    but missing from our titles:
    Our titles: {ai_titles}
    Competitor titles: {competitor_batch}
    """
    # Returns structured gap analysis with confidence scores
```

**Batch Processing Strategy**:
- Processes competitor data in 50-title batches
- Aggregates gap frequencies across batches
- Sorts by competitor coverage depth
- Handles API rate limiting gracefully

### trend_clusterer.py - Social Trend Intelligence
**Purpose**: Clusters social discussions and calculates relevance scores

**Scoring Algorithm Implementation**:
```python
def calculate_relevance_scores(clusters_data, posts_by_title):
    """Multi-factor scoring with normalization"""
    
    # Engagement normalization (0-100 scale)
    engagement_score = (raw_engagement / max_engagement) * 100
    
    # Freshness calculation (time decay)
    post_freshness = max(((WINDOW_DAYS - days_ago) / WINDOW_DAYS) * 100, 0)
    
    # Final weighted score
    relevance_score = (
        engagement_score * WEIGHTS["engagement"] +     # 40%
        freshness_score * WEIGHTS["freshness"] +       # 35% 
        normalized_frequency * WEIGHTS["frequency"]    # 25%
    )
```

**LLM Clustering Process**:
- Groups similar post titles into thematic clusters
- Handles diverse discussion topics and terminology
- Produces descriptive cluster names (2-5 words)
- Ensures each post assigned to exactly one cluster

### brief_generator.py - Content Strategy Engine  
**Purpose**: Transforms insights into actionable content briefs

**Brief Structure**:
```python
class ContentBrief(BaseModel):
    audience: str           # Target demographic
    job_to_be_done: str    # User problem/goal
    angle: str             # Content positioning
    promise: str           # Value proposition
    cta: str              # Call-to-action
    key_talking_points: List[str]  # Content outline
```

**Generation Process**:
- Combines high-priority gaps and trending topics
- Uses structured prompts for consistent brief quality
- Validates output format using Pydantic models
- Prioritizes topics by source type and relevance scores

## Error Handling Strategy

### Comprehensive Error Recovery
The system implements multiple layers of error handling:

1. **Configuration Validation**: Pre-flight checks for all required parameters
2. **Network Error Handling**: Retry logic with exponential backoff
3. **API Error Recovery**: Rate limit handling and timeout management
4. **Data Validation**: Schema validation at each pipeline stage
5. **Graceful Degradation**: Continue processing with partial data when possible

### Error Types & Recovery Strategies

| Error Type | Recovery Strategy | Impact | Prevention |
|------------|------------------|---------|------------|
| Configuration Missing | Early termination with clear message | High | Config validation |
| Network Timeout | Retry with backoff | Medium | Connection pooling |
| API Rate Limit | Exponential backoff + queue | Medium | Request throttling |
| Invalid Sitemap | Skip and continue | Low | URL validation |
| LLM Parsing Error | Retry with adjusted prompt | Medium | Response validation |

### Logging Strategy
```python
# Comprehensive logging at multiple levels
logger.info("Phase started")           # Progress tracking
logger.warning("Retrying request")     # Recoverable errors  
logger.error("Critical failure")       # Non-recoverable errors
```

## Performance Considerations

### Optimization Techniques

**Async Processing**:
- Parallel sitemap crawling (10x+ performance improvement)
- Concurrent Reddit API requests
- Batch processing for LLM calls

**Memory Management**:
- Stream processing for large sitemaps
- Batch-based LLM processing
- Efficient data structures for aggregation

**API Efficiency**:
- Connection pooling for HTTP requests
- Request batching where possible
- Intelligent retry logic

### Performance Benchmarks

| Phase | Duration | Bottleneck | Optimization |
|-------|----------|------------|--------------|
| Data Collection | 2-5 min | Network I/O | Async processing |
| Gap Analysis | 3-7 min | LLM API calls | Batch processing |
| Trend Clustering | 3-7 min | LLM API calls | Efficient prompts |
| Brief Generation | 2-4 min | LLM API calls | Structured outputs |

### Scalability Considerations
- **Data Volume**: System tested up to 1000+ competitor URLs
- **Subreddit Scale**: Handles 5-10 subreddits efficiently  
- **Concurrent Users**: Single-user system (no multi-tenancy)
- **API Costs**: Estimated $2-5 per full pipeline run

## Testing & Debugging

### Testing Individual Modules
```bash
# Test configuration loading
python -c "from config import validate_config; print(validate_config())"

# Test data collection with small dataset
python data_collector.py --test-mode --limit 10

# Test gap analysis with sample data  
python gap_analyzer.py --debug --sample-data

# Validate output file formats
python -c "import json; json.load(open('data/content_briefs.json'))"
```

### Debugging Common Issues

**Data Collection Problems**:
```bash
# Check sitemap accessibility
curl -I https://yoursite.com/sitemap.xml

# Verify Reddit API connection
python -c "import praw; r=praw.Reddit(...); print(r.user.me())"
```

**LLM Processing Issues**:
```bash
# Verify OpenAI API key
python -c "import openai; client=openai.OpenAI(); print('API key valid')"

# Test with minimal data
python gap_analyzer.py --sample-size 5
```

### Development Workflow
1. **Unit Testing**: Test individual functions with mock data
2. **Integration Testing**: Run phases with small datasets
3. **End-to-End Testing**: Full pipeline with production config
4. **Performance Testing**: Monitor execution times and API usage
5. **Output Validation**: Verify JSON structure and content quality

## Deployment & Operations

### Production Deployment Checklist
- [ ] Environment variables set (OPENAI_API_KEY)
- [ ] Configuration file validated
- [ ] Network access to all required URLs verified
- [ ] Log directory created with write permissions
- [ ] Monitoring and alerting configured
- [ ] Backup strategy for output files

### Operational Monitoring
```bash
# Monitor execution logs
tail -f data/pipeline.log

# Check output file freshness
ls -la data/*.json

# Validate API usage
grep "API error" data/pipeline.log | tail -10
```

### Maintenance Tasks
- **Weekly**: Review and update subreddit list based on relevance
- **Monthly**: Audit competitor sitemap list for accuracy  
- **Quarterly**: Review and adjust scoring weights based on performance
- **As Needed**: Update configuration based on business focus changes

## Future Enhancements

### Planned Improvements
1. **Additional Data Sources**: Twitter/X, LinkedIn, industry forums
2. **Visual Content Analysis**: Image and video trend identification
3. **Automated Publishing**: Direct integration with content management systems
4. **Advanced Analytics**: Historical trend analysis and prediction
5. **Multi-Language Support**: International content gap analysis

### Technical Debt & Refactoring Opportunities
- **Database Integration**: Move from file-based to database storage
- **Caching Layer**: Implement Redis for API response caching
- **Containerization**: Docker deployment for environment consistency
- **CI/CD Pipeline**: Automated testing and deployment
- **Configuration Management**: Environment-specific configs

### Extension Points
```python
# Adding new data sources
class NewDataSource:
    def collect_data(self) -> List[Dict]:
        """Implement data collection logic"""
        pass
    
    def transform_data(self, raw_data) -> Dict:
        """Transform to standard format"""
        pass

# Custom scoring algorithms  
def custom_relevance_scorer(cluster_data, weights):
    """Implement alternative scoring logic"""
    pass
```

## Troubleshooting Playbook

### Quick Diagnostics
```bash
# System health check
python -c "
from config import validate_config
import os
print('Config valid:', validate_config())
print('Data dir exists:', os.path.exists('data'))
print('OpenAI key set:', bool(os.getenv('OPENAI_API_KEY')))
"
```

### Common Failure Scenarios

**Scenario 1: Empty Output Files**
- **Symptoms**: JSON files created but contain empty arrays
- **Diagnosis**: Check input data quality and LLM response parsing
- **Resolution**: Review logs for parsing errors, validate input data format

**Scenario 2: API Rate Limiting**  
- **Symptoms**: Multiple API timeout errors in logs
- **Diagnosis**: Exceeded OpenAI or Reddit API limits
- **Resolution**: Implement request throttling, consider paid API tiers

**Scenario 3: Sitemap Access Issues**
- **Symptoms**: Empty sitemap data, HTTP errors in logs
- **Diagnosis**: Sitemap URLs inaccessible or invalid format
- **Resolution**: Verify URLs manually, check robots.txt restrictions

**Scenario 4: Reddit API Failures**
- **Symptoms**: No social data collected, authentication errors
- **Diagnosis**: Invalid Reddit credentials or subreddit access issues
- **Resolution**: Verify credentials, check subreddit accessibility

### Emergency Recovery Procedures
1. **Partial Data Recovery**: Use existing JSON files for continued processing
2. **Fallback Configuration**: Minimal config for basic functionality testing
3. **Manual Data Input**: Process with sample data for testing
4. **Rollback Procedures**: Restore from known-good configuration state

### Support Resources
- **OpenAI API Documentation**: https://platform.openai.com/docs
- **Reddit API (PRAW) Documentation**: https://praw.readthedocs.io
- **Python Async Programming**: https://docs.python.org/3/library/asyncio.html
