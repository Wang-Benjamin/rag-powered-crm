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

Each backend service reads a local `.env` file (via `python-dotenv`); the
frontend reads `.env.local`. Create one file in each of the four folders below
with the contents shown — they share the **same `JWT_SECRET`** so tokens
issued by one service validate in the others.

> ⚠️ Replace every `<...>` placeholder below with your own value. Real
> credentials must never be committed to this README — keep them only in
> the local `.env` files (which are gitignored).

### `crm/.env`
```bash
# Database (shared GCP Postgres)
SESSIONS_DB_HOST=<DB_HOST>
SESSIONS_DB_PORT=5432
SESSIONS_DB_NAME=postgres
SESSIONS_DB_USER=postgres
SESSIONS_DB_PASSWORD=<DB_PASSWORD>

MANAGEMENT_DB_HOST=<DB_HOST>
MANAGEMENT_DB_PORT=5432
MANAGEMENT_DB_NAME=prelude_user_analytics
MANAGEMENT_DB_USER=postgres
MANAGEMENT_DB_PASSWORD=<DB_PASSWORD>

# Auth
GOOGLE_CLIENT_ID=<GOOGLE_CLIENT_ID>
GOOGLE_CLIENT_SECRET=<GOOGLE_CLIENT_SECRET>
JWT_SECRET=<JWT_SECRET>

MICROSOFT_CLIENT_ID=<MICROSOFT_CLIENT_ID>
MICROSOFT_CLIENT_SECRET=<MICROSOFT_CLIENT_SECRET>
MICROSOFT_TENANT_ID=common

# AI providers
GOOGLE_API_KEY=<GOOGLE_API_KEY>
OPENAI_API_KEY=<OPENAI_API_KEY>
ANTHROPIC_API_KEY=<ANTHROPIC_API_KEY>

DEFAULT_PROVIDER=openai
DEFAULT_OPENAI_MODEL=gpt-4o-mini

# Inter-service
USER_SETTINGS_URL=http://localhost:8005
CRM_SERVICE_URL=http://localhost:8003

# Temporal Cloud
TEMPORAL_HOST=us-east4.gcp.api.temporal.io:7233
TEMPORAL_NAMESPACE=<TEMPORAL_NAMESPACE>
TEMPORAL_API_KEY=<TEMPORAL_API_KEY>

SHOW_EMAIL_SYNC_LOGS=true
```

### `leadgen/.env`
```bash
DATABASE_URL=postgresql://postgres:<DB_PASSWORD_URL_ENCODED>@<DB_HOST>:5432/postgres

# Sessions DB
SESSIONS_DB_HOST=<DB_HOST>
SESSIONS_DB_PORT=5432
SESSIONS_DB_USER=postgres
SESSIONS_DB_PASSWORD=<DB_PASSWORD>
SESSIONS_DB_NAME=postgres

# Management DB (tenant discovery)
MANAGEMENT_DB_HOST=<DB_HOST>
MANAGEMENT_DB_PORT=5432
MANAGEMENT_DB_NAME=prelude_user_analytics
MANAGEMENT_DB_USER=postgres
MANAGEMENT_DB_PASSWORD=<DB_PASSWORD>

# Auth
GOOGLE_CLIENT_ID=<GOOGLE_CLIENT_ID>
GOOGLE_CLIENT_SECRET=<GOOGLE_CLIENT_SECRET>
JWT_SECRET=<JWT_SECRET>

# AI / search keys
OPENAI_API_KEY=<OPENAI_API_KEY>
GOOGLE_API_KEY=<GOOGLE_API_KEY>
GOOGLE_SEARCH_API_KEY=<GOOGLE_SEARCH_API_KEY>
GOOGLE_CUSTOM_SEARCH_ENGINE_ID=<GOOGLE_CUSTOM_SEARCH_ENGINE_ID>
GOOGLE_MAPS_API_KEY=<GOOGLE_MAPS_API_KEY>
PERPLEXITY_API_KEY=<PERPLEXITY_API_KEY>
APOLLO_API_KEY=<APOLLO_API_KEY>
FIRECRAWL_API_KEY=<FIRECRAWL_API_KEY>
IMPORTYETI_API_KEY=<IMPORTYETI_API_KEY>

# Model preferences
GPT_4O_MODEL=gpt-4o
GPT_4O_MINI_MODEL=gpt-4o-mini
GPT_4_1_MINI_MODEL=gpt-4.1-mini

# Pool / runtime
DB_POOL_MIN_CONN=2
DB_POOL_MAX_CONN=10
RATE_LIMIT_REQUESTS_PER_MINUTE=100
MAX_SEARCH_RESULTS=100
SEARCH_TIMEOUT=30
LOG_LEVEL=INFO
DEBUG=False
RELOAD=True
ENVIRONMENT=development
PLAYWRIGHT_HEADLESS=True
PLAYWRIGHT_TIMEOUT=30000
FRONTEND_CORS_ORIGINS=http://localhost:8000

# Temporal Cloud
TEMPORAL_HOST=us-east4.gcp.api.temporal.io:7233
TEMPORAL_NAMESPACE=<TEMPORAL_NAMESPACE>
TEMPORAL_API_KEY=<TEMPORAL_API_KEY>
```

### `user-settings/.env`
```bash
# Databases
DATABASE_URL=postgresql://postgres:<DB_PASSWORD>@<DB_HOST>:5432/prelude_db
SESSIONS_DB_HOST=<DB_HOST>
SESSIONS_DB_PORT=5432
SESSIONS_DB_USER=postgres
SESSIONS_DB_PASSWORD=<DB_PASSWORD>
SESSIONS_DB_NAME=prelude_user_analytics

DB_HOST=<DB_HOST>
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=<DB_PASSWORD>
DB_NAME=prelude_db

# Server
PORT=8005
HOST=0.0.0.0

# Auth
GOOGLE_CLIENT_ID=<GOOGLE_CLIENT_ID>
GOOGLE_CLIENT_SECRET=<GOOGLE_CLIENT_SECRET>
JWT_SECRET=<JWT_SECRET>

MICROSOFT_CLIENT_ID=<MICROSOFT_CLIENT_ID>
MICROSOFT_CLIENT_SECRET=<MICROSOFT_CLIENT_SECRET>
MICROSOFT_TENANT_ID=common

# AI
OPENAI_API_KEY=<OPENAI_API_KEY>
DEFAULT_PROVIDER=openai
DEFAULT_OPENAI_MODEL=gpt-4o-mini

# GCS bucket for email signatures
GCS_SIGNATURE_BUCKET=prelude-signature-logos

# Service URLs / runtime
USER_SETTINGS_URL=http://localhost:8005
USE_LOCAL_SERVICES=false
LOG_LEVEL=INFO
```

### `frontend-next/.env.local`
```bash
NEXT_PUBLIC_CRM_API_URL=http://localhost:8003
NEXT_PUBLIC_BACKEND_LEAD_API_URL=http://localhost:9000
NEXT_PUBLIC_USER_SETTINGS_API_URL=http://localhost:8005
NEXT_PUBLIC_ONE_PAGER_ENABLED=true
```

> If the Postgres password contains URL-reserved characters (e.g. `(`, `)`,
> `{`, `@`), use it as-is in plain `KEY=value` lines, but percent-encode it
> when embedding inside a URL like `DATABASE_URL=postgresql://...`
> (see `leadgen/.env` above for the encoded form).

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

> **⚠️ Each of the four services must run in its own dedicated terminal window
> (or `tmux` pane).** They are long-running foreground processes — closing a
> terminal stops that service. Do **not** try to chain them with `&&` or run
> them all in one shell.

All commands are run from the repository root
(`/Users/dingaoxue/Desktop/rag-powered-crm`). Backends are launched by calling
the venv's Python binary directly, so no `activate` step is required (this
works whether the venv was created with `python -m venv` or `conda create -p`).

### Terminal 1 — CRM service (port 8003)
```bash
cd crm
.venv/bin/python main.py
```
Verify: <http://localhost:8003/health>

### Terminal 2 — Lead-generation service (port 9000)
```bash
cd leadgen
.venv/bin/python main.py
```
Verify: <http://localhost:9000/health>

### Terminal 3 — User-settings service (port 8005)
```bash
cd user-settings
.venv/bin/python main.py
```
Verify: <http://localhost:8005/health>

### Terminal 4 — Frontend (port 8000)
```bash
cd frontend-next
npm install      # one-time, only if node_modules/ is missing
npm run dev
```
Open: <http://localhost:8000>

> Prefer activating the venv yourself? Use `source .venv/bin/activate`
> (standard venv) or `conda activate ./.venv` (conda env) and then run
> `python main.py`. The four-terminal rule still applies.

### Demo login

The login form at `/login` is pre-filled with a demo account. The
username/password values are not committed here — request them from the
project owner, or set your own short-circuit credentials in the
auth handler.

Just click **Sign in** — these credentials short-circuit the password
endpoint and mint a JWT without needing the user to be present in any
database table, so the demo works even if Postgres is unreachable.

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
