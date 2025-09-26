import json
import re
from openai import OpenAI
from pydantic import BaseModel
from typing import List

# ---------------------------
# Initialize OpenAI client
# ---------------------------
client = OpenAI()

# ---------------------------
# Load input files
# ---------------------------
try:
    with open("content_gaps_report.json", "r", encoding="utf-8") as f:
        content_gaps = json.load(f).get("content_gaps", [])
except Exception as e:
    print(f"❌ Error loading content_gaps_report.json: {e}")
    exit(1)

try:
    with open("trending_topics_report.json", "r", encoding="utf-8") as f:
        trending_topics = json.load(f).get("trending_topics", [])
except Exception as e:
    print(f"❌ Error loading trending_topics_report.json: {e}")
    exit(1)

# Combine all topics
all_topics = [
    {"source_type": "Content Gap", "topic": t["gap_topic"], "priority": "High"}
    for t in content_gaps
] + [
    {"source_type": "Trending Topic", "topic": t["topic_cluster"], "priority": "Medium"}
    for t in trending_topics
]


if not all_topics:
    print("❌ No topics to process")
    exit(1)

print(f"📊 Total topics to process: {len(all_topics)}")

# ---------------------------
# JSON-safe parser
# ---------------------------
def parse_json_safe(text):
    import json, re
    try:
        match = re.search(r'(\[.*\]|\{.*\})', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
    except json.JSONDecodeError as e:
        print("JSON decode error:", e)
    return None

# ---------------------------
# Function to generate content brief via LLM
# ---------------------------
# dfrom openai import OpenAI

# ---------------------------
# Pydantic model for structured output
# ---------------------------
class ContentBrief(BaseModel):
    audience: str
    job_to_be_done: str
    angle: str
    promise: str
    cta: str
    key_talking_points: List[str]

# ---------------------------
# Function to generate content brief via LLM (structured output)
# ---------------------------
def generate_brief(topic, source_type, max_retries=3):
    prompt = f"""
You are a content strategist. Generate a detailed content brief for the following topic.

Topic: "{topic}"
Source Type: {source_type}

Generate a JSON object with the following fields ONLY:

{{
  "audience": "Who is this content for?",
  "job_to_be_done": "What problem or goal does this content solve for the audience?",
  "angle": "The unique perspective or approach of this content",
  "promise": "The main value or benefit the audience will get",
  "cta": "Call-to-action for the audience",
  "key_talking_points": ["3–5 concise key points to cover"]
}}

⚠️ IMPORTANT: Return ONLY valid JSON. Do not add any explanations, text, or comments outside the JSON.
"""

    for attempt in range(max_retries):
        try:
            response = client.responses.parse(
                model="gpt-4o-2024-08-06",
                input=[
                    {"role": "system", "content": "You are a helpful content strategist."},
                    {"role": "user", "content": prompt}
                ],
                text_format=ContentBrief,
            )
            if response.output_parsed:
                return response.output_parsed
            print(f"⚠️ Retry {attempt+1}/{max_retries}: empty or invalid output")
        except Exception as e:
            print(f"⚠️ Retry {attempt+1}/{max_retries}: API error: {e}")
    print(f"❌ Failed to generate brief for topic: {topic}")
    return None

# ---------------------------
# Process all topics
# ---------------------------
content_briefs = []

for idx, t in enumerate(all_topics, start=1):
    print(f"🤖 Processing topic {idx}/{len(all_topics)}: {t['topic']}")
    brief = generate_brief(t['topic'], t['source_type'])
    # print(f"Generated brief: {brief.dict()}\n")
    # break
    if brief:
        content_briefs.append({
            "source_type": t["source_type"],
            "topic": t["topic"],
            "priority": t["priority"],
            "brief": brief.model_dump() 
        })

# ---------------------------
# Save final JSON
# ---------------------------
try:
    with open("content_briefs.json", "w", encoding="utf-8") as f:
        json.dump(content_briefs, f, indent=2, ensure_ascii=False)
    print("✅ Content briefs saved to content_briefs.json")
    print(f"📈 Total briefs generated: {len(content_briefs)}")
except Exception as e:
    print(f"❌ Error saving content_briefs.json: {e}")
    exit(1)
