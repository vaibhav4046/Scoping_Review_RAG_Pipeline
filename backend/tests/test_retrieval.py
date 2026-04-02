"""Tests for retrieval schemas — Vaibhav's module."""
import pytest
from app.schemas.retrieval import (
    ChunkResult, RetrievalRequest, RetrievalResponse,
    IngestRequest, IngestResponse, DocumentMetadata,
    PICORetrievalResponse, BulkIngestRequest, BulkIngestResponse,
)


class TestChunkResult:
    def test_creation(self):
        chunk = ChunkResult(
            chunk_id="abc123",
            document_id="doc-1",
            source_file_name="test.pdf",
            page_number=1,
            chunk_index=0,
            chunk_text="Sample chunk text",
            score=0.95,
        )
        assert chunk.score == 0.95
        assert chunk.page_number == 1

    def test_score_bounds(self):
        with pytest.raises(ValueError):
            ChunkResult(
                chunk_id="x", document_id="x", source_file_name="x",
                page_number=1, chunk_index=0, chunk_text="x", score=1.5,
            )


class TestRetrievalRequest:
    def test_defaults(self):
        req = RetrievalRequest(query="test query")
        assert req.top_k == 5
        assert req.min_score == 0.0

    def test_custom(self):
        req = RetrievalRequest(query="test", top_k=10, study_id="s1")
        assert req.top_k == 10
        assert req.study_id == "s1"


class TestRetrievalResponse:
    def test_creation(self):
        resp = RetrievalResponse(
            query="test",
            results=[],
            total_results=0,
            retrieval_time_ms=12.5,
        )
        assert resp.total_results == 0


class TestIngestResponse:
    def test_creation(self):
        resp = IngestResponse(
            document_id="doc-1",
            source_file_name="test.pdf",
            total_pages=5,
            total_chunks=20,
            chunks_indexed=20,
        )
        assert resp.status == "completed"


class TestPICORetrievalResponse:
    def test_creation(self):
        resp = PICORetrievalResponse(
            study_id="study-1",
            context_chunks=[],
            total_chunks_available=0,
            pico_queries_used=["population", "intervention"],
        )
        assert resp.study_id == "study-1"
