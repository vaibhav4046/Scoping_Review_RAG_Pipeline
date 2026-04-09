"""
Validation Prompt Templates
============================
Owner : Pranjali (Step 4)
Repo  : vaibhav4046/Scoping_Review_RAG_Pipeline

Centralised prompt strings used by ValidationService.
Kept separate from service logic so Jatin / Hitesh can tune prompts independently.
"""

# ---------------------------------------------------------------------------
# Prompt 1: Independent re-extraction (used by the VALIDATOR LLM)
# ---------------------------------------------------------------------------

VALIDATOR_REEXTRACTION_PROMPT = """You are an independent medical data extractor performing a blind cross-check.

SOURCE TEXT (excerpt from the original clinical paper):
\"\"\"
{source_text}
\"\"\"

Your task: Extract the PICO framework data STRICTLY from the source text above.
You have NOT seen any prior extraction. Do NOT guess or infer beyond what is explicitly stated.
If a field cannot be found in the text, use exactly the string "Not Reported".

Return ONLY a valid JSON object with these exact keys (no extra keys, no markdown):
{{
  "population":   "<patient/participant description or Not Reported>",
  "intervention": "<treatment or experimental arm or Not Reported>",
  "comparator":   "<control/placebo/comparator arm or Not Reported>",
  "outcome":      "<primary outcome measure or Not Reported>",
  "study_design": "<study design type (RCT, cohort, etc.) or Not Reported>",
  "sample_size":  "<total N or group sizes or Not Reported>"
}}

Hard rules:
1. Return ONLY the JSON. No preamble, no explanation, no markdown fences.
2. Maximum 200 characters per field value.
3. Prefer verbatim short phrases from the text.
4. NEVER fabricate values not present in the source text.
"""

# ---------------------------------------------------------------------------
# Prompt 2: Discrepancy explanation (optional — for flagged fields)
# Used if team wants a human-readable reason for disagreement in the UI.
# ---------------------------------------------------------------------------

DISCREPANCY_EXPLANATION_PROMPT = """Two AI models extracted the same medical data field and disagreed.

Field: {field_name}
Model A extracted: "{primary_value}"
Model B extracted: "{validator_value}"
Source text excerpt: "{source_excerpt}"

In one sentence, explain WHY these values differ (e.g., one model was more specific,
the text is ambiguous, or one model hallucinated). Be concise and factual.
"""

# ---------------------------------------------------------------------------
# Prompt 3: Grounding check (spot-check whether a value exists in the text)
# ---------------------------------------------------------------------------

GROUNDING_CHECK_PROMPT = """Check whether the following extracted value is explicitly supported by the source text.

Extracted value: "{extracted_value}"
Source text:
\"\"\"
{source_text}
\"\"\"

Answer with ONLY one of: "GROUNDED" or "UNGROUNDED"
- GROUNDED means the value can be directly traced to words in the source text.
- UNGROUNDED means the value was fabricated or inferred beyond what the text states.

Answer:"""
