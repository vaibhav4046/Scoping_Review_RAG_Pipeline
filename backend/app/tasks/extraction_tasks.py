"""Extraction tasks — Celery worker implementation.

Owner: Harmeet (task orchestration) + Jatin (extraction_service logic)

This task is the orchestration layer. It:
  1. Picks up studies that passed screening (screening_status='include')
     and are waiting for extraction (extraction_status='pending')
  2. For studies with a PDF ingested into the vector store, uses Vaibhav's
     retrieve_pico_context_rich() to pull grounded source chunks
  3. Calls extraction_service.extract_pico() which internally uses RAG + LLM
  4. Persists the Extraction row to DB
  5. Updates study.extraction_status and TaskLog progress

Notes
-----
- Studies with NO pdf / embeddings fall back to abstract-only extraction
- Each study is committed individually so a single LLM failure doesn't roll
  back the whole batch
"""
import asyncio
import logging

from celery import Task
from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import async_session_factory
from app.models.embedding import Embedding
from app.models.extraction import Extraction
from app.models.review import Review
from app.models.study import Study
from app.models.task_log import TaskLog
from app.services.extraction_service import extraction_service

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
            TaskLog.task_type == "extraction",
        )
    )
    task_log = result.scalar_one_or_none()
    if task_log is None:
        task_log = TaskLog(
            review_id=review_id,
            task_type="extraction",
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
# Helper: check if a study has embeddings in the vector store
# ---------------------------------------------------------------------------

async def _has_embeddings(db, study_id: str) -> bool:
    """Return True if the study has at least one embedding chunk stored."""
    result = await db.execute(
        select(Embedding.id).where(Embedding.study_id == study_id).limit(1)
    )
    return result.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# Main Celery task
# ---------------------------------------------------------------------------

@celery_app.task(
    name="extract_pico",
    queue="extraction",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def extract_pico(self: Task, review_id: str, batch_size: int = 5):
    """
    PICO extraction for all included studies in a review.

    Steps
    -----
    1. Load studies where screening_status='include' AND extraction_status='pending'
    2. For each study, check if vector embeddings exist (from Vaibhav's pipeline)
    3. Call extraction_service.extract_pico() — uses RAG if embeddings exist,
       falls back to abstract-only extraction otherwise
    4. Persist Extraction row; update study.extraction_status
    5. Keep TaskLog.progress live for the frontend
    """
    logger.info("[extract_pico] START review=%s batch_size=%d", review_id, batch_size)

    async def _pipeline():
        async with async_session_factory() as db:

            # 0. Set review status
            result = await db.execute(select(Review).where(Review.id == review_id))
            review = result.scalar_one_or_none()
            if review is None:
                raise ValueError(f"Review {review_id} not found")
            review.status = "extracting"
            await db.flush()

            # 1. Create / update TaskLog
            task_log = await _get_or_create_task_log(db, review_id, self.request.id)

            # 2. Load studies that passed screening and are waiting for extraction
            result = await db.execute(
                select(Study).where(
                    Study.review_id == review_id,
                    Study.screening_status == "include",
                    Study.extraction_status == "pending",
                )
            )
            studies = result.scalars().all()

            if not studies:
                logger.info(
                    "[extract_pico] No studies ready for extraction in review %s", review_id
                )
                await _update_task_log(
                    db, task_log,
                    status="completed",
                    progress=1.0,
                    total_items=0,
                    completed_items=0,
                )
                review.status = "extraction_complete"
                await db.commit()
                return {"status": "completed", "extracted": 0}

            total = len(studies)
            await _update_task_log(db, task_log, status="running", total_items=total, progress=0.05)
            logger.info("[extract_pico] Extracting PICO from %d studies", total)

            # 3. Extract each study
            success_count = failed_count = rag_count = abstract_count = 0

            for i, study in enumerate(studies, start=1):
                try:
                    # Check if Vaibhav's pipeline has embeddings for this study
                    has_emb = await _has_embeddings(db, study.id)

                    if has_emb:
                        rag_count += 1
                        logger.info(
                            "[extract_pico] Study %s: using RAG (full-text embeddings found)",
                            study.id,
                        )
                    else:
                        abstract_count += 1
                        logger.info(
                            "[extract_pico] Study %s: falling back to abstract-only extraction",
                            study.id,
                        )

                    # Run extraction (RAG or abstract-only, handled inside extraction_service)
                    pico = await extraction_service.extract_pico(
                        db=db,
                        study_id=study.id,
                        title=study.title,
                        abstract=study.abstract,
                        has_embeddings=has_emb,
                    )

                    # Persist Extraction row
                    from app.config import get_settings
                    settings = get_settings()
                    extraction_row = Extraction(
                        study_id=study.id,
                        population=pico.population,
                        intervention=pico.intervention,
                        comparator=pico.comparator,
                        outcome=pico.outcome,
                        study_design=pico.study_design,
                        sample_size=pico.sample_size,
                        duration=pico.duration,
                        setting=pico.setting,
                        confidence_scores=pico.confidence_scores,
                        source_quotes=pico.source_quotes,
                        model_used=settings.primary_llm_model,
                        provider=settings.primary_llm_provider,
                    )
                    db.add(extraction_row)

                    # Update study status
                    study.extraction_status = "completed"
                    success_count += 1

                    logger.info(
                        "[extract_pico] Study %s extracted — "
                        "population='%s...' intervention='%s...'",
                        study.id,
                        pico.population[:60],
                        pico.intervention[:60],
                    )

                except Exception as exc:
                    logger.error(
                        "[extract_pico] Extraction failed for study %s: %s",
                        study.id, exc, exc_info=True,
                    )
                    study.extraction_status = "failed"
                    failed_count += 1

                # Commit each study individually + update progress
                await db.commit()
                progress = round(0.05 + (i / total) * 0.95, 3)
                await _update_task_log(db, task_log, progress=progress, completed_items=i)

                # Pause between batches to respect LLM rate limits
                if i % batch_size == 0 and i < total:
                    logger.info("[extract_pico] Batch checkpoint at %d/%d", i, total)
                    await asyncio.sleep(2)

            # 4. Finish
            review.status = "extraction_complete"
            await _update_task_log(
                db, task_log,
                status="completed",
                progress=1.0,
                completed_items=total,
            )
            await db.commit()

            logger.info(
                "[extract_pico] DONE review=%s — success=%d failed=%d "
                "(rag=%d abstract_fallback=%d)",
                review_id, success_count, failed_count, rag_count, abstract_count,
            )
            return {
                "status": "completed",
                "total": total,
                "success": success_count,
                "failed": failed_count,
                "used_rag": rag_count,
                "used_abstract_fallback": abstract_count,
            }

    try:
        return _run(_pipeline())
    except Exception as exc:
        logger.error("[extract_pico] Task failed: %s", exc, exc_info=True)
        raise
