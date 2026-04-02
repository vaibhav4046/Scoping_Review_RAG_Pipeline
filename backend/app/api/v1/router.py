"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1 import auth, reviews, search, screening, extraction, validation, results, retrieval

router = APIRouter(prefix="/api/v1")

router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(reviews.router, prefix="/reviews", tags=["Reviews"])
router.include_router(search.router, prefix="/reviews", tags=["Search"])
router.include_router(screening.router, prefix="/reviews", tags=["Screening"])
router.include_router(extraction.router, prefix="/reviews", tags=["Extraction"])
router.include_router(validation.router, prefix="/reviews", tags=["Validation"])
router.include_router(results.router, prefix="/reviews", tags=["Results"])
router.include_router(retrieval.router, prefix="/retrieval", tags=["Retrieval & RAG"])
