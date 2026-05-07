import os
import asyncio
import time
import psycopg2
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools import BaseTool, ToolContext
# from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, SseConnectionParams
from google.genai import types
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from .prompt import SYSTEM_INSTRUCTION

load_dotenv()

MAX_WAIT_TIME = 15


def get_status_from_db(function_call_id: str, user_email: str = None):
    """Synchronous DB query for tool approval status"""
    if user_email:
        from data.database_router import get_database_url_for_user
        db_url = get_database_url_for_user(user_email)
    else:
        db_url = os.getenv("SESSIONS_DB_CONNECTION_URL")

    if not db_url:
        return None

    # Convert asyncpg URL to psycopg2 format
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute("SET search_path TO chat_sessions")
            cur.execute(
                "SELECT status FROM tool_calls WHERE toolcall_id = %s",
                (function_call_id,),
            )
            row = cur.fetchone()
            return row["status"] if row else None
    finally:
        conn.close()


def make_before_tool_call(user_email: str):
    """Factory function to create before_tool_call with user_email closure"""
    async def before_tool_call(
        tool: BaseTool, args: dict, tool_context: ToolContext
    ) -> dict | None:
        """Database polling for tool approval with 15 second timeout"""
        function_call_id = tool_context.function_call_id
        print(f"Before tool call: {tool.name} with args: {args} (id: {function_call_id})")

        # Development bypass for approval workflow
        if os.getenv("BYPASS_APPROVAL", "false").lower() == "true":
            print(f"Bypassing approval for tool call: {tool.name}")
            return None  # Auto-approve for development

        # Poll database every second until status is 'approved' or 'denied'
        start_time = time.time()
        while time.time() - start_time < MAX_WAIT_TIME:
            status = await asyncio.to_thread(get_status_from_db, function_call_id, user_email)
            if status == "approved":
                return None  # Proceed with tool execution
            elif status == "denied":
                return {"error": "Tool call denied by user"}
            await asyncio.sleep(1)

        return {"error": "Tool call timed out"}

    return before_tool_call


def get_agent(model: str = "gemini-2.5-flash", user_id: str = "default", user_email: str = None):
    """Create and return the main chat agent with MCP tools"""
    tools = []

    # MCP tools (optional - comment out if MCP server not running)
    # mcp_url = os.getenv("PRELUDE_MCP_SERVER_URL")
    # if mcp_url:
    #     headers = {"X-User-Id": user_id} if user_id else {}
    #     tools.append(
    #         MCPToolset(
    #             connection_params=SseConnectionParams(
    #                 url=f"{mcp_url}/sse",
    #                 headers=headers,
    #             )
    #         )
    #     )

    return LlmAgent(
        model=model,
        name="chat_agent",
        instruction=SYSTEM_INSTRUCTION,
        tools=tools,
        before_tool_callback=make_before_tool_call(user_email) if user_email else None,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
        ),
    )
