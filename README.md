# RAG-Powered CRM Platform

> **CS510 Final Project** — submitted for the CS510 course final project.

A multi-service CRM and lead-generation platform with AI-powered email generation,
analytics insights, RAG retrieval, two-pager reports, and CSV column mapping.

The repository is a monorepo of three Python (FastAPI) backend services, one
Next.js frontend, and two shared Python libraries.

---

## Architecture

```
rag-powered-crm/
├── crm/             FastAPI service · port 8003 · CRM, deals, RAG, AI emails, Temporal
├── leadgen/         FastAPI service · port 9000 · lead gen, scraping, ImportYeti, two-pager
├── user-settings/   FastAPI service · port 8005 · invitations, profiles, OAuth, ingestion
├── frontend-next/   Next.js 16 app  · port 8000 · proxies /api/proxy/* → backend services
├── shared/          Python lib `service_core` + `email_core` (pool, auth, email core)
└── csv/             Python lib `csv_mapping` (AI-powered CSV→DB column mapping)
```

The frontend talks to backends through Next.js route handlers under
`app/api/proxy/{crm,leads,settings}/...` (see `frontend-next/lib/api/proxy.ts`),
which forward authenticated requests to the corresponding FastAPI service.

---

## Prerequisites

- **Python 3.11+** (Dockerfiles use 3.12)
- **Node.js 20+** and npm
- **PostgreSQL 14+** (multiple databases — see *Databases* below)
- **Redis 6+** (used by `leadgen` for caching; optional but recommended)
- **Temporal** (optional — only needed if you enable workers in `crm`)
- API keys: OpenAI, Google Gemini, optionally Anthropic, Cohere, SendGrid

---

## 1. Install backend dependencies

For each Python service, create a venv and install:

```bash
# CRM service
cd crm
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
deactivate && cd ..

# Lead-generation service
cd leadgen
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium          # leadgen scrapes via Playwright
deactivate && cd ..

# User-settings service
cd user-settings
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
deactivate && cd ..
```

`-e ../shared` and `-e ../csv` install the two local libraries in editable mode,
so changes there are picked up by all services without re-installing.

## 2. Install the frontend

```bash
cd frontend-next
npm install
```

---

## 3. Environment variables

Each service reads a local `.env` file (via `python-dotenv`). Create one in
each backend folder and one (`.env.local`) in `frontend-next/`.

### `crm/.env`
```bash
# Required
JWT_SECRET=replace-me-with-a-long-random-string
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# Database (Postgres) — required
SESSIONS_DB_HOST=localhost
SESSIONS_DB_PORT=5432
SESSIONS_DB_NAME=prelude_sessions
SESSIONS_DB_USER=postgres
SESSIONS_DB_PASSWORD=...
MANAGEMENT_DB_HOST=localhost
MANAGEMENT_DB_PORT=5432
MANAGEMENT_DB_NAME=prelude_management
MANAGEMENT_DB_USER=postgres
MANAGEMENT_DB_PASSWORD=...

# AI providers — at least one
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
ANTHROPIC_API_KEY=...
COHERE_API_KEY=...                   # for RAG reranking

# Optional integrations
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
MICROSOFT_TENANT_ID=common
SENDGRID_API_KEY=
TRACKING_BASE_URL=http://localhost:8003
USER_SETTINGS_URL=http://localhost:8005

# Temporal (off by default — leave unset to disable workers)
# TEMPORAL_HOST=...
# TEMPORAL_NAMESPACE=...
# ENABLE_TEMPORAL_SCHEDULER_WORKER=false
# ENABLE_TEMPORAL_MASS_EMAIL_WORKER=false
```

### `leadgen/.env`
```bash
JWT_SECRET=same-as-crm
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
OPENAI_API_KEY=sk-...
GOOGLE_MAPS_API_KEY=...
PERPLEXITY_API_KEY=...                # optional

# Redis (caching)
REDIS_HOST=localhost
REDIS_PORT=6379

# Playwright (scraping) — keep headless in dev
PLAYWRIGHT_HEADLESS=true
```

### `user-settings/.env`
```bash
JWT_SECRET=same-as-crm
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
MICROSOFT_TENANT_ID=common
OPENAI_API_KEY=sk-...

# Postgres for user_profiles + analytics
DATABASE_URL=postgresql://postgres:...@localhost:5432/prelude_user_analytics
```

### `frontend-next/.env.local`
```bash
NEXT_PUBLIC_CRM_API_URL=http://localhost:8003
NEXT_PUBLIC_BACKEND_LEAD_API_URL=http://localhost:9000
NEXT_PUBLIC_USER_SETTINGS_API_URL=http://localhost:8005
NEXT_PUBLIC_ONE_PAGER_ENABLED=true
```

> All three services should share the **same `JWT_SECRET`** so tokens issued by
> one service validate in the others.

---

## 4. Databases

`user-settings` ships Alembic migrations for two databases. Run them after
creating the DBs in Postgres:

```bash
cd user-settings
source .venv/bin/activate
alembic -c alembic_postgres/alembic.ini  upgrade head    # main app DB
alembic -c alembic_analytics/alembic.ini upgrade head    # analytics DB
```

The `crm` and `leadgen` services connect to the same Postgres cluster via the
`SESSIONS_DB_*` / `MANAGEMENT_DB_*` env vars; create those databases manually
if they don't yet exist.

---

## 5. Run everything

Open four terminals (or use `tmux` / a process manager).

```bash
# Terminal 1 — CRM (port 8003)
cd crm && source .venv/bin/activate && python main.py

# Terminal 2 — Lead generation (port 9000)
cd leadgen && source .venv/bin/activate && python main.py

# Terminal 3 — User settings (port 8005)
cd user-settings && source .venv/bin/activate && python main.py

# Terminal 4 — Frontend (port 8000)
cd frontend-next && npm run dev
```

Then visit:

| URL                                | Purpose                          |
| ---------------------------------- | -------------------------------- |
| http://localhost:8000              | Frontend application             |
| http://localhost:8003/docs         | CRM API (Swagger)                |
| http://localhost:9000/docs         | Lead-generation API (Swagger)    |
| http://localhost:8005/docs         | User-settings API (Swagger)      |
| http://localhost:8003/health       | CRM health check                 |
| http://localhost:9000/health       | Lead-generation health check     |
| http://localhost:8005/health       | User-settings health check       |
