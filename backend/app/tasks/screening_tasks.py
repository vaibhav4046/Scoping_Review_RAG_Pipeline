"""Screening tasks — STUB.

Owner: Harmeet/Jatin
"""
import logging
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="screen_studies", queue="screening")
def screen_studies(review_id: str, batch_size: int = 10):
    """STUB: Screen studies for relevance."""
    logger.warning(f"screen_studies STUB called for review {review_id}")
    return {"status": "stub"}
