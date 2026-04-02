"""Search endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.review import Review
from app.models.study import Study
from app.models.task_log import TaskLog
from app.models.user import User
from app.schemas.search import SearchRequest, TaskStatusResponse
from app.schemas.study import StudyResponse, StudyBrief
from app.tasks.search_tasks import search_pubmed

router = APIRouter()


@router.post("/{review_id}/search", response_model=TaskStatusResponse)
async def trigger_search(
    review_id: str,
    data: SearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger PubMed search for a review."""
    result = await db.execute(
        select(Review)
        .where(Review.id == review_id)
        .where(Review.owner_id == current_user.id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # Update search query
    review.search_query = data.query
    review.status = "searching"

    # Launch Celery task
    task = search_pubmed.delay(review_id, data.query, data.max_results)

    return TaskStatusResponse(
        task_id=task.id,
        task_type="search",
        status="pending",
    )


@router.get("/{review_id}/studies", response_model=list[StudyBrief])
async def list_studies(
    review_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all studies for a review."""
    result = await db.execute(
        select(Study)
        .where(Study.review_id == review_id)
        .order_by(Study.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{review_id}/studies/{study_id}", response_model=StudyResponse)
async def get_study(
    review_id: str,
    study_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get detailed study information."""
    result = await db.execute(
        select(Study)
        .where(Study.id == study_id)
        .where(Study.review_id == review_id)
    )
    study = result.scalar_one_or_none()
    if not study:
        raise HTTPException(status_code=404, detail="Study not found")
    return study


@router.get("/{review_id}/progress", response_model=list[TaskStatusResponse])
async def get_progress(
    review_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all task progress for a review."""
    result = await db.execute(
        select(TaskLog)
        .where(TaskLog.review_id == review_id)
        .order_by(TaskLog.created_at.desc())
    )
    return result.scalars().all()
