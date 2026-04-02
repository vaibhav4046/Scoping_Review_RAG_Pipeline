# Retrieval Contract — API & Service Interface

## Service Interface (Python)

### Ingest a document
```python
from app.services.rag_service import rag_service

result = await rag_service.ingest_document(
    db=session,
    study_id="study-uuid",
    pdf_path="/app/uploads/review-1/study-1.pdf",
    reindex=False,
)
# Returns: {"document_id": "...", "total_pages": 5, "chunks_indexed": 23, "status": "completed"}
```

### Retrieve context for extraction (Jatin)
```python
result = await rag_service.retrieve_pico_context_rich(
    db=session,
    study_id="study-uuid",
    top_k=8,
)
# Returns dict with:
# - context_chunks: list of ChunkResult dicts with page_number, chunk_text, score, section_hint
# - pico_queries_used: list of queries used
# - total_chunks_available: int
```

### Retrieve context for validation (Pranjali)
```python
chunks = await rag_service.retrieve_relevant_chunks_rich(
    db=session,
    query="survival rate 85%",
    study_id="study-uuid",
    top_k=3,
    min_score=0.5,
)
# Returns list of dicts, each with:
# - chunk_text, page_number, score, chunk_id, section_hint, source_file_name
```

### Get all chunks for display (Yuan)
```python
data = await rag_service.get_study_chunks(db=session, study_id="study-uuid")
# Returns dict with document_id, source_file_name, total_chunks, chunks (list)
```

## REST API

### POST /api/v1/retrieval/ingest
```json
// Request
{"study_id": "uuid", "reindex": false}

// Response
{"document_id": "uuid", "source_file_name": "study.pdf", "total_pages": 5, "total_chunks": 23, "chunks_indexed": 23, "status": "completed"}
```

### POST /api/v1/retrieval/retrieve
```json
// Request
{"query": "intervention treatment drug", "top_k": 5, "study_id": "uuid", "min_score": 0.3}

// Response
{
  "query": "intervention treatment drug",
  "results": [
    {
      "chunk_id": "a1b2c3d4",
      "document_id": "doc-uuid",
      "source_file_name": "study.pdf",
      "page_number": 2,
      "chunk_text": "The intervention group received...",
      "score": 0.92,
      "section_hint": "Methods"
    }
  ],
  "total_results": 5,
  "retrieval_time_ms": 45.2
}
```

### GET /api/v1/retrieval/studies/{study_id}/pico-context
```json
// Response
{
  "study_id": "uuid",
  "source_file_name": "study.pdf",
  "context_chunks": [...],
  "total_chunks_available": 23,
  "pico_queries_used": ["population...", "intervention...", ...]
}
```

## Evidence Package Format (for Pranjali)
```json
{
  "extracted_value": "85% survival rate",
  "field_name": "outcome",
  "source_chunks": [
    {
      "chunk_text": "Survival rate was 85% in the intervention group...",
      "page_number": 4,
      "score": 0.95,
      "section_hint": "Results"
    }
  ],
  "page_references": [4],
  "confidence_note": "Direct quote match with high similarity"
}
```
