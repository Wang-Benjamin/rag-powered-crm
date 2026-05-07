"""
Email Signature Router
======================
PUT/PATCH/GET/DELETE routes for structured email signatures stored in
employee_info.signature_fields JSONB.

IDOR fix: user_email is always derived from the JWT — the request body never
accepts an email field. Audit log emitted when signature.email differs from
the JWT email.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from pydantic import BaseModel, ConfigDict, model_validator
from pydantic.alias_generators import to_camel

from service_core.db import get_tenant_connection
from utils.gcs import upload_file, GCS_SIGNATURE_BUCKET
from src.services.signature_service import (
    get_email_signature_service,
    upsert_email_signature_service,
    partial_update_email_signature_service,
    delete_email_signature_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/signature")


class SignatureFields(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    location: Optional[str] = None
    link: Optional[str] = None
    logo_url: Optional[str] = None

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel,
    )


class EmailSignatureDTO(BaseModel):
    signature_fields: SignatureFields
    updated_at: datetime

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel,
        from_attributes=True,
    )


class CreateEmailSignatureDTO(SignatureFields):
    """Body for PUT /signature. Adds a 4 KB column-level cap on the JSONB blob."""

    @model_validator(mode='after')
    def total_size_under_4kb(self) -> 'CreateEmailSignatureDTO':
        encoded = json.dumps(self.model_dump(exclude_none=True))
        if len(encoded) > 4096:
            raise ValueError(
                f"Signature fields exceed 4 KB column-level cap "
                f"(actual: {len(encoded)} bytes)"
            )
        return self


# PATCH and PUT share the same body shape; semantics differ at the service layer.
UpdateEmailSignatureDTO = CreateEmailSignatureDTO


def _maybe_audit_email_override(jwt_email: str, body: SignatureFields) -> None:
    if body.email and body.email != jwt_email:
        logger.info(
            "signature_email_override",
            extra={'employee_email': jwt_email, 'signature_email': body.email},
        )


@router.get("", response_model=Optional[EmailSignatureDTO])
async def get_signature(
    tenant=Depends(get_tenant_connection),
):
    """Get current user's email signature. Returns null if not set (no 404)."""
    conn, user = tenant
    user_email = user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    result = await get_email_signature_service(conn, user_email)
    if not result:
        return None
    return EmailSignatureDTO(
        signature_fields=SignatureFields(**result['signature_fields']),
        updated_at=result['updated_at'],
    )


@router.put("", response_model=EmailSignatureDTO)
async def put_signature(
    body: CreateEmailSignatureDTO,
    tenant=Depends(get_tenant_connection),
):
    """Replace the entire signature (PUT semantics). Omitted fields are cleared."""
    conn, user = tenant
    user_email = user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Store keys in camelCase (by_alias=True) so the email signature formatter
    # can read phoneNumber/logoUrl directly. Without by_alias the JSONB ends up
    # snake_case and the formatter silently skips those fields.
    fields_dict = body.model_dump(exclude_none=True, by_alias=True)
    _maybe_audit_email_override(user_email, body)

    try:
        result = await upsert_email_signature_service(conn, user_email, fields_dict)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return EmailSignatureDTO(
        signature_fields=SignatureFields(**result['signature_fields']),
        updated_at=result['updated_at'],
    )


@router.patch("", response_model=EmailSignatureDTO)
async def patch_signature(
    body: UpdateEmailSignatureDTO,
    tenant=Depends(get_tenant_connection),
):
    """Partial update (PATCH semantics). Only provided fields change."""
    conn, user = tenant
    user_email = user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    # exclude_unset (not exclude_none) so an explicit `null` clears the field.
    # by_alias keeps the JSONB schema in camelCase to match the formatter.
    partial = body.model_dump(exclude_unset=True, by_alias=True)
    _maybe_audit_email_override(user_email, body)

    try:
        result = await partial_update_email_signature_service(conn, user_email, partial)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return EmailSignatureDTO(
        signature_fields=SignatureFields(**result['signature_fields']),
        updated_at=result['updated_at'],
    )


@router.delete("", status_code=204)
async def delete_signature(
    tenant=Depends(get_tenant_connection),
):
    """Clear the signature."""
    conn, user = tenant
    user_email = user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    await delete_email_signature_service(conn, user_email)
    return None


@router.post("/upload-logo")
async def upload_logo(
    file: UploadFile = File(...),
    tenant=Depends(get_tenant_connection),
):
    """Upload signature logo to GCS."""
    conn, user = tenant
    user_email = user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Only image files allowed")

    try:
        logo_url = upload_file(file, "signatures", user_email, bucket_name=GCS_SIGNATURE_BUCKET)
        return {"success": True, "logo_url": logo_url}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading logo: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload logo: {str(e)}")
