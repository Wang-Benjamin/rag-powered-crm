"""Document Ingestion Router.

Endpoints for the upload-to-autofill flow (see DOC_INGESTION_PLAN.md).

M3 covers the ``company_profile`` lane end-to-end. Other lanes accept
uploads and return a job id, but the runner will mark them ``failed`` with
a "kind not yet supported" message until M4–M6 land.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from pydantic import BaseModel

from data.repositories import ingestion_repository, product_catalog_repository
from service_core.db import get_tenant_connection
from services.document_ingestion import product_csv_mapper, runner
from services.document_ingestion.schemas import JobKind, ProductCatalogDraft
from utils.gcs import download_bytes, upload_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingestion")


# MIME / extension allowlist per lane, mirroring DOC_INGESTION_PLAN §4.
_ACCEPT: Dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    # kind -> (allowed MIME types, allowed extensions)
    "company_profile": (("application/pdf",), (".pdf",)),
    "product_csv": (
        ("text/csv", "application/vnd.ms-excel",
         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        (".csv", ".xlsx"),
    ),
    "product_pdf": (("application/pdf",), (".pdf",)),
    "certification": (
        ("application/pdf", "image/png", "image/jpeg"),
        (".pdf", ".png", ".jpg", ".jpeg"),
    ),
}

MAX_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB cap from plan §10.


class UploadResponse(BaseModel):
    job_id: uuid.UUID
    status: str


class JobResponse(BaseModel):
    job_id: uuid.UUID
    kind: str
    status: str
    draft_payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    source_url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CommitRequest(BaseModel):
    payload: Optional[Dict[str, Any]] = None


class ApplyMappingRequest(BaseModel):
    """Phase-2 request for the CSV lane (see DOC_INGESTION_CODING_PLAN §7.2)."""
    mapping: Dict[str, str]


class ApplyMappingResponse(BaseModel):
    success: bool
    product_count: int


class CommitResponse(BaseModel):
    success: bool
    inserted_count: Optional[int] = None


class DiscardResponse(BaseModel):
    success: bool


def _validate_upload(kind: str, file: UploadFile) -> None:
    if kind not in _ACCEPT:
        raise HTTPException(status_code=400, detail=f"invalid kind {kind!r}")

    allowed_mimes, allowed_exts = _ACCEPT[kind]
    mime_ok = bool(file.content_type) and file.content_type in allowed_mimes
    name = (file.filename or "").lower()
    ext_ok = any(name.endswith(e) for e in allowed_exts)
    if not (mime_ok or ext_ok):
        raise HTTPException(
            status_code=400,
            detail=f"file type not allowed for {kind} (expected {allowed_exts})",
        )


def _job_to_response(row: dict) -> JobResponse:
    return JobResponse(
        job_id=row["job_id"],
        kind=row["kind"],
        status=row["status"],
        draft_payload=row.get("draft_payload"),
        error=row.get("error"),
        source_url=row.get("source_url"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    kind: str = Form(...),
    file: UploadFile = File(...),
    tenant=Depends(get_tenant_connection),
) -> UploadResponse:
    """Accept a document, stage it in GCS, and enqueue background extraction."""
    conn, user = tenant
    user_email = user.get("email")
    db_name = user.get("db_name")
    if not user_email or not db_name:
        raise HTTPException(status_code=401, detail="Authentication required")

    _validate_upload(kind, file)

    # Size check. FastAPI populates ``file.size`` from the multipart
    # Content-Length when present; if the client omitted it we fall back to
    # buffering the body so we still reject oversized uploads before they
    # reach GCS.
    size = file.size
    if size is None:
        buf = await file.read()
        size = len(buf)
        file.file.seek(0)
    if size > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"file exceeds {MAX_SIZE_BYTES // (1024 * 1024)} MB limit",
        )

    # GCS path: ingestion/{kind}/{sanitized_email}_{ts}{ext}
    folder = f"ingestion/{kind}"
    source_url = upload_file(file, folder=folder, email=user_email)

    job_id = await ingestion_repository.create_job(
        conn, email=user_email, kind=kind, source_url=source_url,
    )
    logger.info(
        "ingestion.upload: job_id=%s kind=%s email=%s size=%d",
        job_id, kind, user_email, size,
    )

    background_tasks.add_task(runner.run_job, job_id, user_email, db_name)
    return UploadResponse(job_id=job_id, status="queued")


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    tenant=Depends(get_tenant_connection),
) -> JobResponse:
    """Return the current state of one job, scoped to the caller."""
    conn, user = tenant
    user_email = user.get("email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    row = await ingestion_repository.get_job(conn, job_id, user_email)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    return _job_to_response(row)


@router.post("/jobs/{job_id}/commit", response_model=CommitResponse)
async def commit_job(
    job_id: uuid.UUID,
    request: CommitRequest,
    tenant=Depends(get_tenant_connection),
) -> CommitResponse:
    """Mark a reviewed draft as committed.

    Behaviour depends on the job's ``kind``:

    * ``company_profile`` / ``certification`` — bookkeeping only. The wizard
      has already written the authoritative row via
      ``/factory-profile/save`` or ``/certifications`` respectively. We just
      stamp ``status=committed`` and record the reviewed payload.
    * ``product_pdf`` / ``product_csv`` — authoritative write. The draft is
      validated as :class:`ProductCatalogDraft` and bulk-inserted into
      ``product_catalog`` in a single transaction.
    """
    conn, user = tenant
    user_email = user.get("email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    row = await ingestion_repository.get_job(conn, job_id, user_email)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    if row["status"] not in ("ready_for_review", "committed"):
        raise HTTPException(
            status_code=409,
            detail=f"cannot commit job in status {row['status']!r}",
        )

    draft = request.payload if request.payload is not None else row.get("draft_payload")
    kind = row["kind"]
    inserted_count: Optional[int] = None

    if kind in ("product_pdf", "product_csv"):
        if not isinstance(draft, dict):
            raise HTTPException(
                status_code=400,
                detail="payload must be a ProductCatalogDraft object",
            )
        try:
            catalog = ProductCatalogDraft.model_validate(draft)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"invalid payload: {e}")

        # Single transaction: rows + status flip.
        async with conn.transaction():
            product_rows = [p.model_dump(mode="json") for p in catalog.products]
            ids = await product_catalog_repository.bulk_insert_products(
                conn,
                email=user_email,
                products=product_rows,
                source_job_id=job_id,
            )
            inserted_count = len(ids)
            await ingestion_repository.update_job_status(
                conn, job_id, "committed",
                draft_payload=catalog.model_dump(mode="json"),
            )
        logger.info(
            "ingestion.commit: job %s kind=%s inserted %d products",
            job_id, kind, inserted_count,
        )
    else:
        # Bookkeeping-only lanes.
        await ingestion_repository.update_job_status(
            conn, job_id, "committed", draft_payload=draft,
        )

    return CommitResponse(success=True, inserted_count=inserted_count)


@router.post("/jobs/{job_id}/apply-mapping", response_model=ApplyMappingResponse)
async def apply_mapping(
    job_id: uuid.UUID,
    request: ApplyMappingRequest,
    tenant=Depends(get_tenant_connection),
) -> ApplyMappingResponse:
    """Phase 2 of the CSV lane — turn a confirmed column mapping into products.

    Re-downloads the source file from GCS, applies the user's mapping to
    materialise ``ProductRecordDraft`` rows, attaches embedded xlsx images
    (if any), and overwrites ``draft_payload`` with the full product list.
    Job stays in ``ready_for_review`` so the frontend can render the table.
    """
    conn, user = tenant
    user_email = user.get("email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    row = await ingestion_repository.get_job(conn, job_id, user_email)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    if row["kind"] != "product_csv":
        raise HTTPException(
            status_code=400,
            detail=f"apply-mapping only supports product_csv (got {row['kind']!r})",
        )
    if row["status"] != "ready_for_review":
        raise HTTPException(
            status_code=409,
            detail=f"cannot apply mapping on job in status {row['status']!r}",
        )

    source_url = row["source_url"]
    file_bytes = download_bytes(source_url)
    df, ext = product_csv_mapper.read_table(file_bytes, source_url)

    products, data_row_indices = product_csv_mapper.apply_mapping(df, request.mapping)

    if ext == ".xlsx":
        images_by_row = product_csv_mapper.extract_xlsx_images(file_bytes)
        if images_by_row:
            products = product_csv_mapper.finalize_with_embedded_images(
                products, images_by_row,
                job_id=str(job_id),
                email=user_email,
                df_row_indices=data_row_indices,
            )

    draft = ProductCatalogDraft(products=products, column_mapping=request.mapping)
    existing_payload = row.get("draft_payload") or {}
    new_payload: Dict[str, Any] = {
        **existing_payload,
        **draft.model_dump(mode="json"),
    }
    await ingestion_repository.update_job_status(
        conn, job_id, "ready_for_review", draft_payload=new_payload,
    )
    logger.info(
        "ingestion.apply_mapping: job %s produced %d products (ext=%s)",
        job_id, len(products), ext,
    )
    return ApplyMappingResponse(success=True, product_count=len(products))


@router.delete("/jobs/{job_id}", response_model=DiscardResponse)
async def discard_job(
    job_id: uuid.UUID,
    tenant=Depends(get_tenant_connection),
) -> DiscardResponse:
    """Mark a job as discarded. The GCS blob is retained for the 30-day window."""
    conn, user = tenant
    user_email = user.get("email")
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    row = await ingestion_repository.get_job(conn, job_id, user_email)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")

    await ingestion_repository.update_job_status(conn, job_id, "discarded")
    return DiscardResponse(success=True)
