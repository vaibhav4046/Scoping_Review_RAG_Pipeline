# Scoping Review AI — Large Text AI Analysis Platform

A production-grade system for automating scoping reviews using LLMs with **zero hallucination tolerance**.

## Architecture

```
Frontend (Next.js :3000) → Backend (FastAPI :8000) → PostgreSQL+pgvector + Redis
                                    ↓
                           Celery Workers (search, screen, extract, validate)
                                    ↓
                           LLMs (Ollama | Gemini | Groq)
```

## Pipeline

```
Search (PubMed) → Screen (LLM) → Retrieve (RAG) → Extract (PICO) → Validate (Cross-LLM) → Store → Display
```

## Quick Start

### 1. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys:
#   GEMINI_API_KEY=...
#   GROQ_API_KEY=...
```

### 2. Launch with Docker Compose

```bash
docker compose up -d
```

This starts 8 services:
- **API** (FastAPI): http://localhost:8000
- **Frontend** (Next.js): http://localhost:3000
- **Flower** (Task Monitor): http://localhost:5555
- **PostgreSQL** + pgvector: localhost:5432
- **Redis**: localhost:6379
- **Ollama**: localhost:11434
- **Celery Worker** + **Beat**

### 3. Default Login

```
Email: admin@scopingreview.local
Password: changeme123
```

### 4. Pull Ollama Embedding Model

```bash
docker compose exec ollama ollama pull nomic-embed-text
```

## Features

### Zero-Hallucination Extraction
- All extracted values require source quotes from the original text
- Values without textual evidence are automatically set to "Not Reported"
- Post-extraction grounding validation rejects ungrounded claims

### Cross-LLM Validation
- Primary model (Gemini) extracts PICO data
- Validator model (Groq/Llama) independently re-extracts
- Field-by-field comparison generates agreement scores
- Discrepancies flagged for human review

### PICO Schema
```json
{
  "population": "...",
  "intervention": "...",
  "comparator": "...",
  "outcome": "...",
  "study_design": "...",
  "sample_size": "...",
  "confidence_scores": {"population": 0.95, ...},
  "source_quotes": {"population": "exact quote...", ...}
}
```

### PDF Processing
- Auto-download from PubMed Central (open access)
- Manual PDF upload via UI
- PyMuPDF text extraction → chunking → embedding → pgvector

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Register |
| POST | `/api/v1/auth/login` | Login (JWT) |
| POST | `/api/v1/reviews` | Create review |
| POST | `/api/v1/reviews/{id}/search` | PubMed search |
| POST | `/api/v1/reviews/{id}/screen` | LLM screening |
| POST | `/api/v1/reviews/{id}/extract` | PICO extraction |
| POST | `/api/v1/reviews/{id}/validate` | Cross-validation |
| GET | `/api/v1/reviews/{id}/export` | Export CSV/JSON |

Full API docs: http://localhost:8000/docs

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, TypeScript, Vanilla CSS |
| Backend | FastAPI, SQLAlchemy 2.0, Pydantic v2 |
| Database | PostgreSQL 16 + pgvector |
| Queue | Celery 5.4 + Redis 7 |
| LLMs | Ollama (local), Google Gemini, Groq |
| PDF | PyMuPDF |
| Container | Docker Compose |

## Development

```bash
# Backend only
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend only
cd frontend
npm install
npm run dev
```

## License

Private — for research use only.
