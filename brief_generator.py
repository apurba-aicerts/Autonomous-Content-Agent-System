import json
import logging
import os
from openai import OpenAI
from pydantic import BaseModel
from typing import List
from config import get_config, ensure_data_directory

logger = logging.getLogger(__name__)

# Pydantic model for structured LLM output
class ContentBrief(BaseModel):
    audience: str
    job_to_be_done: str
    angle: str
    promise: str
    cta: str
    key_talking_points: List[str]

def make_llm_call(prompt, response_model, max_retries=3):
    """Standardized LLM call with retry logic."""
    client = OpenAI()
    
    for attempt in range(max_retries):
        try:
            response = client.responses.parse(
                model="gpt-4o-2024-08-06",
                input=[
                    {"role": "system", "content": "You are a helpful content strategist."},
                    {"role": "user", "content": prompt}
                ],
                text_format=response_model,
            )
            
            parsed = getattr(response, "output_parsed", None)
            if parsed is not None:
                return parsed
                
            logger.warning(f"Retry {attempt+1}/{max_retries}: empty or invalid output")
            
        except Exception as e:
            logger.warning(f"Retry {attempt+1}/{max_retries}: API error: {e}")
    
    logger.error("Failed to generate brief after all retries")
    return None

def load_content_gaps():
    """Load content gaps from file."""
    input_file = os.path.join("data", "content_gaps_report.json")
    
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Loaded content gaps from {input_file}")
        return data.get("content_gaps", [])
    except FileNotFoundError:
        logger.error(f"Required file not found: {input_file}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {input_file}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading {input_file}: {e}")
        raise

def load_trending_topics():
    """Load trending topics from file."""
    input_file = os.path.join("data", "trending_topics_report.json")
    
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Loaded trending topics from {input_file}")
        return data.get("trending_topics", [])
    except FileNotFoundError:
        logger.error(f"Required file not found: {input_file}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {input_file}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading {input_file}: {e}")
        raise

def generate_brief_for_topic(topic, source_type):
    """Generate content brief for a single topic."""
    prompt = f"""
You are a content strategist. Generate a detailed content brief for the following topic.

Topic: "{topic}"
Source Type: {source_type}
"""
    
    result = make_llm_call(prompt, ContentBrief)
    if result is None:
        logger.error(f"Failed to generate brief for topic: {topic}")
        return None
    
    # Convert to dict format
    brief_dict = result.model_dump() if hasattr(result, "model_dump") else result.dict()
    return brief_dict

def process_content_briefs(content_gaps, trending_topics):
    """Process all topics and generate content briefs."""
    # Combine all topics
    all_topics = [
        {"source_type": "Content Gap", "topic": t["gap_topic"], "priority": "High"}
        for t in content_gaps
    ] + [
        {"source_type": "Trending Topic", "topic": t["topic_cluster"], "priority": "Medium"}
        for t in trending_topics
    ]
    
    if not all_topics:
        logger.error("No topics to process")
        raise ValueError("No topics found for brief generation")
    
    logger.info(f"Processing {len(all_topics)} topics for content briefs")
    
    content_briefs = []
    
    for idx, topic_info in enumerate(all_topics, start=1):
        topic = topic_info["topic"]
        source_type = topic_info["source_type"]
        priority = topic_info["priority"]
        
        logger.info(f"Processing topic {idx}/{len(all_topics)}: {topic}")
        
        brief = generate_brief_for_topic(topic, source_type)
        
        if brief:
            content_briefs.append({
                "source_type": source_type,
                "topic": topic,
                "priority": priority,
                "brief": brief
            })
        else:
            logger.warning(f"Failed to generate brief for: {topic}")
    
    logger.info(f"Successfully generated {len(content_briefs)} content briefs")
    return content_briefs

def save_content_briefs(content_briefs):
    """Save content briefs to file."""
    output_file = os.path.join("data", "content_briefs.json")
    
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(content_briefs, f, indent=2, ensure_ascii=False)
        logger.info(f"Content briefs saved to {output_file}")
        return True
    except Exception as e:
        logger.error(f"Failed to save content briefs: {e}")
        return False

def validate_inputs():
    """Validate that required input files exist."""
    required_files = [
        os.path.join("data", "content_gaps_report.json"),
        os.path.join("data", "trending_topics_report.json")
    ]
    
    for file_path in required_files:
        if not os.path.exists(file_path):
            logger.error(f"Required input file missing: {file_path}")
            return False
    
    # Validate content gaps file
    try:
        with open(required_files[0], "r", encoding="utf-8") as f:
            gaps_data = json.load(f)
        
        if "content_gaps" not in gaps_data:
            logger.error("Missing 'content_gaps' in content gaps file")
            return False
        
        gaps_count = len(gaps_data.get("content_gaps", []))
        logger.info(f"Found {gaps_count} content gaps")
        
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Error validating content gaps file: {e}")
        return False
    
    # Validate trending topics file
    try:
        with open(required_files[1], "r", encoding="utf-8") as f:
            trends_data = json.load(f)
        
        if "trending_topics" not in trends_data:
            logger.error("Missing 'trending_topics' in trending topics file")
            return False
        
        trends_count = len(trends_data.get("trending_topics", []))
        logger.info(f"Found {trends_count} trending topics")
        
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Error validating trending topics file: {e}")
        return False
    
    total_topics = gaps_count + trends_count
    if total_topics == 0:
        logger.error("No topics found for brief generation")
        return False
    
    logger.info(f"Input validation passed - total topics for processing: {total_topics}")
    return True

def print_summary(content_briefs):
    """Print generation summary."""
    logger.info("="*50)
    logger.info("CONTENT BRIEF GENERATION SUMMARY")
    logger.info("="*50)
    
    # Count by source type
    gap_briefs = [b for b in content_briefs if b["source_type"] == "Content Gap"]
    trend_briefs = [b for b in content_briefs if b["source_type"] == "Trending Topic"]
    
    logger.info(f"Total briefs generated: {len(content_briefs)}")
    logger.info(f"Content gap briefs: {len(gap_briefs)}")
    logger.info(f"Trending topic briefs: {len(trend_briefs)}")
    
    # Show top 3 briefs
    logger.info("\nTop 3 content briefs:")
    for i, brief in enumerate(content_briefs[:3], 1):
        logger.info(f"  {i}. {brief['topic']} ({brief['source_type']})")
        logger.info(f"     Audience: {brief['brief']['audience']}")
        logger.info(f"     Promise: {brief['brief']['promise']}")

def run_brief_generation():
    """Main function to run content brief generation."""
    logger.info("Starting content brief generation process...")
    
    # Ensure data directory exists
    ensure_data_directory()
    
    # Validate inputs
    if not validate_inputs():
        logger.error("Input validation failed - stopping brief generation")
        raise ValueError("Input validation failed")
    
    try:
        # Load input data
        content_gaps = load_content_gaps()
        trending_topics = load_trending_topics()
        
        # Process content briefs
        content_briefs = process_content_briefs(content_gaps, trending_topics)
        
        if not content_briefs:
            logger.warning("No content briefs generated")
            raise ValueError("No content briefs generated")
        
        # Save results
        if not save_content_briefs(content_briefs):
            raise Exception("Failed to save content briefs")
        
        # Print summary
        print_summary(content_briefs)
        
        logger.info("Content brief generation completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Brief generation failed: {e}")
        raise

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        run_brief_generation()
        logger.info("Brief generation module executed successfully")
    except Exception as e:
        logger.error(f"Brief generation module failed: {e}")
        exit(1)