import json
import re
from collections import defaultdict
from openai import OpenAI

# ---------------------------
# Initialize OpenAI client
# ---------------------------
client = OpenAI()

# ---------------------------
# Load data
# ---------------------------
try:
    with open("sitemaps_data.json", "r", encoding="utf-8") as f:
        data = json.load(f)
except FileNotFoundError:
    print("❌ Error: sitemaps_data.json not found")
    exit(1)
except json.JSONDecodeError:
    print("❌ Error: Invalid JSON in sitemaps_data.json")
    exit(1)

ai_titles = data.get("ai_certs_titles", [])
competitor_titles = data.get("competitor_titles", [])

if not ai_titles or not competitor_titles:
    print("❌ Error: Missing ai_certs_titles or competitor_titles")
    exit(1)

print(f"📊 Loaded {len(ai_titles)} AI titles and {len(competitor_titles)} competitor titles")

# ---------------------------
# JSON-safe parser
# ---------------------------
def parse_json_safe(text):
    try:
        match = re.search(r'(\[.*\]|\{.*\})', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
    except json.JSONDecodeError as e:
        print("JSON decode error:", e)
    return []

# ---------------------------
# Function to call OpenAI for a batch
# ---------------------------
def identify_gaps(ai_titles, competitor_batch, max_retries=3):
    prompt = f"""
You are a content analyst. Compare the following lists:

Our content titles:
{ai_titles}

Competitor content titles:
{competitor_batch}

Identify topics present in the competitor titles but missing from our titles.
Return ONLY valid JSON in this format:
[
  {{"gap_topic": "Topic here", "competitor_coverage": number}}
]
"""
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            content = response.choices[0].message.content.strip()
            gaps = parse_json_safe(content)
            if gaps:
                return gaps
            print(f"⚠️ Retry {attempt+1}/{max_retries}: empty or invalid JSON")
        except Exception as e:
            print(f"⚠️ Retry {attempt+1}/{max_retries}: API error: {e}")
    print("❌ Failed to get valid gaps after retries")
    with open("content_gaps_raw.txt", "w", encoding="utf-8") as f:
        f.write(content)
    exit(1)

# ---------------------------
# Process competitor titles in batches
# ---------------------------
batch_size = 50
all_gaps = defaultdict(int)

for i in range(0, len(competitor_titles), batch_size):
    batch = competitor_titles[i:i+batch_size]
    print(f"🤖 Processing batch {i//batch_size + 1} ({len(batch)} titles)...")
    batch_gaps = identify_gaps(ai_titles, batch)
    for gap in batch_gaps:
        all_gaps[gap["gap_topic"]] += gap["competitor_coverage"]

# ---------------------------
# Save aggregated results
# ---------------------------
final_gaps = [{"gap_topic": topic, "competitor_coverage": coverage}
              for topic, coverage in all_gaps.items()]

try:
    with open("content_gaps_report.json", "w", encoding="utf-8") as f:
        json.dump({"content_gaps": final_gaps}, f, indent=2, ensure_ascii=False)
    print("✅ Content gaps report saved as content_gaps_report.json")
    print(f"📈 Total gaps identified: {len(final_gaps)}")
except Exception as e:
    print(f"❌ Error saving file: {e}")
    exit(1)
