# additions + replacements for your script
from openai import OpenAI
from pydantic import BaseModel
from typing import List
import json
import re
from collections import defaultdict

client = OpenAI()

# ---------- Pydantic schema for structured output ----------
class GapItem(BaseModel):
    gap_topic: str
    competitor_coverage: int

class Gaps(BaseModel):
    gaps: List[GapItem]

# keep your parse_json_safe helper
def parse_json_safe(text):
    try:
        match = re.search(r'(\[.*\]|\{.*\})', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
    except json.JSONDecodeError as e:
        print("JSON decode error:", e)
    return []

# ---------- new identify_gaps using structured outputs ----------
def identify_gaps(ai_titles, competitor_batch, max_retries=3):
    system_msg = {
        "role": "system",
        "content": "You are a content analyst. Compare two lists of page titles and identify topics present in competitor titles but missing from our titles."
    }

    user_prompt = (
        "Our titles:\n"
        f"{ai_titles}\n\n"
        "Competitor titles (this batch):\n"
        f"{competitor_batch}\n\n"
        "Return ONLY JSON that matches the Pydantic schema: "
        '{"gaps":[{"gap_topic":"<string>", "competitor_coverage":<integer>}, ...]}.\n'
        "If there are no gaps, return {\"gaps\": []}."
    )

    user_msg = {"role": "user", "content": user_prompt}

    for attempt in range(max_retries):
        try:
            # NOTE: model must support structured outputs; text_format=Gaps instructs the SDK to validate/parse
            response = client.responses.parse(
                model="gpt-4o-2024-08-06",
                input=[system_msg, user_msg],
                text_format=Gaps,
                temperature=0,
            )

            # Preferred: use the validated pydantic output
            parsed: Gaps | None = getattr(response, "output_parsed", None)
            # if parsed is not None:
            #     # parsed.gaps is a list[GapItem]
            #     return [g.dict() for g in parsed.gaps]

            if parsed is not None:
                return [
                    g.model_dump() if hasattr(g, "model_dump") else g.dict()
                    for g in parsed.gaps
                ]


            # Fallback: try to extract text pieces and parse them
            raw_text = ""
            for item in getattr(response, "output", []) or []:
                # some SDKs return dict-like entries
                if isinstance(item, dict):
                    for c in item.get("content", []) or []:
                        if isinstance(c, dict) and c.get("type") == "output_text":
                            raw_text += c.get("text", "")
                else:
                    # attempt string conversion
                    raw_text += str(item)

            if raw_text:
                gaps = parse_json_safe(raw_text)
                if gaps:
                    return gaps

            print(f"⚠️ Retry {attempt+1}/{max_retries}: no parsed output")
        except Exception as e:
            print(f"⚠️ Retry {attempt+1}/{max_retries}: API error: {e}")

    # all retries exhausted: provide the best effort
    print("❌ Failed to get validated gaps after retries — returning empty list as fallback")
    return []

# ---------- rest of your aggregation code remains the same ----------
# (example excerpt showing how to call the function)
if __name__ == "__main__":
    # load sitemaps_data.json like your original script
    with open("sitemaps_data.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    ai_titles = data.get("ai_certs_titles", [])
    competitor_titles = data.get("competitor_titles", [])

    batch_size = 50
    all_gaps = defaultdict(int)

    for i in range(0, len(competitor_titles), batch_size):
        batch = competitor_titles[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1} ({len(batch)} titles)...")
        batch_gaps = identify_gaps(ai_titles, batch)
        for gap in batch_gaps:
            all_gaps[gap["gap_topic"]] += int(gap.get("competitor_coverage", 0))

    final_gaps = [{"gap_topic": t, "competitor_coverage": c} for t, c in all_gaps.items()]
    with open("content_gaps_report.json", "w", encoding="utf-8") as f:
        json.dump({"content_gaps": final_gaps}, f, indent=2, ensure_ascii=False)

    print("Saved content_gaps_report.json")
