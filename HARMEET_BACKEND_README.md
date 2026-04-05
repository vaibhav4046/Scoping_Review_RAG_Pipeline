# Harmeet — Backend, API & Search: Implementation Notes

## What was done

### 1. `backend/app/tasks/search_tasks.py` — Full implementation (was a STUB)

This is the core Celery task that drives the entire ingestion pipeline.

**Pipeline steps inside `search_pubmed` task:**

| Step | What happens |
|------|-------------|
| 0 | Set `review.status = "searching"` |
| 1 | Create / update `TaskLog` row so frontend can poll progress |
| 2 | Call `pubmed_service.search()` — gets PMIDs via E-utilities esearch |
| 3 | Call `pubmed_service.fetch_details()` — efetch metadata in batches of 200 |
| 4 | Upsert `Study` rows into DB (skips duplicates by PMID) |
| 5 | For every study with a PMCID, attempt open-access PDF download |
| 6 | For every downloaded PDF → call `rag_service.ingest_document()` (Vaibhav's pipeline) |
| 7 | Update `TaskLog.progress` (0→1) throughout; set `review.status = "searching_complete"` |

**Key design decisions:**
- **Duplicate-safe**: `_upsert_study()` checks for existing PMID before inserting
- **Fail-tolerant**: PDF/RAG failures don't abort the whole task — paper is still saved
- **Retry-safe**: Celery `bind=True` with `max_retries=3`, retries on PubMed API failures
- **Async in sync worker**: `_run()` helper creates an event loop for async DB/HTTP calls

---

### 2. `backend/alembic/versions/0001_initial_schema.py` — Initial DB migration

Creates all 8 tables from scratch including Vaibhav's retrieval metadata columns on `embeddings`:

- `users`, `reviews`, `studies`, `task_logs`
- `screenings`, `extractions`, `validations`
- `embeddings` (with pgvector, `page_number`, `section_hint`, `source_file_name`, `document_id`)

---

## How to run (once Docker is up)

```bash
# 1. Copy .env into place (fill in your API keys first)
cp .env.example .env

# 2. Start all services
docker compose up -d

# 3. Run the Alembic migration (Vaibhav's crucial first step)
docker compose exec api alembic upgrade head

# 4. Pull Ollama embedding model
docker compose exec ollama ollama pull nomic-embed-text

# 5. Access the system
# Frontend:  http://localhost:3000
# API docs:  http://localhost:8000/docs
# Flower:    http://localhost:5555   (Celery task monitor)
```

---

## Integration points with teammates

| Teammate | How my code connects to theirs |
|----------|-------------------------------|
| **Vaibhav** | After every PDF download I call `rag_service.ingest_document(db, study_id, pdf_path)` — this triggers his chunker + embedder |
| **Jatin** | My task saves `Study` rows with `extraction_status="pending"`. His extraction task reads these rows |
| **Pranjali** | Her validation task reads `Study` rows I've saved; she also calls Vaibhav's `retrieve_relevant_chunks_rich()` |
| **Saood** | The `docker-compose.yml` and Alembic migration are both ready for CI/CD integration |

---

## Files I own

```
backend/app/tasks/search_tasks.py          ← Main implementation (was STUB)
backend/alembic/versions/0001_initial_schema.py  ← DB migration
```

## Files I depend on (do not modify without coordinating)

```
backend/app/services/pubmed_service.py     ← Hitesh / existing
backend/app/services/rag_service.py        ← Vaibhav
backend/app/models/study.py               ← Hitesh / existing
backend/app/models/task_log.py            ← Hitesh / existing
```
