"""Review project schemas."""

from datetime import datetime
from pydantic import BaseModel


class ReviewCreate(BaseModel):
    title: str
    description: str | None = None
    search_query: str | None = None
    inclusion_criteria: str | None = None
    exclusion_criteria: str | None = None


class ReviewUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    search_query: str | None = None
    inclusion_criteria: str | None = None
    exclusion_criteria: str | None = None


class ReviewResponse(BaseModel):
    id: str
    title: str
    description: str | None = None
    search_query: str | None = None
    inclusion_criteria: str | None = None
    exclusion_criteria: str | None = None
    status: str
    total_studies: int
    owner_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReviewStats(BaseModel):
    total_studies: int = 0
    screened: int = 0
    included: int = 0
    excluded: int = 0
    uncertain: int = 0
    extracted: int = 0
    validated: int = 0
    pending_review: int = 0


class ReviewWithStats(ReviewResponse):
    stats: ReviewStats = ReviewStats()
