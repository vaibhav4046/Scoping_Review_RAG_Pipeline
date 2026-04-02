# Vaibhav's Workstream — Handoff Document

**Module**: PDF Processing & RAG (Retrieval-Augmented Generation)
**Owner**: Vaibhav Lalwani
**Status**: Implementation Complete
**Date**: April 2026

---

## What Was Built

### Step 5.1 — PDF-to-Text Pipeline
**File**: `backend/app/services/pdf_service.py`

A production-quality PDF extraction service using PyMuPDF with:
- Block-level extraction (`get_text("dict")`) for structure preservation
- Heading detection (bold text, font size analysis)
- Table region detection and marking
- Page-level metadata (page number, section hints, word count)
- Document-level metadata (UUID, checksum, timestamp, file path)
- Full backward compatibility with the original `extract_text()` and `chunk_text()` APIs

**Key method**: `pdf_service.extract_and_chunk_rich(pdf_path)` → returns `(DocumentExtraction, list[ChunkRecord])`

### Step 5.2 — Vector Database Indexing
**Files**:
- `backend/app/services/vector_store/chroma_store.py` — ChromaDB local store
- `backend/app/models/embedding.py` — Enhanced pgvector model with metadata
- `backend/app/services/rag_service.py` — Enhanced RAG service

Two vector store options:
1. **pgvector** (production) — PostgreSQL extension, used by default
2. **ChromaDB** (development) — File-based, no PostgreSQL required

Both store rich metadata per chunk: document_id, page_number, section_hint, source_file_name.

### Step 5.3 — Context Retriever
**Files**:
- `backend/app/services/rag_service.py` — Core retrieval logic
- `backend/app/api/v1/retrieval.py` — API endpoints
- `backend/app/schemas/retrieval.py` — Pydantic schemas

The retrieval service returns structured results with full provenance:
```json
{
    "chunk_id": "a1b2c3d4e5f67890",
    "document_id": "doc-uuid",
    "source_file_name": "study_123.pdf",
    "page_number": 3,
    "page_range": [3, 4],
    "chunk_text": "The intervention group received Drug X...",
    "score": 0.92,
    "section_hint": "Methods",
    "has_table_content": false
}
```

---

## API Endpoints Added

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/retrieval/health` | Retrieval subsystem health check |
| POST | `/api/v1/retrieval/ingest` | Ingest a PDF (extract + chunk + index) |
| POST | `/api/v1/retrieval/retrieve` | Retrieve relevant chunks for a query |
| GET | `/api/v1/retrieval/studies/{id}/pico-context` | PICO-optimized retrieval |
| GET | `/api/v1/retrieval/studies/{id}/chunks` | List all chunks for a study |

---

## How Teammates Should Use This

### Jatin (Extraction)
Call `retrieve_pico_context_rich(db, study_id)` to get PICO-optimized chunks before extraction.
Each chunk includes `page_number`, `section_hint`, and `chunk_text` that you can include in your extraction prompt as source context.

### Pranjali (Validation)
Call `retrieve_relevant_chunks_rich(db, query, study_id)` with the extracted value as the query.
Compare the returned `chunk_text` against the extraction to verify grounding. The `page_number` and `score` tell you exactly where the evidence comes from and how confident the match is.

### Harmeet (Backend)
The retrieval API routes are at `/api/v1/retrieval/`. They follow the same auth pattern as existing routes. After PubMed search downloads a PDF, call `rag_service.ingest_document(db, study_id, pdf_path)` to index it.

### Yuan (Frontend)
The `/retrieval/studies/{id}/chunks` endpoint gives you all indexed chunks for a study. The `/retrieval/studies/{id}/pico-context` endpoint gives the PICO-relevant chunks. You can use `page_number` and `section_hint` to build the document side-panel view.

### Saood (DevOps)
ChromaDB is added to requirements. The docker-compose already handles pgvector. For ChromaDB dev mode, set `VECTOR_STORE_BACKEND=chromadb` in .env. The data persists in `/app/data/chroma_db`.

---

## Schemas

### ChunkResult (retrieval output)
```python
class ChunkResult(BaseModel):
    chunk_id: str
    document_id: str
    source_file_name: str
    page_number: int
    page_range: list[int]
    chunk_index: int
    chunk_text: str
    score: float  # 0.0 to 1.0
    section_hint: str | None
    preview: str | None
    has_table_content: bool
```

### IngestResponse
```python
class IngestResponse(BaseModel):
    document_id: str
    source_file_name: str
    total_pages: int
    total_chunks: int
    chunks_indexed: int
    status: str  # "completed" | "warning" | "error"
    message: str
```

### RetrievalRequest
```python
class RetrievalRequest(BaseModel):
    query: str
    top_k: int = 5
    study_id: str | None = None
    min_score: float = 0.0
```

---

## Database Migration Required

The Embedding model has 8 new columns. Run Alembic migration:
```bash
cd backend
alembic revision --autogenerate -m "Add retrieval metadata to embeddings"
alembic upgrade head
```

New columns (all nullable for backward compat):
- `document_id` (String, indexed)
- `source_file_name` (String)
- `page_number` (Integer)
- `page_range` (String, JSON)
- `chunk_id` (String, unique, indexed)
- `section_hint` (String)
- `has_table_content` (Boolean)
- `char_count` (Integer)

---

## Files Changed/Created

| File | Status | Description |
|------|--------|-------------|
| `backend/app/services/pdf_service.py` | REWRITTEN | Rich PDF extraction with metadata |
| `backend/app/services/pdf_ingestion/__init__.py` | NEW | Chunker module init |
| `backend/app/services/pdf_ingestion/chunker.py` | NEW | Page-aware semantic chunker |
| `backend/app/services/vector_store/__init__.py` | NEW | Vector store module init |
| `backend/app/services/vector_store/chroma_store.py` | NEW | ChromaDB local store |
| `backend/app/services/rag_service.py` | REWRITTEN | Enhanced RAG with rich metadata |
| `backend/app/models/embedding.py` | UPDATED | Added 8 metadata columns |
| `backend/app/schemas/retrieval.py` | NEW | Retrieval Pydantic schemas |
| `backend/app/schemas/documents.py` | NEW | Document schemas |
| `backend/app/api/v1/retrieval.py` | NEW | Retrieval API endpoints |
| `backend/app/api/v1/router.py` | UPDATED | Added retrieval router |
| `backend/app/tasks/*.py` | NEW | Celery task stubs |
| `backend/tests/test_*.py` | NEW | Unit tests |
| `scripts/ingest_sample.py` | NEW | Manual ingestion script |
| `scripts/smoke_test_retrieval.py` | NEW | Smoke test script |
```

---

## Known Limitations

1. Table extraction is heuristic — complex multi-column tables may not be perfectly preserved
2. ChromaDB store is for dev only — production should use pgvector
3. Embedding generation requires Ollama running with `nomic-embed-text` model
4. Celery tasks are stubs — actual orchestration depends on Harmeet's implementation
