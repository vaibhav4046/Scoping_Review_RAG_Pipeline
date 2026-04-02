"""Validation tasks — STUB.

Owner: Pranjali
"""
import logging
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="validate_extractions", queue="validation")
def validate_extractions(review_id: str, batch_size: int = 5):
    """STUB: Cross-validate extractions using secondary LLM.

    TODO (Pranjali):
    - Load extractions with validation_status='pending'
    - For each extraction, call rag_service.retrieve_relevant_chunks_rich()
      to get source evidence
    - Compare extracted values against source chunks
    - Assign confidence scores
    """
    logger.warning(f"validate_extractions STUB called for review {review_id}")
    return {"status": "stub"}
