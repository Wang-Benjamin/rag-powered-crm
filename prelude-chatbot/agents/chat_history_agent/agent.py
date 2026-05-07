import os
import psycopg2
from google.adk.agents.llm_agent import LlmAgent
from psycopg2.extras import RealDictCursor


def make_get_chat_history(user_email: str):
    """Factory function to create get_chat_history with user_email closure"""
    def get_chat_history(session_id: str) -> dict:
        """Fetch chat history from database"""
        if user_email:
            from data.database_router import get_database_url_for_user
            db_url = get_database_url_for_user(user_email)
        else:
            db_url = os.getenv("SESSIONS_DB_CONNECTION_URL")

        if not db_url:
            raise RuntimeError("Database URL not available")

        # Convert asyncpg URL to psycopg2 format
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        try:
            with conn.cursor() as cur:
                cur.execute("SET search_path TO chat_sessions")
                cur.execute(
                    "SELECT content FROM events WHERE session_id = %s AND app_name = 'chat_agent' ORDER BY timestamp ASC",
                    (session_id,),
                )
                rows = cur.fetchall()
                return {
                    "status": "success",
                    "chat_history": [row["content"] for row in rows],
                }
        except Exception as e:
            print(f"Error getting chat history: {e}")
            return {"status": "error", "error_message": str(e)}
        finally:
            conn.close()

    return get_chat_history


def get_agent(model: str = "gemini-2.5-flash", user_id: str = "default", user_email: str = None):
    """Create and return the chat history agent for title generation"""
    return LlmAgent(
        model=model,
        name="chat_history_agent",
        instruction="""Generate a short title for a chat conversation.

Steps:
1. Call get_chat_history tool with the session_id to retrieve the conversation
2. Analyze the conversation content
3. Generate a concise title (around 5 words)
4. Return ONLY the title, no other text
""",
        tools=[make_get_chat_history(user_email)],
    )
