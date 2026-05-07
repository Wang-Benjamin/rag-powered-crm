import os
import logging
import warnings

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from google.adk.sessions import InMemorySessionService
from google.adk.sessions.database_session_service import DatabaseSessionService
from google.adk.runners import Runner
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types
from sqlalchemy import Table, Column, String, text

from agents import chat_agent, chat_history_agent
from data.database_router import get_database_url_for_user


# Logging setup
class MCPLogFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        suppress_patterns = [
            "auth_config or auth_config.auth_scheme is missing",
            "Attempted to exit cancel scope in a different task",
            "Task exception was never retrieved",
            "unhandled errors in a TaskGroup",
        ]
        return not any(p in msg for p in suppress_patterns)

for logger_name in ["", "google.adk", "mcp", "anyio", "asyncio"]:
    logging.getLogger(logger_name).addFilter(MCPLogFilter())

warnings.filterwarnings("ignore", message=".*cancel scope.*")
warnings.filterwarnings("ignore", message=".*Task exception was never retrieved.*")

logger = logging.getLogger(__name__)


# Agents registry
AGENTS = {
    "chat_agent": chat_agent.get_agent,
    "chat_history_agent": chat_history_agent.get_agent,
}


# App
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request model
class AgentRunRequest(BaseModel):
    app_name: str
    user_id: str
    session_id: str
    user_email: Optional[str] = None  # For database routing
    model: Optional[str] = "gemini-2.5-flash"
    new_message: types.Content


def get_session_service(user_email: Optional[str] = None):
    """Get session service - routes to user-specific DB if email provided"""
    if user_email:
        db_url = get_database_url_for_user(user_email)
        if db_url:
            return DatabaseSessionService(db_url=db_url)

    # Fallback to env-based config
    db_url = os.getenv("SESSIONS_DB_CONNECTION_URL")
    if db_url:
        return DatabaseSessionService(db_url=db_url)

    return InMemorySessionService()


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/run")
async def agent_run(req: AgentRunRequest) -> list:
    agent_factory = AGENTS.get(req.app_name)
    if not agent_factory:
        raise HTTPException(status_code=404, detail="Agent not found")

    session_service = get_session_service(req.user_email)

    session = await session_service.get_session(
        app_name=req.app_name, user_id=req.user_id, session_id=req.session_id
    )
    if not session:
        session = await session_service.create_session(
            app_name=req.app_name, user_id=req.user_id, session_id=req.session_id
        )
        logger.info(f"Created session: {session.id}")

    runner = Runner(
        agent=agent_factory(model=req.model, user_id=req.user_id, user_email=req.user_email),
        app_name=req.app_name,
        session_service=session_service,
    )

    events = [
        event async for event in runner.run_async(
            user_id=req.user_id,
            session_id=req.session_id,
            new_message=req.new_message,
        )
    ]
    return events


@app.post("/run_sse")
async def agent_run_sse(req: AgentRunRequest) -> StreamingResponse:
    agent_factory = AGENTS.get(req.app_name)
    if not agent_factory:
        raise HTTPException(status_code=404, detail="Agent not found")

    session_service = get_session_service(req.user_email)

    session = await session_service.get_session(
        app_name=req.app_name, user_id=req.user_id, session_id=req.session_id
    )
    if not session:
        session = await session_service.create_session(
            app_name=req.app_name, user_id=req.user_id, session_id=req.session_id
        )
        logger.info(f"Created session: {session.id}")

    runner = Runner(
        agent=agent_factory(model=req.model, user_id=req.user_id, user_email=req.user_email),
        app_name=req.app_name,
        session_service=session_service,
    )

    async def event_generator():
        try:
            async for event in runner.run_async(
                user_id=req.user_id,
                session_id=req.session_id,
                new_message=req.new_message,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            ):
                yield f"data: {event.model_dump_json(exclude_none=True, by_alias=True)}\n\n"
        except Exception as e:
            logger.exception(f"Error: {e}")
            yield f'data: {{"error": "{str(e)}"}}\n\n'

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=os.getenv("ENV") != "production")
