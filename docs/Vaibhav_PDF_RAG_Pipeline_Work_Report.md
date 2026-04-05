# Individual Contribution Report — Vaibhav

## PDF Processing & RAG Retrieval Pipeline

**MSc Group Project: Scoping Review RAG Pipeline**
**Date:** April 2026
**Repository:** [github.com/vaibhav4046/Scoping_Review_RAG_Pipeline](https://github.com/vaibhav4046/Scoping_Review_RAG_Pipeline)

---

## 1. Executive Summary

Vaibhav designed and implemented the complete PDF Processing & Retrieval-Augmented Generation (RAG) pipeline for the Scoping Review RAG Pipeline project. This end-to-end system covers PDF text extraction with metadata preservation, semantic document chunking, dual vector database storage (ChromaDB for development, pgvector for production), embedding generation via Ollama, PICO-optimized retrieval tailored for medical research, 5 authenticated REST API endpoints, Alembic-managed database migration, and a comprehensive 27-test unit test suite.

*Total contribution: approximately 2,345 lines of production-grade Python code across 14 files, plus 39 additional integration tests written for a teammate's module.*

---

## 2. Assigned Responsibilities

| Step | Description | Status |
|------|-------------|--------|
| **5.1** | Build robust PDF-to-Text pipeline using PyMuPDF preserving table headers, page context, and source metadata | **COMPLETED** |
| **5.2** | Setup Vector Database (ChromaDB + pgvector) to index all clinical papers found in search | **COMPLETED** |
| **5.3** | Implement Context Retriever with exact chunk, page number, and source references for extraction engine | **COMPLETED** |
| **Extra** | Team integration coordination, REST API endpoints, DB migration, test suite, teammate file integration | **COMPLETED** |

---

## 3. Technical Implementation Details

### 3.1 PDF Processing Service

**File:** `backend/app/services/pdf_service.py` (416 lines)

- **PDFService** class using PyMuPDF (fitz) for block-level text extraction
- **BlockInfo** dataclass: captures text, type, font size, bold flag, bounding box, and page number for every text block
- **PageExtraction** dataclass: page-level output with raw/cleaned text, detected section hints, and word count
- **DocumentExtraction**: complete document metadata including UUID, MD5 checksum, and extraction timestamp
- Intelligent heading detection via font-size analysis (1.1x multiplier over body font calculated from most-common size)
- Table region detection and marking for downstream processing
- Backward-compatible legacy API methods (`extract_text`, `chunk_text`) preserved for existing consumers

### 3.2 Semantic Document Chunking

**File:** `backend/app/services/pdf_ingestion/chunker.py` (427 lines)

- **DocumentChunker** class with paragraph-boundary-aware splitting strategy
- **ChunkRecord** dataclass with deterministic SHA256-based chunk IDs for reproducibility and idempotent re-ingestion
- Per-chunk metadata: page number, page range, section hint (heading context), token count estimate, character count, table content flag
- Configuration: `chunk_size=800` chars, `overlap=150` chars, `min_chunk_size=100` chars
- Post-processing step merges undersized chunks for better embedding coherence
- Multi-strategy heading detection: normalized section hints, all-caps heuristic (>60% uppercase), font-size and bold indicators

### 3.3 Vector Store & Embeddings

**ChromaDB Store** (`chroma_store.py` — 250 lines):
- ChromaDB local vector store for development and testing
- Idempotent upsert with full metadata preservation
- Vector similarity search with configurable score threshold filtering
- Study-level and document-level deletion for clean reindexing

**pgvector Embedding Model** (`embedding.py` — 35 lines):
- 8 new metadata columns added: `document_id`, `source_file_name`, `page_number`, `page_range`, `chunk_id`, `section_hint`, `has_table_content`, `char_count`
- `vector(768)` column for nomic-embed-text embeddings with HNSW index (`m=16`, `ef_construction=64`)

**Embedding Generation** (`embeddings.py` — 46 lines):
- Ollama-based local embedding using nomic-embed-text model
- Single-text and batch embedding with error-resilient fallback
- Cosine similarity utility function

### 3.4 RAG Service (Core Orchestrator)

**File:** `backend/app/services/rag_service.py` (384 lines)

- `ingest_document()`: Full pipeline orchestration — extract PDF → chunk → batch embed → store with metadata; supports reindexing
- `retrieve_relevant_chunks_rich()`: Query-based retrieval with similarity score filtering and rich metadata
- `retrieve_pico_context_rich()`: PICO-optimized retrieval running 8 predefined clinical queries (Population, Intervention, Comparator, Outcome, Study Design, Sample Size, Duration, Setting), deduplicating by `chunk_id`, sorting by page number
- `get_study_chunks()`: Full document chunk listing for debugging and frontend display

### 3.5 REST API Endpoints

**File:** `backend/app/api/v1/retrieval.py` (145 lines)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| **GET** | `/api/v1/retrieval/health` | Health check with module version |
| **POST** | `/api/v1/retrieval/ingest` | Ingest PDF into vector store |
| **POST** | `/api/v1/retrieval/retrieve` | Query-based chunk retrieval |
| **GET** | `/api/v1/retrieval/studies/{id}/pico-context` | PICO-optimized evidence retrieval |
| **GET** | `/api/v1/retrieval/studies/{id}/chunks` | Full document chunk listing |

### 3.6 Pydantic Schemas

**File:** `backend/app/schemas/retrieval.py` (108 lines)

9 validated Pydantic models: `ChunkResult`, `RetrievalRequest`, `RetrievalResponse`, `PICORetrievalResponse`, `IngestRequest`, `IngestResponse`, `DocumentMetadata`, `BulkIngestRequest`, `BulkIngestResponse`. All schemas enforce type validation, value bounds (similarity scores 0.0–1.0), and string length limits.

### 3.7 Database Migration

**File:** `backend/alembic/versions/0001_initial_schema.py` (211 lines)

- Creates 8 tables: `users`, `reviews`, `studies`, `task_logs`, `screenings`, `extractions`, `validations`, `embeddings`
- pgvector extension setup with HNSW index for fast cosine similarity search
- Alembic-managed, fully reversible migration with upgrade/downgrade support

---

## 4. Testing

All 27 original unit tests pass. Test results verified on Python 3.13.3 / pytest 8.3.4.

| Test Module | Tests | Coverage Area |
|-------------|-------|---------------|
| `test_chunking.py` (104 lines) | 9 | ChunkRecord creation, page preservation, deterministic IDs, multi-page documents, paragraph boundaries, empty documents |
| `test_pdf_extraction.py` (90 lines) | 9 | BlockInfo, PageExtraction, DocumentExtraction dataclasses, PDFService singleton, custom config, missing files, legacy API |
| `test_retrieval.py` (75 lines) | 9 | ChunkResult score validation (0–1 bounds), RetrievalRequest defaults, IngestResponse, PICO response, BulkIngestResponse |
| **TOTAL** | **27** | **All passing** |

---

## 5. Team Integration & Coordination

### 5.1 Prince/Harmeet Backend Integration (PR #1)

- Reviewed and verified Pull Request #1: `search_tasks.py`, `screening_tasks.py`, `extraction_tasks.py`, and DB migration
- Confirmed full compatibility with the RAG pipeline — no import conflicts, no schema mismatches
- PR merged to master branch

### 5.2 Durgesh's Medical NLP Module Integration

- Integrated `medical_keyword_mapper.py` and `mesh_loader.py` into `backend/app/services/`
- Fixed module imports for project package structure: changed bare `from mesh_loader` to `from app.services.mesh_loader`
- Durgesh's test file was empty (0 bytes) — wrote 39 comprehensive unit tests covering MeSHEntry, lookup, subtree, mapper, expand, PubMed query builder, and manual synonyms
- All 39 tests passing; committed and pushed to master

### 5.3 API Handoff to Teammates

| Teammate | Role | Integration Point |
|----------|------|-------------------|
| **Jatin** | LLM Extraction | `rag_service.retrieve_pico_context_rich()` returns clinical text chunks with `page_number` and `section_hint` for citation |
| **Pranjali** | Validation & QA | `rag_service.retrieve_relevant_chunks_rich()` with similarity scores (0–1) for hallucination defense |
| **Yuan** | Frontend/UI | 5 REST API endpoints with `page_number` field in JSON response for PDF page navigation |
| **Saood** | DevOps & Testing | Docker-compose compatible; 27 passing tests ready for GitHub Actions CI pipeline |

---

## 6. Code Statistics

| Category | Files | Lines of Code |
|----------|-------|---------------|
| Core Services (pdf_service, rag_service, chunker) | 3 | 1,227 |
| Vector Store (chroma_store, embedding model) | 2 | 285 |
| API Endpoints + Pydantic Schemas | 2 | 253 |
| Unit Tests (original) | 3 | 269 |
| Database Migration (Alembic) | 1 | 211 |
| Documentation | 3 | ~350 |
| **TOTAL (Vaibhav)** | **14** | **~2,345** |
| Durgesh integration (39 tests written) | 1 | 311 |

---

## 7. Technical Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| **PyMuPDF over pdfminer** | Better table preservation and block-level metadata extraction with font/bold analysis |
| **ChromaDB + pgvector** | Dual-store strategy: ChromaDB for fast local development, pgvector for production PostgreSQL deployment |
| **Deterministic chunk IDs** | SHA256 hash of (document_id + page + index) ensures idempotent re-ingestion without duplicate entries |
| **PICO-optimized retrieval** | 8 predefined clinical queries (Population, Intervention, Comparator, Outcome, etc.) tailored to medical scoping reviews |
| **Nomic-embed-text via Ollama** | Local inference with no API costs; privacy-preserving for sensitive medical data; no cloud dependency |
| **Semantic chunking** | Respects paragraph and heading boundaries with configurable overlap, rather than naive fixed-size splitting |

---

## 8. Git Commit History

| Commit | Description |
|--------|-------------|
| `1c7c70f` | Initial commit without secrets — complete PDF/RAG pipeline with all services, tests, and documentation |
| `f2e101f` | Merge PR #1 — Prince/Harmeet's backend Celery tasks (search, screening, extraction) + DB migration |
| `4373803` | feat(nlp): add Durgesh's Medical Keyword Mapper & MeSH loader with 39 unit tests |
| `627d431` | test: add full repo integration test suite (91 passed, 13 skipped for Docker-only deps) |

---

*End of Report*
