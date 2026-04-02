"""Screening schemas."""

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Literal


class ScreeningDecision(BaseModel):
    """Schema for LLM screening output — strict validation."""
    decision: Literal["include", "exclude", "uncertain"]
    rationale: str = Field(..., min_length=10, description="Explanation grounded in the abstract")
    confidence: float = Field(..., ge=0.0, le=1.0)


class ScreeningResponse(BaseModel):
    id: str
    study_id: str
    decision: str
    rationale: str
    confidence: float
    model_used: str
    provider: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ScreeningTrigger(BaseModel):
    """Request to trigger screening for a review."""
    inclusion_criteria: str | None = None
    exclusion_criteria: str | None = None
    batch_size: int = Field(default=10, ge=1, le=100)
