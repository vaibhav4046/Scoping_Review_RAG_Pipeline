"""Review CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.review import Review
from app.models.study import Study
from app.models.user import User
from app.schemas.review import (
    ReviewCreate,
    ReviewUpdate,
    ReviewResponse,
    ReviewWithStats,
    ReviewStats,
)

router = APIRouter()


@router.post("/", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_review(
    data: ReviewCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new scoping review project."""
    review = Review(
        title=data.title,
        description=data.description,
        search_query=data.search_query,
        inclusion_criteria=data.inclusion_criteria,
        exclusion_criteria=data.exclusion_criteria,
        owner_id=current_user.id,
    )
    db.add(review)
    await db.flush()
    await db.refresh(review)
    return review


@router.get("/", response_model=list[ReviewResponse])
async def list_reviews(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all reviews for the current user."""
    result = await db.execute(
        select(Review)
        .where(Review.owner_id == current_user.id)
        .order_by(Review.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{review_id}", response_model=ReviewWithStats)
async def get_review(
    review_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get review with statistics."""
    result = await db.execute(
        select(Review)
        .where(Review.id == review_id)
        .where(Review.owner_id == current_user.id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # Compute stats
    stats = await _compute_stats(db, review_id)
    review_data = ReviewResponse.model_validate(review)
    return ReviewWithStats(**review_data.model_dump(), stats=stats)


@router.patch("/{review_id}", response_model=ReviewResponse)
async def update_review(
    review_id: str,
    data: ReviewUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a review."""
    result = await db.execute(
        select(Review)
        .where(Review.id == review_id)
        .where(Review.owner_id == current_user.id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(review, field, value)

    await db.flush()
    await db.refresh(review)
    return review


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a review and all associated data."""
    result = await db.execute(
        select(Review)
        .where(Review.id == review_id)
        .where(Review.owner_id == current_user.id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    await db.delete(review)


async def _compute_stats(db: AsyncSession, review_id: str) -> ReviewStats:
    """Compute review statistics."""
    total = await db.execute(
        select(func.count()).select_from(Study).where(Study.review_id == review_id)
    )
    total_count = total.scalar()

    screened = await db.execute(
        select(func.count()).select_from(Study)
        .where(Study.review_id == review_id)
        .where(Study.screening_status != "pending")
    )
    included = await db.execute(
        select(func.count()).select_from(Study)
        .where(Study.review_id == review_id)
        .where(Study.screening_status == "include")
    )
    excluded = await db.execute(
        select(func.count()).select_from(Study)
        .where(Study.review_id == review_id)
        .where(Study.screening_status == "exclude")
    )
    uncertain = await db.execute(
        select(func.count()).select_from(Study)
        .where(Study.review_id == review_id)
        .where(Study.screening_status == "uncertain")
    )
    extracted = await db.execute(
        select(func.count()).select_from(Study)
        .where(Study.review_id == review_id)
        .where(Study.extraction_status == "completed")
    )
    validated = await db.execute(
        select(func.count()).select_from(Study)
        .where(Study.review_id == review_id)
        .where(Study.validation_status == "completed")
    )
    pending_review = await db.execute(
        select(func.count()).select_from(Study)
        .where(Study.review_id == review_id)
        .where(Study.validation_status == "review_needed")
    )

    return ReviewStats(
        total_studies=total_count,
        screened=screened.scalar(),
        included=included.scalar(),
        excluded=excluded.scalar(),
        uncertain=uncertain.scalar(),
        extracted=extracted.scalar(),
        validated=validated.scalar(),
        pending_review=pending_review.scalar(),
    )
