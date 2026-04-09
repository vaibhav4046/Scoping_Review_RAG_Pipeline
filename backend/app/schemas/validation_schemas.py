"""
Validation Schemas (Pydantic v2)
=================================
Owner : Pranjali (Step 4)
Repo  : vaibhav4046/Scoping_Review_RAG_Pipeline

These schemas are used by:
  - POST /api/v1/reviews/{review_id}/validate   (API route)
  - validate_task (Celery task)
  - ValidationService (service layer)

Kept in backend/app/schemas/ to match how other schema modules
(e.g. screening schemas, extraction schemas) are organised in this repo.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class ValidationRequest(BaseModel):
    """
    Body sent to POST /api/v1/reviews/{review_id}/validate
    Can validate a single study or trigger batch validation for the whole review.
    """
    study_id:    Optional[str] = Field(
        default=None,
        description="Validate a specific study. If None, validate all extracted studies in the review.",
    )
    force_rerun: bool = Field(
        default=False,
        description="Re-run validation even if a result already exists.",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class FieldValidationOut(BaseModel):
    """Per-field result exposed to the frontend."""
    field_name:            str
    final_value:           str
    confidence_score:      float = Field(ge=0.0, le=1.0)
    agreement:             bool
    requires_human_review: bool
    discrepancy_reason:    Optional[str] = None


class ValidationResultOut(BaseModel):
    """
    API response for a single validated study.
    Matches the confidence_scores + source_quotes shape shown in the repo README PICO schema.
    """
    study_id:           str
    overall_confidence: float = Field(ge=0.0, le=1.0)
    validation_passed:  bool
    flagged_fields:     list[str]
    validation_model:   str
    field_results:      list[FieldValidationOut]

    # The cleaned final PICO values ready for the results table
    population:   str
    intervention: str
    comparator:   str
    outcome:      str
    study_design: str
    sample_size:  str
    confidence_scores: dict[str, float]


class ValidationBatchOut(BaseModel):
    """Response when validating all studies in a review."""
    review_id:        str
    total_studies:    int
    passed:           int
    failed:           int
    flagged_studies:  list[str]
    results:          list[ValidationResultOut]


class ValidationStatusOut(BaseModel):
    """Lightweight status check for the Celery task progress bar in the frontend."""
    review_id:  str
    task_id:    str
    status:     str   # "pending" | "running" | "complete" | "error"
    progress:   int   # 0-100
    message:    Optional[str] = None
