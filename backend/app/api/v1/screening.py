"""Screening endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.review import Review
from app.models.screening import Screening
from app.models.user import User
from app.schemas.screening import ScreeningResponse, ScreeningTrigger
from app.schemas.search import TaskStatusResponse
from app.tasks.screening_tasks import screen_studies

router = APIRouter()


@router.post("/{review_id}/screen", response_model=TaskStatusResponse)
async def trigger_screening(
    review_id: str,
    data: ScreeningTrigger | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger LLM screening for pending studies."""
    result = await db.execute(
        select(Review)
        .where(Review.id == review_id)
        .where(Review.owner_id == current_user.id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # Update criteria if provided
    if data:
        if data.inclusion_criteria:
            review.inclusion_criteria = data.inclusion_criteria
        if data.exclusion_criteria:
            review.exclusion_criteria = data.exclusion_criteria

    batch_size = data.batch_size if data else 10
    task = screen_studies.delay(review_id, batch_size)

    return TaskStatusResponse(
        task_id=task.id,
        task_type="screening",
        status="pending",
    )


@router.get("/{review_id}/screenings", response_model=list[ScreeningResponse])
async def list_screenings(
    review_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all screening results for a review."""
    from app.models.study import Study

    result = await db.execute(
        select(Screening)
        .join(Study, Screening.study_id == Study.id)
        .where(Study.review_id == review_id)
        .order_by(Screening.created_at.desc())
    )
    return result.scalars().all()
