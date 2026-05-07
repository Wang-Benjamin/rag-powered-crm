"""Shared Perplexity-backed Chinese company name resolution helpers."""

import asyncio
import os
import re
from typing import Optional

from openai import AsyncOpenAI

_CN_NAME_PATTERN = re.compile(r"[\u4e00-\u9fff][\u4e00-\u9fff\u00b7\uff08\uff09\(\)]+")


def _build_prompt(supplier_name: str, address: Optional[str] = None) -> str:
    address_line = f'\nAddress: "{address}"' if address else ""
    return (
        "Search for the official Chinese company name (公司名称) of this manufacturer.\n\n"
        f'English name from US customs/trade records: "{supplier_name}"'
        f"{address_line}\n\n"
        "Search Chinese business registries, company websites, or trade databases. "
        "Return ONLY the Chinese company name, nothing else. "
        'If you cannot find it, return "UNKNOWN".'
    )


async def resolve_chinese_company_name(
    supplier_name: str,
    address: Optional[str] = None,
    timeout_seconds: int = 30,
) -> Optional[str]:
    """Resolve an official Chinese company name using Perplexity web search."""
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key or not supplier_name:
        return None

    client = AsyncOpenAI(api_key=api_key, base_url="https://api.perplexity.ai")
    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model="sonar",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You search the web to find official Chinese company names "
                            "for manufacturers. Return only the Chinese name, nothing else."
                        ),
                    },
                    {"role": "user", "content": _build_prompt(supplier_name, address)},
                ],
            ),
            timeout=timeout_seconds,
        )
    finally:
        await client.close()

    result = (response.choices[0].message.content or "").strip()
    if not result or "UNKNOWN" in result.upper():
        return None

    match = _CN_NAME_PATTERN.search(result)
    return match.group(0) if match else None
