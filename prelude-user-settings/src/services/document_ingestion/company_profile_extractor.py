"""Company profile extractor (M3 reference lane).

Turns a factory brochure / profile PDF into a :class:`CompanyProfileDraft`.

Approach
--------

1. Extract text from the PDF with ``pdfplumber`` (plan §11 "text pre-pass").
2. Ask ``gpt-5.4`` — same model ``hs_codes_router`` uses — for a JSON object
   matching the draft schema. We ask for strict JSON and validate with
   pydantic; one retry on parse/validation failure, then raise.

This is a minor deviation from plan §7.2, which mentions "native PDF input"
to OpenAI. For company-profile prose (names, descriptions, locations,
markets) a text-only pre-pass carries no accuracy penalty and avoids a file
upload round-trip to OpenAI. Layout-sensitive lanes (product PDF specs) can
revisit native input in M6 if needed.
"""

from __future__ import annotations

import io
import json
import logging
import os
from typing import Optional

from openai import AsyncOpenAI
from pydantic import ValidationError

from services.document_ingestion.schemas import CompanyProfileDraft

logger = logging.getLogger(__name__)

# Hard cap from plan §11. A 50-page brochure is already extreme; we truncate
# the extracted text rather than attempting to paginate the model call.
MAX_PAGES = 50
MAX_CHARS = 120_000  # ~30k tokens — comfortably inside gpt-5.4 context.

_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")
        _client = AsyncOpenAI(api_key=api_key)
    return _client


def _extract_text(pdf_bytes: bytes) -> str:
    """Best-effort text extraction. Raises if the PDF can't be opened."""
    import pdfplumber

    chunks: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for idx, page in enumerate(pdf.pages):
            if idx >= MAX_PAGES:
                break
            text = page.extract_text() or ""
            if text:
                chunks.append(text)
    joined = "\n\n".join(chunks).strip()
    if len(joined) > MAX_CHARS:
        joined = joined[:MAX_CHARS]
    return joined


_PROMPT = (
    "You are extracting structured fields from a factory / manufacturer "
    "company-profile document. Return a JSON object with these fields, or "
    "omit / use null for anything the document does not clearly state — do "
    "NOT guess.\n\n"
    "Fields:\n"
    "- company_name_en (string): the company's English trading name, if the document shows one.\n"
    "- company_name_local (string): the native-language name as written in the document.\n"
    "- year_founded (integer).\n"
    "- headquarters_location (string): city, region, country.\n"
    "- employee_count_range (string, e.g. '50-200').\n"
    "- business_type: one of 'manufacturer', 'trading', 'oem', 'odm', 'other'.\n"
    "- product_description (string): 1–3 sentence summary of what they make.\n"
    "- main_markets (array of country names, normalised to English — "
    "use 'United States' not '美国').\n"
    "- factory_location (string).\n"
    "- factory_size_sqm (integer): square metres.\n"
    "- production_capacity (string): free-form, e.g. '500,000 pairs/month'.\n"
    "- certifications_mentioned (array of short standard codes like 'ISO 9001', 'BSCI').\n"
    "- key_customers_mentioned (array of customer names, only if the document lists them).\n\n"
    "Language rule: for free-text fields (product_description, "
    "headquarters_location, factory_location, production_capacity), respond "
    "in the SAME language as the source document — do NOT translate. The "
    "two name fields follow their own rule above. main_markets and "
    "certifications_mentioned are normalised per the bullets. Everything else "
    "is a literal value from the document.\n\n"
    "Return ONLY a single JSON object. No markdown, no prose around it."
)


async def extract(pdf_bytes: bytes) -> CompanyProfileDraft:
    """Extract a CompanyProfileDraft from PDF bytes. Retries once on failure."""
    text = _extract_text(pdf_bytes)
    if not text:
        # Empty extraction = visual-only PDF. Return an empty draft rather
        # than pretending we succeeded; runner will flag `failed`.
        raise RuntimeError("no extractable text in PDF (likely image-only)")

    client = _get_client()
    last_error: Optional[Exception] = None

    for attempt in (1, 2):
        try:
            response = await client.chat.completions.create(
                model="gpt-5.4",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": _PROMPT},
                    {
                        "role": "user",
                        "content": f"Document text:\n\n{text}",
                    },
                ],
            )
            raw = (response.choices[0].message.content or "").strip()
            data = json.loads(raw)
            draft = CompanyProfileDraft.model_validate(data)
            logger.info(
                "company_profile_extractor: attempt %d ok (fields populated=%d)",
                attempt,
                sum(1 for v in draft.model_dump().values() if v),
            )
            return draft
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(
                "company_profile_extractor: parse failure on attempt %d: %s",
                attempt,
                e,
            )
            last_error = e
        except Exception as e:
            logger.error("company_profile_extractor: unexpected error: %s", e)
            raise

    raise RuntimeError(f"extraction failed after retry: {last_error}")
