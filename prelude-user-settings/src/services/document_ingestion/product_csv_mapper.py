"""Product-CSV / XLSX mapper (M6).

Two-phase flow (plan §7.2)
--------------------------

Phase 1 (runner):
    * Read the uploaded file into a ``pandas.DataFrame``.
    * Take ``source_headers``, a 3-row ``sample_rows`` preview, and ``row_count``.
    * Ask ``gpt-5.4`` to propose a mapping from each source header → one of our
      :class:`ProductRecordDraft` targets or ``ignore``.
    * Persist ``{proposed_mapping, source_headers, sample_rows, row_count}`` on
      the job's ``draft_payload`` and leave the job in ``ready_for_review``.

Phase 2 (``POST /ingestion/jobs/{id}/apply-mapping``):
    * Re-download the source file, re-read the DataFrame.
    * For XLSX, walk the zip for embedded product photos anchored to rows.
    * Run :func:`apply_mapping` → ``list[ProductRecordDraft]``.
    * Upload any embedded images to GCS and attach as ``image_url`` on the
      matching row.
    * Overwrite ``draft_payload`` with the full product list and keep the job
      at ``ready_for_review`` for the review-table step.

The :func:`apply_mapping` function itself is pure — image uploads live in
:func:`finalize_with_embedded_images` so the mapper stays easy to unit-test.
"""

from __future__ import annotations

import io
import json
import logging
import os
import zipfile
from typing import Any, Optional
from xml.etree import ElementTree as ET

import pandas as pd
from openai import AsyncOpenAI
from pydantic import ValidationError

from services.document_ingestion.schemas import (
    PriceRange,
    ProductRecordDraft,
)
from utils.gcs import upload_bytes

logger = logging.getLogger(__name__)


# XLSX uses these XML namespaces. Declared globally so the anchor walker below
# stays readable.
_NS = {
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


# Mapping targets the frontend modal exposes. Kept in lock-step with the
# fields on :class:`ProductRecordDraft`. Free-form spec keys take the shape
# ``specs.<label>`` — the label is whatever the source header was.
_TARGETS = {
    "name",
    "description",
    "moq",
    "price_range.min",
    "price_range.max",
    "price_range.currency",
    "price_range.unit",
    "image_url",
    "hs_code_suggestion",
    "ignore",
}


# -------- file reading --------

def read_table(data: bytes, filename: str) -> tuple[pd.DataFrame, str]:
    """Parse a CSV or XLSX upload into a DataFrame.

    Returns (df, ext) where ``ext`` is ``.csv`` or ``.xlsx``.
    Multi-sheet workbooks default to the first sheet — we log a warning so
    the runner can surface it if we want to later.
    """
    name = (filename or "").lower()
    if name.endswith(".xlsx"):
        buf = io.BytesIO(data)
        # Peek sheet count so we can log if we're dropping data.
        try:
            xl = pd.ExcelFile(buf, engine="openpyxl")
            if len(xl.sheet_names) > 1:
                logger.warning(
                    "product_csv_mapper: xlsx has %d sheets, using first (%r)",
                    len(xl.sheet_names), xl.sheet_names[0],
                )
            # ``keep_default_na=False`` + empty ``na_values`` keeps cells like
            # "-", "NA", "N/A", "—" intact as strings instead of pandas
            # silently converting them to NaN and wiping user data.
            df = xl.parse(
                xl.sheet_names[0],
                dtype=str,
                keep_default_na=False,
                na_values=[],
            )
        finally:
            buf.close()
        logger.info(
            "product_csv_mapper: xlsx read (rows=%d cols=%d headers=%r)",
            len(df), len(df.columns), list(df.columns)[:20],
        )
        return df, ".xlsx"

    # CSV — default UTF-8, fall back to cp1252 which covers most Windows exports.
    try:
        df = pd.read_csv(io.BytesIO(data), dtype=str, keep_default_na=False)
    except UnicodeDecodeError:
        df = pd.read_csv(
            io.BytesIO(data), dtype=str, keep_default_na=False, encoding="cp1252",
        )
    logger.info(
        "product_csv_mapper: csv read (rows=%d cols=%d headers=%r)",
        len(df), len(df.columns), list(df.columns)[:20],
    )
    return df, ".csv"


def sample_rows(df: pd.DataFrame, n: int = 3) -> list[dict[str, str]]:
    """First ``n`` rows as plain ``str → str`` dicts (for the preview modal)."""
    out: list[dict[str, str]] = []
    for _, row in df.head(n).iterrows():
        out.append({str(k): _stringify(v) for k, v in row.items()})
    return out


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


# -------- embedded xlsx images --------

def extract_xlsx_images(xlsx_bytes: bytes) -> dict[int, tuple[bytes, str]]:
    """Return embedded product photos anchored to data rows.

    Key is the 0-based **data-row index** (i.e. df.iloc row index; the header
    row is row 0 in the sheet and row -1 in the data). Value is
    ``(image_bytes, extension_with_dot)``.

    We only look at the first sheet — matches :func:`read_table`'s default.
    Missing / malformed drawings are logged and skipped; an xlsx with no
    embedded images returns an empty dict.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(xlsx_bytes))
    except zipfile.BadZipFile:
        logger.warning("product_csv_mapper: not a valid xlsx zip")
        return {}

    try:
        names = set(zf.namelist())
        # Find the first sheet's drawing, if any. ``xl/workbook.xml`` declares
        # the sheet order; the first sheet is conventionally sheet1.xml.
        sheet_rels_name = "xl/worksheets/_rels/sheet1.xml.rels"
        if sheet_rels_name not in names:
            return {}

        drawing_target = _resolve_relationship(
            zf, sheet_rels_name,
            rel_type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing",
        )
        if not drawing_target:
            return {}

        # Relationship Targets resolve relative to the SOURCE part's directory
        # (the xml file the rels describe), not the rels file's own directory.
        # sheet1.xml.rels describes xl/worksheets/sheet1.xml → source dir is
        # xl/worksheets/; target "../drawings/drawing1.xml" → xl/drawings/…
        drawing_path = _normalize_zip_path("xl/worksheets/", drawing_target)
        if drawing_path not in names:
            logger.warning(
                "product_csv_mapper: drawing relationship points at %s (missing)",
                drawing_path,
            )
            return {}

        # The drawing's own rels resolve relative to the drawing file's dir.
        drawing_rels_path = _rels_for(drawing_path)
        drawing_dir = os.path.dirname(drawing_path) + "/"
        rel_map = _load_rels(zf, drawing_rels_path) if drawing_rels_path in names else {}

        # Walk anchors and collect (row, rel_id) pairs.
        results: dict[int, tuple[bytes, str]] = {}
        try:
            drawing_xml = zf.read(drawing_path)
        except KeyError:
            return {}
        root = ET.fromstring(drawing_xml)
        anchors: list[ET.Element] = []
        anchors.extend(root.findall("xdr:twoCellAnchor", _NS))
        anchors.extend(root.findall("xdr:oneCellAnchor", _NS))
        for anchor in anchors:
            from_el = anchor.find("xdr:from", _NS)
            if from_el is None:
                continue
            row_el = from_el.find("xdr:row", _NS)
            if row_el is None or not (row_el.text or "").strip().isdigit():
                continue
            sheet_row = int(row_el.text.strip())
            # Anchor's row is 0-based. pandas (default header=0) consumes row 0
            # as the header, so the first data row is sheet_row=1 → data_idx=0.
            data_idx = sheet_row - 1
            if data_idx < 0:
                continue

            # pic/blipFill/blip carries the r:embed rel id.
            blip = anchor.find(".//a:blip", _NS)
            if blip is None:
                continue
            rel_id = blip.attrib.get(f"{{{_NS['r']}}}embed")
            if not rel_id or rel_id not in rel_map:
                continue
            media_target = rel_map[rel_id]
            media_path = _normalize_zip_path(drawing_dir, media_target)
            if media_path not in names:
                continue
            try:
                img_bytes = zf.read(media_path)
            except KeyError:
                continue
            ext = os.path.splitext(media_path)[1].lower() or ".png"
            # If multiple images anchor to the same row, keep the first (most
            # common: one product photo per row).
            results.setdefault(data_idx, (img_bytes, ext))

        return results
    finally:
        zf.close()


def _resolve_relationship(zf: zipfile.ZipFile, rels_path: str, *, rel_type: str) -> Optional[str]:
    try:
        xml = zf.read(rels_path)
    except KeyError:
        return None
    root = ET.fromstring(xml)
    for rel in root.findall("rel:Relationship", _NS):
        if rel.attrib.get("Type") == rel_type:
            return rel.attrib.get("Target")
    return None


def _load_rels(zf: zipfile.ZipFile, rels_path: str) -> dict[str, str]:
    """Return ``{Id: Target}`` for one .rels file."""
    try:
        xml = zf.read(rels_path)
    except KeyError:
        return {}
    root = ET.fromstring(xml)
    out: dict[str, str] = {}
    for rel in root.findall("rel:Relationship", _NS):
        rid = rel.attrib.get("Id")
        target = rel.attrib.get("Target")
        if rid and target:
            out[rid] = target
    return out


def _rels_for(file_path: str) -> str:
    """``xl/drawings/drawing1.xml`` → ``xl/drawings/_rels/drawing1.xml.rels``."""
    directory, base = os.path.split(file_path)
    return f"{directory}/_rels/{base}.rels" if directory else f"_rels/{base}.rels"


def _normalize_zip_path(base_dir: str, target: str) -> str:
    """Resolve a relationship Target relative to its source-part directory.

    OOXML allows two Target shapes:
    * absolute — starts with ``/``, resolves from the package root. openpyxl
      writes these.
    * relative — e.g. ``../drawings/drawing1.xml``, resolves from ``base_dir``.
    """
    if target.startswith("/"):
        combined = target.lstrip("/")
    else:
        combined = base_dir.rstrip("/") + "/" + target
    parts = combined.split("/")
    out: list[str] = []
    for part in parts:
        if not part or part == ".":
            continue
        if part == "..":
            if out:
                out.pop()
            continue
        out.append(part)
    return "/".join(out)


# -------- OpenAI mapping proposal --------

_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")
        _client = AsyncOpenAI(api_key=api_key)
    return _client


_MAPPING_PROMPT = (
    "You are mapping columns from a factory's product-catalog spreadsheet to "
    "our product schema. Return a JSON object with one key `mapping` — an "
    "object whose keys are the user's source headers (verbatim) and values "
    "are one of the allowed targets.\n\n"
    "Allowed targets:\n"
    "- name, description, moq, hs_code_suggestion, image_url\n"
    "- price_range.min, price_range.max, price_range.currency, price_range.unit\n"
    "- specs.<label>  — use this for spec / attribute columns (material, "
    "wattage, dimensions, color, etc.). <label> should be the human-readable "
    "name for the spec. You can invent a clean label (e.g. `specs.Material`).\n"
    "- ignore  — use when the column is clearly not part of the product record "
    "(internal IDs, notes to self, blank columns).\n\n"
    "Rules:\n"
    "- Every input header must appear exactly once in the mapping.\n"
    "- At most one header maps to `name`; pick the best candidate even if "
    "you're unsure. If no column looks like a product name at all, map the "
    "most plausible one to `name` anyway.\n"
    "- If only one price column exists, map it to `price_range.min`.\n"
    "- `image_url` is for columns of URLs pointing at product photos "
    "(whether http/https, gs://, or already-on-GCS links).\n"
    "- Use sample rows to disambiguate. For example, `Unit: USD` implies "
    "price_range.currency, not price_range.unit; `Unit: piece` implies "
    "price_range.unit, not currency.\n\n"
    "Return ONLY a single JSON object. No markdown, no prose."
)


async def propose_mapping(
    headers: list[str],
    sample_rows_preview: list[dict[str, str]],
) -> dict[str, str]:
    """One OpenAI call → ``{header: target}`` for every input header."""
    client = _get_client()
    payload = {
        "source_headers": headers,
        "sample_rows": sample_rows_preview[:3],
    }
    logger.info(
        "product_csv_mapper: proposing mapping (headers=%r, sample_rows=%d)",
        headers[:20], len(sample_rows_preview),
    )
    last_error: Optional[Exception] = None
    for attempt in (1, 2):
        try:
            response = await client.chat.completions.create(
                model="gpt-5.4",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": _MAPPING_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False),
                    },
                ],
            )
            raw = (response.choices[0].message.content or "").strip()
            data = json.loads(raw)
            mapping = data.get("mapping")
            if not isinstance(mapping, dict):
                raise ValueError("response missing dict `mapping`")
            cleaned = _sanitize_mapping(headers, mapping)
            logger.info(
                "product_csv_mapper: mapping proposed %r", cleaned,
            )
            return cleaned
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(
                "product_csv_mapper: parse failure on attempt %d: %s", attempt, e,
            )
            last_error = e
        except Exception as e:
            logger.error("product_csv_mapper: openai error: %s", e)
            raise
    # Defensive fallback: everything ignored. The user can still fix it in
    # the modal — beats failing the job outright.
    logger.warning(
        "product_csv_mapper: giving up on OpenAI mapping after retries (%s); "
        "returning all-ignore", last_error,
    )
    return {h: "ignore" for h in headers}


def _sanitize_mapping(headers: list[str], raw: dict[str, Any]) -> dict[str, str]:
    """Force the model's output into the contract: every header present, each
    value an allowed target or a ``specs.*`` free-form.
    """
    out: dict[str, str] = {}
    for h in headers:
        value = raw.get(h)
        if not isinstance(value, str):
            out[h] = "ignore"
            continue
        v = value.strip()
        if v in _TARGETS:
            out[h] = v
        elif v.startswith("specs.") and len(v) > len("specs."):
            out[h] = v
        else:
            out[h] = "ignore"
    return out


# -------- apply_mapping --------

def apply_mapping(
    df: pd.DataFrame,
    mapping: dict[str, str],
) -> tuple[list[ProductRecordDraft], list[int]]:
    """Coerce DataFrame rows into ``ProductRecordDraft`` objects per the mapping.

    Returns ``(products, data_row_indices)``. The two lists are aligned by
    position — ``data_row_indices[i]`` is the 0-based index in ``df`` of the
    row that produced ``products[i]``. The second list is used by the xlsx
    image path to attach embedded photos back onto the right product after
    rows with blank names have been dropped.

    Pure function — no I/O, no GCS. Image uploads live in
    :func:`finalize_with_embedded_images`.
    """
    products: list[ProductRecordDraft] = []
    row_indices: list[int] = []
    headers = list(df.columns)
    slot_targets = {h: mapping.get(str(h), "ignore") for h in headers}

    for data_idx, (_, row) in enumerate(df.iterrows()):
        fields: dict[str, Any] = {}
        specs: dict[str, str] = {}
        price: dict[str, Any] = {}

        for header, target in slot_targets.items():
            if target == "ignore":
                continue
            text = _stringify(row.get(header))
            if not text:
                continue
            if target == "name":
                fields["name"] = text
            elif target == "description":
                fields["description"] = text
            elif target == "moq":
                fields["moq"] = _coerce_int(text)
            elif target == "hs_code_suggestion":
                fields["hs_code_suggestion"] = text
            elif target == "image_url":
                fields["image_url"] = text
            elif target == "price_range.min":
                price["min"] = _coerce_float(text)
            elif target == "price_range.max":
                price["max"] = _coerce_float(text)
            elif target == "price_range.currency":
                price["currency"] = text
            elif target == "price_range.unit":
                price["unit"] = text
            elif target.startswith("specs."):
                label = target[len("specs."):].strip() or str(header)
                specs[label] = text

        if not fields.get("name"):
            continue  # required field missing, drop the row

        if specs:
            fields["specs"] = specs
        if any(v is not None for v in price.values()):
            fields["price_range"] = PriceRange(**price)

        try:
            products.append(ProductRecordDraft(**fields))
            row_indices.append(data_idx)
        except ValidationError as e:
            logger.warning(
                "product_csv_mapper: row %d validation failed: %s", data_idx, e,
            )
            continue

    return products, row_indices


def _coerce_int(text: str) -> Optional[int]:
    """Parse an int from a string that may contain commas, currency, or units."""
    # Strip everything but digits and a leading minus.
    s = text.replace(",", "").strip()
    # Keep leading sign, drop trailing non-numeric (e.g. "300 pcs" → "300").
    sign = ""
    if s.startswith(("-", "+")):
        sign, s = s[0], s[1:]
    digits = ""
    for ch in s:
        if ch.isdigit():
            digits += ch
        elif digits:
            break
    if not digits:
        return None
    try:
        return int(sign + digits)
    except ValueError:
        return None


def _coerce_float(text: str) -> Optional[float]:
    """Parse a float from a string that may contain commas, currency, or units."""
    s = text.replace(",", "").strip()
    sign = ""
    if s.startswith(("-", "+")):
        sign, s = s[0], s[1:]
    buf = ""
    seen_dot = False
    for ch in s:
        if ch.isdigit():
            buf += ch
        elif ch == "." and not seen_dot and buf:
            buf += ch
            seen_dot = True
        elif buf:
            break
    if not buf or buf == ".":
        return None
    try:
        return float(sign + buf)
    except ValueError:
        return None


# -------- embedded image upload (I/O) --------

_CONTENT_TYPE_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


def finalize_with_embedded_images(
    products: list[ProductRecordDraft],
    images_by_row: dict[int, tuple[bytes, str]],
    *,
    job_id: str,
    email: str,
    df_row_indices: list[int],
) -> list[ProductRecordDraft]:
    """Upload one embedded image per product row that has one.

    ``df_row_indices`` aligns with ``products`` (same length, same order) and
    carries the original DataFrame row index for each product — needed because
    :func:`apply_mapping` drops rows with missing names, so positional index
    in the output list ≠ index in the sheet.

    Rows where the user mapped an ``image_url`` column keep that URL; we only
    fill rows that came out with ``image_url=None`` and have an embedded
    image anchored to them.
    """
    if len(df_row_indices) != len(products):
        logger.warning(
            "product_csv_mapper: row-index list length mismatch (%d vs %d); "
            "skipping image attachment",
            len(df_row_indices), len(products),
        )
        return products

    for out_idx, product in enumerate(products):
        if product.image_url:
            continue
        data_row_idx = df_row_indices[out_idx]
        img = images_by_row.get(data_row_idx)
        if not img:
            continue
        data, ext = img
        content_type = _CONTENT_TYPE_BY_EXT.get(ext, "application/octet-stream")
        try:
            url = upload_bytes(
                data,
                folder=f"ingestion/product/{job_id}",
                email=email,
                file_id=f"csv_{data_row_idx}",
                ext=ext,
                content_type=content_type,
            )
            product.image_url = url
        except Exception as e:
            logger.warning(
                "product_csv_mapper: upload failed for data row %d: %s",
                data_row_idx, e,
            )
    return products


