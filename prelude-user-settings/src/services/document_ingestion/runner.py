"""Background job runner for ingestion.

Dispatches a queued ``ingestion_jobs`` row to the right extractor based on
``kind``, writes the draft (or error) back onto the row. M3 implements the
``company_profile`` branch only; later milestones add the other three.

Called via FastAPI ``BackgroundTasks`` after the upload endpoint has
returned. Because it runs after the request, it cannot borrow the request's
connection — it re-acquires one from the tenant pool manager.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from data.repositories import ingestion_repository
from services.document_ingestion import (
    certification_extractor,
    company_profile_extractor,
    product_csv_mapper,
    product_pdf_extractor,
)
from service_core.db import get_pool_manager
from utils.gcs import download_bytes

logger = logging.getLogger(__name__)


async def run_job(job_id: uuid.UUID, email: str, db_name: str) -> None:
    """Run extraction for one job. Never raises — writes failure to the row."""
    logger.info(f"runner: start job_id={job_id} email={email} db={db_name}")

    pm = get_pool_manager()

    async def _set_status(status: str, *, draft: Optional[dict] = None, err: Optional[str] = None):
        async with pm.acquire(db_name) as conn:
            await ingestion_repository.update_job_status(
                conn, job_id, status, draft_payload=draft, error=err,
            )

    # 1. Load the job and flip to processing.
    try:
        async with pm.acquire(db_name) as conn:
            job = await ingestion_repository.get_job(conn, job_id, email)
        if not job:
            logger.error(f"runner: job {job_id} not found for {email}")
            return
        await _set_status("processing")
    except Exception as e:
        logger.exception(f"runner: failed to start job {job_id}: {e}")
        try:
            await _set_status("failed", err=f"runner bootstrap failed: {e}")
        except Exception:
            pass
        return

    # 2. Dispatch. Only company_profile is wired in M3.
    try:
        source_url = job["source_url"]
        kind = job["kind"]

        if kind == "company_profile":
            pdf_bytes = download_bytes(source_url)
            draft = await company_profile_extractor.extract(pdf_bytes)
            draft_payload = draft.model_dump(mode="json")
            await _set_status("ready_for_review", draft=draft_payload)
            logger.info(f"runner: job {job_id} ready_for_review")
            return

        if kind == "certification":
            file_bytes = download_bytes(source_url)
            draft = await certification_extractor.extract(file_bytes, source_url)
            draft_payload = draft.model_dump(mode="json")
            await _set_status("ready_for_review", draft=draft_payload)
            logger.info(f"runner: job {job_id} ready_for_review")
            return

        if kind == "product_pdf":
            pdf_bytes = download_bytes(source_url)
            draft = await product_pdf_extractor.extract(
                pdf_bytes, job_id=str(job_id), email=email,
            )
            draft_payload = draft.model_dump(mode="json")
            await _set_status("ready_for_review", draft=draft_payload)
            logger.info(
                f"runner: job {job_id} ready_for_review "
                f"(products={len(draft.products)})"
            )
            return

        if kind == "product_csv":
            # M6: propose the mapping AND apply it in one pass so the user
            # lands straight in the review table. The review table exposes a
            # "Re-map columns" button that re-opens the mapping modal for
            # the rare case where the LLM misidentified a whole column — that
            # button calls POST /jobs/{id}/apply-mapping with the corrected
            # mapping.
            file_bytes = download_bytes(source_url)
            df, ext = product_csv_mapper.read_table(file_bytes, source_url)
            headers = [str(c) for c in df.columns]
            preview = product_csv_mapper.sample_rows(df, n=3)
            proposed = await product_csv_mapper.propose_mapping(headers, preview)
            products, data_row_indices = product_csv_mapper.apply_mapping(
                df, proposed,
            )
            if ext == ".xlsx":
                images_by_row = product_csv_mapper.extract_xlsx_images(file_bytes)
                if images_by_row:
                    products = product_csv_mapper.finalize_with_embedded_images(
                        products, images_by_row,
                        job_id=str(job_id),
                        email=email,
                        df_row_indices=data_row_indices,
                    )
            draft_payload = {
                "products": [p.model_dump(mode="json") for p in products],
                "column_mapping": proposed,
                "proposed_mapping": proposed,
                "source_headers": headers,
                "sample_rows": preview,
                "row_count": int(len(df)),
                "file_ext": ext,
            }
            await _set_status("ready_for_review", draft=draft_payload)
            logger.info(
                f"runner: job {job_id} ready_for_review "
                f"(csv headers={len(headers)} rows={len(df)} products={len(products)})"
            )
            return

        await _set_status("failed", err=f"kind {kind!r} not yet supported")
        logger.warning(f"runner: job {job_id} kind={kind} not implemented yet")

    except Exception as e:
        logger.exception(f"runner: extraction failed for {job_id}: {e}")
        try:
            await _set_status("failed", err=str(e))
        except Exception:
            pass
