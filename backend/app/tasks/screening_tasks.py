"""Screening tasks — Celery worker implementation.

Owner: Harmeet (task orchestration) + Jatin (screening_service logic)

Pipeline per study:
  1. Load all Study rows for the review with screening_status='pending'
  2. Call screening_service.screen_study() for each (title + abstract)
  3. Persist Screening record to DB
  4. Update study.screening_status -> 'included' | 'excluded' | 'uncertain'
  5. Update TaskLog progress so the frontend progress bar stays live
"""
import asyncio
import logging

from celery import Task
from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import async_session_factory
from app.models.review import Review
from app.models.screening import Screening
from app.models.study import Study
from app.models.task_log import TaskLog
from app.services.screening_service import screening_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: run async code inside a Celery (sync) worker
# ---------------------------------------------------------------------------

def _run(coro):
    """Execute an async coroutine from a synchronous Celery task."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ---------------------------------------------------------------------------
# Helpers: TaskLog persistence
# ---------------------------------------------------------------------------

async def _get_or_create_task_log(db, review_id: str, celery_task_id: str) -> TaskLog:
    result = await db.execute(
        select(TaskLog).where(
            TaskLog.review_id == review_id,
            TaskLog.task_type == "screening",
        )
    )
    task_log = result.scalar_one_or_none()
    if task_log is None:
        task_log = TaskLog(
            review_id=review_id,
            task_type="screening",
            celery_task_id=celery_task_id,
            status="running",
            progress=0.0,
            total_items=0,
            completed_items=0,
        )
        db.add(task_log)
        await db.flush()
    return task_log


async def _update_task_log(
    db,
    task_log: TaskLog,
    *,
    status: str | None = None,
    progress: float | None = None,
    total_items: int | None = None,
    completed_items: int | None = None,
    error_message: str | None = None,
) -> None:
    if status is not None:
        task_log.status = status
    if progress is not None:
        task_log.progress = round(progress, 3)
    if total_items is not None:
        task_log.total_items = total_items
    if completed_items is not None:
        task_log.completed_items = completed_items
    if error_message is not None:
        task_log.error_message = error_message
    await db.commit()


# ---------------------------------------------------------------------------
# Main Celery task
# ---------------------------------------------------------------------------

@celery_app.task(
    name="screen_studies",
    queue="screening",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def screen_studies(self: Task, review_id: str, batch_size: int = 10):
    """
    Screen all pending studies for a review using the primary LLM.

    Steps
    -----
    1. Load studies where screening_status='pending'
    2. For each study, call screening_service.screen_study(title, abstract, criteria)
    3. Persist Screening row; update study.screening_status
    4. Keep TaskLog.progress live for the frontend
    """
    logger.info("[screen_studies] START review=%s batch_size=%d", review_id, batch_size)

    async def _pipeline():
        async with async_session_factory() as db:

            # 0. Load review (need inclusion/exclusion criteria)
            result = await db.execute(select(Review).where(Review.id == review_id))
            review = result.scalar_one_or_none()
            if review is None:
                raise ValueError(f"Review {review_id} not found")

            inclusion = review.inclusion_criteria or "Include all relevant studies."
            exclusion = review.exclusion_criteria or "Exclude studies with insufficient data."
            review.status = "screening"
            await db.flush()

            # 1. Create / update TaskLog
            task_log = await _get_or_create_task_log(db, review_id, self.request.id)

            # 2. Load pending studies
            result = await db.execute(
                select(Study).where(
                    Study.review_id == review_id,
                    Study.screening_status == "pending",
                )
            )
            studies = result.scalars().all()

            if not studies:
                logger.info("[screen_studies] No pending studies for review %s", review_id)
                await _update_task_log(
                    db, task_log,
                    status="completed",
                    progress=1.0,
                    total_items=0,
                    completed_items=0,
                )
                review.status = "screening_complete"
                await db.commit()
                return {"status": "completed", "screened": 0}

            total = len(studies)
            await _update_task_log(db, task_log, status="running", total_items=total, progress=0.05)
            logger.info("[screen_studies] Screening %d studies", total)

            # 3. Screen each study
            included = excluded = uncertain = 0
            for i, study in enumerate(studies, start=1):
                try:
                    decision = await screening_service.screen_study(
                        title=study.title,
                        abstract=study.abstract,
                        inclusion_criteria=inclusion,
                        exclusion_criteria=exclusion,
                    )

                    # Persist Screening row
                    from app.config import get_settings
                    settings = get_settings()
                    screening_row = Screening(
                        study_id=study.id,
                        decision=decision.decision,
                        rationale=decision.rationale,
                        confidence=decision.confidence,
                        model_used=settings.primary_llm_model,
                        provider=settings.primary_llm_provider,
                    )
                    db.add(screening_row)

                    # Update study status
                    study.screening_status = decision.decision  # 'include'|'exclude'|'uncertain'

                    if decision.decision == "include":
                        included += 1
                    elif decision.decision == "exclude":
                        excluded += 1
                    else:
                        uncertain += 1

                    logger.info(
                        "[screen_studies] Study %s -> %s (conf=%.2f)",
                        study.id, decision.decision, decision.confidence,
                    )

                except Exception as exc:
                    logger.error(
                        "[screen_studies] Screening failed for study %s: %s",
                        study.id, exc, exc_info=True,
                    )
                    # Mark as uncertain rather than crashing the whole batch
                    study.screening_status = "uncertain"
                    uncertain += 1

                # Commit each study individually + update progress
                await db.commit()
                progress = round(0.05 + (i / total) * 0.95, 3)
                await _update_task_log(db, task_log, progress=progress, completed_items=i)

                # Respect batch_size: small sleep between batches to avoid LLM rate limits
                if i % batch_size == 0 and i < total:
                    logger.info("[screen_studies] Batch checkpoint at %d/%d", i, total)
                    await asyncio.sleep(1)

            # 4. Finish
            review.status = "screening_complete"
            await _update_task_log(
                db, task_log,
                status="completed",
                progress=1.0,
                completed_items=total,
            )
            await db.commit()

            logger.info(
                "[screen_studies] DONE review=%s — included=%d excluded=%d uncertain=%d",
                review_id, included, excluded, uncertain,
            )
            return {
                "status": "completed",
                "total_screened": total,
                "included": included,
                "excluded": excluded,
                "uncertain": uncertain,
            }

    try:
        return _run(_pipeline())
    except Exception as exc:
        logger.error("[screen_studies] Task failed: %s", exc, exc_info=True)
        raise
