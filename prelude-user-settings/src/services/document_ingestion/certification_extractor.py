"""Certification extractor (M4).

Turns a single-cert PDF or image into a :class:`CertificationDraft`.

Branches by file extension:
- ``.pdf``  → pdfplumber text pre-pass → ``gpt-5.4`` chat completions
  (same recipe as the company-profile lane).
- ``.png`` / ``.jpg`` / ``.jpeg`` → ``gpt-5.4`` vision (base64 data URL in a
  user message); no OCR dep pulled in.

Both branches ask for a strict JSON object, validate with pydantic, retry once
on parse/validation failure, then raise. All draft fields are optional so a
partial extraction still round-trips.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
from typing import Optional

from openai import AsyncOpenAI
from pydantic import ValidationError

from services.document_ingestion.schemas import CertificationDraft

logger = logging.getLogger(__name__)

# Certs are almost always 1–2 pages. Cap anyway so a mis-uploaded book
# can't stall the extractor.
MAX_PAGES = 10
MAX_CHARS = 40_000

_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")
        _client = AsyncOpenAI(api_key=api_key)
    return _client


_PROMPT = (
    "You are extracting fields from a single factory / product certification "
    "document (e.g. ISO 9001, BSCI, CE, FDA, Sedex, REACH). Return a JSON "
    "object with these fields, or omit / use null for anything the document "
    "does not clearly state — do NOT guess.\n\n"
    "Fields:\n"
    "- cert_type (string): short standard code — 'ISO 9001', 'ISO 14001', "
    "'ISO 45001', 'CE', 'UL', 'RoHS', 'REACH', 'BSCI', 'SA8000', 'FDA', "
    "'Sedex'. If the document shows a longer name ('ISO 9001:2015 Quality "
    "Management System'), return just the code. If none of the common codes "
    "fit, return the short name the document itself uses.\n"
    "- cert_number (string): the certificate / registration number exactly as "
    "printed. Do not invent separators.\n"
    "- issuing_body (string): the body that issued the certificate (e.g. "
    "'SGS', 'TÜV Rheinland', 'Bureau Veritas'). Strip country suffixes like "
    "'China' only if they are clearly locational and not part of the legal "
    "name.\n"
    "- issue_date (string, ISO-8601 YYYY-MM-DD): the date the certificate was "
    "issued / effective from. If the document prints a range (e.g. "
    "'2023-06-14 to 2026-06-13'), use the start date here.\n"
    "- expiry_date (string, ISO-8601 YYYY-MM-DD): the valid-until date.\n"
    "- notes (string): a single short sentence summarising the scope if the "
    "document calls one out (e.g. 'Manufacture of sports footwear'). Leave "
    "null if the scope is not explicitly written.\n\n"
    "Return ONLY a single JSON object. No markdown, no prose around it."
)


def _extract_pdf_text(pdf_bytes: bytes) -> str:
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


def _image_mime_for(source_url: str) -> str:
    name = source_url.lower()
    if name.endswith(".png"):
        return "image/png"
    if name.endswith(".jpg") or name.endswith(".jpeg"):
        return "image/jpeg"
    raise RuntimeError(f"unsupported image extension for {source_url!r}")


async def _call_model(user_content) -> CertificationDraft:
    """Run one model call + validate. Used identically for PDF and image branches."""
    client = _get_client()
    response = await client.chat.completions.create(
        model="gpt-5.4",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _PROMPT},
            {"role": "user", "content": user_content},
        ],
    )
    raw = (response.choices[0].message.content or "").strip()
    data = json.loads(raw)
    return CertificationDraft.model_validate(data)


async def extract(file_bytes: bytes, source_url: str) -> CertificationDraft:
    """Extract a CertificationDraft from cert bytes. Retries once on failure.

    ``source_url`` is inspected only for its extension — the actual HTTP
    fetch already happened in the runner.
    """
    url = source_url.lower()
    is_pdf = url.endswith(".pdf")
    is_image = url.endswith(".png") or url.endswith(".jpg") or url.endswith(".jpeg")
    if not (is_pdf or is_image):
        raise RuntimeError(f"unsupported file extension in {source_url!r}")

    if is_pdf:
        text = _extract_pdf_text(file_bytes)
        if not text:
            # Visual-only PDF (scanned cert without OCR). Bubble up so the
            # runner can surface a clear error; we don't fall through to
            # vision here because we don't know the page count is small.
            raise RuntimeError("no extractable text in PDF (likely scanned image)")
        user_content = f"Document text:\n\n{text}"
    else:
        mime = _image_mime_for(source_url)
        b64 = base64.b64encode(file_bytes).decode("ascii")
        user_content = [
            {"type": "text", "text": "Extract the fields from this certificate image."},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
            },
        ]

    last_error: Optional[Exception] = None
    for attempt in (1, 2):
        try:
            draft = await _call_model(user_content)
            logger.info(
                "certification_extractor: attempt %d ok (fields populated=%d)",
                attempt,
                sum(1 for v in draft.model_dump().values() if v),
            )
            return draft
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(
                "certification_extractor: parse failure on attempt %d: %s",
                attempt, e,
            )
            last_error = e
        except Exception as e:
            logger.error("certification_extractor: unexpected error: %s", e)
            raise

    raise RuntimeError(f"extraction failed after retry: {last_error}")
