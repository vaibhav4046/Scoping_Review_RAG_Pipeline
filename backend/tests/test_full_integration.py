"""
Full repo integration test - validates ALL three contributors' code.

- Vaibhav: PDF Service, Chunker, RAG Service, Vector Store, Embeddings, Schemas
- Durgesh: MeSH Loader, Medical Keyword Mapper
- Prince:  Celery Tasks (search, screening, extraction), PubMed Service, Models
- Cross-module: API routers, config, inter-service references

NOTE: Tests that need Docker-only deps (celery, asyncpg, redis) are skipped
when running locally. They will pass in the CI/Docker environment.
"""
import dataclasses
import importlib
import sys

import numpy as np
import pytest


def _can_import(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
        return True
    except (ImportError, ModuleNotFoundError):
        return False


requires_celery = pytest.mark.skipif(
    not _can_import("celery"), reason="celery not installed (Docker-only dep)"
)
requires_asyncpg = pytest.mark.skipif(
    not _can_import("asyncpg"), reason="asyncpg not installed (Docker-only dep)"
)


# =============================================================================
# VAIBHAV: PDF Service + Chunker + RAG Pipeline
# =============================================================================

class TestVaibhavPDFService:
    def test_pdf_service_instantiates(self):
        from app.services.pdf_service import PDFService
        svc = PDFService()
        assert svc is not None
        assert svc.chunk_size > 0
        assert svc.chunk_overlap >= 0

    def test_block_info(self):
        from app.services.pdf_service import BlockInfo
        b = BlockInfo(text="Hello", block_type="text", font_size=12.0,
                      is_bold=False, bbox=(0, 0, 100, 20), page_number=1)
        assert b.text == "Hello" and b.page_number == 1

    def test_page_extraction(self):
        from app.services.pdf_service import PageExtraction
        p = PageExtraction(page_number=1, raw_text="Hi", cleaned_text="Hi",
                           blocks=[], section_hints=["Intro"], word_count=1)
        assert p.word_count == 1

    def test_missing_file_returns_none(self):
        from app.services.pdf_service import PDFService
        assert PDFService().extract_text("/nonexistent.pdf") is None

    def test_legacy_chunk_text(self):
        from app.services.pdf_service import PDFService
        chunks = PDFService().chunk_text("Word " * 5000)
        assert len(chunks) >= 1


class TestVaibhavChunker:
    def test_chunker_instantiates(self):
        from app.services.pdf_ingestion.chunker import DocumentChunker
        c = DocumentChunker(chunk_size=200, chunk_overlap=50)
        assert c is not None

    def test_chunk_record_fields(self):
        from app.services.pdf_ingestion.chunker import ChunkRecord
        assert len(dataclasses.fields(ChunkRecord)) == 12

    def test_deterministic_chunk_ids(self):
        from app.services.pdf_ingestion.chunker import DocumentChunker
        # min_chunk_size=50 so shorter text passes the threshold
        chunker = DocumentChunker(chunk_size=500, chunk_overlap=50, min_chunk_size=50)
        text = "Randomized clinical trial on lung cancer immunotherapy outcomes in elderly patients over 65."
        c1 = chunker._create_chunk(text, "doc1", "f.pdf", 1, 0, "Methods", False)
        c2 = chunker._create_chunk(text, "doc1", "f.pdf", 1, 0, "Methods", False)
        assert c1 is not None and c2 is not None
        assert c1.chunk_id == c2.chunk_id

    def test_different_inputs_different_ids(self):
        from app.services.pdf_ingestion.chunker import DocumentChunker
        chunker = DocumentChunker(chunk_size=500, chunk_overlap=50, min_chunk_size=50)
        text = "Randomized clinical trial on lung cancer immunotherapy outcomes in elderly patients over 65."
        c1 = chunker._create_chunk(text, "doc1", "f.pdf", 1, 0, "Methods", False)
        c2 = chunker._create_chunk(text + " Extra data.", "doc1", "f.pdf", 1, 1, "Results", False)
        assert c1 is not None and c2 is not None
        assert c1.chunk_id != c2.chunk_id

    def test_chunk_metadata_preserved(self):
        from app.services.pdf_ingestion.chunker import DocumentChunker
        chunker = DocumentChunker(chunk_size=500, chunk_overlap=50, min_chunk_size=50)
        text = "Randomized clinical trial on lung cancer immunotherapy outcomes in elderly patients over 65."
        c = chunker._create_chunk(text, "doc1", "f.pdf", 1, 0, "Methods", False)
        assert c is not None
        assert c.section_hint == "Methods"
        assert c.page_number == 1
        assert c.char_count > 0
        assert c.token_count_estimate > 0
        assert c.cleaned_text is not None

    def test_chunk_document_full(self):
        from app.services.pdf_service import PageExtraction, DocumentExtraction
        from app.services.pdf_ingestion.chunker import DocumentChunker
        chunker = DocumentChunker(chunk_size=200, chunk_overlap=50)
        text = "Clinical trial analysis of immunotherapy outcomes and survival rates. " * 10
        doc = DocumentExtraction(
            document_id="d1", source_file_name="t.pdf", source_file_path="/t.pdf",
            total_pages=1, extraction_timestamp="2026-01-01", file_checksum="x",
            total_word_count=100, full_text=text,
            pages=[PageExtraction(page_number=1, raw_text=text, cleaned_text=text,
                                  blocks=[], section_hints=["Methods"], word_count=100)],
        )
        chunks = chunker.chunk_document(doc)
        assert len(chunks) > 0
        assert all(c.document_id == "d1" for c in chunks)


class TestVaibhavVectorAndEmbeddings:
    def test_chroma_store_imports(self):
        from app.services.vector_store.chroma_store import ChromaStore
        assert ChromaStore is not None

    def test_cosine_similarity(self):
        from app.ai.embeddings import cosine_similarity
        assert abs(cosine_similarity(np.array([1, 0, 0]), np.array([1, 0, 0])) - 1.0) < 0.001
        assert abs(cosine_similarity(np.array([1, 0, 0]), np.array([0, 1, 0]))) < 0.001

    @requires_asyncpg
    def test_embedding_model_columns(self):
        from app.models.embedding import Embedding
        for col in ["chunk_id", "page_number", "section_hint", "document_id",
                     "has_table_content", "source_file_name", "page_range", "char_count"]:
            assert hasattr(Embedding, col), f"Missing column: {col}"


class TestVaibhavSchemas:
    def test_chunk_result(self):
        from app.schemas.retrieval import ChunkResult
        cr = ChunkResult(chunk_id="c1", document_id="d1", source_file_name="f.pdf",
                         page_number=1, chunk_index=0, chunk_text="text", score=0.85)
        assert 0 <= cr.score <= 1

    def test_retrieval_request_defaults(self):
        from app.schemas.retrieval import RetrievalRequest
        req = RetrievalRequest(query="lung cancer", study_id="1")
        assert req.top_k == 5
        assert req.min_score == 0.0

    @requires_asyncpg
    def test_pico_retrieval_response(self):
        from app.schemas.retrieval import PICORetrievalResponse
        pico = PICORetrievalResponse(study_id="1", context_chunks=[],
                                      total_chunks_available=10, queries_used=["population"])
        assert pico.total_chunks_available == 10

    @requires_asyncpg
    def test_rag_service_singleton(self):
        from app.services.rag_service import rag_service
        assert rag_service is not None


# =============================================================================
# DURGESH: MeSH Loader + Medical Keyword Mapper
# =============================================================================

class TestDurgeshMeSHLoader:
    def _mock_db(self):
        from app.services.mesh_loader import MeSHEntry
        e = MeSHEntry(ui="D008175", preferred_name="Lung Neoplasms",
                      synonyms=["Lung Cancer", "Pulmonary Neoplasms"],
                      tree_numbers=["C04.588.894.797"], pubmed_tag="Lung Neoplasms[MeSH]")
        return {t.lower(): e for t in e.all_terms()}

    def test_lookup_term(self):
        from app.services.mesh_loader import lookup_term
        db = self._mock_db()
        assert lookup_term("lung cancer", db).ui == "D008175"
        assert lookup_term("LUNG NEOPLASMS", db).ui == "D008175"
        assert lookup_term("unknown", db) is None

    def test_lookup_subtree(self):
        from app.services.mesh_loader import lookup_subtree
        db = self._mock_db()
        assert len(lookup_subtree("C04", db)) == 1
        assert len(lookup_subtree("Z99", db)) == 0


class TestDurgeshKeywordMapper:
    def _mapper(self):
        from app.services.mesh_loader import MeSHEntry
        from app.services.medical_keyword_mapper import MedicalKeywordMapper
        e = MeSHEntry(ui="D008175", preferred_name="Lung Neoplasms",
                      synonyms=["Lung Cancer"], tree_numbers=["C04.588.894.797"],
                      pubmed_tag="Lung Neoplasms[MeSH]")
        db = {t.lower(): e for t in e.all_terms()}
        return MedicalKeywordMapper(mesh_db=db, eager_load=False)

    def test_get_synonyms_merges(self):
        syns = self._mapper().get_synonyms("lung neoplasms")
        assert "NSCLC" in syns
        assert "Lung Cancer" in syns

    def test_get_mesh_tag(self):
        assert self._mapper().get_mesh_tag("lung neoplasms") == "Lung Neoplasms[MeSH]"

    def test_expand(self):
        exp = self._mapper().expand("lung neoplasms")
        assert exp["mesh_ui"] == "D008175"
        assert len(exp["all_terms"]) > 3

    def test_build_pubmed_query(self):
        q = self._mapper().build_pubmed_query(["lung neoplasms"], filters=["humans[MeSH]"])
        assert "Lung Neoplasms[MeSH]" in q
        assert "[TIAB]" in q
        assert "humans[MeSH]" in q

    def test_unknown_term(self):
        assert self._mapper().expand("xyzzy")["mesh_ui"] is None


# =============================================================================
# PRINCE: Celery Tasks + PubMed + Models
# =============================================================================

class TestPrinceTasks:
    @requires_celery
    def test_search_task_imports(self):
        from app.tasks.search_tasks import search_pubmed
        assert search_pubmed is not None

    @requires_celery
    def test_screening_task_imports(self):
        from app.tasks.screening_tasks import screen_studies
        assert screen_studies is not None

    @requires_celery
    def test_extraction_task_imports(self):
        from app.tasks.extraction_tasks import extract_pico
        assert extract_pico is not None

    def test_pubmed_service(self):
        from app.services.pubmed_service import pubmed_service
        assert pubmed_service is not None

    @requires_asyncpg
    def test_study_model(self):
        from app.models.study import Study
        assert hasattr(Study, "mesh_terms")
        assert hasattr(Study, "pmid")

    @requires_asyncpg
    def test_task_log_model(self):
        from app.models.task_log import TaskLog
        assert hasattr(TaskLog, "status")
        assert hasattr(TaskLog, "progress")

    @requires_celery
    def test_search_references_rag(self):
        import inspect
        from app.tasks.search_tasks import search_pubmed
        src = inspect.getsource(search_pubmed)
        assert "rag_service" in src or "ingest" in src


# =============================================================================
# CROSS-MODULE INTEGRATION
# =============================================================================

class TestCrossModuleIntegration:
    @requires_asyncpg
    def test_main_api_router(self):
        from app.api.v1.router import router
        assert router is not None

    @requires_asyncpg
    def test_all_api_routers_import(self):
        from app.api.v1.retrieval import router as r1
        from app.api.v1.search import router as r2
        assert r1 is not None and r2 is not None

    def test_schemas_import(self):
        from app.schemas.search import SearchRequest
        from app.schemas.screening import ScreeningDecision
        assert SearchRequest is not None and ScreeningDecision is not None

    @requires_celery
    def test_celery_app(self):
        from app.core.celery_app import celery_app
        assert celery_app is not None

    @requires_asyncpg
    def test_database_session(self):
        from app.core.database import async_session_factory
        assert async_session_factory is not None

    def test_app_settings(self):
        from app.config import get_settings
        settings = get_settings()
        assert settings is not None
