"""Results and export endpoints."""

import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.review import Review
from app.models.study import Study
from app.models.extraction import Extraction
from app.models.validation import Validation
from app.models.user import User

router = APIRouter()


@router.get("/{review_id}/export")
async def export_results(
    review_id: str,
    format: str = "csv",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export review results as CSV or JSON."""
    # Verify review
    result = await db.execute(
        select(Review)
        .where(Review.id == review_id)
        .where(Review.owner_id == current_user.id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # Fetch all studies with extractions
    studies_result = await db.execute(
        select(Study).where(Study.review_id == review_id)
    )
    studies = studies_result.scalars().all()

    rows = []
    for study in studies:
        # Get latest extraction
        ext_result = await db.execute(
            select(Extraction)
            .where(Extraction.study_id == study.id)
            .order_by(Extraction.created_at.desc())
            .limit(1)
        )
        extraction = ext_result.scalar_one_or_none()

        # Get latest validation
        val = None
        if extraction:
            val_result = await db.execute(
                select(Validation)
                .where(Validation.extraction_id == extraction.id)
                .order_by(Validation.created_at.desc())
                .limit(1)
            )
            val = val_result.scalar_one_or_none()

        row = {
            "pmid": study.pmid or "",
            "title": study.title,
            "authors": study.authors or "",
            "journal": study.journal or "",
            "year": study.publication_date or "",
            "screening_status": study.screening_status,
            "population": extraction.population if extraction else "Not Reported",
            "intervention": extraction.intervention if extraction else "Not Reported",
            "comparator": extraction.comparator if extraction else "Not Reported",
            "outcome": extraction.outcome if extraction else "Not Reported",
            "study_design": extraction.study_design if extraction else "Not Reported",
            "sample_size": extraction.sample_size if extraction else "Not Reported",
            "duration": extraction.duration if extraction else "Not Reported",
            "setting": extraction.setting if extraction else "Not Reported",
            "extraction_model": extraction.model_used if extraction else "",
            "validation_agreement": val.agreement_score if val else "",
            "needs_human_review": val.needs_human_review if val else "",
        }
        rows.append(row)

    if format == "json":
        return rows

    # CSV export
    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={review.title}_export.csv"
        },
    )
