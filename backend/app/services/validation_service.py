"""
Validation & Hallucination Defense Service
==========================================
Owner : Pranjali (Step 4)
Repo  : vaibhav4046/Scoping_Review_RAG_Pipeline

Responsibilities
----------------
4.1  ValidationService — receives Jatin's PICO extraction + Vaibhav's raw text chunk
4.2  Cross-LLM check  — independent re-extraction by the VALIDATOR LLM (Groq / Llama)
4.3  Confidence scores — per-field 0.0-1.0, discrepancies flagged for human review

Design decisions that match the existing codebase
--------------------------------------------------
* Primary LLM  : Gemini (PRIMARY_LLM_PROVIDER / PRIMARY_LLM_MODEL from .env)
* Validator LLM: Groq  (VALIDATOR_LLM_PROVIDER / VALIDATOR_LLM_MODEL from .env)
* Pydantic v2 models — strict typing throughout
* async / await throughout (FastAPI + SQLAlchemy async pattern in this repo)
* Logging via standard `logging` module (matches other services)
* "Not Reported" default — ungrounded values are reset, never hallucinated
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PICO_FIELDS = [
    "population",
    "intervention",
    "comparator",
    "outcome",
    "study_design",
    "sample_size",
]

NOT_REPORTED = "Not Reported"

# Agreement thresholds
HIGH_CONFIDENCE_THRESHOLD = 0.85   # both LLMs agree → high confidence
LOW_CONFIDENCE_THRESHOLD  = 0.40   # strong disagreement → flag for human review

# LLM config from environment (mirrors .env.example)
GEMINI_API_KEY           = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY             = os.getenv("GROQ_API_KEY", "")
PRIMARY_LLM_MODEL        = os.getenv("PRIMARY_LLM_MODEL",   "gemini-2.0-flash")
VALIDATOR_LLM_MODEL      = os.getenv("VALIDATOR_LLM_MODEL", "llama-3.3-70b-versatile")
VALIDATOR_LLM_PROVIDER   = os.getenv("VALIDATOR_LLM_PROVIDER", "groq")

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_API_URL   = "https://api.groq.com/openai/v1/chat/completions"

# ---------------------------------------------------------------------------
# Pydantic schemas (Pydantic v2)
# ---------------------------------------------------------------------------

class PICOExtraction(BaseModel):
    """
    The structured PICO output produced by Jatin's extraction service.
    Matches the PICO schema documented in the repo README.
    """
    population:       str = Field(default=NOT_REPORTED, description="Study population / participants")
    intervention:     str = Field(default=NOT_REPORTED, description="Intervention / treatment")
    comparator:       str = Field(default=NOT_REPORTED, description="Comparator / control")
    outcome:          str = Field(default=NOT_REPORTED, description="Primary outcome measure")
    study_design:     str = Field(default=NOT_REPORTED, description="Study design (RCT, cohort, etc.)")
    sample_size:      str = Field(default=NOT_REPORTED, description="Sample size / N")
    confidence_scores: dict[str, float] = Field(
        default_factory=lambda: {f: 0.0 for f in PICO_FIELDS},
        description="Per-field confidence 0.0-1.0 from primary extractor",
    )
    source_quotes: dict[str, str] = Field(
        default_factory=dict,
        description="Supporting quotes from source text per field",
    )


class FieldValidationResult(BaseModel):
    """Result for a single PICO field after cross-LLM comparison."""
    field_name:          str
    primary_value:       str
    validator_value:     str
    final_value:         str
    confidence_score:    float = Field(ge=0.0, le=1.0)
    agreement:           bool
    requires_human_review: bool
    discrepancy_reason:  Optional[str] = None


class ValidationResult(BaseModel):
    """
    Full validation output for one paper's PICO extraction.
    This is what gets stored to the DB and returned via the API.
    """
    study_id:              str
    validated_extraction:  PICOExtraction
    field_results:         list[FieldValidationResult]
    overall_confidence:    float = Field(ge=0.0, le=1.0)
    validation_passed:     bool
    flagged_fields:        list[str] = Field(default_factory=list)
    validation_model:      str
    validation_timestamp:  float
    raw_validator_response: Optional[str] = None


# ---------------------------------------------------------------------------
# Internal helper: LLM clients
# ---------------------------------------------------------------------------

async def _call_gemini(prompt: str, model: str = PRIMARY_LLM_MODEL) -> str:
    """Call Google Gemini API and return raw text response."""
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set in environment.")

    url = GEMINI_API_URL.format(model=model)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.0,   # deterministic for validation
            "maxOutputTokens": 1024,
        },
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            url,
            params={"key": GEMINI_API_KEY},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


async def _call_groq(prompt: str, model: str = VALIDATOR_LLM_MODEL) -> str:
    """Call Groq API (OpenAI-compatible) and return raw text response."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set in environment.")

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a meticulous medical data validator. "
                    "Extract ONLY information explicitly stated in the provided text. "
                    "Return ONLY valid JSON. Never hallucinate values."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 1024,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Prompt builder (Step 4.2)
# ---------------------------------------------------------------------------

def _build_validator_prompt(source_text: str, primary_extraction: PICOExtraction) -> str:
    """
    Build the cross-check prompt sent to the second (validator) LLM.
    The validator is given only the raw source text — NOT the primary extraction —
    so it performs a completely independent re-extraction.
    """
    return f"""You are an independent medical data extractor performing a cross-check.

SOURCE TEXT (from the original clinical paper):
\"\"\"
{source_text[:4000]}
\"\"\"

Task: Extract PICO data STRICTLY from the source text above.
Do NOT guess or infer beyond what is explicitly written.
If a field is not mentioned, use exactly "Not Reported".

Return ONLY a JSON object with these exact keys:
{{
  "population":   "<extracted value or Not Reported>",
  "intervention": "<extracted value or Not Reported>",
  "comparator":   "<extracted value or Not Reported>",
  "outcome":      "<extracted value or Not Reported>",
  "study_design": "<extracted value or Not Reported>",
  "sample_size":  "<extracted value or Not Reported>"
}}

Rules:
- Return ONLY the JSON object. No explanation, no markdown, no preamble.
- Values must be verbatim phrases from the source text where possible.
- Maximum 200 characters per field value.
"""


# ---------------------------------------------------------------------------
# Confidence scorer (Step 4.3)
# ---------------------------------------------------------------------------

def _compute_field_confidence(
    primary_value: str,
    validator_value: str,
    primary_confidence: float,
) -> tuple[float, bool, bool, Optional[str]]:
    """
    Compare primary vs validator values and produce a final confidence score.

    Returns
    -------
    (final_confidence, agreement, requires_human_review, discrepancy_reason)
    """
    p = primary_value.strip().lower()
    v = validator_value.strip().lower()

    # Both say "Not Reported" — low but certain
    if p == NOT_REPORTED.lower() and v == NOT_REPORTED.lower():
        return 0.30, True, False, None

    # Perfect agreement
    if p == v:
        score = min(1.0, (primary_confidence + 0.95) / 2)
        return round(score, 4), True, False, None

    # Partial agreement: one value is a substring of the other
    if p in v or v in p:
        score = min(0.82, (primary_confidence + 0.70) / 2)
        return round(score, 4), True, False, "Minor wording difference"

    # One side says Not Reported, the other doesn't — suspicious
    if p == NOT_REPORTED.lower() or v == NOT_REPORTED.lower():
        score = max(0.20, primary_confidence * 0.4)
        return round(score, 4), False, True, (
            f"Primary says '{primary_value[:60]}' but validator says '{validator_value[:60]}'"
        )

    # Full disagreement
    score = max(0.10, primary_confidence * 0.3)
    return round(score, 4), False, True, (
        f"Primary: '{primary_value[:60]}' — Validator: '{validator_value[:60]}'"
    )


# ---------------------------------------------------------------------------
# Main ValidationService (Steps 4.1 + 4.2 + 4.3)
# ---------------------------------------------------------------------------

class ValidationService:
    """
    Cross-LLM Validation & Hallucination Defense.

    Usage (from Celery task or API route):
    ----------------------------------------
    svc = ValidationService()
    result = await svc.validate(
        study_id      = "pmid_12345678",
        primary_pico  = PICOExtraction(...),   # from Jatin's extraction_service
        source_text   = "...raw text chunk from Vaibhav's RAG retriever..."
    )
    """

    def __init__(self) -> None:
        self._validator_call = (
            _call_groq if VALIDATOR_LLM_PROVIDER == "groq" else _call_gemini
        )
        self._validator_model = VALIDATOR_LLM_MODEL
        logger.info(
            "ValidationService initialised | validator=%s model=%s",
            VALIDATOR_LLM_PROVIDER,
            self._validator_model,
        )

    # ------------------------------------------------------------------ #
    # Public entry-point                                                   #
    # ------------------------------------------------------------------ #

    async def validate(
        self,
        study_id: str,
        primary_pico: PICOExtraction,
        source_text: str,
    ) -> ValidationResult:
        """
        Main validation pipeline.

        Step 4.1: Receive primary extraction + source text
        Step 4.2: Run independent validator LLM
        Step 4.3: Score every field, flag discrepancies
        """
        logger.info("Starting cross-LLM validation for study_id=%s", study_id)
        start = time.time()

        # --- Step 4.2: Independent re-extraction by validator LLM ---
        validator_raw = await self._run_validator(source_text, primary_pico)
        validator_pico = self._parse_validator_response(validator_raw)

        # --- Step 4.3: Per-field comparison + confidence scoring ---
        field_results: list[FieldValidationResult] = []
        final_values:  dict[str, str] = {}
        final_scores:  dict[str, float] = {}
        flagged:       list[str] = []

        for field_name in PICO_FIELDS:
            primary_val   = getattr(primary_pico, field_name, NOT_REPORTED)
            validator_val = validator_pico.get(field_name, NOT_REPORTED)
            primary_conf  = primary_pico.confidence_scores.get(field_name, 0.5)

            conf, agreed, needs_review, reason = _compute_field_confidence(
                primary_val, validator_val, primary_conf
            )

            # Final value selection: prefer primary if confident, else validator
            if agreed or conf >= HIGH_CONFIDENCE_THRESHOLD:
                final_val = primary_val
            elif needs_review and conf < LOW_CONFIDENCE_THRESHOLD:
                # Both uncertain — reset to Not Reported to avoid hallucination
                final_val = NOT_REPORTED
                logger.warning(
                    "study=%s field=%s reset to Not Reported (conf=%.2f)",
                    study_id, field_name, conf,
                )
            else:
                final_val = primary_val  # keep primary, flag for review

            if needs_review:
                flagged.append(field_name)

            field_results.append(FieldValidationResult(
                field_name=field_name,
                primary_value=primary_val,
                validator_value=validator_val,
                final_value=final_val,
                confidence_score=conf,
                agreement=agreed,
                requires_human_review=needs_review,
                discrepancy_reason=reason,
            ))
            final_values[field_name] = final_val
            final_scores[field_name] = conf

        # Build validated extraction with corrected values + new confidence scores
        validated = PICOExtraction(
            **{k: final_values[k] for k in PICO_FIELDS},
            confidence_scores=final_scores,
            source_quotes=primary_pico.source_quotes,
        )

        overall_conf = round(sum(final_scores.values()) / len(PICO_FIELDS), 4)
        passed = len(flagged) == 0 or overall_conf >= LOW_CONFIDENCE_THRESHOLD

        elapsed = round(time.time() - start, 3)
        logger.info(
            "Validation complete | study=%s overall_conf=%.3f flagged=%s elapsed=%.2fs",
            study_id, overall_conf, flagged, elapsed,
        )

        return ValidationResult(
            study_id=study_id,
            validated_extraction=validated,
            field_results=field_results,
            overall_confidence=overall_conf,
            validation_passed=passed,
            flagged_fields=flagged,
            validation_model=self._validator_model,
            validation_timestamp=time.time(),
            raw_validator_response=validator_raw,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    async def _run_validator(
        self,
        source_text: str,
        primary_pico: PICOExtraction,
    ) -> str:
        """Call the second LLM with ONLY the source text (no primary values)."""
        prompt = _build_validator_prompt(source_text, primary_pico)
        try:
            raw = await self._validator_call(prompt, model=self._validator_model)
            logger.debug("Validator raw response (first 300 chars): %s", raw[:300])
            return raw
        except Exception as exc:
            logger.error("Validator LLM call failed: %s", exc, exc_info=True)
            # Return a safe fallback so validation degrades gracefully
            return json.dumps({f: NOT_REPORTED for f in PICO_FIELDS})

    def _parse_validator_response(self, raw: str) -> dict[str, str]:
        """
        Parse validator JSON response robustly.
        Strips markdown fences if present, then parses JSON.
        Returns a dict guaranteed to have all PICO_FIELDS keys.
        """
        fallback = {f: NOT_REPORTED for f in PICO_FIELDS}
        if not raw:
            return fallback

        # Strip markdown code fences (```json ... ```)
        cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()

        # Find the first {...} block in case there is preamble text
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            logger.warning("Validator response contained no JSON object.")
            return fallback

        try:
            parsed: dict[str, Any] = json.loads(match.group())
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse validator JSON: %s", exc)
            return fallback

        # Normalise: ensure all fields present, cap value length
        result: dict[str, str] = {}
        for f in PICO_FIELDS:
            raw_val = str(parsed.get(f, NOT_REPORTED)).strip()
            result[f] = raw_val[:250] if raw_val else NOT_REPORTED

        return result


# ---------------------------------------------------------------------------
# Module-level singleton (mirrors pattern used by pdf_service.py in this repo)
# ---------------------------------------------------------------------------
validation_service = ValidationService()
