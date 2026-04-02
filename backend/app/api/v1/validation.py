"""Validation endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.review import Review
from app.models.study import Study
from app.models.extraction import Extraction
from app.models.validation import Validation
from app.models.user import User
from app.schemas.validation import ValidationResponse, ValidationTrigger
from app.schemas.search import TaskStatusResponse
from app.tasks.validation_tasks import validate_extractions

router = APIRouter()


@router.post("/{review_id}/validate", response_model=TaskStatusResponse)
async def trigger_validation(
    review_id: str,
    data: ValidationTrigger | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger cross-LLM validation."""
    result = await db.execute(
        select(Review)
        .where(Review.id == review_id)
        .where(Review.owner_id == current_user.id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    batch_size = data.batch_size if data else 5
    task = validate_extractions.delay(review_id, batch_size)

    return TaskStatusResponse(
        task_id=task.id,
        task_type="validation",
        status="pending",
    )


@router.get("/{review_id}/validations", response_model=list[ValidationResponse])
async def list_validations(
    review_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all validation results for a review."""
    result = await db.execute(
        select(Validation)
        .join(Extraction, Validation.extraction_id == Extraction.id)
        .join(Study, Extraction.study_id == Study.id)
        .where(Study.review_id == review_id)
        .order_by(Validation.created_at.desc())
    )
    return result.scalars().all()
