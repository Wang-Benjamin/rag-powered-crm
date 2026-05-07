"""Product-PDF extractor (M5).

Turns a product catalog / brochure PDF into a :class:`ProductCatalogDraft`
with per-product cropped thumbnails.

Three-step pipeline
-------------------

1. **Structured text extraction.** ``pdfplumber`` text pre-pass (plan §11) →
   ``gpt-5.4`` ``json_object`` returning a list of products. Each product
   carries an optional ``image_hint`` ``{page_number, bbox}`` where ``bbox``
   is ``[x0, y0, x1, y1]`` in page-relative 0–1 coordinates.
2. **Image crop + upload.** For every product that came back with an
   ``image_hint``: render the page with ``pdf2image.convert_from_bytes``,
   crop the bbox with Pillow, upload the PNG via :func:`utils.gcs.upload_bytes`,
   and set ``image_url`` on the record.
3. **Graceful fallback.** Any failure in step 2 for a single product leaves
   its ``image_url`` at ``None``; the record still ships. The runner never
   fails the whole job because a thumbnail couldn't be cropped — text is
   the load-bearing part.

Library choice notes (DOC_INGESTION_CODING_PLAN §6.1, §10)
----------------------------------------------------------
* ``pdf2image`` + ``Pillow`` are both MIT. Do **not** swap to ``PyMuPDF``
  (AGPL) — that would force a license review of the whole service.
* ``pdf2image`` shells out to ``poppler-utils`` — make sure the Docker
  runtime stage installs it (already done in the user-settings Dockerfile).
"""

from __future__ import annotations

import io
import json
import logging
import os
from typing import Any, Optional

from openai import AsyncOpenAI
from pydantic import ValidationError

from services.document_ingestion.schemas import (
    ProductCatalogDraft,
    ProductRecordDraft,
)
from utils.gcs import upload_bytes

logger = logging.getLogger(__name__)

# Plan §11: cap at 50 pages, truncate text to keep one call under model context.
MAX_PAGES = 50
MAX_CHARS = 120_000

# Rendering DPI for image crops. 150 is a good balance: tall product photos
# stay readable and a 10-page brochure renders in < 5 seconds on CPU.
RENDER_DPI = 150

# Crop budget: at most this many thumbnails per job. Defensive — a model that
# hallucinates a bbox for every line-item in a dense table could otherwise
# generate hundreds of crops. Onboarding catalogs rarely exceed this.
MAX_CROPS = 60

_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")
        _client = AsyncOpenAI(api_key=api_key)
    return _client


def _extract_text_with_pages(pdf_bytes: bytes) -> tuple[str, int]:
    """Text pre-pass. Returns (joined_text, page_count)."""
    import pdfplumber

    chunks: list[str] = []
    page_count = 0
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for idx, page in enumerate(pdf.pages):
            if idx >= MAX_PAGES:
                break
            page_count = idx + 1
            text = page.extract_text() or ""
            # Tag each page so the model can emit correct page_number hints.
            chunks.append(f"[[page {idx + 1}]]\n{text}" if text else f"[[page {idx + 1}]]")
    joined = "\n\n".join(chunks).strip()
    if len(joined) > MAX_CHARS:
        joined = joined[:MAX_CHARS]
    return joined, page_count


_PROMPT = (
    "You are extracting a product catalog from a factory / manufacturer "
    "brochure. Return a JSON object with a single key `products` — an array "
    "of product objects. If the document is not a product catalog, return "
    "`{\"products\": []}`.\n\n"
    "Each product object has these fields (omit / null for anything the "
    "document does not clearly state — do NOT invent values):\n"
    "- name (string, required): the product name as printed. Language: match the source document.\n"
    "- description (string): 1–2 sentence summary. Language: match source.\n"
    "- specs (object of string → string): key-value pairs from the product's spec "
    "table, e.g. {\"Material\": \"Aluminum\", \"Wattage\": \"50W\"}. Use spec "
    "names and values verbatim from the document.\n"
    "\n"
    "IMPORTANT — collapse size/variant rows. When the document lists multiple "
    "sizes / colors / wattages / lengths that SHARE the same hero photo, "
    "material, and description, emit ONE product — not one per variant. Put "
    "the variant list into `specs` under a single key, picking a key name that "
    "fits the document (e.g. \"Sizes\", \"规格\", \"Wattage options\", "
    "\"Available colors\"). The value is the comma-separated variant list "
    "in the document's language. Only emit separate products when the items "
    "have meaningfully different attributes (different material, different "
    "product family, different hero photo).\n"
    "\n"
    "- moq (integer): minimum order quantity in pieces. Integer only, no units.\n"
    "- price_range (object): {min: number, max: number, currency: string, unit: string}. "
    "`unit` is the unit the price is quoted per, e.g. \"piece\", \"carton\". "
    "Use a single value for both min and max if only one price is shown.\n"
    "- hs_code_suggestion (string): HS code if the document prints one.\n"
    "- image_hint (object or null): a pointer to the product photo in the PDF.\n"
    "    - page_number (1-indexed int): ALWAYS return this if you can tell which "
    "page the product appears on — use the `[[page N]]` markers in the text "
    "below to figure this out. This is the most important field.\n"
    "    - bbox ([x0, y0, x1, y1], optional): 0–1 page-relative coordinates "
    "(0,0 = top-left, 1,1 = bottom-right). Only include if you are confident "
    "where the photo sits; omit when the page likely contains one hero photo "
    "for the product — we will render the whole page as the thumbnail.\n"
    "    - Return image_hint: null ONLY when the document shows no photo for this product.\n\n"
    "The text below is extracted page-by-page with `[[page N]]` markers — use "
    "them to assign `page_number` for every product you extract. When in doubt, "
    "set page_number but omit bbox — this is the safer call for us.\n\n"
    "Return ONLY a single JSON object. No markdown, no prose around it."
)


async def _call_openai(text: str) -> dict[str, Any]:
    """One OpenAI call; returns parsed JSON dict. Retries once on parse failure."""
    client = _get_client()
    last_error: Optional[Exception] = None

    for attempt in (1, 2):
        try:
            response = await client.chat.completions.create(
                model="gpt-5.4",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": _PROMPT},
                    {"role": "user", "content": f"Document text:\n\n{text}"},
                ],
            )
            raw = (response.choices[0].message.content or "").strip()
            data = json.loads(raw)
            if not isinstance(data, dict) or "products" not in data:
                raise ValueError("response missing 'products' key")
            return data
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(
                "product_pdf_extractor: parse failure on attempt %d: %s", attempt, e,
            )
            last_error = e
        except Exception as e:
            logger.error("product_pdf_extractor: openai error: %s", e)
            raise

    raise RuntimeError(f"extraction failed after retry: {last_error}")


def _validate_products(raw_products: list[dict]) -> list[tuple[ProductRecordDraft, Optional[dict]]]:
    """Split each raw product into (ProductRecordDraft, image_hint_or_none).

    Invalid rows are dropped with a warning — a single bad row shouldn't sink
    the whole catalog.
    """
    out: list[tuple[ProductRecordDraft, Optional[dict]]] = []
    for idx, raw in enumerate(raw_products):
        if not isinstance(raw, dict):
            logger.warning("product_pdf_extractor: row %d not an object, skipping", idx)
            continue
        hint = raw.pop("image_hint", None)
        try:
            draft = ProductRecordDraft.model_validate(raw)
        except ValidationError as e:
            logger.warning(
                "product_pdf_extractor: row %d failed validation, skipping: %s",
                idx, e,
            )
            continue
        out.append((draft, hint if isinstance(hint, dict) else None))
    return out


def _render_or_crop(
    pdf_bytes: bytes,
    *,
    page_number: int,
    bbox: Optional[list[float]],
) -> Optional[bytes]:
    """Render a page, optionally crop to bbox, return PNG bytes.

    When ``bbox`` is missing or unusable, returns the full page — factory
    catalogs are typically one-hero-photo-per-page, so a page render is a
    useful thumbnail even without a tight crop.
    """
    try:
        from pdf2image import convert_from_bytes
    except ImportError:
        logger.error("product_pdf_extractor: pdf2image not installed")
        return None

    if page_number < 1:
        return None

    try:
        images = convert_from_bytes(
            pdf_bytes,
            dpi=RENDER_DPI,
            first_page=page_number,
            last_page=page_number,
        )
    except Exception as e:
        logger.warning(
            "product_pdf_extractor: render failed for page %d: %s",
            page_number, e,
        )
        return None
    if not images:
        return None
    page_img = images[0]
    w, h = page_img.size

    # Default crop: top 70% of the page. Factory catalogs put the hero photo
    # at the top and spec text at the bottom; we've already extracted the
    # text via pdfplumber + the LLM, so the footer is redundant in the
    # thumbnail. A model-supplied bbox overrides this.
    x0, y0, x1, y1 = 0.0, 0.0, 1.0, 0.70
    if bbox and isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        try:
            bx0, by0, bx1, by1 = [float(v) for v in bbox]
            bx0, bx1 = sorted([max(0.0, min(1.0, bx0)), max(0.0, min(1.0, bx1))])
            by0, by1 = sorted([max(0.0, min(1.0, by0)), max(0.0, min(1.0, by1))])
            if bx1 - bx0 >= 0.02 and by1 - by0 >= 0.02:
                x0, y0, x1, y1 = bx0, by0, bx1, by1
        except (TypeError, ValueError) as e:
            logger.warning("product_pdf_extractor: bad bbox %r: %s", bbox, e)

    left, upper = int(x0 * w), int(y0 * h)
    right, lower = int(x1 * w), int(y1 * h)
    cropped_region = (
        page_img.crop((left, upper, right, lower))
        if right > left and lower > upper
        else page_img
    )

    try:
        buf = io.BytesIO()
        cropped_region.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        logger.warning("product_pdf_extractor: encode failed: %s", e)
        return None


async def extract(
    pdf_bytes: bytes,
    *,
    job_id: str,
    email: str,
) -> ProductCatalogDraft:
    """Extract a ProductCatalogDraft from a brochure PDF."""
    text, page_count = _extract_text_with_pages(pdf_bytes)
    if not text or page_count == 0:
        raise RuntimeError("no extractable text in PDF (likely image-only)")

    data = await _call_openai(text)
    raw_products = data.get("products") or []
    if not isinstance(raw_products, list):
        raise RuntimeError("'products' field was not a list")

    validated = _validate_products(raw_products)
    hint_count = sum(1 for _, hint in validated if hint)
    logger.info(
        "product_pdf_extractor: got %d raw / %d validated products / %d with image_hint",
        len(raw_products), len(validated), hint_count,
    )
    if hint_count == 0 and validated:
        # Log first raw product so we can see what shape the model returned —
        # tells us whether the model is omitting image_hint, returning a
        # different key, or returning null.
        logger.warning(
            "product_pdf_extractor: zero image_hints; first raw product=%r",
            raw_products[0] if raw_products else None,
        )

    # Step 2 — render page and (optionally) crop per product, with a graceful
    # per-row fallback. Rendered pages are memoized so a catalog with N
    # products on the same page only hits pdf2image once.
    page_cache: dict[int, Optional[bytes]] = {}
    cropped_count = 0
    for idx, (draft, hint) in enumerate(validated):
        if cropped_count >= MAX_CROPS:
            break
        if not hint:
            continue
        page_number = hint.get("page_number")
        bbox = hint.get("bbox")
        if not isinstance(page_number, int):
            continue

        # Cache by (page, bbox-or-none). When bbox is present we re-crop; when
        # not, reuse the full page render across products on the same page.
        cache_key = (page_number, tuple(bbox) if isinstance(bbox, list) and len(bbox) == 4 else None)
        if cache_key not in page_cache:
            page_cache[cache_key] = _render_or_crop(
                pdf_bytes, page_number=page_number, bbox=bbox if cache_key[1] else None,
            )
        png = page_cache[cache_key]
        if not png:
            continue
        try:
            url = upload_bytes(
                png,
                folder=f"ingestion/product/{job_id}",
                email=email,
                file_id=str(idx),
                ext=".png",
                content_type="image/png",
            )
            draft.image_url = url
            cropped_count += 1
        except Exception as e:
            logger.warning(
                "product_pdf_extractor: upload failed for row %d: %s", idx, e,
            )

    logger.info(
        "product_pdf_extractor: cropped %d of %d products (unique pages rendered=%d)",
        cropped_count, len(validated), len(page_cache),
    )

    return ProductCatalogDraft(
        products=[draft for draft, _ in validated],
        column_mapping=None,
    )
