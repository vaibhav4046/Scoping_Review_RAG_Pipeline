import json
import os
from typing import Dict, Any
import google.generativeai as genai

# 1. Importing Durgesh's Medical NLP module
from app.services.medical_keyword_mapper import get_mapper

# Configure Gemini via environment variable
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-2.5-flash')

# -------------------------------------------------------------------
# 1. Define the System Persona
# -------------------------------------------------------------------
SYSTEM_PROMPT = """
You are an expert clinical data abstractor. Your task is to extract PICO
(Population, Intervention, Comparator, Outcome) data from clinical trial
excerpts and output the data STRICTLY as a JSON object.

RULES:
1. DO NOT hallucinate or infer data. If a specific value is not explicitly
   mentioned in the text, you MUST return `null` for that field.
2. STANDARDIZE TERMINOLOGY: Map specific diseases and treatments to their
   broader canonical categories if known (e.g., "NSCLC" -> "lung neoplasms").
3. Output ONLY valid JSON.
"""

# -------------------------------------------------------------------
# 2. Define the Golden Examples
# -------------------------------------------------------------------
FEW_SHOT_EXAMPLES = [
    {
        "input": "This phase 3 randomized, double-blind trial evaluated the efficacy of Pembrolizumab versus standard chemotherapy (Docetaxel) in patients with advanced non-small-cell lung cancer (NSCLC). A total of 1034 patients (median age 63 years) were enrolled. The primary endpoint was overall survival (OS).",
        "expected_output": {
            "paper_id": "example_1",
            "population": {
                "condition": "lung neoplasms",
                "sample_size": 1034,
                "age_range": "median age 63 years",
                "key_demographics": []
            },
            "intervention": {
                "category": "immunotherapy",
                "name": "Pembrolizumab",
                "dosage_and_duration": None
            },
            "comparator": {
                "category": "chemotherapy",
                "name": "Docetaxel"
            },
            "outcome": {
                "primary_endpoint": "overall survival",
                "statistical_results": None,
                "adverse_events": []
            }
        }
    }
]

# -------------------------------------------------------------------
# 3. Prompt Constructors & API Calls
# -------------------------------------------------------------------
def build_extraction_prompt(paper_id: str, text_chunk: str) -> str:
    prompt = f"{SYSTEM_PROMPT}\n\n--- EXAMPLES ---\n"
    for i, example in enumerate(FEW_SHOT_EXAMPLES, 1):
        prompt += f"\nExample {i}:\nInput Text:\n{example['input']}\n"
        prompt += f"Expected JSON Output:\n{json.dumps(example['expected_output'], indent=2)}\n"
        prompt += "-" * 40 + "\n"
    prompt += f"\n--- ACTUAL EXTRACTION TASK ---\nPaper ID: {paper_id}\nInput Text:\n{text_chunk}\n\nExpected JSON Output:\n"
    return prompt

# FIX: Added paper_id to the critique prompt so the auditor doesn't delete it
CRITIQUE_PROMPT_TEMPLATE = """
You are a strict Medical Data Auditor. Review this AI's data extraction against the original text.
Paper ID: {paper_id}
Original Text: {original_text}
AI Extraction: {ai_extraction}
Task: Verify all non-null values are supported by the text. Fix any hallucinations.
Note: The paper_id is provided above, do not mark it as a hallucination.
Output the CORRECTED JSON exactly.
"""

def call_llm(prompt: str) -> str:
    response = model.generate_content(prompt)
    raw_text = response.text.strip()

    # Safely strip out markdown formatting without triggering Syntax errors
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    elif raw_text.startswith("```"):
        raw_text = raw_text[3:]

    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]

    return raw_text.strip()

# -------------------------------------------------------------------
# 4. The Orchestration Loop
# -------------------------------------------------------------------
def execute_cove_pipeline(paper_id: str, text_chunk: str) -> Dict[str, Any]:
    print(f"Starting extraction for Paper: {paper_id}")

    # PASS 1: Extraction
    first_draft_json_str = call_llm(build_extraction_prompt(paper_id, text_chunk))
    print("Pass 1 Complete. Initiating Verification...")

    # PASS 2: CoVe Verification (FIX: Passing paper_id here)
    critique_prompt = CRITIQUE_PROMPT_TEMPLATE.format(
        paper_id=paper_id,
        original_text=text_chunk,
        ai_extraction=first_draft_json_str
    )
    final_verified_json_str = call_llm(critique_prompt)

    try:
        final_data = json.loads(final_verified_json_str)
        print("Verification Complete. Applying Medical NLP Standardization...")

        # PASS 3: Durgesh's Dictionary Normalization
        try:
            mapper = get_mapper(eager_load=False)
            if final_data.get("population") and final_data["population"].get("condition"):
                condition_term = final_data["population"]["condition"]
                expanded = mapper.expand(condition_term)
                final_data["population"]["condition"] = expanded.get("preferred", condition_term)
        except Exception as e:
            print(f"Note: Skipping NLP normalization ({e})")

        print("Pipeline Finished. Data is clean.")
        return final_data
    except json.JSONDecodeError:
        print("Error: LLM did not return valid JSON.")
        return {}

# --- Example Usage ---
if __name__ == "__main__":
    sample_paper_id = "PMID_78910"
    sample_text = "This trial evaluated the efficacy of Pembrolizumab versus Placebo in 400 patients with NSCLC."

    final_result = execute_cove_pipeline(sample_paper_id, sample_text)
    print("\n--- FINAL VERIFIED & STANDARDIZED OUTPUT ---")
    print(json.dumps(final_result, indent=2))
