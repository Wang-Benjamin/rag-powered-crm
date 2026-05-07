"""
Communication Analysis Agents.

Agents that analyze email and note communications.
"""

from .email_agent import EmailAgent
from .note_agent import NoteAgent

__all__ = [
    "EmailAgent",
    "NoteAgent",
]

