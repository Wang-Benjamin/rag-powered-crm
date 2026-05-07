# Prelude Chatbot Service

ADK-powered chat backend using SSE streaming. Port 8001.

## Architecture

```
┌─────────────────────┐         ┌─────────────────────┐
│      Frontend       │         │      Backend        │
│  (Next.js :8000)    │         │   (FastAPI :8001)   │
└─────────┬───────────┘         └──────────┬──────────┘
          │                                │
          │  POST /api/chat/stream         │
          │  { user_email, message }       │
          ├───────────────────────────────►│
          │                                │
          │                     ┌──────────▼──────────┐
          │                     │   database_router   │
          │                     │  (user_email→db)    │
          │                     └──────────┬──────────┘
          │                                │
          │                     ┌──────────▼──────────┐
          │                     │    ADK Agent        │
          │                     │  + MCP Tools        │
          │                     └──────────┬──────────┘
          │                                │
          │◄───────────────────────────────┤
          │      SSE stream events         │
          │                                │
```

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/run` | POST | Non-streaming agent execution |
| `/run_sse` | POST | SSE streaming agent execution |

### Request Body

```json
{
  "app_name": "chat_agent",
  "user_id": "john",
  "session_id": "thread-123",
  "user_email": "john@company.com",
  "model": "gemini-2.5-flash",
  "new_message": { "role": "user", "parts": [{ "text": "Hello" }] }
}
```

- `user_email` routes to user-specific database via `user_profiles` table
- `user_id` identifies user within session storage
- `session_id` groups messages into conversations

## Agents

| Agent | Purpose |
|-------|---------|
| `chat_agent` | Main assistant with MCP tools |
| `chat_history_agent` | Generates conversation titles |

## Database Routing

1. `user_email` � query `prelude_user_analytics.user_profiles`
2. Get `db_name` for user
3. Connect to `{db_name}.chat_sessions` schema

Tables in `chat_sessions` schema:
- `sessions` - Session metadata (ADK managed)
- `events` - Chat events (ADK managed)
- `tool_calls` - Tool approval status

## Environment Variables

```bash
# Required
PRELUDE_MCP_SERVER_URL=http://localhost:8080/sse
GOOGLE_API_KEY=your-key

# Database
SESSIONS_DB_HOST=localhost
SESSIONS_DB_PORT=5432
SESSIONS_DB_USER=postgres
SESSIONS_DB_PASSWORD=secret

# Optional
BYPASS_APPROVAL=true   # Skip tool approval (dev only)
PORT=8001
```

## Run

```bash
# Development
python main.py

# Docker
docker build -t prelude-chatbot .
docker run -p 8001:8000 prelude-chatbot
```

## Frontend Integration

The frontend (`prelude-frontend-next`) connects via:

1. **`/api/chat/stream`** - Proxies to `/run_sse`, streams SSE events
2. **`/api/chat/sessions`** - Lists user sessions (direct DB query)
3. **`/api/chat/events`** - Loads message history (direct DB query)
4. **`/api/chat/tool`** - Stores tool approval status
5. **`/api/chat/title`** - Calls `/run` with `chat_history_agent`
6. **`/api/chat/archive`** - Archives sessions

Frontend env:
```bash
CHAT_BACKEND_URL=http://localhost:8001
SESSIONS_DB_HOST=...
SESSIONS_DB_PORT=5432
SESSIONS_DB_USER=...
SESSIONS_DB_PASSWORD=...
```
