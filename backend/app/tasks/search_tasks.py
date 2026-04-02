"""Search tasks — Celery worker implementation.

Owner: Harmeet (Backend / Search Engine)

Pipeline:
  1. Search PubMed (esearch) -> get PMIDs
  2. Fetch article metadata in batches (efetch)
  3. Persist Study records to DB
  4. For each paper with a PMCID, attempt open-access PDF download
  5. Trigger Vaibhav's RAG ingestion pipeline for every downloaded PDF
  6. Update TaskLog progress throughout so the frontend can poll status
"""
import asyncio
import logging
import os

from celery import Task
from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import async_session_factory
from app.models.review import Review
from app.models.study import Study
from app.models.task_log import TaskLog
from app.services.pubmed_service import pubmed_service
from app.services.rag_service import rag_service

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
    """Return existing TaskLog for this review's search task, or create one."""
    result = await db.execute(
        select(TaskLog).where(
            TaskLog.review_id == review_id,
            TaskLog.task_type == "search",
        )
    )
    task_log = result.scalar_one_or_none()

    if task_log is None:
        task_log = TaskLog(
            review_id=review_id,
            task_type="search",
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
    """Update fields on task_log and commit to DB."""
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
# Helper: persist one Study record, skipping duplicates
# ---------------------------------------------------------------------------

async def _upsert_study(db, review_id: str, article: dict) -> Study:
    """
    Insert a Study row if no row with same pmid+review_id already exists.
    Returns the (possibly pre-existing) Study instance.
    """
    pmid = article.get("pmid")

    if pmid:
        result = await db.execute(
            select(Study).where(
                Study.pmid == pmid,
                Study.review_id == review_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            logger.debug("Skipping duplicate PMID %s for review %s", pmid, review_id)
            return existing

    study = Study(
        review_id=review_id,
        pmid=pmid,
        pmcid=article.get("pmcid"),
        doi=article.get("doi"),
        title=article.get("title", "Untitled"),
        abstract=article.get("abstract"),
        authors=article.get("authors"),
        journal=article.get("journal"),
        publication_date=article.get("publication_date"),
        mesh_terms=article.get("mesh_terms"),
        screening_status="pending",
        extraction_status="pending",
        validation_status="pending",
    )
    db.add(study)
    await db.flush()
    return study


# ---------------------------------------------------------------------------
# Helper: download PDF and hand off to Vaibhav's RAG ingestion pipeline
# ---------------------------------------------------------------------------

async def _try_pdf_download_and_ingest(db, study: Study, upload_dir: str) -> bool:
    """
    1. Ask PMC Open-Access API if there is a downloadable PDF.
    2. Download it to disk.
    3. Call rag_service.ingest_document() so Vaibhav's chunker/embedder runs.
    Returns True if ingestion succeeded, False otherwise.
    """
    if not study.pmcid:
        return False

    pdf_url = await pubmed_service.check_pmc_availability(study.pmcid)
    if not pdf_url:
        logger.info("No OA PDF for PMCID %s (study %s)", study.pmcid, study.id)
        return False

    os.makedirs(upload_dir, exist_ok=True)
    pdf_filename = f"{study.id}.pdf"
    pdf_path = os.path.join(upload_dir, pdf_filename)

    downloaded = await pubmed_service.download_pdf(pdf_url, pdf_path)
    if not downloaded:
        logger.warning("PDF download failed for study %s (%s)", study.id, pdf_url)
        return False

    # Persist PDF path on the Study record
    study.pdf_path = pdf_path
    study.pdf_available = True
    await db.flush()

    # Hand off to Vaibhav's RAG pipeline
    try:
        ingest_result = await rag_service.ingest_document(
            db=db,
            study_id=study.id,
            pdf_path=pdf_path,
        )
        chunk_count = ingest_result.get("total_chunks", 0)
        logger.info(
            "RAG ingestion complete for study %s: %d chunks (PDF: %s)",
            study.id, chunk_count, pdf_filename,
        )
        return True
    except Exception as exc:
        logger.error(
            "RAG ingestion failed for study %s: %s", study.id, exc, exc_info=True
        )
        # Don't fail the whole pipeline — PDF is on disk, can be re-ingested later
        return False


# ---------------------------------------------------------------------------
# Main Celery task
# ---------------------------------------------------------------------------

@celery_app.task(
    name="search_pubmed",
    queue="search",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def search_pubmed(self: Task, review_id: str, query: str, max_results: int = 50):
    """
    Full PubMed search pipeline for a scoping review.

    Steps
    -----
    1. esearch   -> get up to max_results PMIDs
    2. efetch    -> get metadata (title, abstract, authors, PMCID ...)
    3. Persist   -> upsert Study rows in DB
    4. PDF       -> attempt open-access download for papers with a PMCID
    5. Ingest    -> call rag_service.ingest_document() for every downloaded PDF
    6. Update    -> keep TaskLog.progress current so the frontend can poll
    """
    logger.info(
        "[search_pubmed] START review=%s query='%s' max=%d",
        review_id, query, max_results,
    )

    async def _pipeline():
        from app.config import get_settings
        settings = get_settings()
        upload_dir = settings.upload_dir

        async with async_session_factory() as db:

            # 0. Set review status to 'searching'
            result = await db.execute(select(Review).where(Review.id == review_id))
            review = result.scalar_one_or_none()
            if review is None:
                raise ValueError(f"Review {review_id} not found in database")
            review.status = "searching"
            await db.flush()

            # 1. Create / update TaskLog
            task_log = await _get_or_create_task_log(db, review_id, self.request.id)
            await _update_task_log(db, task_log, status="running", progress=0.05)

            # 2. PubMed esearch -> PMIDs
            try:
                pmids = await pubmed_service.search(query, max_results=max_results)
            except Exception as exc:
                await _update_task_log(
                    db, task_log,
                    status="failed",
                    error_message=f"PubMed esearch failed: {exc}",
                )
                raise self.retry(exc=exc)

            if not pmids:
                logger.warning("[search_pubmed] No results for query '%s'", query)
                await _update_task_log(
                    db, task_log,
                    status="completed",
                    progress=1.0,
                    total_items=0,
                    completed_items=0,
                )
                review.status = "searching_complete"
                await db.commit()
                return {"status": "completed", "total_found": 0, "ingested": 0}

            total = len(pmids)
            await _update_task_log(db, task_log, total_items=total, progress=0.10)
            logger.info("[search_pubmed] Found %d PMIDs", total)

            # 3. PubMed efetch -> article metadata
            try:
                articles = await pubmed_service.fetch_details(pmids)
            except Exception as exc:
                await _update_task_log(
                    db, task_log,
                    status="failed",
                    error_message=f"PubMed efetch failed: {exc}",
                )
                raise self.retry(exc=exc)

            await _update_task_log(db, task_log, progress=0.25)

            # 4. Persist Study rows
            studies = []
            for article in articles:
                study = await _upsert_study(db, review_id, article)
                studies.append(study)

            review.total_studies = len(studies)
            await db.commit()
            await _update_task_log(
                db, task_log,
                progress=0.40,
                completed_items=len(studies),
            )
            logger.info("[search_pubmed] Persisted %d studies", len(studies))

            # 5. PDF download + RAG ingestion
            ingested_count = 0
            pdf_candidates = [s for s in studies if s.pmcid]
            logger.info(
                "[search_pubmed] %d/%d studies have PMCIDs — attempting PDF download",
                len(pdf_candidates), len(studies),
            )

            for i, study in enumerate(pdf_candidates, start=1):
                success = await _try_pdf_download_and_ingest(db, study, upload_dir)
                if success:
                    ingested_count += 1

                # Progress: 0.40 -> 0.95 spread across PDF candidates
                pdf_progress = 0.40 + (i / max(len(pdf_candidates), 1)) * 0.55
                await _update_task_log(db, task_log, progress=round(pdf_progress, 3))
                await db.commit()

            # 6. Finish
            review.status = "searching_complete"
            await _update_task_log(
                db, task_log,
                status="completed",
                progress=1.0,
                completed_items=len(studies),
            )
            await db.commit()

            logger.info(
                "[search_pubmed] DONE review=%s — %d studies, %d PDFs ingested",
                review_id, len(studies), ingested_count,
            )
            return {
                "status": "completed",
                "total_found": total,
                "studies_saved": len(studies),
                "pdfs_ingested": ingested_count,
            }

    try:
        return _run(_pipeline())
    except Exception as exc:
        logger.error("[search_pubmed] Task failed: %s", exc, exc_info=True)
        raise
