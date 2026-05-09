"""
Query Rewriter - LLM-based multi-query expansion for the CRM retriever.

The retriever takes short, sometimes ambiguous user queries
("follow-up on Acme pricing"). A single embedding of that string can miss
relevant context phrased differently in the corpus ("Q3 quote sent to
Acme", "discount discussion with Acme"). Multi-query rewriting expands
the original into a small set of paraphrases; the retriever runs hybrid
search for each and unions the candidates before RRF + rerank.

Cost is bounded: one LLM call per user query, cached by query hash so a
reloading dashboard pays once.
"""

import os
import json
import logging
import hashlib
from functools import lru_cache
from typing import List, Optional

logger = logging.getLogger(__name__)

REWRITE_MODEL = "gpt-4o-mini"
DEFAULT_NUM_REWRITES = 3
MAX_QUERY_CHARS = 500

_SYSTEM_PROMPT = """You expand a CRM search query into paraphrases that surface differently-worded but equivalent passages in a corpus of customer notes, emails, and call transcripts.

Rules:
- Output {n} paraphrases, JSON array of strings only, no preamble.
- Each paraphrase must preserve the original intent. Do not narrow or broaden the meaning.
- Vary surface form: synonyms, alternate phrasings, expanded acronyms, customer-name variants.
- Keep each paraphrase under 25 words.
- Do not include the original query in the output."""


_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    import openai
    _client = openai.AsyncOpenAI(api_key=api_key, max_retries=2)
    return _client


def _cache_key(query: str, n: int) -> str:
    return hashlib.sha1(f"{n}::{query}".encode("utf-8")).hexdigest()


# Process-local LRU. The harness re-runs the same golden queries during
# eval so caching here makes a measurable cost difference.
_REWRITE_CACHE: dict[str, List[str]] = {}
_CACHE_MAX = 512


async def rewrite_query(
    query: str,
    n: int = DEFAULT_NUM_REWRITES,
) -> List[str]:
    """
    Return a list of queries: [original, paraphrase_1, ..., paraphrase_n].

    Falls back to [query] if the LLM call fails or no API key is set, so
    the retriever degrades gracefully to single-query mode.
    """
    if not query or not query.strip():
        return []

    query = query.strip()[:MAX_QUERY_CHARS]
    base = [query]

    if n <= 0:
        return base

    key = _cache_key(query, n)
    cached = _REWRITE_CACHE.get(key)
    if cached is not None:
        return base + cached

    client = _get_client()
    if client is None:
        logger.debug("OPENAI_API_KEY not set — rewriter disabled, returning original query only")
        return base

    try:
        resp = await client.chat.completions.create(
            model=REWRITE_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT.format(n=n)},
                {"role": "user", "content": query},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
            max_tokens=300,
        )
        raw = resp.choices[0].message.content or "{}"
        parsed = json.loads(raw)

        # Accept either {"queries": [...]} or a bare array — we asked for an
        # array but some models wrap it in an object regardless.
        if isinstance(parsed, list):
            rewrites = parsed
        elif isinstance(parsed, dict):
            for v in parsed.values():
                if isinstance(v, list):
                    rewrites = v
                    break
            else:
                rewrites = []
        else:
            rewrites = []

        rewrites = [str(r).strip() for r in rewrites if str(r).strip()]
        rewrites = [r for r in rewrites if r.lower() != query.lower()][:n]

    except Exception as e:
        logger.warning(f"Query rewrite failed for '{query[:60]}...': {e}")
        return base

    if len(_REWRITE_CACHE) >= _CACHE_MAX:
        _REWRITE_CACHE.pop(next(iter(_REWRITE_CACHE)))
    _REWRITE_CACHE[key] = rewrites

    return base + rewrites


def reset_rewriter():
    """Test-only: clear cache and client."""
    global _client, _REWRITE_CACHE
    _client = None
    _REWRITE_CACHE = {}
