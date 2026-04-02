# Team Dependency Handoff — From Vaibhav's Module

## Dependency Matrix

| Teammate | Dependency Status | What Vaibhav Provides | Their Next Step |
|----------|-------------------|----------------------|-----------------|
| Jatin | **UNBLOCKED** | PICO context retrieval with page refs | Wire `retrieve_pico_context_rich()` into extraction prompts |
| Pranjali | **UNBLOCKED** | Source chunk evidence with scores | Wire `retrieve_relevant_chunks_rich()` into validation service |
| Harmeet | **PARTIALLY BLOCKED** | Retrieval API routes, service contracts | Run Alembic migration, wire ingestion into search pipeline |
| Yuan | **UNBLOCKED** | Chunk listing API, evidence data format | Build document side-panel using chunk/page data |
| Saood | **UNBLOCKED** | docker-compose works, ChromaDB added | Add Alembic migration to startup, add smoke tests to CI |
| Hitesh | **UNBLOCKED** | Module complete, API contract defined | Review integration, finalize master schema |
| Durgesh | **NOT DIRECTLY DEPENDENT** | N/A | Keyword mapper can be used to enhance retrieval queries |

## Detailed Handoff per Teammate

### Jatin — Extraction
- **Status**: Can start immediately
- **What's ready**: `rag_service.retrieve_pico_context_rich(db, study_id, top_k=8)` returns chunks optimized for PICO fields
- **Each chunk includes**: text, page_number, section_hint, score
- **Integration point**: In your extraction flow, call this method and format the chunks as context in your few-shot prompt
- **Schema**: See `backend/app/schemas/retrieval.py` → `ChunkResult`

### Pranjali — Validation
- **Status**: Can start immediately
- **What's ready**: `rag_service.retrieve_relevant_chunks_rich(db, query, study_id)` finds the source evidence for any extracted value
- **Usage**: Pass the extracted value as `query` to find the supporting text. Compare `chunk_text` with the extraction. Use `score` as a relevance signal.
- **Evidence format**: See `docs/retrieval_contract.md` → Evidence Package Format

### Harmeet — Backend
- **Status**: Needs migration step
- **What's ready**: API routes at `/api/v1/retrieval/`, service functions, schemas
- **Action needed**:
  1. Run `alembic revision --autogenerate -m "Add retrieval metadata"` then `alembic upgrade head`
  2. In your search pipeline, after downloading a PDF, call `rag_service.ingest_document(db, study_id, pdf_path)`
  3. Update Celery extraction task to use `retrieve_pico_context_rich()` instead of `retrieve_pico_context()`
- **Celery task stubs**: `backend/app/tasks/` — fill in the actual orchestration logic

### Yuan — Frontend
- **Status**: Can start building UI
- **What's ready**:
  - `GET /api/v1/retrieval/studies/{id}/chunks` — all chunks for document side-panel
  - `GET /api/v1/retrieval/studies/{id}/pico-context` — PICO-relevant chunks
  - Each chunk has `page_number` and `section_hint` for navigation
- **Sample payload**: See `docs/retrieval_contract.md`

### Saood — DevOps
- **Status**: Can proceed with CI/CD
- **What's ready**: docker-compose unchanged (pgvector already there), ChromaDB in requirements, test files in `backend/tests/`
- **Action needed**:
  1. Add `pip install chromadb` to Docker image if using ChromaDB for tests
  2. Add Alembic migration to docker startup script
  3. Run `pytest backend/tests/` in CI pipeline
  4. Smoke test: `python scripts/smoke_test_retrieval.py`

### Hitesh — Integration
- **Status**: Can review
- **What's ready**: Full API contract documented, service interfaces defined, module complete
- **Action needed**: Review the retrieval contract, confirm it meets the master schema requirements, sign off on the integration pattern
