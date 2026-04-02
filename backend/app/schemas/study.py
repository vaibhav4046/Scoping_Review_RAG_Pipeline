"""Study schemas."""

from datetime import datetime
from pydantic import BaseModel


class StudyResponse(BaseModel):
    id: str
    pmid: str | None = None
    pmcid: str | None = None
    doi: str | None = None
    title: str
    abstract: str | None = None
    authors: str | None = None
    journal: str | None = None
    publication_date: str | None = None
    mesh_terms: str | None = None
    pdf_available: bool = False
    screening_status: str = "pending"
    extraction_status: str = "pending"
    validation_status: str = "pending"
    review_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StudyBrief(BaseModel):
    id: str
    pmid: str | None = None
    title: str
    authors: str | None = None
    journal: str | None = None
    screening_status: str = "pending"
    extraction_status: str = "pending"
    validation_status: str = "pending"

    model_config = {"from_attributes": True}
