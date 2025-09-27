import json
import logging
import os
from collections import defaultdict
from openai import OpenAI
from pydantic import BaseModel
from typing import List
from config import get_config, ensure_data_directory

logger = logging.getLogger(__name__)

# Pydantic models for structured LLM output
class GapItem(BaseModel):
    gap_topic: str
    competitor_coverage: int

class Gaps(BaseModel):
    gaps: List[GapItem]

def make_llm_call(prompt, response_model, max_retries=3):
    """Standardized LLM call with retry logic."""
    client = OpenAI()
    
    for attempt in range(max_retries):
        try:
            response = client.responses.parse(
                model="gpt-4o-2024-08-06",
                input=[
                    {"role": "system", "content": "You are a content analyst. Compare two lists of page titles and identify topics present in competitor titles but missing from our titles."},
                    {"role": "user", "content": prompt}
                ],
                text_format=response_model,
                temperature=0,
            )
            
            parsed = getattr(response, "output_parsed", None)
            if parsed is not None:
                return parsed
            
            logger.warning(f"Retry {attempt+1}/{max_retries}: no parsed output")
            
        except Exception as e:
            logger.warning(f"Retry {attempt+1}/{max_retries}: API error: {e}")
    
    logger.error("Failed to get valid LLM response after all retries")
    return None

def identify_gaps_batch(ai_titles, competitor_batch):
    """Identify content gaps for a batch of competitor titles."""
    user_prompt = f"""
    Our titles: {ai_titles}
    Competitor titles (this batch): {competitor_batch}
    """
    
    result = make_llm_call(user_prompt, Gaps)
    if result is None:
        logger.error("Failed to identify gaps for batch")
        return []
    
    # Convert to dict format
    gaps = []
    for gap in result.gaps:
        gap_dict = gap.model_dump() if hasattr(gap, "model_dump") else gap.dict()
        gaps.append(gap_dict)
    
    return gaps

def load_sitemap_data():
    """Load sitemap data from file."""
    input_file = os.path.join("data", "sitemaps_data.json")
    
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Loaded sitemap data from {input_file}")
        return data
    except FileNotFoundError:
        logger.error(f"Required file not found: {input_file}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {input_file}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading {input_file}: {e}")
        raise

def process_gap_analysis(ai_titles, competitor_titles, batch_size=50):
    """Process gap analysis in batches."""
    logger.info(f"Processing gap analysis for {len(competitor_titles)} competitor titles in batches of {batch_size}")
    
    all_gaps = defaultdict(int)
    
    for i in range(0, len(competitor_titles), batch_size):
        batch = competitor_titles[i:i+batch_size]
        batch_num = i//batch_size + 1
        total_batches = (len(competitor_titles) + batch_size - 1) // batch_size
        
        logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} titles)...")
        
        batch_gaps = identify_gaps_batch(ai_titles, batch)
        
        # Aggregate gaps
        for gap in batch_gaps:
            topic = gap.get("gap_topic", "")
            coverage = int(gap.get("competitor_coverage", 0))
            if topic:  # Only add non-empty topics
                all_gaps[topic] += coverage
        
        logger.info(f"Batch {batch_num} completed - found {len(batch_gaps)} gaps")
    
    # Convert to final format
    final_gaps = [
        {"gap_topic": topic, "competitor_coverage": coverage} 
        for topic, coverage in all_gaps.items()
    ]
    
    # Sort by coverage (highest first)
    final_gaps.sort(key=lambda x: x["competitor_coverage"], reverse=True)
    
    logger.info(f"Gap analysis completed - identified {len(final_gaps)} unique content gaps")
    return final_gaps

def save_gap_analysis(gaps):
    """Save gap analysis results to file."""
    output_file = os.path.join("data", "content_gaps_report.json")
    
    try:
        output_data = {"content_gaps": gaps}
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Content gaps report saved to {output_file}")
        return True
    except Exception as e:
        logger.error(f"Failed to save gap analysis: {e}")
        return False

def validate_inputs():
    """Validate that required input files exist."""
    input_file = os.path.join("data", "sitemaps_data.json")
    
    if not os.path.exists(input_file):
        logger.error(f"Required input file missing: {input_file}")
        return False
    
    # Validate file content
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if "ai_certs_titles" not in data:
            logger.error("Missing 'ai_certs_titles' in sitemap data")
            return False
        
        if "competitor_titles" not in data:
            logger.error("Missing 'competitor_titles' in sitemap data")
            return False
        
        ai_titles_count = len(data.get("ai_certs_titles", []))
        competitor_titles_count = len(data.get("competitor_titles", []))
        
        if ai_titles_count == 0:
            logger.error("No AI Certs titles found in data")
            return False
        
        if competitor_titles_count == 0:
            logger.error("No competitor titles found in data")
            return False
        
        logger.info(f"Input validation passed - AI titles: {ai_titles_count}, Competitor titles: {competitor_titles_count}")
        return True
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in input file: {e}")
        return False
    except Exception as e:
        logger.error(f"Error validating inputs: {e}")
        return False

def run_gap_analysis():
    """Main function to run gap analysis process."""
    logger.info("Starting gap analysis process...")
    
    # Ensure data directory exists
    ensure_data_directory()
    
    # Validate inputs
    if not validate_inputs():
        logger.error("Input validation failed - stopping gap analysis")
        raise ValueError("Input validation failed")
    
    try:
        # Load sitemap data
        sitemap_data = load_sitemap_data()
        
        ai_titles = sitemap_data.get("ai_certs_titles", [])
        competitor_titles = sitemap_data.get("competitor_titles", [])
        
        logger.info(f"Loaded {len(ai_titles)} AI Certs titles and {len(competitor_titles)} competitor titles")
        
        # Process gap analysis
        gaps = process_gap_analysis(ai_titles, competitor_titles)
        
        if not gaps:
            logger.warning("No content gaps identified")
        else:
            logger.info(f"Identified {len(gaps)} content gaps")
            
            # Log top 5 gaps
            logger.info("Top content gaps:")
            for i, gap in enumerate(gaps[:5], 1):
                logger.info(f"  {i}. {gap['gap_topic']} (coverage: {gap['competitor_coverage']})")
        
        # Save results
        if not save_gap_analysis(gaps):
            raise Exception("Failed to save gap analysis results")
        
        logger.info("Gap analysis completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Gap analysis failed: {e}")
        raise

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        run_gap_analysis()
        logger.info("Gap analysis module executed successfully")
    except Exception as e:
        logger.error(f"Gap analysis module failed: {e}")
        exit(1)