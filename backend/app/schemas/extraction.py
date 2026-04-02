"""PICO extraction schemas with strict validation and grounding."""

from datetime import datetime
from pydantic import BaseModel, Field


class PICOExtraction(BaseModel):
    """
    Strict PICO extraction schema.
    Every field defaults to "Not Reported" — the LLM must NEVER hallucinate data.
    Every non-"Not Reported" value must have a source_quote.
    """
    population: str = Field(
        default="Not Reported",
        description="Study population/participants. Return 'Not Reported' if not found.",
    )
    intervention: str = Field(
        default="Not Reported",
        description="Intervention or exposure. Return 'Not Reported' if not found.",
    )
    comparator: str = Field(
        default="Not Reported",
        description="Comparator or control. Return 'Not Reported' if not found.",
    )
    outcome: str = Field(
        default="Not Reported",
        description="Primary outcome(s). Return 'Not Reported' if not found.",
    )
    study_design: str = Field(
        default="Not Reported",
        description="Study design (RCT, cohort, etc). Return 'Not Reported' if not found.",
    )
    sample_size: str = Field(
        default="Not Reported",
        description="Number of participants. Return 'Not Reported' if not found.",
    )
    duration: str = Field(
        default="Not Reported",
        description="Follow-up duration. Return 'Not Reported' if not found.",
    )
    setting: str = Field(
        default="Not Reported",
        description="Study setting/location. Return 'Not Reported' if not found.",
    )

    # Confidence per field (0.0 = no evidence, 1.0 = directly stated)
    confidence_scores: dict[str, float] = Field(
        default_factory=lambda: {
            "population": 0.0, "intervention": 0.0, "comparator": 0.0,
            "outcome": 0.0, "study_design": 0.0, "sample_size": 0.0,
            "duration": 0.0, "setting": 0.0,
        }
    )

    # Direct quotes from source text grounding each extraction
    source_quotes: dict[str, str] = Field(
        default_factory=lambda: {
            "population": "", "intervention": "", "comparator": "",
            "outcome": "", "study_design": "", "sample_size": "",
            "duration": "", "setting": "",
        }
    )


class ExtractionResponse(BaseModel):
    id: str
    study_id: str
    population: str
    intervention: str
    comparator: str
    outcome: str
    study_design: str
    sample_size: str
    duration: str
    setting: str
    confidence_scores: dict[str, float]
    source_quotes: dict[str, str]
    model_used: str
    provider: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ExtractionTrigger(BaseModel):
    """Request to trigger PICO extraction."""
    batch_size: int = Field(default=5, ge=1, le=50)
    force_re_extract: bool = False
