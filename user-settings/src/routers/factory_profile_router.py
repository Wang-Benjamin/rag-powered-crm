"""
Factory Profile Router
======================
Handles factory profile CRUD and photo/logo uploads to GCS.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging

from service_core.db import get_tenant_connection
from utils.gcs import upload_file
from utils.json_helpers import parse_jsonb

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/factory-profile")


# Pydantic models
class FactoryProfileSaveRequest(BaseModel):
    company_profile: Optional[Dict[str, Any]] = None
    factory_details: Optional[Dict[str, Any]] = None


class FactoryProfileResponse(BaseModel):
    success: bool
    company_profile: Optional[Dict[str, Any]] = None
    factory_details: Optional[Dict[str, Any]] = None
    hs_codes: Optional[List[Any]] = None
    updated_at: Optional[str] = None


class PhotoUploadResponse(BaseModel):
    success: bool
    url: str


def _validate_image(file: UploadFile):
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Only image files allowed")


async def persist_factory_profile(
    conn,
    company_profile: Optional[Dict[str, Any]] = None,
    factory_details: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Write company_profile / factory_details onto ``tenant_subscription``.

    Shared between the user-facing ``/factory-profile/save`` endpoint and
    the document-ingestion commit endpoint. At least one of the two fields
    must be provided — the caller is expected to have validated that.

    Bootstraps the singleton ``tenant_subscription`` row if missing, then
    shallow-merges the provided JSONB blobs onto the existing columns via
    ``||`` (top-level key replacement). Storefront sections autosave to
    different parts of the same blob in parallel, so a REPLACE write would
    race-clobber sibling keys. Nested objects still require full-object
    writes from the caller.

    Returns the new ``updated_at`` as an ISO-8601 string.
    """
    if company_profile is None and factory_details is None:
        raise HTTPException(
            status_code=400,
            detail="At least one of company_profile or factory_details is required",
        )

    updates: list[str] = []
    params: list[Any] = []
    idx = 1

    # ``CASE jsonb_typeof = 'object'`` guards against legacy rows where the
    # column is a JSONB array or string scalar (an earlier version of this
    # router accidentally double-serialized writes). Without the guard,
    # ``array || object`` would append instead of merge, compounding the
    # corruption on every save.
    #
    # Pass the dict directly (not ``json.dumps``) — the connection-level
    # JSONB codec in ``service_core.pool._init_connection`` already encodes
    # via ``json.dumps``, so wrapping here would double-encode and produce a
    # JSONB string scalar. ``object || string_scalar`` would then yield
    # ``[object, string]``, which is the bug we're fixing.
    if company_profile is not None:
        updates.append(
            f"company_profile = (CASE WHEN jsonb_typeof(company_profile) = 'object' "
            f"THEN company_profile ELSE '{{}}'::jsonb END) || ${idx}::jsonb"
        )
        params.append(company_profile)
        idx += 1

    if factory_details is not None:
        updates.append(
            f"factory_details = (CASE WHEN jsonb_typeof(factory_details) = 'object' "
            f"THEN factory_details ELSE '{{}}'::jsonb END) || ${idx}::jsonb"
        )
        params.append(factory_details)
        idx += 1

    updates.append("updated_at = NOW()")

    await conn.execute(
        "INSERT INTO tenant_subscription (id) VALUES (TRUE) ON CONFLICT DO NOTHING"
    )
    row = await conn.fetchrow(
        f"UPDATE tenant_subscription SET {', '.join(updates)} RETURNING updated_at",
        *params,
    )
    updated_at = row['updated_at'] if row else None
    return updated_at.isoformat() if updated_at else None


@router.post("/save", response_model=FactoryProfileResponse)
async def save_factory_profile(
    request: FactoryProfileSaveRequest,
    tenant=Depends(get_tenant_connection)
):
    """Save company_profile and factory_details to tenant_subscription."""
    conn, user = tenant
    user_email = user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        updated_at = await persist_factory_profile(
            conn,
            company_profile=request.company_profile,
            factory_details=request.factory_details,
        )
        # Re-read so the response reflects the merged state, not just the
        # caller's partial payload — storefront sections rely on this to
        # stay in sync with siblings written in parallel.
        merged = await conn.fetchrow(
            "SELECT company_profile, factory_details FROM tenant_subscription LIMIT 1",
        )
        return FactoryProfileResponse(
            success=True,
            company_profile=parse_jsonb(merged['company_profile']) if merged else None,
            factory_details=parse_jsonb(merged['factory_details']) if merged else None,
            updated_at=updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving factory profile: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save factory profile: {str(e)}")


@router.get("", response_model=FactoryProfileResponse)
async def get_factory_profile(
    tenant=Depends(get_tenant_connection)
):
    """Get factory profile for authenticated user."""
    conn, user = tenant
    user_email = user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        result = await conn.fetchrow(
            "SELECT company_profile, factory_details, hs_codes, updated_at FROM tenant_subscription LIMIT 1",
        )

        if not result:
            return FactoryProfileResponse(success=True)

        company_profile = parse_jsonb(result['company_profile'])
        factory_details = parse_jsonb(result['factory_details'])
        hs_codes = parse_jsonb(result['hs_codes'])
        updated_at = result['updated_at']

        return FactoryProfileResponse(
            success=True, company_profile=company_profile,
            factory_details=factory_details, hs_codes=hs_codes,
            updated_at=updated_at.isoformat() if updated_at else None,
        )
    except Exception as e:
        logger.error(f"Error fetching factory profile: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch factory profile: {str(e)}")


@router.post("/upload-photo", response_model=PhotoUploadResponse)
async def upload_factory_photo(
    file: UploadFile = File(...),
    tenant=Depends(get_tenant_connection)
):
    """Upload factory photo to Google Cloud Storage."""
    conn, user = tenant
    user_email = user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        _validate_image(file)
        url = upload_file(file, "factory-photos", user_email)
        return PhotoUploadResponse(success=True, url=url)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading factory photo: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload photo: {str(e)}")


@router.post("/upload-logo", response_model=PhotoUploadResponse)
async def upload_company_logo(
    file: UploadFile = File(...),
    tenant=Depends(get_tenant_connection)
):
    """Upload company logo to Google Cloud Storage."""
    conn, user = tenant
    user_email = user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        _validate_image(file)
        url = upload_file(file, "logos", user_email)
        return PhotoUploadResponse(success=True, url=url)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading company logo: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload logo: {str(e)}")
