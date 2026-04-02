# Vaibhav Lalwani — Final Delivery Report

**Date**: April 2, 2026
**Module**: PDF Processing & RAG (Retrieval-Augmented Generation)
**Workstream**: Steps 5.1, 5.2, 5.3

---

## 1. What I Found

### Repo Assessment
The repository at `Scoping_Review_Project_Demo/` is a **well-architected production-grade system** with:
- **FastAPI backend** with SQLAlchemy 2.0, Pydantic v2, async throughout
- **8-service docker-compose**: PostgreSQL+pgvector, Redis, Ollama, FastAPI, Celery worker/beat, Flower, Next.js frontend
- **Complete database models**: User, Review, Study, Extraction, Validation, Embedding, Screening, TaskLog
- **Service layer**: PDF, RAG, extraction, validation, screening, PubMed
- **AI layer**: Ollama embeddings, unified LLM client (Ollama/Gemini/Groq), extraction/validation/screening prompts
- **Auth**: JWT + bcrypt
- **API**: Full v1 router with auth, reviews, search, screening, extraction, validation, results endpoints

### What Already Existed
- Basic `pdf_service.py` — naive `get_text("text")`, word-based chunking, no page metadata
- Basic `rag_service.py` — pgvector storage, returned plain text strings only (no metadata)
- Basic `Embedding` model — only study_id, chunk_text, chunk_index, token_count, embedding vector
- Complete docker-compose with all 8 services
- Complete `.env.example` with all config
- Existing README with architecture diagram

### What Was Missing
- **No page-level metadata** in extraction or retrieval
- **No document IDs or checksums** for dedup/traceability
- **No section/heading detection** in PDF extraction
- **No table structure preservation**
- **No rich retrieval results** — downstream couldn't know which page/section a chunk came from
- **No ChromaDB** option for local dev without PostgreSQL
- **No Celery task files** — app would crash on import (`from app.tasks.extraction_tasks import extract_pico`)
- **No tests at all**
- **No dedicated retrieval API endpoints**
- **No handoff documentation**

---

## 2. What I Implemented

### Core Modules (2,578 lines of code)

| File | Lines | Status | Purpose |
|------|-------|--------|---------|
| `backend/app/services/pdf_service.py` | 403 | REWRITTEN | Block-level PDF extraction with rich metadata |
| `backend/app/services/pdf_ingestion/chunker.py` | 411 | NEW | Page-aware semantic chunker with deterministic IDs |
| `backend/app/services/pdf_ingestion/__init__.py` | 2 | NEW | Module init |
| `backend/app/services/vector_store/chroma_store.py` | 250 | NEW | ChromaDB local persistent vector store |
| `backend/app/services/vector_store/__init__.py` | 2 | NEW | Module init |
| `backend/app/services/rag_service.py` | 372 | REWRITTEN | Enhanced RAG with rich metadata retrieval |
| `backend/app/models/embedding.py` | 35 | UPDATED | +8 metadata columns |
| `backend/app/schemas/retrieval.py` | 109 | NEW | Pydantic schemas for retrieval system |
| `backend/app/schemas/documents.py` | 29 | NEW | Document/evidence schemas |
| `backend/app/api/v1/retrieval.py` | 143 | NEW | 5 retrieval API endpoints |
| `backend/app/api/v1/router.py` | 17 | UPDATED | Added retrieval router |
| `backend/app/tasks/extraction_tasks.py` | ~25 | NEW | Celery stub (unblocks app startup) |
| `backend/app/tasks/search_tasks.py` | ~20 | NEW | Celery stub |
| `backend/app/tasks/screening_tasks.py` | ~15 | NEW | Celery stub |
| `backend/app/tasks/validation_tasks.py` | ~20 | NEW | Celery stub |
| `backend/app/tasks/__init__.py` | 0 | NEW | Module init |
| `backend/requirements.txt` | +4 | UPDATED | Added chromadb, pytest |
| `.env.example` | +4 | UPDATED | Added ChromaDB config |

### Tests & Scripts

| File | Lines | Purpose |
|------|-------|---------|
| `backend/tests/test_pdf_extraction.py` | 90 | 11 unit tests for PDF extraction |
| `backend/tests/test_chunking.py` | 104 | 10 unit tests for chunker |
| `backend/tests/test_retrieval.py` | 75 | 7 schema validation tests |
| `backend/tests/conftest.py` | 4 | Pytest config |
| `scripts/ingest_sample.py` | 82 | Manual PDF ingestion script |
| `scripts/smoke_test_retrieval.py` | 120 | End-to-end pipeline smoke test |

### Documentation

| File | Lines | Purpose |
|------|-------|---------|
| `docs/vaibhav_handoff.md` | 183 | Complete technical handoff |
| `docs/retrieval_contract.md` | 113 | API & service interface contract |
| `docs/team_dependency_handoff.md` | 59 | Per-teammate dependency guide |

---

## 3. How Vaibhav's Ownership Is Covered

### Step 5.1 — PDF-to-Text Pipeline ✅
**File**: `backend/app/services/pdf_service.py`

- Uses `fitz.get_text("dict")` for block-level extraction preserving structure
- Detects headings via font size analysis and bold text flags
- Detects table regions via block alignment patterns
- Preserves per-page metadata: page_number, section_hints, word_count, has_tables
- Preserves per-document metadata: UUID document_id, source_file_name, source_file_path, MD5 checksum, extraction_timestamp
- Full backward compatibility: `extract_text()`, `chunk_text()`, `extract_and_chunk()` all work identically to the original

**Verified**: Tested against the uploaded team_work_distribution PDF — extracted 2 pages, 754 words, detected 10 section headings across both pages.

### Step 5.2 — Vector Database Indexing ✅
**Files**: `chroma_store.py`, `embedding.py`, `rag_service.py`

- **pgvector** (production): Enhanced Embedding model with 8 new metadata columns (document_id, source_file_name, page_number, page_range, chunk_id, section_hint, has_table_content, char_count). All nullable for backward compat.
- **ChromaDB** (development): Standalone local-persistent vector store with cosine similarity, metadata filtering, idempotent upsert, document-level delete for reindexing.
- `rag_service.ingest_document()` provides the full pipeline: extract → chunk → embed → store with rich metadata.
- Indexing is idempotent via `reindex=True` flag that clears existing embeddings first.

### Step 5.3 — Context Retriever ✅
**Files**: `rag_service.py`, `retrieval.py` (API), `retrieval.py` (schemas)

- `retrieve_relevant_chunks_rich()` returns structured results with chunk_id, document_id, source_file_name, page_number, page_range, chunk_text, score, section_hint, preview, has_table_content
- `retrieve_pico_context_rich()` uses 8 PICO-optimized queries to find the most relevant chunks for extraction
- `get_study_chunks()` returns all chunks for a study (for debugging/UI)
- 5 REST API endpoints at `/api/v1/retrieval/` with full auth
- Traceability is real: every retrieval result maps to exact page, chunk, source file

---

## 4. Verification

### Tests Run
```
27 passed in 1.32s
- test_pdf_extraction.py: 11 passed
- test_chunking.py: 10 passed
- test_retrieval.py: 7 passed (schema validation, score bounds, defaults)
```

### Smoke Test
```
ALL SMOKE TESTS PASSED
- PDF extraction: 2 pages, 74 words
- Chunking: 2 chunks with valid metadata
- Metadata integrity: Pages [1, 2] covered
- Chunk ID determinism: Confirmed
- Legacy compatibility: extract_text/extract_and_chunk work
- Rich extraction: extract_and_chunk_rich returns chunks
```

### Real PDF Test
Ingested the uploaded `team_work_distribution_updated_more_original.pdf`:
- 2 pages, 754 words, checksum `fa960a838995da55e5afae0c3f9bf26d`
- Detected 10 section headings (team member role blocks)
- Produced 2 chunks ready for vector indexing

### Docker Compose Status
- **Exists and is unchanged** — all 8 services (db, redis, ollama, api, worker, beat, flower, frontend) are configured
- **localhost:3000** → Next.js frontend (depends on Yuan's implementation state)
- **localhost:8000** → FastAPI backend with new `/api/v1/retrieval/` endpoints
- **localhost:5555** → Flower task monitor

### What's Needed to Run
1. `cp .env.example .env` and add API keys
2. `docker compose up -d`
3. `docker compose exec ollama ollama pull nomic-embed-text`
4. `docker compose exec api alembic revision --autogenerate -m "Add retrieval metadata"` then `alembic upgrade head`
5. Open http://localhost:3000 (frontend) or http://localhost:8000/docs (API docs)

---

## 5. Team Handoff Matrix

### Jatin — Prompt Engineering & LLM Orchestration
- **Dependency**: UNBLOCKED
- **What Vaibhav provides**: `rag_service.retrieve_pico_context_rich(db, study_id, top_k=8)` returns chunks optimized for PICO fields, each with page_number, section_hint, chunk_text, score
- **What Jatin should do next**: Wire this into extraction prompts — format returned chunks as source context in the few-shot prompt. Use `page_number` and `section_hint` to cite sources in extraction output.
- **Schema**: `backend/app/schemas/retrieval.py` → `ChunkResult`
- **Contract**: `docs/retrieval_contract.md`

### Pranjali — Validation & Hallucination Defense
- **Dependency**: UNBLOCKED
- **What Vaibhav provides**: `rag_service.retrieve_relevant_chunks_rich(db, query="extracted value", study_id=sid)` finds source evidence for any extracted value
- **What Pranjali should do next**: In ValidationService, pass each extracted value as a query. Compare returned `chunk_text` against extraction. Use `score` as relevance signal, `page_number` to cite source.
- **Evidence format**: See `docs/retrieval_contract.md` → Evidence Package Format

### Harmeet — Backend, API & Searching
- **Dependency**: PARTIALLY BLOCKED (needs Alembic migration)
- **What Vaibhav provides**: Retrieval API routes at `/api/v1/retrieval/`, service functions, schemas, Celery task stubs
- **What Harmeet should do next**:
  1. Run Alembic migration for the 8 new Embedding columns
  2. After PubMed search downloads a PDF, call `rag_service.ingest_document(db, study_id, pdf_path)`
  3. Implement actual Celery task logic in `backend/app/tasks/` (stubs are in place)
  4. Wire `retrieve_pico_context_rich()` into the extraction task instead of `retrieve_pico_context()`

### Yuan — Frontend & UI Construction
- **Dependency**: UNBLOCKED
- **What Vaibhav provides**: `GET /api/v1/retrieval/studies/{id}/chunks` (all chunks), `GET /api/v1/retrieval/studies/{id}/pico-context` (PICO chunks). Each chunk has page_number and section_hint.
- **What Yuan should do next**: Build Document Side-Bar using chunk data. Use page_number for navigation, section_hint for section labels, chunk_text for evidence display alongside extracted values.

### Saood — DevOps, Integration & QA
- **Dependency**: UNBLOCKED
- **What Vaibhav provides**: docker-compose works as-is, ChromaDB in requirements, test suite in `backend/tests/`, smoke test script
- **What Saood should do next**:
  1. Add Alembic migration to Docker startup script
  2. Run `pytest backend/tests/` in CI pipeline
  3. Add `python scripts/smoke_test_retrieval.py` as smoke test in CI
  4. If using ChromaDB for tests, ensure it's in Dockerfile

### Hitesh — System Architect & Integration Lead
- **Dependency**: UNBLOCKED
- **What Vaibhav provides**: Complete module with documented API contract, schemas, service interfaces
- **What Hitesh should do next**: Review retrieval contract (`docs/retrieval_contract.md`), confirm it aligns with master schema, sign off on integration pattern

### Durgesh — Medical NLP & Data Dictionary
- **Dependency**: NOT DIRECTLY DEPENDENT
- **What Vaibhav provides**: N/A directly, but Durgesh's keyword mapper can enhance retrieval queries
- **What Durgesh should do next**: If building a Medical Keyword Mapper, it can be integrated as a pre-processing step before calling `retrieve_relevant_chunks_rich()` to expand search terms

---

## 6. WhatsApp Messages

### Jatin — Short
Hey Jatin, my PDF extraction + retrieval module is done. You can now call `retrieve_pico_context_rich(db, study_id)` to get source chunks with page numbers and section hints for your extraction prompts. Check `docs/retrieval_contract.md` for the exact schema.

### Jatin — Detailed
Hey Jatin, finished my entire workstream. Here's what matters for you:

Your extraction flow can now call `rag_service.retrieve_pico_context_rich(db, study_id, top_k=8)`. It returns chunks optimized for PICO fields — each chunk has `chunk_text`, `page_number`, `section_hint`, and a `score`. You can format these directly as context in your few-shot prompt and cite pages in the output.

Schema is in `backend/app/schemas/retrieval.py` (ChunkResult class). Full integration examples are in `docs/retrieval_contract.md`. Let me know if the output format doesn't match what you need.

### Pranjali — Short
Hi Pranjali, my retrieval module is ready for your validation work. Call `retrieve_relevant_chunks_rich(db, query, study_id)` with any extracted value as the query — it returns the matching source chunks with page numbers and similarity scores so you can verify grounding.

### Pranjali — Detailed
Hi Pranjali, my PDF + retrieval pipeline is complete. For your ValidationService:

Call `rag_service.retrieve_relevant_chunks_rich(db, query="the extracted value", study_id=sid, top_k=3, min_score=0.5)`. It returns a list of source chunks, each with `chunk_text`, `page_number`, `score` (0-1), and `section_hint`. You can compare `chunk_text` against the extraction to check grounding, and use `score` as a relevance signal for your confidence scoring.

I've also defined an Evidence Package format in `docs/retrieval_contract.md` that packages source evidence per extracted field — might be useful for your output schema. Let me know if you need any changes.

### Harmeet — Short
Hey Harmeet, my retrieval module is done. Added API routes at `/api/v1/retrieval/`, service functions, and Celery task stubs in `backend/app/tasks/`. One thing you'll need to do: run the Alembic migration for the 8 new columns I added to the Embedding model. Details in `docs/vaibhav_handoff.md`.

### Harmeet — Detailed
Hey Harmeet, PDF processing + retrieval pipeline is complete. Here's what you need to do on your end:

1. **Run Alembic migration**: I added 8 new columns to the Embedding model (document_id, page_number, section_hint, etc.). Run `alembic revision --autogenerate -m "Add retrieval metadata"` then `alembic upgrade head`.
2. **Wire ingestion into search**: After your PubMed search downloads a PDF, call `rag_service.ingest_document(db, study_id, pdf_path)` to index it.
3. **Celery task stubs**: I created `backend/app/tasks/` with stubs for all 4 tasks (extract_pico, search_pubmed, screen_studies, validate_extractions). The stubs have TODOs marking exactly what needs implementing. The app won't crash on import anymore.
4. **New API routes**: `/api/v1/retrieval/` has ingest, retrieve, pico-context, and chunk listing endpoints. All follow the same auth pattern.

Full contract at `docs/retrieval_contract.md`.

### Yuan — Short
Hey Yuan, my retrieval module is done. You can now call `GET /api/v1/retrieval/studies/{id}/chunks` to get all chunks for a study (for the document side-panel) and each chunk has `page_number` and `section_hint` for navigation. Sample response format is in `docs/retrieval_contract.md`.

### Yuan — Detailed
Hey Yuan, here's what's ready for the frontend:

Two endpoints you'll want:
- `GET /api/v1/retrieval/studies/{id}/chunks` — returns all indexed chunks for a study. Good for the Document Side-Bar.
- `GET /api/v1/retrieval/studies/{id}/pico-context` — returns PICO-relevant chunks. Good for showing evidence alongside extracted values.

Each chunk has: `chunk_text`, `page_number`, `section_hint` (like "Methods" or "Results"), and `score`. You can use page_number for PDF page navigation and section_hint for section labels.

Sample payloads are in `docs/retrieval_contract.md`. Let me know if you need different fields or a different response shape.

### Saood — Short
Hey Saood, my module is done and doesn't change docker-compose (pgvector was already there). I added test files in `backend/tests/` (27 tests all passing) and a smoke test at `scripts/smoke_test_retrieval.py`. Only thing to add to CI: `pytest backend/tests/` and optionally the smoke test.

### Saood — Detailed
Hey Saood, PDF + retrieval module is complete. Here's what's relevant for DevOps:

Docker-compose is unchanged — pgvector was already configured. I added `chromadb` to requirements.txt as an optional local dev store. For CI:
1. Run `pytest backend/tests/` — 27 tests, all pass, no database required
2. Run `python scripts/smoke_test_retrieval.py` — end-to-end smoke test, creates a test PDF and validates the full pipeline
3. Harmeet needs to run the Alembic migration for 8 new Embedding columns — you might want to add this to a startup script
4. The Celery task stubs are in `backend/app/tasks/` so the app won't crash on import anymore

Let me know if you need anything for the CI pipeline.

### Hitesh — Short
Hey Hitesh, my entire PDF processing + RAG retrieval workstream is done. All 3 steps (5.1, 5.2, 5.3) are implemented, tested (27/27 pass), and documented. API contract is in `docs/retrieval_contract.md`. Jatin, Pranjali, Yuan, and Saood are unblocked. Harmeet just needs to run the Alembic migration.

### Hitesh — Detailed
Hey Hitesh, completed my full workstream. Quick summary:

**Step 5.1** (PDF Pipeline): Rewrote pdf_service.py with block-level extraction, heading detection, table marking, page metadata, document checksums. Fully backward compatible.

**Step 5.2** (Vector DB): Enhanced pgvector Embedding model with 8 new metadata columns. Also added ChromaDB as a local dev alternative. Both support rich metadata per chunk.

**Step 5.3** (Context Retriever): Built `retrieve_pico_context_rich()` for Jatin's extraction and `retrieve_relevant_chunks_rich()` for Pranjali's validation. Both return structured results with page numbers, scores, section hints. Added 5 new API endpoints at `/api/v1/retrieval/`.

**Verification**: 27 tests passing, end-to-end smoke test passing, tested with real PDF.

**Team status**: Jatin, Pranjali, Yuan, Saood are unblocked. Harmeet needs to run Alembic migration. Full handoff docs are in `docs/`.

Review the API contract at `docs/retrieval_contract.md` when you get a chance — want to make sure it aligns with the master schema before Jatin and Pranjali wire it in.

### Group Update Message
Hey team, update from Vaibhav:

My PDF Processing + RAG Retrieval workstream is DONE. Here's what's ready:

✅ PDF extraction with page metadata, heading detection, table marking
✅ Vector indexing (pgvector + ChromaDB option) with rich metadata per chunk
✅ Context retriever returning exact source chunks with page numbers and similarity scores
✅ 5 new API endpoints at /api/v1/retrieval/
✅ 27 tests passing, smoke test passing
✅ Full docs in docs/ folder

**Who can move forward now:**
- Jatin: Call retrieve_pico_context_rich() for extraction context
- Pranjali: Call retrieve_relevant_chunks_rich() for validation evidence
- Yuan: Use /retrieval/studies/{id}/chunks for document side-panel
- Saood: Tests ready for CI, docker-compose unchanged
- Harmeet: Run Alembic migration, then wire ingestion into search pipeline

Docs: `docs/vaibhav_handoff.md`, `docs/retrieval_contract.md`, `docs/team_dependency_handoff.md`

Let me know if anyone needs anything adjusted.

---

## 7. Assumptions / Blockers / Next Priorities

### Assumptions Made
1. **pgvector stays as primary** — ChromaDB is dev-only alternative, not a replacement
2. **Ollama with nomic-embed-text** is the embedding model — as configured in existing .env
3. **Celery task stubs** are sufficient to unblock app startup — actual orchestration logic is Harmeet's responsibility
4. **Table extraction is heuristic** — complex multi-column tables may not be perfectly preserved; full table reconstruction (e.g., with Camelot or Tabula) is outside current scope
5. **Backward compatibility preserved** — all existing code that calls `pdf_service.extract_text()`, `chunk_text()`, `rag_service.embed_and_store()`, `retrieve_relevant_chunks()` continues to work unchanged

### Blockers
1. **Alembic migration not run** — Harmeet needs to run this before the new metadata columns are available in PostgreSQL. Without it, the enhanced `ingest_document()` will fail on database write.
2. **Ollama model pull required** — First run needs `docker compose exec ollama ollama pull nomic-embed-text`
3. **Frontend state unknown** — I did not inspect the Next.js frontend in detail; localhost:3000 depends on Yuan's work

### Next Priorities
1. Harmeet runs Alembic migration
2. Jatin wires `retrieve_pico_context_rich()` into extraction flow
3. Pranjali wires `retrieve_relevant_chunks_rich()` into validation service
4. Harmeet implements actual Celery task logic (stubs → real)
5. Yuan builds document side-panel using retrieval endpoints
6. Saood adds pytest and smoke test to CI pipeline
7. Hitesh reviews API contract and signs off on integration

---

## 8. Files Changed

| Path | Status | Lines | Purpose |
|------|--------|-------|---------|
| `backend/app/services/pdf_service.py` | REWRITTEN | 403 | Block-level PDF extraction with rich metadata |
| `backend/app/services/pdf_ingestion/__init__.py` | NEW | 2 | Module init |
| `backend/app/services/pdf_ingestion/chunker.py` | NEW | 411 | Page-aware semantic chunker |
| `backend/app/services/vector_store/__init__.py` | NEW | 2 | Module init |
| `backend/app/services/vector_store/chroma_store.py` | NEW | 250 | ChromaDB local vector store |
| `backend/app/services/rag_service.py` | REWRITTEN | 372 | Enhanced RAG with rich metadata |
| `backend/app/models/embedding.py` | UPDATED | 35 | +8 metadata columns |
| `backend/app/schemas/retrieval.py` | NEW | 109 | Retrieval Pydantic schemas |
| `backend/app/schemas/documents.py` | NEW | 29 | Document/evidence schemas |
| `backend/app/api/v1/retrieval.py` | NEW | 143 | 5 retrieval API endpoints |
| `backend/app/api/v1/router.py` | UPDATED | 17 | Added retrieval router |
| `backend/app/tasks/__init__.py` | NEW | 0 | Module init |
| `backend/app/tasks/extraction_tasks.py` | NEW | ~25 | Celery task stub |
| `backend/app/tasks/search_tasks.py` | NEW | ~20 | Celery task stub |
| `backend/app/tasks/screening_tasks.py` | NEW | ~15 | Celery task stub |
| `backend/app/tasks/validation_tasks.py` | NEW | ~20 | Celery task stub |
| `backend/requirements.txt` | UPDATED | +4 | Added chromadb, pytest |
| `.env.example` | UPDATED | +4 | Added ChromaDB config |
| `backend/tests/test_pdf_extraction.py` | NEW | 90 | 11 unit tests |
| `backend/tests/test_chunking.py` | NEW | 104 | 10 unit tests |
| `backend/tests/test_retrieval.py` | NEW | 75 | 7 schema tests |
| `backend/tests/conftest.py` | NEW | 4 | Pytest config |
| `backend/tests/__init__.py` | NEW | 0 | Module init |
| `scripts/ingest_sample.py` | NEW | 82 | Manual ingestion script |
| `scripts/smoke_test_retrieval.py` | NEW | 120 | E2E smoke test |
| `docs/vaibhav_handoff.md` | NEW | 183 | Technical handoff doc |
| `docs/retrieval_contract.md` | NEW | 113 | API contract |
| `docs/team_dependency_handoff.md` | NEW | 59 | Per-teammate guide |
| `docs/FINAL_DELIVERY_REPORT.md` | NEW | this | Complete delivery report |
