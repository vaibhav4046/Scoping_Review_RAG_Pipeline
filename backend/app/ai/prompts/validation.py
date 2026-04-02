"""Validation prompt templates for cross-LLM verification."""

VALIDATION_SYSTEM_PROMPT = """You are a validation assistant for systematic review data extraction. Your task is to independently extract PICO data from a research paper and compare your extractions against a previous extraction.

CRITICAL RULES:
1. Extract data independently — do NOT simply agree with the original extraction.
2. Base all extractions ONLY on the provided text.
3. Return "Not Reported" for any field without explicit textual evidence.
4. After your independent extraction, compare field-by-field with the original.
5. Flag any discrepancies where the two extractions disagree.

You MUST respond in valid JSON with this structure:
{
    "independent_extraction": {
        "population": "...",
        "intervention": "...",
        "comparator": "...",
        "outcome": "...",
        "study_design": "...",
        "sample_size": "...",
        "duration": "...",
        "setting": "..."
    },
    "field_agreements": {
        "population": true/false,
        "intervention": true/false,
        "comparator": true/false,
        "outcome": true/false,
        "study_design": true/false,
        "sample_size": true/false,
        "duration": true/false,
        "setting": true/false
    },
    "discrepancies": {
        "field_name": {
            "original": "original value",
            "validator": "your value",
            "reasoning": "why they differ"
        }
    },
    "agreement_score": 0.875,
    "needs_human_review": false
}"""


def build_validation_prompt(
    title: str,
    text_chunks: list[str],
    original_extraction: dict,
) -> str:
    """Build the cross-validation prompt."""
    combined_text = "\n\n---\n\n".join(text_chunks)

    return f"""Independently verify the PICO extraction for the following paper.

## Paper Title
{title}

## Source Text
{combined_text}

## Original Extraction (to validate)
Population: {original_extraction.get('population', 'Not Reported')}
Intervention: {original_extraction.get('intervention', 'Not Reported')}
Comparator: {original_extraction.get('comparator', 'Not Reported')}
Outcome: {original_extraction.get('outcome', 'Not Reported')}
Study Design: {original_extraction.get('study_design', 'Not Reported')}
Sample Size: {original_extraction.get('sample_size', 'Not Reported')}
Duration: {original_extraction.get('duration', 'Not Reported')}
Setting: {original_extraction.get('setting', 'Not Reported')}

## Instructions
1. First, perform YOUR OWN independent extraction from the source text.
2. Then, compare your extraction field-by-field with the original.
3. Mark agreement as true if both extractions convey the same meaning (exact wording not required).
4. If both are "Not Reported", that counts as agreement.
5. Flag "needs_human_review" as true if agreement_score < 0.75 or any critical field disagrees.

Respond ONLY with valid JSON."""
