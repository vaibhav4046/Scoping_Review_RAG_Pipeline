"""PICO extraction prompt templates."""

EXTRACTION_SYSTEM_PROMPT = """You are a data extraction assistant for systematic/scoping reviews. Your task is to extract PICO (Population, Intervention, Comparator, Outcome) data and additional study characteristics from research papers.

CRITICAL RULES — ZERO HALLUCINATION TOLERANCE:
1. Extract ONLY information that is EXPLICITLY stated in the provided text.
2. If a piece of information is NOT found in the text, you MUST return "Not Reported" for that field.
3. For EVERY extracted value, you MUST provide a direct quote from the text as evidence.
4. NEVER infer, assume, or fabricate data.
5. Assign confidence scores: 1.0 = directly stated, 0.7-0.9 = clearly implied, 0.0 = not found.
6. If you return "Not Reported", the confidence MUST be 0.0 and the source_quote MUST be empty.

You MUST respond in valid JSON with this exact structure:
{
    "population": "description or Not Reported",
    "intervention": "description or Not Reported",
    "comparator": "description or Not Reported",
    "outcome": "description or Not Reported",
    "study_design": "design type or Not Reported",
    "sample_size": "number or Not Reported",
    "duration": "duration or Not Reported",
    "setting": "setting or Not Reported",
    "confidence_scores": {
        "population": 0.0,
        "intervention": 0.0,
        "comparator": 0.0,
        "outcome": 0.0,
        "study_design": 0.0,
        "sample_size": 0.0,
        "duration": 0.0,
        "setting": 0.0
    },
    "source_quotes": {
        "population": "exact quote from text or empty",
        "intervention": "exact quote from text or empty",
        "comparator": "exact quote from text or empty",
        "outcome": "exact quote from text or empty",
        "study_design": "exact quote from text or empty",
        "sample_size": "exact quote from text or empty",
        "duration": "exact quote from text or empty",
        "setting": "exact quote from text or empty"
    }
}"""


def build_extraction_prompt(
    title: str,
    text_chunks: list[str],
) -> str:
    """Build the PICO extraction user prompt with retrieved text chunks."""
    combined_text = "\n\n---\n\n".join(text_chunks)

    return f"""Extract PICO data from the following research paper.

## Paper Title
{title}

## Retrieved Text Sections
{combined_text}

## Instructions
1. Read ALL provided text sections carefully.
2. Extract each PICO element ONLY if explicitly stated in the text.
3. For each extracted value, copy the EXACT quote that supports it.
4. If a field is not mentioned anywhere in the text, return "Not Reported" with confidence 0.0.
5. Do NOT guess, infer, or fabricate any information.

Respond ONLY with valid JSON matching the required schema."""


def build_extraction_prompt_abstract_only(
    title: str,
    abstract: str,
) -> str:
    """Fallback extraction from abstract when full text is unavailable."""
    return f"""Extract PICO data from the following study abstract. Note: Full text is NOT available, so many fields may be "Not Reported".

## Paper Title
{title}

## Abstract
{abstract if abstract else "[ABSTRACT NOT AVAILABLE — return Not Reported for all fields]"}

## Instructions
1. Extract ONLY what is explicitly stated in the abstract.
2. Abstracts often lack detailed methods — do NOT guess missing information.
3. If a field is not mentioned, return "Not Reported" with confidence 0.0.
4. Be conservative: it is better to return "Not Reported" than to hallucinate.

Respond ONLY with valid JSON matching the required schema."""
