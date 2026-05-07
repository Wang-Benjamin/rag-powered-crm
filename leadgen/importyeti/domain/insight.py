"""LLM-generated buyer insight using gpt-5.4-mini.

Generates a one-liner trade intelligence insight for the buyer detail view.
Called lazily on first detail view click, then cached in bol_detail_context.
"""

import asyncio
import json
import logging
import os

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        _client = AsyncOpenAI(api_key=api_key)
    return _client


SYSTEM_PROMPT = """You are a trade intelligence analyst writing a one-liner insight for a Chinese supplier evaluating whether to pursue a US buyer.

Given the buyer's import data, write ONE concise actionable insight (max 35 words) highlighting the most important signal for outreach. Focus on whichever is most relevant:
- Reorder timing (days since last import vs average cycle)
- Supplier displacement (declining Chinese suppliers = opportunity)
- Supplier diversification (few suppliers = open to new vendors)
- Import growth or decline trends
- Volume and scale indicators

End with a brief suggested action. Be specific with numbers from the data.
Respond in {locale_name}. No markdown, no bullet points — one flowing sentence."""

CONDENSED_SYSTEM_PROMPT = """You are a trade intelligence analyst writing a very short tagline for a buyer card.

Given the buyer's scoring signals, write a VERY short tagline (max 8 words) summarizing the top 1-2 signals.
Use a middle dot (·) to separate two ideas. Examples:
- English: "Reorder window open · supplier declining"
- Chinese: "采购窗口临近·供应商下降"

No markdown, no bullet points, no period at the end.
Respond in {locale_name}."""


def _build_data_parts(
    import_context: dict | None,
    supplier_context: dict | None,
    bol_detail_context: dict | None,
) -> list[str]:
    """Assemble structured data lines from buyer contexts for LLM prompts."""
    data_parts = []

    # Scoring signals summary
    if bol_detail_context:
        signals = bol_detail_context.get("scoringSignals") or {}
        if signals:
            summary = {
                k: f"{v['points']}/{v['max']}"
                for k, v in signals.items()
                if isinstance(v, dict)
            }
            data_parts.append(f"Scoring signals: {json.dumps(summary)}")
        china_pct = bol_detail_context.get("chinaConcentration")
        if china_pct is not None:
            data_parts.append(f"China concentration: {china_pct}%")
        growth = bol_detail_context.get("growth12mPct")
        if growth is not None:
            data_parts.append(f"12-month import growth: {growth}%")

    # Import context
    if import_context:
        products = import_context.get("topProducts")
        if products:
            data_parts.append(f"Products: {str(products)[:200]}")
        last_ship = import_context.get("mostRecentShipment")
        if last_ship:
            data_parts.append(f"Last shipment: {last_ship}")
        avg_cycle = import_context.get("avgOrderCycleDays")
        if avg_cycle:
            data_parts.append(f"Avg order cycle: {avg_cycle} days")
        total = import_context.get("totalShipments")
        if total:
            data_parts.append(f"Total shipments: {total}")
        total_suppliers = import_context.get("totalSuppliers")
        if total_suppliers:
            data_parts.append(f"Total suppliers: {total_suppliers}")
        containers = import_context.get("annualVolumeContainers")
        if containers:
            data_parts.append(f"Annual volume: ~{containers} containers")
        days_ago = import_context.get("lastImportDaysAgo")
        if days_ago is not None:
            data_parts.append(f"Days since last import: {days_ago}")
        company = import_context.get("companyName")
        if company:
            data_parts.append(f"Company: {company}")
        location = import_context.get("location")
        if location:
            data_parts.append(f"Location: {location}")

    # Supplier breakdown
    if supplier_context:
        suppliers = supplier_context.get("suppliers") or []
        if suppliers:
            top = suppliers[:5]
            lines = [
                f"{s.get('name', '?')} ({s.get('country', '?')}, "
                f"{s.get('share', 0)}% share, "
                f"12m: {s.get('shipments12m', 0)}, "
                f"prior 12m: {s.get('shipments12_24m', 0)}, "
                f"trend: {s.get('trend', 0)}%)"
                for s in top
            ]
            data_parts.append(f"Top suppliers: {'; '.join(lines)}")

    return data_parts


async def _llm_call(system_prompt: str, user_message: str, max_tokens: int = 150) -> str | None:
    """Shared LLM call wrapper with timeout and error handling."""
    try:
        client = _get_client()
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model="gpt-5.4-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_completion_tokens=max_tokens,
                temperature=0.3,
            ),
            timeout=10.0,
        )
        return response.choices[0].message.content.strip()
    except asyncio.TimeoutError:
        logger.warning("AI insight LLM call timed out after 10s")
        return None
    except Exception as e:
        logger.error(f"AI insight LLM call failed: {e}")
        return None


async def generate_ai_insight(
    import_context: dict | None,
    supplier_context: dict | None,
    bol_detail_context: dict | None,
    locale: str = "en",
) -> str | None:
    """Generate a one-liner buyer insight via gpt-5.4-mini.

    Returns None on failure so the caller can fall back gracefully.
    """
    locale_name = "Chinese (Simplified)" if locale.startswith("zh") else "English"
    data_parts = _build_data_parts(import_context, supplier_context, bol_detail_context)
    if not data_parts:
        return None
    return await _llm_call(
        SYSTEM_PROMPT.format(locale_name=locale_name),
        "\n".join(data_parts),
        max_tokens=150,
    )


async def generate_condensed_insight(
    import_context: dict | None,
    supplier_context: dict | None,
    bol_detail_context: dict | None,
    locale: str = "en",
) -> str | None:
    """Generate a very short tagline (~8 words) for the buyer table/card view.

    Returns None on failure so the caller can fall back gracefully.
    """
    locale_name = "Chinese (Simplified)" if locale.startswith("zh") else "English"
    data_parts = _build_data_parts(import_context, supplier_context, bol_detail_context)
    if not data_parts:
        return None
    return await _llm_call(
        CONDENSED_SYSTEM_PROMPT.format(locale_name=locale_name),
        "\n".join(data_parts),
        max_tokens=40,
    )
