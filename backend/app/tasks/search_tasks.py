"""Search tasks — STUB for Celery worker.

Owner: Harmeet (PubMed search)
"""
import logging
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="search_pubmed", queue="search")
def search_pubmed(review_id: str, query: str, max_results: int = 50):
    """STUB: Search PubMed for papers matching a query.

    TODO (Harmeet):
    - Use pubmed_service to search
    - Create Study records
    - Download available PDFs
    - Trigger PDF ingestion via Vaibhav's pipeline
    """
    logger.warning(f"search_pubmed STUB called for review {review_id}")
    return {"status": "stub"}
