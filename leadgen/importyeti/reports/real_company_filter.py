"""Real-company pre-filter for two-pager buyer lists.

Uses the Perplexity Sonar API (cheap, purpose-built for web search) to classify
each candidate buyer as 'real', 'unclear', or 'likely_shell' before burning
ImportYeti deep-enrich credits on companies with no actual web presence.

Typical cost: ~$0.005-0.01 per batch of 40 companies (Perplexity sonar-pro).

Public contract:

    async def classify_real_companies(
        buyers: List[Dict[str, Any]],
        hs_category: str,
        timeout: float = 30.0,
    ) -> Dict[str, str]:
        ...

Returns {slug: 'real' | 'unclear' | 'likely_shell'} for each buyer.
Returns {} on any failure — caller treats as "keep all".
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

import httpx
from service_core.llm_json import extract_json

logger = logging.getLogger(__name__)

_PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
_MODEL = "sonar"

_SYSTEM_PROMPT = """You are a business intelligence analyst. Your job is to verify whether US import companies have a real, legitimate business presence — not shell LLCs, Amazon-FBA dropshippers, or single-trade-name consignees.

For each company provided, search the web and check:
1. Does the company have a working website with real product/service content?
2. Is the company listed on LinkedIn with employees?
3. Does the company name make semantic sense for the HS product category given?
4. Are there any red flags: generic toponym-based name (city/region name + generic suffix like "Inc"), no web presence, single-person operation, Amazon seller account only, European or foreign geographic name?

Classification rules:
- "real": company has clear web presence, employees, and product offering consistent with the HS category
- "likely_shell": 2+ of these red flags: toponym/geographic name (e.g. "Diocese Inc", "Juliaca Inc", "Paroisse Inc"), no website found, no LinkedIn with >1 employee, name semantically inconsistent with HS category (e.g. a religious organization importing plastic household goods)
- "unclear": everything else — when in doubt, classify as "unclear" NOT "likely_shell"

IMPORTANT: Be conservative. Only classify "likely_shell" when there is strong evidence of at least 2 red flags. Default to "unclear" on any doubt.

Return ONLY valid JSON with this exact shape, no markdown fences, no prose:
{"verdicts": {"<slug>": {"class": "real|unclear|likely_shell", "reason": "<one short sentence>"}}}"""


import re

# Matches one fully-complete verdict entry inside the outer `verdicts` object.
# Used to salvage partial classifications when the response is truncated.
_VERDICT_ENTRY_RE = re.compile(
    r'"([a-z0-9][a-z0-9\-_]*)"\s*:\s*\{\s*"class"\s*:\s*"(real|unclear|likely_shell)"\s*,\s*"reason"\s*:\s*"([^"]*)"\s*\}',
    re.IGNORECASE,
)


def _salvage_truncated_verdicts(content: str) -> Dict[str, Dict[str, str]]:
    """Extract all completely-closed verdict entries from a truncated response.

    If the Perplexity reply was cut off mid-stream, the outer JSON won't
    parse, but the first N verdicts are usually intact. Regex-extract the
    complete ones so we still filter on what we got.
    """
    out: Dict[str, Dict[str, str]] = {}
    for slug, cls, reason in _VERDICT_ENTRY_RE.findall(content):
        out[slug] = {"class": cls.lower(), "reason": reason}
    return out


def _build_user_prompt(buyers: List[Dict[str, Any]], hs_category: str) -> str:
    lines = [
        f"HS product category: {hs_category}",
        "",
        "Companies to classify (JSON array):",
        json.dumps(
            [
                {
                    "slug": b.get("slug", ""),
                    "name": b.get("name", ""),
                    "city": b.get("city") or "",
                    "state": b.get("state") or "",
                }
                for b in buyers
                if b.get("slug")
            ],
            ensure_ascii=False,
        ),
    ]
    return "\n".join(lines)


async def classify_real_companies(
    buyers: List[Dict[str, Any]],
    hs_category: str,
    timeout: float = 30.0,
) -> Dict[str, str]:
    """Return {slug: 'real' | 'unclear' | 'likely_shell'} for each buyer.

    Batched: one API call for all buyers. Uses Perplexity Sonar web-search
    to verify each company has real business presence (website, employees,
    etc.). Conservative: defaults to 'unclear' on uncertainty; only
    classifies 'likely_shell' when strong evidence (no web presence,
    generic/toponym name, Amazon-FBA pattern).

    Never raises — returns {} on any failure (caller treats as "keep all").
    """
    if not buyers:
        return {}

    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        logger.warning("[TwoPager/real-filter] PERPLEXITY_API_KEY not set; skipping classifier")
        return {}

    user_prompt = _build_user_prompt(buyers, hs_category)

    # max_tokens sized for 45 companies × ~140 chars/verdict ≈ 6300 chars
    # output. Tokenized that's ~2000-2500 tokens — we were clipping at the
    # previous 2000 cap. 8000 gives comfortable headroom for the full batch
    # plus the `reason` field per company.
    payload = {
        "model": _MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 8000,
        "temperature": 0.1,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                _PERPLEXITY_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("[TwoPager/real-filter] API call failed: %s", e)
        return {}

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        logger.warning("[TwoPager/real-filter] Unexpected API response shape: %s", e)
        return {}

    # Strip markdown fences if the model added them despite instructions
    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        # Remove first and last fence lines
        content = "\n".join(
            l for l in lines if not l.strip().startswith("```")
        )

    parsed = extract_json(content)
    if parsed is None:
        # Salvage pass: if the response was truncated (most common failure
        # mode), try to extract complete verdict entries up to the cutoff.
        # This keeps the filter partially useful instead of dropping all
        # classifications when the tail of the response was clipped.
        salvaged = _salvage_truncated_verdicts(content)
        if salvaged:
            logger.warning(
                "[TwoPager/real-filter] JSON parse failed; salvaged %d/%d verdicts from truncated response",
                len(salvaged), content.count('"class"'),
            )
            parsed = {"verdicts": salvaged}
        else:
            logger.warning(
                "[TwoPager/real-filter] JSON parse failed | raw=%r",
                content[:300],
            )
            return {}

    verdicts_raw = parsed.get("verdicts") or {}
    if not isinstance(verdicts_raw, dict):
        logger.warning("[TwoPager/real-filter] verdicts not a dict: %r", verdicts_raw)
        return {}

    result: Dict[str, str] = {}
    for slug, v in verdicts_raw.items():
        if not isinstance(v, dict):
            continue
        cls = v.get("class", "unclear")
        if cls not in ("real", "unclear", "likely_shell"):
            cls = "unclear"
        result[slug] = cls

    # Log per-verdict reasons for observability
    for slug, v in verdicts_raw.items():
        if isinstance(v, dict):
            logger.debug(
                "[TwoPager/real-filter] %s → %s: %s",
                slug,
                v.get("class", "?"),
                v.get("reason", ""),
            )

    return result
