"""Search-related schemas."""

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=3, description="PubMed search query")
    max_results: int = Field(default=100, ge=1, le=10000)


class SearchProgress(BaseModel):
    task_id: str
    status: str
    total_found: int = 0
    fetched: int = 0


class TaskStatusResponse(BaseModel):
    task_id: str
    task_type: str
    status: str
    progress: float = 0.0
    total_items: int = 0
    completed_items: int = 0
    error_message: str | None = None

    model_config = {"from_attributes": True}
