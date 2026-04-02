"""RAG (Retrieval-Augmented Generation) service — Enhanced by Vaibhav.

Supports:
- pgvector (production, requires PostgreSQL)
- ChromaDB (local dev, file-based persistence)
- Rich metadata retrieval with page/source provenance
"""

import json
import logging
import os
from typing import List, Optional

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import generate_embedding, generate_embeddings_batch
from app.config import get_settings
from app.models.embedding import Embedding
from app.services.pdf_service import pdf_service

logger = logging.getLogger(__name__)
settings = get_settings()


class RAGService:
    """Handles document embedding, storage, and retrieval with full provenance."""

    # ──────────────────────────────────────────────
    # INGESTION (new)
    # ──────────────────────────────────────────────
    async def ingest_document(
        self,
        db: AsyncSession,
        study_id: str,
        pdf_path: str,
        reindex: bool = False,
    ) -> dict:
        """Full pipeline: extract PDF → chunk → embed → store with rich metadata.

        Returns dict compatible with IngestResponse schema.

        Args:
            db: Async database session
            study_id: Study ID to associate chunks with
            pdf_path: Path to PDF file
            reindex: If True, delete existing embeddings for this study first

        Returns:
            Dict with ingestion results
        """
        # Extract and chunk with rich metadata
        doc_extraction, chunks = pdf_service.extract_and_chunk_rich(pdf_path)

        if not chunks:
            return {
                "document_id": doc_extraction.document_id,
                "source_file_name": doc_extraction.source_file_name,
                "total_pages": doc_extraction.total_pages,
                "total_chunks": 0,
                "chunks_indexed": 0,
                "status": "warning",
                "message": "No chunks extracted from PDF",
            }

        # Delete existing embeddings if reindexing
        if reindex:
            await db.execute(delete(Embedding).where(Embedding.study_id == study_id))
            await db.flush()
            logger.info(f"Cleared existing embeddings for study {study_id}")

        # Batch embed with error handling
        texts = [c.cleaned_text for c in chunks]
        try:
            embeddings = await generate_embeddings_batch(texts)
        except Exception as e:
            logger.error(f"Embedding generation failed for study {study_id}: {e}", exc_info=True)
            return {
                "document_id": doc_extraction.document_id,
                "source_file_name": doc_extraction.source_file_name,
                "total_pages": doc_extraction.total_pages,
                "total_chunks": len(chunks),
                "chunks_indexed": 0,
                "status": "failed",
                "message": f"Embedding generation failed: {str(e)}",
            }

        # Store with rich metadata
        db_embeddings = []
        for chunk, emb_vector in zip(chunks, embeddings):
            db_emb = Embedding(
                study_id=study_id,
                chunk_text=chunk.raw_text,
                chunk_index=chunk.chunk_index,
                token_count=chunk.token_count_estimate,
                embedding=emb_vector,
                # New metadata fields
                document_id=chunk.document_id,
                source_file_name=chunk.source_file_name,
                page_number=chunk.page_number,
                page_range=json.dumps(chunk.page_range),
                chunk_id=chunk.chunk_id,
                section_hint=chunk.section_hint,
                has_table_content=chunk.has_table_content,
                char_count=chunk.char_count,
            )
            db_embeddings.append(db_emb)

        db.add_all(db_embeddings)
        await db.flush()

        logger.info(
            f"Ingested {len(db_embeddings)} chunks for study {study_id} from {doc_extraction.source_file_name}"
        )

        return {
            "document_id": doc_extraction.document_id,
            "source_file_name": doc_extraction.source_file_name,
            "total_pages": doc_extraction.total_pages,
            "total_chunks": len(chunks),
            "chunks_indexed": len(db_embeddings),
            "status": "completed",
            "message": f"Successfully indexed {len(db_embeddings)} chunks from {doc_extraction.total_pages} pages",
        }

    # ──────────────────────────────────────────────
    # LEGACY METHODS (backward compatible)
    # ──────────────────────────────────────────────
    async def embed_and_store(
        self,
        db: AsyncSession,
        study_id: str,
        pdf_path: str,
    ) -> int:
        """Legacy: Extract text from PDF, chunk, embed, and store in pgvector."""
        result = await self.ingest_document(db, study_id, pdf_path)
        return result.get("chunks_indexed", 0)

    async def embed_text_and_store(
        self,
        db: AsyncSession,
        study_id: str,
        full_text: str,
    ) -> int:
        """Legacy: Chunk text, embed, and store (for pre-extracted text)."""
        chunks = pdf_service.chunk_text(full_text)
        if not chunks:
            return 0
        texts = [c["text"] for c in chunks]
        embeddings = await generate_embeddings_batch(texts)
        db_embeddings = []
        for chunk, emb_vector in zip(chunks, embeddings):
            db_emb = Embedding(
                study_id=study_id,
                chunk_text=chunk["text"],
                chunk_index=chunk["index"],
                token_count=chunk["token_count"],
                embedding=emb_vector,
            )
            db_embeddings.append(db_emb)
        db.add_all(db_embeddings)
        await db.flush()
        return len(db_embeddings)

    async def retrieve_relevant_chunks(
        self, db: AsyncSession, study_id: str, query: str, top_k: int = 5
    ) -> List[str]:
        """Legacy: Retrieve chunks as plain text list."""
        rich_results = await self.retrieve_relevant_chunks_rich(
            db=db, query=query, study_id=study_id, top_k=top_k
        )
        return [r["chunk_text"] for r in rich_results]

    async def retrieve_pico_context(
        self,
        db: AsyncSession,
        study_id: str,
        top_k: int = 8,
    ) -> List[str]:
        """Legacy: Retrieve PICO context as plain text list."""
        result = await self.retrieve_pico_context_rich(db, study_id, top_k)
        return [c["chunk_text"] for c in result.get("context_chunks", [])]

    # ──────────────────────────────────────────────
    # RICH RETRIEVAL (new — Vaibhav's primary API)
    # ──────────────────────────────────────────────
    async def retrieve_relevant_chunks_rich(
        self,
        db: AsyncSession,
        query: str,
        study_id: Optional[str] = None,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> list[dict]:
        """Retrieve chunks with full metadata and similarity scores.

        Args:
            db: Async database session
            query: Search query text
            study_id: Optional study filter
            top_k: Maximum results
            min_score: Minimum similarity score (0-1)

        Returns:
            List of dicts with chunk data and metadata
        """
        query_embedding = await generate_embedding(query)

        # Build WHERE clause
        where_clause = ""
        params = {"query_vec": str(query_embedding), "top_k": top_k}

        if study_id:
            where_clause = "WHERE study_id = :study_id"
            params["study_id"] = study_id

        result = await db.execute(
            text(
                f"""
                SELECT
                    id, chunk_text, chunk_index, token_count,
                    document_id, source_file_name, page_number, page_range,
                    chunk_id, section_hint, has_table_content, char_count,
                    study_id,
                    1 - (embedding <=> :query_vec::vector) AS similarity
                FROM embeddings
                {where_clause}
                ORDER BY embedding <=> :query_vec::vector
                LIMIT :top_k
            """
            ),
            params,
        )

        rows = result.fetchall()
        chunks = []
        for row in rows:
            score = float(row.similarity) if row.similarity else 0.0
            if score < min_score:
                continue

            page_range_raw = row.page_range
            try:
                page_range = json.loads(page_range_raw) if page_range_raw else []
            except Exception:
                page_range = []

            chunks.append(
                {
                    "chunk_id": row.chunk_id or row.id,
                    "document_id": row.document_id or "",
                    "source_file_name": row.source_file_name or "",
                    "page_number": row.page_number or 0,
                    "page_range": page_range,
                    "chunk_index": row.chunk_index,
                    "chunk_text": row.chunk_text,
                    "score": round(score, 4),
                    "section_hint": row.section_hint,
                    "preview": row.chunk_text[:200] + "..." if len(row.chunk_text) > 200 else row.chunk_text,
                    "has_table_content": bool(row.has_table_content),
                }
            )

        logger.info(f"Retrieved {len(chunks)} rich chunks for query='{query[:50]}...'")
        return chunks

    async def retrieve_pico_context_rich(
        self,
        db: AsyncSession,
        study_id: str,
        top_k: int = 8,
    ) -> dict:
        """Retrieve chunks optimized for PICO extraction with full metadata.

        Args:
            db: Async database session
            study_id: Study ID to retrieve from
            top_k: Maximum results

        Returns:
            Dict with context_chunks and metadata
        """
        queries = [
            "study population participants demographics inclusion criteria",
            "intervention treatment exposure experimental group",
            "comparator control group placebo standard care",
            "primary outcome secondary outcome results findings",
            "study design methodology randomized cohort cross-sectional",
            "sample size number of participants enrolled",
            "follow-up duration study period length",
            "study setting location hospital community",
        ]

        seen_chunk_ids = set()
        all_chunks = []

        for query in queries:
            results = await self.retrieve_relevant_chunks_rich(
                db=db, query=query, study_id=study_id, top_k=3
            )
            for chunk in results:
                cid = chunk.get("chunk_id") or chunk.get("chunk_index")
                if cid not in seen_chunk_ids:
                    seen_chunk_ids.add(cid)
                    all_chunks.append(chunk)

        # Sort by page then chunk_index for reading order
        all_chunks.sort(key=lambda c: (c.get("page_number", 0), c.get("chunk_index", 0)))
        all_chunks = all_chunks[:top_k]

        # Count total chunks for this study
        count_result = await db.execute(
            text("SELECT COUNT(*) FROM embeddings WHERE study_id = :sid"),
            {"sid": study_id},
        )
        total = count_result.scalar() or 0

        return {
            "study_id": study_id,
            "source_file_name": all_chunks[0]["source_file_name"] if all_chunks else None,
            "context_chunks": all_chunks,
            "total_chunks_available": total,
            "pico_queries_used": queries,
        }

    async def get_study_chunks(self, db: AsyncSession, study_id: str) -> dict:
        """Get all chunks for a study for inspection/debugging.

        Args:
            db: Async database session
            study_id: Study ID to retrieve

        Returns:
            Dict with all chunks and metadata for the study
        """
        result = await db.execute(
            text(
                """
                SELECT chunk_id, document_id, source_file_name, page_number, page_range,
                       chunk_index, chunk_text, section_hint, has_table_content
                FROM embeddings
                WHERE study_id = :study_id
                ORDER BY chunk_index
            """
            ),
            {"study_id": study_id},
        )
        rows = result.fetchall()

        chunks = []
        doc_id = ""
        source_name = ""
        for row in rows:
            doc_id = row.document_id or doc_id
            source_name = row.source_file_name or source_name
            page_range_raw = row.page_range
            try:
                page_range = json.loads(page_range_raw) if page_range_raw else []
            except Exception:
                page_range = []
            chunks.append(
                {
                    "chunk_id": row.chunk_id or "",
                    "document_id": row.document_id or "",
                    "source_file_name": row.source_file_name or "",
                    "page_number": row.page_number or 0,
                    "page_range": page_range,
                    "chunk_index": row.chunk_index,
                    "chunk_text": row.chunk_text,
                    "score": 1.0,
                    "section_hint": row.section_hint,
                    "has_table_content": bool(row.has_table_content),
                }
            )

        return {
            "document_id": doc_id,
            "source_file_name": source_name,
            "total_chunks": len(chunks),
            "chunks": chunks,
        }


rag_service = RAGService()
