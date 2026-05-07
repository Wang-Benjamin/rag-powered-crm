"""
Certification Router
====================
Handles factory certification CRUD and document uploads to GCS.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date, timezone
import logging
import uuid

from service_core.db import get_tenant_connection
from utils.gcs import upload_file, delete_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/certifications")

ALLOWED_CERT_TYPES = {'application/pdf', 'image/jpeg', 'image/png', 'image/gif', 'image/webp'}


# Pydantic models
class CertificationItem(BaseModel):
    cert_id: str
    email: str
    cert_type: Optional[str] = None
    cert_number: Optional[str] = None
    issuing_body: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    notes: Optional[str] = None
    document_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class CertificationListResponse(BaseModel):
    success: bool
    certifications: List[CertificationItem]


class CertificationResponse(BaseModel):
    success: bool
    certification: Optional[CertificationItem] = None


class CertificationUpdateRequest(BaseModel):
    cert_type: Optional[str] = None
    cert_number: Optional[str] = None
    issuing_body: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    notes: Optional[str] = None


class DocumentUploadResponse(BaseModel):
    success: bool
    document_url: str


def _validate_cert_file(file: UploadFile):
    """Validate that the uploaded file is a PDF or image."""
    if not file.content_type or file.content_type not in ALLOWED_CERT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only PDF and image files (JPEG, PNG, GIF, WebP) are allowed"
        )


def _row_to_item(row) -> CertificationItem:
    """Convert a database row to a CertificationItem."""
    return CertificationItem(
        cert_id=str(row['cert_id']),
        email=row['email'],
        cert_type=row['cert_type'],
        cert_number=row['cert_number'],
        issuing_body=row['issuing_body'],
        issue_date=str(row['issue_date']) if row['issue_date'] else None,
        expiry_date=str(row['expiry_date']) if row['expiry_date'] else None,
        notes=row['notes'],
        document_url=row['document_url'],
        created_at=row['created_at'],
        updated_at=row['updated_at']
    )


@router.get("", response_model=CertificationListResponse)
async def list_certifications(
    tenant=Depends(get_tenant_connection)
):
    """List all certifications for authenticated user."""
    conn, user = tenant
    user_email = user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        rows = await conn.fetch(
            """
            SELECT cert_id, email, cert_type, cert_number, issuing_body,
                   issue_date, expiry_date, notes, document_url,
                   created_at, updated_at
            FROM factory_certifications
            WHERE email = $1
            ORDER BY created_at DESC
            """,
            user_email
        )

        certifications = [_row_to_item(row) for row in rows]
        return CertificationListResponse(success=True, certifications=certifications)

    except Exception as e:
        logger.error(f"Error listing certifications: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list certifications: {str(e)}")


@router.post("", response_model=CertificationResponse)
async def add_certification(
    cert_type: Optional[str] = Form(None),
    cert_number: Optional[str] = Form(None),
    issuing_body: Optional[str] = Form(None),
    issue_date: Optional[str] = Form(None),
    expiry_date: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    tenant=Depends(get_tenant_connection)
):
    """Add a certification with optional document upload."""
    conn, user = tenant
    user_email = user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        cert_id = str(uuid.uuid4())
        document_url = None

        if file and file.filename:
            _validate_cert_file(file)
            document_url = upload_file(file, "certs", user_email, cert_id)

        # Parse date strings to date objects for asyncpg
        parsed_issue_date = date.fromisoformat(issue_date) if issue_date else None
        parsed_expiry_date = date.fromisoformat(expiry_date) if expiry_date else None

        row = await conn.fetchrow(
            """
            INSERT INTO factory_certifications
                (cert_id, email, cert_type, cert_number, issuing_body,
                 issue_date, expiry_date, notes, document_url,
                 created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())
            RETURNING cert_id, email, cert_type, cert_number, issuing_body,
                      issue_date, expiry_date, notes, document_url,
                      created_at, updated_at
            """,
            cert_id, user_email, cert_type, cert_number, issuing_body,
            parsed_issue_date, parsed_expiry_date, notes, document_url
        )

        return CertificationResponse(success=True, certification=_row_to_item(row))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding certification: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add certification: {str(e)}")


@router.put("/{cert_id}", response_model=CertificationResponse)
async def update_certification(
    cert_id: str,
    request: CertificationUpdateRequest,
    tenant=Depends(get_tenant_connection)
):
    """Update certification metadata."""
    conn, user = tenant
    user_email = user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        row = await conn.fetchrow(
            """
            UPDATE factory_certifications
            SET cert_type = COALESCE($1, cert_type),
                cert_number = COALESCE($2, cert_number),
                issuing_body = COALESCE($3, issuing_body),
                issue_date = COALESCE($4, issue_date),
                expiry_date = COALESCE($5, expiry_date),
                notes = COALESCE($6, notes),
                updated_at = NOW()
            WHERE cert_id =$7 AND email = $8
            RETURNING cert_id, email, cert_type, cert_number, issuing_body,
                      issue_date, expiry_date, notes, document_url,
                      created_at, updated_at
            """,
            request.cert_type, request.cert_number, request.issuing_body,
            date.fromisoformat(request.issue_date) if request.issue_date else None,
            date.fromisoformat(request.expiry_date) if request.expiry_date else None,
            request.notes, cert_id, user_email
        )

        if not row:
            raise HTTPException(status_code=404, detail="Certification not found")

        return CertificationResponse(success=True, certification=_row_to_item(row))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating certification: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update certification: {str(e)}")


@router.post("/{cert_id}/upload", response_model=DocumentUploadResponse)
async def upload_certification_document(
    cert_id: str,
    file: UploadFile = File(...),
    tenant=Depends(get_tenant_connection)
):
    """Upload or replace document for an existing certification."""
    conn, user = tenant
    user_email = user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        _validate_cert_file(file)

        existing = await conn.fetchrow(
            "SELECT cert_id, document_url FROM factory_certifications WHERE cert_id =$1 AND email = $2",
            cert_id, user_email
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Certification not found")

        # Delete old file if it exists
        if existing['document_url']:
            delete_file(existing['document_url'])

        document_url = upload_file(file, "certs", user_email, cert_id)

        await conn.execute(
            """
            UPDATE factory_certifications
            SET document_url = $1, updated_at = NOW()
            WHERE cert_id =$2 AND email = $3
            """,
            document_url, cert_id, user_email
        )

        return DocumentUploadResponse(success=True, document_url=document_url)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading certification document: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload document: {str(e)}")


@router.delete("/{cert_id}")
async def delete_certification(
    cert_id: str,
    tenant=Depends(get_tenant_connection)
):
    """Delete a certification and its GCS document if present."""
    conn, user = tenant
    user_email = user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        row = await conn.fetchrow(
            "SELECT cert_id, document_url FROM factory_certifications WHERE cert_id =$1 AND email = $2",
            cert_id, user_email
        )

        if not row:
            raise HTTPException(status_code=404, detail="Certification not found")

        # Delete GCS file if it exists
        if row['document_url']:
            delete_file(row['document_url'])

        await conn.execute(
            "DELETE FROM factory_certifications WHERE cert_id =$1 AND email = $2",
            cert_id, user_email
        )

        return {"success": True, "message": "Certification deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting certification: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete certification: {str(e)}")
