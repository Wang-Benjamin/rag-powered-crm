"""Shared helpers for extracting JSON objects from LLM responses."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract the first JSON object from plain text or markdown-fenced output."""
    if not text:
        return None
    # Strip code fences if the model added them despite instructions.
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        # Fallback: find first {...} block.
        m = re.search(r"\{.*\}", stripped, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
