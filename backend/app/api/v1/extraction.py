"""Extraction endpoints."""

import os
import shutil

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import get_settings
from app.core.database import get_db
from app.models.review import Review
from app.models.study import Study
from app.models.extraction import Extraction
from app.models.user import User
from app.schemas.extraction import ExtractionResponse, ExtractionTrigger
from app.schemas.search import TaskStatusResponse
from app.tasks.extraction_tasks import extract_pico

router = APIRouter()
settings = get_settings()


@router.post("/{review_id}/extract", response_model=TaskStatusResponse)
async def trigger_extraction(
    review_id: str,
    data: ExtractionTrigger | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger PICO extraction for included studies."""
    result = await db.execute(
        select(Review)
        .where(Review.id == review_id)
        .where(Review.owner_id == current_user.id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    batch_size = data.batch_size if data else 5
    task = extract_pico.delay(review_id, batch_size)

    return TaskStatusResponse(
        task_id=task.id,
        task_type="extraction",
        status="pending",
    )


@router.get("/{review_id}/extractions", response_model=list[ExtractionResponse])
async def list_extractions(
    review_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all extractions for a review."""
    result = await db.execute(
        select(Extraction)
        .join(Study, Extraction.study_id == Study.id)
        .where(Study.review_id == review_id)
        .order_by(Extraction.created_at.desc())
    )
    return result.scalars().all()


@router.post("/{review_id}/studies/{study_id}/upload-pdf")
async def upload_pdf(
    review_id: str,
    study_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a PDF for a study (manual upload)."""
    result = await db.execute(
        select(Study)
        .where(Study.id == study_id)
        .where(Study.review_id == review_id)
    )
    study = result.scalar_one_or_none()
    if not study:
        raise HTTPException(status_code=404, detail="Study not found")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Save file
    pdf_dir = os.path.join(settings.upload_dir, review_id)
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_path = os.path.join(pdf_dir, f"{study_id}.pdf")

    with open(pdf_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    study.pdf_path = pdf_path
    study.pdf_available = True

    return {"message": "PDF uploaded successfully", "pdf_path": pdf_path}
