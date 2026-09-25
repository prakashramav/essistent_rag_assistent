# Enterprise RAG Assistant

A production-grade, multi-tenant SaaS Retrieval-Augmented Generation (RAG) platform. Enables organizations to ingest enterprise knowledge documents (PDF, DOCX, TXT, web sources) and query them through an AI assistant with strictly cited, grounded answers, multi-tenant data isolation, role-based access control (RBAC), an LLM-as-a-judge evaluation harness, and production observability.

---

## Key Features

- **Multi-Tenant Data Isolation & RBAC**: Strict organization scoping at the database level (`organization_id` foreign key on every entity). Role-based privileges (`Admin`, `Member`, `Viewer`) enforced on all API endpoints.
- **Document Ingestion Pipeline**: Ingest PDF, DOCX, TXT, and live web pages. Recursive text chunking (1000 characters, 200 overlap) with metadata preservation (page numbers, section headings, token counts).
- **Hybrid Retrieval Engine**:
  - Dense semantic search using PostgreSQL `pgvector` (Cosine distance `<=>`) with 768-dimensional embeddings.
  - Sparse lexical search using PostgreSQL Full-Text Search (`tsvector` / `ts_rank_cd`).
  - Reciprocal Rank Fusion (RRF, $k=60$) combining dense and sparse candidate sets.
  - Cross-encoder / heuristic reranking to filter false positives.
- **Grounded Generation & Citation Discipline**: Strict anti-hallucination system prompt requiring bracketed citations (`[Doc Title, p. X]`). Only claims supported by retrieved context are answered.
- **Real-Time Streaming UX (SSE)**: Token-by-token streaming via Server-Sent Events with progress phases (`retrieval_status`, `sources`, `delta`, `done`).
- **Interactive Web Client**: Next.js 16 (App Router, plain JavaScript, Tailwind CSS) featuring a conversation sidebar, interactive citation inspection modals, grounded source drawers, and RBAC team management.
- **Evaluation Harness & LLM-as-a-Judge**:
  - Automated retrieval metrics: Precision@K, Recall@K, Mean Reciprocal Rank (MRR), Hit Rate@K.
  - LLM-as-a-Judge RAG Triad: Groundedness / Faithfulness (atomic claim verification against source context) and Answer Relevance.
  - Synthetic benchmark dataset generation from ingested chunks with regression run tracking.
- **Observability & Production Hardening**:
  - Structured JSON logging with distributed `X-Trace-ID` and `X-Request-ID` context propagation.
  - Native Prometheus scraping metrics endpoint (`/api/v1/metrics`) tracking HTTP request counts, latency histograms, and process uptime.
  - Distributed Redis sliding-window tenant rate limiting (`ZADD`/`ZCARD`) with automatic in-memory fallback.
  - Subsystem health and latency diagnostics (`/api/v1/health/diagnostics`).

---

## Architecture Overview

```mermaid
flowchart TB
    subgraph ClientLayer["Frontend Client (Next.js 16 / App Router)"]
        UI["Tailwind CSS UI & Dashboard"]
        ChatUI["Streaming Chat & Citation Modal"]
        EvalUI["Evaluation & Benchmark Harness"]
        ObsUI["Observability & Telemetry View"]
        APIClient["REST + SSE Streaming Client"]
    end

    subgraph GatewayLayer["API & Security Boundary"]
        FastAPI["FastAPI 0.111 (Python 3.11+)"]
        MW["Observability & Rate Limiting Middleware\n(Trace ID, Prometheus, Rate Limiter)"]
        JWT["JWT Auth & Org-Scoped RBAC\n(Admin / Member / Viewer)"]
    end

    subgraph ServiceLayer["Backend Core & Pipelines"]
        AuthSvc["Auth & Organization Service"]
        IngestSvc["Document Ingestion\n(Parse, Chunk, Embed)"]
        Retriever["Hybrid Retrieval Engine\n(pgvector + FTS tsvector + RRF)"]
        Reranker["Cross-Encoder Reranking"]
        RAGSvc["Generation & Grounded Citations\n(Gemini 1.5 Pro / Flash)"]
        EvalSvc["Evaluation & LLM-as-a-Judge\n(Precision@K, MRR, Faithfulness)"]
    end

    subgraph StorageLayer["Data & Persistence"]
        PG[("PostgreSQL 16 + pgvector")]
        RedisDB[("Redis 7 (Rate Limiter & Cache)")]
    end

    UI --> APIClient
    ChatUI --> APIClient
    EvalUI --> APIClient
    ObsUI --> APIClient
    APIClient -->|REST + SSE| MW
    MW --> FastAPI
    FastAPI --> JWT
    JWT --> AuthSvc
    FastAPI --> IngestSvc
    FastAPI --> Retriever
    FastAPI --> RAGSvc
    FastAPI --> EvalSvc
    Retriever --> PG
    IngestSvc --> PG
    MW --> RedisDB
    Retriever --> Reranker
    Reranker --> RAGSvc
    RAGSvc -->|SSE Stream + Structured Citations| APIClient
```

---

## Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | Next.js 16 (App Router), React, JavaScript (ES6+), Tailwind CSS, Lucide Icons |
| **Backend** | FastAPI, Python 3.11+, Pydantic v2, Starlette Middleware |
| **Database & ORM**| PostgreSQL 16 with `pgvector` extension, SQLAlchemy 2.0 (async), Alembic |
| **Embeddings & LLM**| Google Gemini (`text-embedding-004`, `gemini-1.5-pro` / `gemini-2.0-flash`) via adapter with deterministic offline fallback |
| **Caching & Rate Limit**| Redis 7 (sliding window sorted sets `ZSET`) with in-memory fallback |
| **Document Processing**| `pypdf`, `python-docx`, `beautifulsoup4` |
| **Testing** | `pytest`, `pytest-asyncio`, `httpx` (24 automated tests passing) |
| **Containers** | Docker & Docker Compose |

---

## Quickstart & Setup

### Prerequisites
- [Docker & Docker Compose](https://www.docker.com/) installed and running
- Python 3.11+ (optional, for running tests and local scripts)
- Node.js 20+ (optional, for standalone frontend development)

### 1. Clone & Configure Environment
Create a `.env` file in the project root (or inside `backend/`):

```bash
# Security
SECRET_KEY=supersecret_enterprise_rag_jwt_key_change_in_production_32bytes
ENVIRONMENT=development

# Database & Cache (Docker service names)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/enterprise_rag
SYNC_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5433/enterprise_rag
REDIS_URL=redis://localhost:6380/0

# AI Provider Keys (Optional: works offline with deterministic fallback if unset)
GEMINI_API_KEY=
OPENAI_API_KEY=
```

### 2. Launch with Docker Compose
Start all four containers (PostgreSQL + pgvector, Redis, FastAPI Backend, Next.js Frontend):

```bash
docker compose up -d --build
```

### 3. Exposed Services & Endpoints
| Service | URL | Description |
|---|---|---|
| **Frontend Web App** | [http://localhost:3000](http://localhost:3000) | Multi-tenant web dashboard & chat |
| **API Documentation** | [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs) | Interactive Swagger / OpenAPI UI |
| **Prometheus Metrics**| [http://localhost:8000/api/v1/metrics](http://localhost:8000/api/v1/metrics) | Scrape metrics for Grafana / Datadog |
| **System Diagnostics**| [http://localhost:8000/api/v1/health/diagnostics](http://localhost:8000/api/v1/health/diagnostics) | Subsystem health, latencies, pgvector version |
| **PostgreSQL Database** | `localhost:5433` | Database with `pgvector` enabled |
| **Redis Cache** | `localhost:6380` | Cache and sliding window rate limiter |

### 4. Default Seeded Credentials
When the database bootstraps, you can sign in immediately:
- **Email**: `admin@acme.com`
- **Password**: `SuperPassword123!`
- **Organization**: `Acme Global` (Role: `admin`)

---

## Development & Local Testing

### Backend Virtual Environment Setup
```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate   # Windows (source venv/bin/activate on Linux/macOS)
pip install -r requirements.txt
```

### Running the Full Test Suite
The automated test suite covers all 7 phases:

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest tests/ -v
```

**Test Suite Coverage (24 Passed in ~16s)**:
- `tests/test_auth.py` (6 tests): Signup, email duplication rejection, login, token rotation, `/auth/me`.
- `tests/test_chat.py` (3 tests): Conversation CRUD, RAG generation with citations, SSE stream.
- `tests/test_evaluation.py` (3 tests): Retrieval metrics (Precision@K, Recall@K, MRR), single query audit, benchmark suite.
- `tests/test_ingestion.py` (5 tests): TXT parser, recursive chunker, embedding adapter, document upload lifecycle, tenant isolation.
- `tests/test_observability.py` (4 tests): `X-Trace-ID` propagation, Prometheus `/metrics`, rate-limiter 429 enforcement, diagnostics endpoint.
- `tests/test_rbac.py` (1 test): Cross-tenant isolation assertions and role privilege checks.
- `tests/test_retrieval.py` (2 tests): Hybrid search (dense + sparse + RRF) and metadata filtering.

### Database Migrations (Alembic)
Migrations run automatically on container startup. To inspect or manage migrations manually:

```powershell
cd backend
alembic upgrade head
alembic revision --autogenerate -m "migration_description"
```

---

## API Reference Overview

### Authentication & RBAC (`/api/v1/auth`, `/api/v1/organizations`)
- `POST /api/v1/auth/signup`: Register user and bootstrap organization with Admin role.
- `POST /api/v1/auth/login`: Authenticate and receive JWT access and refresh tokens.
- `POST /api/v1/auth/refresh`: Rotate refresh token for a new token pair.
- `GET /api/v1/auth/me`: Get authenticated user profile, active tenant, and memberships.
- `POST /api/v1/organizations/{id}/members`: Invite team member with specific role (`admin`, `member`, `viewer`).

### Document Ingestion (`/api/v1/documents`)
- `POST /api/v1/documents/upload`: Upload PDF, DOCX, or TXT file for chunking and embedding.
- `POST /api/v1/documents/url`: Crawl and ingest web page content.
- `GET /api/v1/documents`: List organization documents with status (`pending`, `processing`, `completed`, `failed`).
- `GET /api/v1/documents/{id}/chunks`: Inspect chunks, token counts, headings, and page numbers.
- `DELETE /api/v1/documents/{id}`: Delete document and cascade chunks from vector store.

### Hybrid Retrieval & Chat (`/api/v1/retrieval`, `/api/v1/chat`)
- `POST /api/v1/retrieval/search`: Hybrid search combining pgvector cosine distance, `tsvector` FTS, and RRF.
- `GET /api/v1/chat/conversations`: List tenant conversations.
- `POST /api/v1/chat/conversations`: Create conversation thread.
- `POST /api/v1/chat/conversations/{id}/messages`: Non-streaming query generation with cited sources.
- `POST /api/v1/chat/conversations/{id}/messages/stream`: Server-Sent Events (SSE) streaming endpoint.

### Evaluation & Benchmarks (`/api/v1/evaluation`)
- `POST /api/v1/evaluation/single`: Live query auditor evaluating Faithfulness and Answer Relevance.
- `POST /api/v1/evaluation/run`: Execute automated benchmark test suite against ingested chunks.
- `GET /api/v1/evaluation/runs`: Retrieve historical benchmark runs and aggregate metrics.

### Observability & Health (`/api/v1/health`, `/api/v1/metrics`)
- `GET /api/v1/health`: Basic liveness check and database ping.
- `GET /api/v1/health/diagnostics`: Detailed subsystem report (PostgreSQL + pgvector version, Redis cache latency, AI providers).
- `GET /api/v1/metrics`: Standard Prometheus OpenMetrics endpoint.

---

## Phase Roadmap & Implementation Status

- [x] **Phase 1: Foundation**
  - FastAPI async project structure, Next.js 16 frontend, SQLAlchemy 2.0 async models.
  - PostgreSQL 16 + `pgvector` container, Redis 7 container, Docker Compose setup.
  - JWT authentication with access/refresh token rotation.
  - Organization-scoped multi-tenancy and RBAC (`Admin`, `Member`, `Viewer`).
- [x] **Phase 2: Document Ingestion Pipeline**
  - Parsers for PDF (`pypdf`), DOCX (`python-docx`), TXT, and Web URLs (`beautifulsoup4`).
  - Recursive chunker preserving page numbers, section titles, and token counts.
  - Gemini `text-embedding-004` (768-dim) adapter with offline deterministic fallback.
  - Ingestion hub tracking async task states and Chunk Inspection UI.
- [x] **Phase 3: Hybrid Retrieval Engine**
  - Dense semantic search using `pgvector` (`<=>` cosine distance).
  - Sparse lexical search using PostgreSQL `tsvector` with `ts_rank_cd`.
  - Reciprocal Rank Fusion (RRF, $k=60$) combining candidate sets.
  - Metadata filtering by document ID and tags, plus cross-encoder reranking.
  - Interactive Hybrid Search Explorer dashboard tab.
- [x] **Phase 4: RAG Generation & Grounding**
  - Strict anti-hallucination system prompt requiring exact citations.
  - Conversation memory sliding window (last $N$ turns).
  - Server-Sent Events (SSE) streaming endpoint delivering `retrieval_status`, `sources`, and `delta` tokens.
- [x] **Phase 5: Full UI Experience**
  - Conversation management sidebar (create, rename, delete chats).
  - Token-by-token streaming chat interface with phase indicators.
  - Clickable citation badges opening a detailed Citation Inspector Modal.
  - Grounded sources drawer and Team / RBAC management console.
- [x] **Phase 6: Evaluation Harness & LLM-as-a-Judge**
  - Automated retrieval metrics: Precision@K, Recall@K, MRR, HitRate@K.
  - LLM-as-a-Judge RAG Triad: Groundedness / Faithfulness (atomic claim decomposition) and Answer Relevance.
  - Synthetic benchmark dataset generation from ingested chunks.
  - Evaluation Dashboard UI with KPI cards, live query auditor, and benchmark run history.
- [x] **Phase 7: Observability & Production Hardening**
  - Distributed `X-Trace-ID` and `X-Request-ID` correlation in structured JSON logs.
  - Prometheus metrics registry (`/api/v1/metrics`) tracking requests, latencies, and uptime.
  - Redis sliding window rate-limiting (`ZADD`/`ZCARD`) with in-memory fallback.
  - Deep subsystem diagnostics endpoint (`/api/v1/health/diagnostics`).
  - Observability & Telemetry dashboard tab in UI with live auto-refresh.

---

## License

This project is licensed under the MIT License.
