"""ChromaDB local vector store — lightweight alternative to pgvector for development.

This module provides a local-persistent ChromaDB collection that can be used
for development/testing without requiring PostgreSQL+pgvector.

Usage:
    store = ChromaStore()
    store.add_chunks(chunks, embeddings)
    results = store.query("what is the intervention?", top_k=5)
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

CHROMA_PERSIST_DIR = os.environ.get("CHROMA_PERSIST_DIR", "/app/data/chroma_db")


@dataclass
class ChromaSearchResult:
    """Structured result from ChromaDB query."""

    chunk_id: str
    document_id: str
    source_file_name: str
    page_number: int
    page_range: list[int]
    chunk_index: int
    chunk_text: str
    score: float
    section_hint: Optional[str] = None
    has_table_content: bool = False


class ChromaStore:
    """Local ChromaDB vector store with rich metadata."""

    def __init__(self, collection_name: str = "scoping_review_chunks", persist_dir: Optional[str] = None):
        """Initialize ChromaDB persistent client.

        Args:
            collection_name: Name of the collection to use
            persist_dir: Directory for persistence (defaults to CHROMA_PERSIST_DIR)
        """
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
        except ImportError:
            raise ImportError("chromadb not installed. Run: pip install chromadb")

        self._persist_dir = persist_dir or CHROMA_PERSIST_DIR
        os.makedirs(self._persist_dir, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=self._persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"ChromaDB store initialized at {self._persist_dir}, collection={collection_name}")

    @property
    def count(self) -> int:
        """Get total number of chunks in collection."""
        return self._collection.count()

    def add_chunks(
        self,
        chunk_ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ) -> int:
        """Add chunks with embeddings and metadata. Idempotent via upsert.

        Args:
            chunk_ids: List of unique chunk IDs
            texts: List of chunk texts
            embeddings: List of embedding vectors
            metadatas: List of metadata dicts

        Returns:
            Number of chunks added/updated
        """
        if not chunk_ids:
            return 0

        # ChromaDB upsert for idempotency
        self._collection.upsert(
            ids=chunk_ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        logger.info(f"Upserted {len(chunk_ids)} chunks into ChromaDB")
        return len(chunk_ids)

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        where: Optional[dict] = None,
        min_score: float = 0.0,
    ) -> list[ChromaSearchResult]:
        """Query by embedding vector with optional metadata filters.

        Args:
            query_embedding: Query embedding vector
            top_k: Maximum number of results to return
            where: Optional metadata filter dict
            min_score: Minimum similarity score (0-1)

        Returns:
            List of ChromaSearchResult objects
        """
        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        results = self._collection.query(**kwargs)

        output = []
        if results and results["ids"] and results["ids"][0]:
            for i, cid in enumerate(results["ids"][0]):
                # ChromaDB returns distance; for cosine, similarity = 1 - distance
                distance = results["distances"][0][i] if results["distances"] else 0
                score = max(0.0, 1.0 - distance)

                if score < min_score:
                    continue

                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                text = results["documents"][0][i] if results["documents"] else ""

                page_range_raw = meta.get("page_range", "[]")
                try:
                    page_range = json.loads(page_range_raw) if isinstance(page_range_raw, str) else page_range_raw
                except (json.JSONDecodeError, TypeError):
                    page_range = []

                output.append(
                    ChromaSearchResult(
                        chunk_id=cid,
                        document_id=meta.get("document_id", ""),
                        source_file_name=meta.get("source_file_name", ""),
                        page_number=int(meta.get("page_number", 0)),
                        page_range=page_range if isinstance(page_range, list) else [],
                        chunk_index=int(meta.get("chunk_index", 0)),
                        chunk_text=text,
                        score=round(score, 4),
                        section_hint=meta.get("section_hint"),
                        has_table_content=bool(meta.get("has_table_content", False)),
                    )
                )

        return output

    def delete_by_document(self, document_id: str) -> int:
        """Delete all chunks for a document (for reindexing).

        Args:
            document_id: Document ID to delete chunks for

        Returns:
            Number of chunks deleted
        """
        try:
            existing = self._collection.get(where={"document_id": document_id})
            if existing and existing["ids"]:
                self._collection.delete(ids=existing["ids"])
                logger.info(f"Deleted {len(existing['ids'])} chunks for document {document_id}")
                return len(existing["ids"])
        except Exception as e:
            logger.warning(f"Delete by document failed: {e}")
        return 0

    def delete_by_study(self, study_id: str) -> int:
        """Delete all chunks for a study.

        Args:
            study_id: Study ID to delete chunks for

        Returns:
            Number of chunks deleted
        """
        try:
            existing = self._collection.get(where={"study_id": study_id})
            if existing and existing["ids"]:
                self._collection.delete(ids=existing["ids"])
                logger.info(f"Deleted {len(existing['ids'])} chunks for study {study_id}")
                return len(existing["ids"])
        except Exception as e:
            logger.warning(f"Delete by study failed: {e}")
        return 0

    def get_document_chunks(self, document_id: str) -> list[ChromaSearchResult]:
        """Get all chunks for a document (for inspection).

        Args:
            document_id: Document ID to retrieve

        Returns:
            List of ChromaSearchResult objects for that document
        """
        try:
            results = self._collection.get(
                where={"document_id": document_id},
                include=["documents", "metadatas"],
            )
            output = []
            if results and results["ids"]:
                for i, cid in enumerate(results["ids"]):
                    meta = results["metadatas"][i] if results["metadatas"] else {}
                    text = results["documents"][i] if results["documents"] else ""
                    page_range_raw = meta.get("page_range", "[]")
                    try:
                        page_range = json.loads(page_range_raw) if isinstance(page_range_raw, str) else []
                    except Exception:
                        page_range = []
                    output.append(
                        ChromaSearchResult(
                            chunk_id=cid,
                            document_id=meta.get("document_id", ""),
                            source_file_name=meta.get("source_file_name", ""),
                            page_number=int(meta.get("page_number", 0)),
                            page_range=page_range,
                            chunk_index=int(meta.get("chunk_index", 0)),
                            chunk_text=text,
                            score=1.0,
                            section_hint=meta.get("section_hint"),
                            has_table_content=bool(meta.get("has_table_content", False)),
                        )
                    )
            return sorted(output, key=lambda x: x.chunk_index)
        except Exception as e:
            logger.error(f"Get document chunks failed: {e}")
            return []
