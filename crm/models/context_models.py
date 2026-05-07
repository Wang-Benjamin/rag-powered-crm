"""
Context models for RAG retrieval system.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum


class ContextSourceType(str, Enum):
    INTERACTION = "interaction"
    EMAIL = "email"
    NOTE = "note"


@dataclass
class ContextItem:
    """A single piece of context retrieved for an AI agent."""
    source_type: str
    source_id: int
    text: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    citation_index: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_type": self.source_type,
            "source_id": self.source_id,
            "text": self.text,
            "score": self.score,
            "metadata": self.metadata,
            "citation_index": self.citation_index,
        }


@dataclass
class ContextResult:
    """Result from a context retrieval operation."""
    items: List[ContextItem]
    run_id: int
    retrieval_method: str  # "smart", "multi_query"
    query: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "retrieval_method": self.retrieval_method,
            "query": self.query,
            "item_count": len(self.items),
            "items": [item.to_dict() for item in self.items]
        }


class JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for context models."""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)
