"""Cross-LLM validation schemas."""

from datetime import datetime
from pydantic import BaseModel, Field


class ValidationResult(BaseModel):
    """Result of cross-model validation."""
    agreement_score: float = Field(..., ge=0.0, le=1.0)
    field_agreements: dict[str, bool] = Field(default_factory=dict)
    discrepancies: dict[str, dict] = Field(default_factory=dict)
    validator_extractions: dict[str, str] = Field(default_factory=dict)
    needs_human_review: bool = False


class ValidationResponse(BaseModel):
    id: str
    extraction_id: str
    validator_model: str
    validator_provider: str
    agreement_score: float
    field_agreements: dict[str, bool]
    discrepancies: dict
    needs_human_review: bool
    human_reviewed: bool
    final_decision: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ValidationTrigger(BaseModel):
    """Request to trigger cross-LLM validation."""
    batch_size: int = Field(default=5, ge=1, le=50)
