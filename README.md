# Content Agent System

An intelligent, automated content strategy pipeline that identifies content gaps, analyzes trending topics, and generates actionable content briefs using AI-powered agents.

## Table of Contents
- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Pipeline Phases](#pipeline-phases)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Output Files](#output-files)
- [Agent Details](#agent-details)
- [Troubleshooting](#troubleshooting)
- [Performance Features](#performance-features)
- [API Rate Limits](#api-rate-limits)

## Overview

The Content Agent System is a multi-phase pipeline designed to automate content strategy research and brief generation. It analyzes competitor content, monitors social trends, identifies content gaps, and produces ready-to-use content briefs for content creators and marketers.

### Key Capabilities
- **Competitor Analysis**: Scrapes competitor websites via sitemaps to identify content topics
- **Trend Monitoring**: Collects and analyzes social media trends from Reddit
- **Content Gap Identification**: Uses AI to identify topics competitors cover that you don't
- **Topic Clustering**: Groups similar trending topics using semantic analysis
- **Content Brief Generation**: Creates detailed, actionable content briefs with audience insights

### Use Cases
- Content strategy planning
- Competitive content analysis  
- Trend-based content creation
- SEO content gap analysis
- Social media content planning

## System Architecture

The system uses a **3-phase pipeline architecture** with built-in validation, error handling, and parallel processing:

```
Phase 1: DATA COLLECTION
├── Sitemap Crawler (async)
└── Reddit Scraper (async)

Phase 2: ANALYSIS & SYNTHESIS  
├── Gap Analysis Agent (AI-powered)
└── Trend Clustering Agent (AI-powered)

Phase 3: CONTENT GENERATION
└── Content Brief Agent (AI-powered)
```

## Pipeline Phases

### Phase 1: Data Collection (Parallel Execution)
**Agent**: `data_collection.py`
- **Sitemap Crawler**: Extracts page titles from your site and competitor sites
- **Reddit Scraper**: Collects trending posts from specified subreddits
- **Output**: Raw data files with titles and social posts

### Phase 2: Analysis & Synthesis (Parallel Execution)
**Agents**: `Gap_AGENT.py`, `Clustering_AGENT.py`
- **Gap Analysis**: Identifies content topics competitors have that you don't
- **Trend Clustering**: Groups similar social posts into thematic clusters
- **Output**: Content gaps report and trending topics analysis

### Phase 3: Content Brief Generation (Sequential Execution)
**Agent**: `Brief_Agent.py`
- Combines gap analysis and trending topics
- Generates detailed content briefs with audience insights
- **Output**: Actionable content briefs ready for content creators

## Prerequisites

### Required Software
- Python 3.8+
- pip package manager

### Required APIs
- **OpenAI API**: For AI-powered analysis and content generation
- **Reddit API**: For social trend monitoring

### Python Packages
```bash
pip install openai praw aiohttp beautifulsoup4 lxml
```

## Installation

1. **Clone or download** all agent files to your working directory:
   - `main.py`
   - `data_collection.py`
   - `Gap_AGENT.py`
   - `Clustering_AGENT.py` 
   - `Brief_Agent.py`

2. **Install dependencies**:
   ```bash
   pip install openai praw aiohttp beautifulsoup4 lxml
   ```

3. **Set up API keys** (see Configuration section)

4. **Create configuration file** (see Configuration section)

## Configuration

Create a `config.json` file in your working directory:

```json
{
  "own_sitemap_url": "https://your-website.com/sitemap.xml",
  "competitor_sitemaps": [
    "https://competitor1.com/sitemap.xml",
    "https://competitor2.com/sitemap.xml"
  ],
  "reddit": {
    "client_id": "your_reddit_client_id",
    "client_secret": "your_reddit_client_secret", 
    "user_agent": "ContentAgent/1.0 by YourUsername",
    "reddit_subreddits": ["MachineLearning", "artificial", "ChatGPT"],
    "posts_limit": 50
  }
}
```

### API Key Setup

#### OpenAI API
Set your OpenAI API key as an environment variable:
```bash
export OPENAI_API_KEY="your-openai-api-key"
```

#### Reddit API
1. Go to https://www.reddit.com/prefs/apps
2. Click "Create App" or "Create Another App"
3. Choose "script" application type
4. Note your client ID and secret
5. Add them to your `config.json`

## Usage

### Basic Execution
Run the complete pipeline:
```bash
python main.py
```

### Individual Agent Execution
Run specific agents independently:
```bash
# Data collection only
python data_collection.py

# Gap analysis only (requires sitemaps_data.json)
python Gap_AGENT.py

# Trend clustering only (requires social_trends_raw.json)
python Clustering_AGENT.py

# Brief generation only (requires gap and trending reports)
python Brief_Agent.py
```

### Pipeline Execution Flow

1. **Pre-flight Validation**: Checks configuration and agent files
2. **Phase 1**: Parallel data collection from sitemaps and Reddit
3. **Phase 2**: Parallel gap analysis and trend clustering
4. **Phase 3**: Sequential content brief generation
5. **Validation**: Verifies all outputs were created successfully

## Output Files

The pipeline generates several JSON files:

### Phase 1 Outputs
- `sitemaps_data.json`: Raw page titles from your site and competitors
- `social_trends_raw.json`: Raw social media posts and engagement data

### Phase 2 Outputs  
- `content_gaps_report.json`: Topics competitors cover that you don't
- `trending_topics_report.json`: Clustered and ranked trending topics
- `social_trends_clusters.json`: Raw clustering results

### Phase 3 Output
- `content_briefs.json`: **Final deliverable** - Actionable content briefs

### Content Brief Structure
Each brief contains:
```json
{
  "source_type": "Content Gap" | "Trending Topic",
  "topic": "Topic name",
  "priority": "High" | "Medium",
  "brief": {
    "audience": "Target audience description",
    "job_to_be_done": "Problem this content solves",
    "angle": "Unique perspective or approach",
    "promise": "Value proposition for readers",
    "cta": "Call-to-action",
    "key_talking_points": ["Point 1", "Point 2", "..."]
  }
}
```

## Agent Details

### Data Collection Agent (`data_collection.py`)
- **Technology**: Async/await with aiohttp for high performance
- **Features**: 
  - Concurrent sitemap crawling
  - Intelligent URL filtering
  - Retry logic for failed requests
  - Progress reporting
- **Performance**: ~50x faster than traditional sequential crawling

### Gap Analysis Agent (`Gap_AGENT.py`)
- **Technology**: OpenAI GPT-4 for semantic analysis
- **Process**: Compares your titles vs competitor titles in batches
- **Output**: Ranked list of content gaps with coverage metrics

### Clustering Agent (`Clustering_AGENT.py`)
- **Technology**: OpenAI GPT for thematic clustering
- **Features**:
  - Semantic topic grouping
  - Multi-factor relevance scoring (engagement, freshness, frequency)
  - Configurable time windows and weights
- **Scoring Formula**: 
  ```
  Relevance = (Engagement × 0.4) + (Freshness × 0.35) + (Frequency × 0.25)
  ```

### Content Brief Agent (`Brief_Agent.py`)
- **Technology**: OpenAI GPT-4 for strategic brief generation
- **Process**: Combines gap analysis and trending topics
- **Output**: Structured content briefs with audience insights

### Main Orchestrator (`main.py`)
- **Technology**: Asyncio for parallel execution
- **Features**:
  - Phase-based execution with validation
  - Automatic retry logic
  - Rate limiting for API calls
  - Comprehensive error handling and reporting

## Troubleshooting

### Common Issues

#### Configuration Errors
```
Error: config.json not found
```
**Solution**: Create config.json with required fields (see Configuration section)

#### API Authentication
```
Error: OpenAI API authentication failed
```
**Solution**: Set OPENAI_API_KEY environment variable

#### Missing Dependencies
```
ImportError: No module named 'openai'
```
**Solution**: Install required packages: `pip install openai praw aiohttp beautifulsoup4 lxml`

#### Empty Results
```
No topics to process
```
**Solution**: Check that your sitemaps are accessible and contain valid content

### Debug Tips

1. **Check individual outputs**: Each phase creates intermediate files you can inspect
2. **Run agents individually**: Test each agent separately to isolate issues  
3. **Review logs**: All agents provide detailed logging output
4. **Validate JSON**: Ensure all output files contain valid JSON

### Performance Issues

#### Slow Execution
- **Cause**: Large sitemaps or high API rate limits
- **Solution**: Reduce batch sizes or add delays between requests

#### Rate Limiting
- **Cause**: Too many API calls
- **Solution**: The system includes built-in rate limiting, but you may need to adjust limits

## Performance Features

### Async Processing
- **Sitemap crawling**: Concurrent requests with connection pooling
- **Agent execution**: Parallel processing where possible
- **Rate limiting**: Built-in throttling to respect API limits

### Memory Efficiency
- **Streaming**: Large files processed in chunks
- **Batch processing**: Data processed in manageable batches
- **Cleanup**: Automatic cleanup of intermediate data

### Error Resilience
- **Retry logic**: Failed requests automatically retried
- **Graceful degradation**: Partial failures don't stop the pipeline
- **Validation**: Output validation at each phase

## API Rate Limits

### Default Limits
- **OpenAI requests**: 50 per minute
- **Retry attempts**: 3 per agent
- **Inter-agent delay**: 2 seconds
- **Retry delay**: 5 seconds

### Customization
Modify limits in `main.py`:
```python
API_RATE_LIMITS = {
    "openai_requests_per_minute": 50,
    "delay_between_agents": 2,
    "retry_attempts": 3,
    "retry_delay": 5
}
```

## Best Practices

### Content Strategy
1. **Regular Execution**: Run pipeline weekly for fresh insights
2. **Diverse Sources**: Include multiple competitor sitemaps
3. **Relevant Subreddits**: Choose subreddits aligned with your niche
4. **Brief Review**: Always review generated briefs before content creation

### Technical
1. **Backup Configuration**: Keep your config.json secure and backed up
2. **Monitor API Usage**: Track your OpenAI API costs
3. **Review Outputs**: Validate generated content aligns with your brand
4. **Update Dependencies**: Keep packages updated for security

---