from .chat_agent import get_agent as get_chat_agent
from .chat_history_agent import get_agent as get_chat_history_agent

AGENTS = {
    "chat_agent": get_chat_agent,
    "chat_history_agent": get_chat_history_agent,
}

__all__ = ["AGENTS", "get_chat_agent", "get_chat_history_agent"]
