"""Retrieval and document ingestion endpoints — Vaibhav's module."""
import logging
import os
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import get_settings
from app.core.database import get_db
from app.models.study import Study
from app.models.user import User
from app.schemas.retrieval import (
    RetrievalRequest, RetrievalResponse,
    IngestRequest, IngestResponse,
    BulkIngestResponse, DocumentMetadata,
    PICORetrievalResponse, DocumentChunkList,
)
from app.services.rag_service import rag_service

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


@router.get("/health")
async def retrieval_health():
    """Health check for retrieval subsystem."""
    return {
        "status": "healthy",
        "module": "vaibhav-pdf-retrieval",
        "version": "1.0.0",
        "vector_store": "pgvector",
    }


@router.post("/ingest", response_model=IngestResponse)
async def ingest_pdf(
    data: IngestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ingest a PDF: extract text, chunk, embed, and index."""
    # Resolve PDF path from study or direct path
    pdf_path = data.pdf_path
    study = None

    if data.study_id:
        result = await db.execute(select(Study).where(Study.id == data.study_id))
        study = result.scalar_one_or_none()
        if not study:
            raise HTTPException(status_code=404, detail="Study not found")
        pdf_path = study.pdf_path

    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(status_code=400, detail=f"PDF not found at path: {pdf_path}")

    try:
        result = await rag_service.ingest_document(
            db=db,
            study_id=data.study_id or "standalone",
            pdf_path=pdf_path,
            reindex=data.reindex,
        )
        return result
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.post("/retrieve", response_model=RetrievalResponse)
async def retrieve_context(
    data: RetrievalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve relevant chunks for a query with full provenance."""
    start = time.time()

    try:
        chunks = await rag_service.retrieve_relevant_chunks_rich(
            db=db,
            query=data.query,
            study_id=data.study_id,
            top_k=data.top_k,
            min_score=data.min_score,
        )

        elapsed_ms = (time.time() - start) * 1000

        return RetrievalResponse(
            query=data.query,
            results=chunks,
            total_results=len(chunks),
            retrieval_time_ms=round(elapsed_ms, 2),
        )
    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")


@router.get("/studies/{study_id}/pico-context", response_model=PICORetrievalResponse)
async def get_pico_context(
    study_id: str,
    top_k: int = Query(default=8, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get PICO-optimized retrieval context for a study. Used by Jatin's extraction engine."""
    result = await db.execute(select(Study).where(Study.id == study_id))
    study = result.scalar_one_or_none()
    if not study:
        raise HTTPException(status_code=404, detail="Study not found")

    try:
        pico_result = await rag_service.retrieve_pico_context_rich(
            db=db,
            study_id=study_id,
            top_k=top_k,
        )
        # Ensure source_file_name is populated from study record
        if not pico_result.get("source_file_name") and study.pdf_path:
            pico_result["source_file_name"] = os.path.basename(study.pdf_path)
        return pico_result
    except Exception as e:
        logger.error(f"PICO context retrieval failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/studies/{study_id}/chunks", response_model=DocumentChunkList)
async def list_study_chunks(
    study_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all indexed chunks for a study (debugging/inspection)."""
    try:
        chunks = await rag_service.get_study_chunks(db=db, study_id=study_id)
        return chunks
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
