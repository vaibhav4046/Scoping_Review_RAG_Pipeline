"""
Validation API Route
=====================
Owner : Pranjali (Step 4)
Repo  : vaibhav4046/Scoping_Review_RAG_Pipeline

Endpoint: POST /api/v1/reviews/{review_id}/validate
          GET  /api/v1/reviews/{review_id}/validate/status/{task_id}

Matches the REST API table in the repo README:
  POST /api/v1/reviews/{id}/validate  →  Cross-validation

The route follows the same pattern as other route modules in this repo:
  - JWT auth via deps.get_current_user
  - async SQLAlchemy session via deps.get_db
  - Celery task dispatch, returns task_id for frontend polling
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.validation_schemas import (
    ValidationRequest,
    ValidationResultOut,
    ValidationBatchOut,
    ValidationStatusOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/reviews/{review_id}/validate",
    tags=["validation"],
)


# ---------------------------------------------------------------------------
# Dependency stubs
# These will be replaced by the actual deps from app.api.deps at integration.
# Kept as stubs so this file is independently importable during development.
# ---------------------------------------------------------------------------

def _get_db_stub():
    """Stub — replaced by app.api.deps.get_db at integration."""
    raise NotImplementedError("Wire up app.api.deps.get_db")


def _get_current_user_stub():
    """Stub — replaced by app.api.deps.get_current_user at integration."""
    raise NotImplementedError("Wire up app.api.deps.get_current_user")


try:
    from app.api.deps import get_db, get_current_user  # type: ignore
    _DB_DEP   = get_db
    _AUTH_DEP = get_current_user
except ImportError:
    # Graceful fallback during isolated development
    _DB_DEP   = _get_db_stub    # type: ignore
    _AUTH_DEP = _get_current_user_stub  # type: ignore


# ---------------------------------------------------------------------------
# POST /api/v1/reviews/{review_id}/validate
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=ValidationStatusOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger cross-LLM validation for a review",
    description=(
        "Dispatches a Celery validation task for the given review. "
        "If study_id is provided, validates only that paper; "
        "otherwise validates all extracted papers in the review."
    ),
)
async def trigger_validation(
    review_id: str,
    body: ValidationRequest,
    db: AsyncSession = Depends(_DB_DEP),
    current_user: Any = Depends(_AUTH_DEP),
) -> ValidationStatusOut:
    """
    Dispatches the Celery validation task.
    Returns a task_id so the frontend can poll for progress.
    """
    from app.tasks.validate_task import run_validation, run_batch_validation

    logger.info(
        "trigger_validation | review=%s study=%s force=%s user=%s",
        review_id, body.study_id, body.force_rerun, getattr(current_user, "id", "?"),
    )

    # --- Load extraction data from DB ---
    # In the integrated system this queries the Study / ExtractedValues ORM model.
    # Stubbed here with a clear comment so Hitesh can wire it up during integration sprint.
    study_payloads = await _load_extraction_payloads(
        db=db,
        review_id=review_id,
        study_id=body.study_id,
        force_rerun=body.force_rerun,
    )

    if not study_payloads:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No extracted studies found for review {review_id}. "
                "Run extraction first."
            ),
        )

    # --- Dispatch Celery task ---
    if body.study_id and len(study_payloads) == 1:
        payload = study_payloads[0]
        task = run_validation.apply_async(
            kwargs={
                "review_id":    review_id,
                "study_id":     payload["study_id"],
                "primary_pico": payload["primary_pico"],
                "source_text":  payload["source_text"],
            },
            queue="validation",
        )
    else:
        task = run_batch_validation.apply_async(
            kwargs={
                "review_id":      review_id,
                "study_payloads": study_payloads,
            },
            queue="validation",
        )

    logger.info("Dispatched validation task_id=%s for review=%s", task.id, review_id)

    return ValidationStatusOut(
        review_id=review_id,
        task_id=task.id,
        status="pending",
        progress=0,
        message=f"Validation queued for {len(study_payloads)} study/studies.",
    )


# ---------------------------------------------------------------------------
# GET /api/v1/reviews/{review_id}/validate/status/{task_id}
# ---------------------------------------------------------------------------

@router.get(
    "/status/{task_id}",
    response_model=ValidationStatusOut,
    summary="Poll validation task progress",
    description="Used by the frontend progress bar to check validation status.",
)
async def get_validation_status(
    review_id: str,
    task_id: str,
    current_user: Any = Depends(_AUTH_DEP),
) -> ValidationStatusOut:
    """
    Returns current task state from Celery / Redis.
    Frontend polls this every 2s to drive the progress bar (Step 9d in the repo).
    """
    from celery.result import AsyncResult  # type: ignore

    result = AsyncResult(task_id)
    state  = result.state
    meta   = result.info or {}

    if state == "PENDING":
        return ValidationStatusOut(
            review_id=review_id,
            task_id=task_id,
            status="pending",
            progress=0,
        )
    elif state == "PROGRESS":
        return ValidationStatusOut(
            review_id=review_id,
            task_id=task_id,
            status="running",
            progress=meta.get("progress", 0),
            message=meta.get("current_study"),
        )
    elif state == "SUCCESS":
        return ValidationStatusOut(
            review_id=review_id,
            task_id=task_id,
            status="complete",
            progress=100,
        )
    else:
        return ValidationStatusOut(
            review_id=review_id,
            task_id=task_id,
            status="error",
            progress=0,
            message=str(meta),
        )


# ---------------------------------------------------------------------------
# GET /api/v1/reviews/{review_id}/validate/results
# ---------------------------------------------------------------------------

@router.get(
    "/results",
    response_model=ValidationBatchOut,
    summary="Fetch completed validation results for a review",
)
async def get_validation_results(
    review_id: str,
    db: AsyncSession = Depends(_DB_DEP),
    current_user: Any = Depends(_AUTH_DEP),
) -> ValidationBatchOut:
    """
    Returns persisted validation results from the database.
    Called by the frontend Extraction tab to show confidence bars.
    """
    # TODO (Hitesh integration sprint): query ValidationResult ORM model
    # For now returns an informative 501 so the contract is clear
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Results retrieval requires DB integration. "
            "Hitesh: wire up ValidationResult ORM model here."
        ),
    )


# ---------------------------------------------------------------------------
# Private helper
# ---------------------------------------------------------------------------

async def _load_extraction_payloads(
    db: AsyncSession,
    review_id: str,
    study_id: str | None,
    force_rerun: bool,
) -> list[dict]:
    """
    Load extraction data from DB for the validation task.

    TODO (Hitesh integration sprint): replace stub with real ORM queries.
    Shape of each dict:
      {
        "study_id":     str,
        "primary_pico": dict,   # serialised PICOExtraction
        "source_text":  str,    # raw text from Vaibhav's RAG retriever
      }
    """
    logger.warning(
        "_load_extraction_payloads is a STUB. "
        "Hitesh: integrate with Study + ExtractedValues ORM models."
    )
    # Return empty list — real implementation queries the DB
    return []
