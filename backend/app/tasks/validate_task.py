"""
Celery Validation Task
=======================
Owner : Pranjali (Step 4)
Repo  : vaibhav4046/Scoping_Review_RAG_Pipeline

This task runs on the "validation" queue as defined in docker-compose.yml:
  -Q default,search,screening,extraction,validation

It is triggered after Jatin's extraction task completes for a study.
The task:
  1. Loads the primary PICO extraction from the database
  2. Loads the source text chunk from Vaibhav's RAG / pdf_service
  3. Calls ValidationService.validate()
  4. Persists ValidationResult back to the database

Celery app import: `from app.core.celery_app import celery_app`
(mirrors how screening_task, extraction_task etc. are structured in this repo)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="app.tasks.validate_task.run_validation",
    queue="validation",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def run_validation(
    self,
    review_id: str,
    study_id: str,
    primary_pico: dict[str, Any],
    source_text: str,
) -> dict[str, Any]:
    """
    Celery task: validate PICO extraction for a single study.

    Parameters
    ----------
    review_id     : str   — UUID of the scoping review
    study_id      : str   — PubMed ID or internal UUID of the paper
    primary_pico  : dict  — serialised PICOExtraction from Jatin's service
    source_text   : str   — raw text chunk from Vaibhav's Context Retriever

    Returns
    -------
    dict  — serialised ValidationResult (persisted to DB by caller)
    """
    import asyncio
    from app.services.validation_service import ValidationService, PICOExtraction

    logger.info(
        "validate_task | review=%s study=%s started (attempt %d)",
        review_id, study_id, self.request.retries + 1,
    )

    # Update task progress (picked up by frontend progress bar poller)
    self.update_state(state="PROGRESS", meta={"progress": 10, "study_id": study_id})

    try:
        # Deserialise primary PICO from dict → Pydantic model
        pico = PICOExtraction(**primary_pico)

        self.update_state(state="PROGRESS", meta={"progress": 30, "study_id": study_id})

        # Run async validation inside synchronous Celery task
        svc = ValidationService()
        result = asyncio.run(
            svc.validate(
                study_id=study_id,
                primary_pico=pico,
                source_text=source_text,
            )
        )

        self.update_state(state="PROGRESS", meta={"progress": 80, "study_id": study_id})

        result_dict = result.model_dump()
        logger.info(
            "validate_task | review=%s study=%s complete | conf=%.3f flagged=%s",
            review_id, study_id,
            result.overall_confidence,
            result.flagged_fields,
        )

        self.update_state(state="PROGRESS", meta={"progress": 100, "study_id": study_id})
        return result_dict

    except Exception as exc:
        logger.error(
            "validate_task | review=%s study=%s FAILED: %s",
            review_id, study_id, exc, exc_info=True,
        )
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="app.tasks.validate_task.run_batch_validation",
    queue="validation",
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def run_batch_validation(
    self,
    review_id: str,
    study_payloads: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Batch validation task — validates all extracted studies in a review.

    Parameters
    ----------
    review_id      : str   — UUID of the scoping review
    study_payloads : list  — list of dicts, each with keys:
                             { study_id, primary_pico, source_text }

    Returns
    -------
    dict — { review_id, total, passed, failed, flagged_study_ids, results[] }
    """
    import asyncio
    from app.services.validation_service import ValidationService, PICOExtraction

    total   = len(study_payloads)
    passed  = 0
    failed  = 0
    flagged: list[str] = []
    results: list[dict] = []

    logger.info("batch_validate | review=%s | %d studies", review_id, total)
    svc = ValidationService()

    for idx, payload in enumerate(study_payloads, start=1):
        study_id    = payload["study_id"]
        source_text = payload["source_text"]
        pico        = PICOExtraction(**payload["primary_pico"])

        progress = int((idx / total) * 100)
        self.update_state(
            state="PROGRESS",
            meta={"progress": progress, "current_study": study_id, "total": total},
        )

        try:
            result = asyncio.run(
                svc.validate(
                    study_id=study_id,
                    primary_pico=pico,
                    source_text=source_text,
                )
            )
            results.append(result.model_dump())

            if result.validation_passed:
                passed += 1
            else:
                failed += 1

            if result.flagged_fields:
                flagged.append(study_id)

        except Exception as exc:
            logger.error(
                "batch_validate | study=%s failed: %s", study_id, exc, exc_info=True
            )
            failed += 1

    logger.info(
        "batch_validate complete | review=%s | passed=%d failed=%d flagged=%d",
        review_id, passed, failed, len(flagged),
    )

    return {
        "review_id":         review_id,
        "total":             total,
        "passed":            passed,
        "failed":            failed,
        "flagged_study_ids": flagged,
        "results":           results,
    }
