"""Extraction tasks — STUB for Celery worker.

Owner: Jatin (extraction logic), Harmeet (task orchestration)
This stub exists so the API module can import the task reference.
Actual implementation pending from Jatin and Harmeet.
"""
import logging
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="extract_pico", queue="extraction")
def extract_pico(review_id: str, batch_size: int = 5):
    """STUB: Trigger PICO extraction for studies in a review.

    TODO (Jatin/Harmeet):
    - Load studies with pdf_available=True and extraction_status='pending'
    - For each study, call rag_service.retrieve_pico_context_rich() to get source chunks
    - Pass chunks to extraction_service for PICO extraction
    - Store results in Extraction model
    """
    logger.warning(f"extract_pico STUB called for review {review_id}, batch_size={batch_size}")
    return {"status": "stub", "message": "Extraction task not yet implemented"}
