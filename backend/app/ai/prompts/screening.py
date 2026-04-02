"""Screening prompt templates."""

SCREENING_SYSTEM_PROMPT = """You are a systematic review screening assistant. Your task is to evaluate whether a study should be INCLUDED or EXCLUDED from a scoping review based on its title and abstract.

CRITICAL RULES:
1. Base your decision ONLY on the title and abstract provided.
2. NEVER fabricate or hallucinate information not present in the text.
3. If the abstract is missing or insufficient, mark the study as "uncertain".
4. Provide a clear rationale grounded in the text.
5. Assign a confidence score between 0.0 and 1.0.

You MUST respond in valid JSON format with exactly these fields:
{
    "decision": "include" | "exclude" | "uncertain",
    "rationale": "Your explanation here, referencing specific parts of the title/abstract",
    "confidence": 0.85
}"""


def build_screening_prompt(
    title: str,
    abstract: str,
    inclusion_criteria: str,
    exclusion_criteria: str,
) -> str:
    """Build the screening user prompt."""
    abstract_text = abstract if abstract else "[ABSTRACT NOT AVAILABLE]"

    return f"""Evaluate the following study for inclusion in a scoping review.

## Inclusion Criteria
{inclusion_criteria}

## Exclusion Criteria
{exclusion_criteria}

## Study to Evaluate

**Title:** {title}

**Abstract:** {abstract_text}

## Instructions
- If the study clearly meets the inclusion criteria and does not meet any exclusion criteria → "include"
- If the study clearly meets one or more exclusion criteria → "exclude"
- If there is insufficient information to decide (e.g., no abstract) → "uncertain"
- Provide a rationale that references SPECIFIC parts of the title or abstract
- If the abstract is missing, you MUST return "uncertain"

Respond ONLY with valid JSON."""
