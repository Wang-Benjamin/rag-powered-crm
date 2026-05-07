"""
Email Template Router
=====================
Handles email template management for template-based email system.
Includes AI generation for templates.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime, timezone
from uuid import UUID, uuid4
import logging
import json
import re
import sys
import os

from services.email_generator import generate_email_with_ai, build_template_generation_prompt, build_leadgen_template_generation_prompt
from service_core.db import get_tenant_connection
from service_core.auth import verify_auth_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/templates")

# Valid tokens by template type
VALID_CRM_TOKENS = {'name', 'primary_contact', 'email', 'phone'}
VALID_LEADGEN_TOKENS = {'company', 'location', 'website', 'phone'}
VALID_TOKENS = VALID_CRM_TOKENS

# Pydantic Models

class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    channel: str = Field(default="email")
    subject: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    template_type: str = Field(default="crm")
    template_category: str = Field(default="user", description="Template category: 'purpose' (system) or 'user' (user-created)")
    prompt_instructions: Optional[str] = Field(default=None, description="AI generation instructions for this template")
    is_shared: bool = Field(default=False, description="If True, template is shared with all users (created_by = NULL)")

class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    is_active: Optional[bool] = None

class TemplateResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    channel: str
    subject: str
    body: str
    tokens: List[str]
    is_active: bool
    is_archived: bool
    performance_stats: Dict
    created_by: Optional[int]
    is_shared: bool
    created_at: datetime
    updated_at: datetime
    level: int = 0
    parent_id: Optional[UUID] = None
    send_count: int = 0
    template_category: str = "user"
    prompt_instructions: Optional[str] = None

class SendTrackingRequest(BaseModel):
    total_sends: int
    successful_sends: int
    failed_sends: int

class PreviewRequest(BaseModel):
    client_id: int

class TemplateGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=10, description="User's instructions for generating the template")

class TemplateGenerateResponse(BaseModel):
    subject: str
    body: str
    tokens: List[str]

class BranchTemplateRequest(BaseModel):
    action: str = Field(..., description="Branch action: create_variation, create_sub_variation, duplicate_base")
    new_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None

# Token Utilities

def extract_tokens(text: str) -> List[str]:
    pattern = r'\[(\w+)\]'
    tokens = re.findall(pattern, text)
    return list(set(tokens))

def validate_tokens(tokens: List[str], template_type: str = 'crm') -> Dict[str, List[str]]:
    valid_token_set = VALID_LEADGEN_TOKENS if template_type == 'leadgen' else VALID_CRM_TOKENS
    invalid = [t for t in tokens if t not in valid_token_set]
    return {
        "valid": [t for t in tokens if t in valid_token_set],
        "invalid": invalid,
        "valid_token_set": valid_token_set
    }

def render_template(template: str, client_data: dict) -> str:
    result = template
    for token, value in client_data.items():
        if value is None:
            value = ''
        result = result.replace(f"[{token}]", str(value))
    return result

def row_to_template_response(row) -> TemplateResponse:
    stats = row.get('performance_stats') or {}
    if isinstance(stats, str):
        stats = json.loads(stats)
    tokens = row.get('tokens') or []
    if isinstance(tokens, str):
        tokens = json.loads(tokens)
    return TemplateResponse(
        id=row['id'],
        name=row['name'],
        description=row.get('description'),
        channel=row['channel'],
        subject=row['subject'],
        body=row['body'],
        tokens=tokens,
        is_active=row.get('is_active', True),
        is_archived=row.get('is_archived', False),
        performance_stats=stats,
        created_by=row.get('created_by'),
        is_shared=row.get('is_shared', False),
        created_at=row['created_at'],
        updated_at=row['updated_at'],
        level=row.get('generation_level', 0),
        parent_id=row.get('parent_template_id'),
        send_count=stats.get('total_sends', 0) if isinstance(stats, dict) else 0,
        template_category=row.get('template_category', 'user'),
        prompt_instructions=row.get('prompt_instructions')
    )

# API Endpoints

@router.get("", response_model=List[TemplateResponse])
async def list_templates(
    tenant=Depends(get_tenant_connection),
    channel: str = Query(default="email"),
    is_active: bool = Query(default=True),
    template_type: Optional[str] = Query(default=None, description="Filter by template type (crm/leadgen)")
):
    """List templates: shared templates (is_shared = true) + user's own templates, optionally filtered by type"""
    conn, user = tenant
    user_email = user.get('email')

    emp_result = await conn.fetchrow(
        "SELECT employee_id FROM employee_info WHERE email = $1", user_email
    )
    employee_id = emp_result['employee_id'] if emp_result else None

    if template_type:
        rows = await conn.fetch(
            """
            SELECT * FROM templates
            WHERE channel = $1 AND is_active = $2 AND is_archived = false
            AND (is_shared = true OR created_by = $3)
            AND template_type = $4
            ORDER BY created_at DESC
            """,
            channel, is_active, employee_id, template_type
        )
    else:
        rows = await conn.fetch(
            """
            SELECT * FROM templates
            WHERE channel = $1 AND is_active = $2 AND is_archived = false
            AND (is_shared = true OR created_by = $3)
            ORDER BY created_at DESC
            """,
            channel, is_active, employee_id
        )

    return [row_to_template_response(row) for row in rows]


@router.post("/{template_id}/branch", response_model=TemplateResponse)
async def branch_template(
    template_id: str,
    request: BranchTemplateRequest,
    tenant=Depends(get_tenant_connection)
):
    """Create a template variation/branch from an existing template"""
    conn, user = tenant
    user_email = user.get('email')

    emp = await conn.fetchrow("SELECT employee_id FROM employee_info WHERE email = $1", user_email)
    employee_id = emp['employee_id'] if emp else None

    source = await conn.fetchrow("SELECT * FROM templates WHERE id = $1", template_id)
    if not source:
        raise HTTPException(404, "Template not found")

    source_level = source.get('generation_level', 0)
    if request.action == 'duplicate_base':
        new_level = 0
        parent_id = None
    else:
        new_level = min(source_level + 1, 2)
        parent_id = template_id

    new_id = uuid4()
    source_tokens = source.get('tokens') or []
    if isinstance(source_tokens, str):
        source_tokens = json.loads(source_tokens)

    row = await conn.fetchrow(
        """
        INSERT INTO templates
        (id, name, channel, subject, body, tokens, created_by, performance_stats,
         generation_level, parent_template_id, description, template_type, is_shared)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, false)
        RETURNING *
        """,
        new_id, request.new_name, source['channel'], source['subject'], source['body'],
        source_tokens, employee_id,
        {"total_sends": 0, "successful_sends": 0, "failed_sends": 0, "success_rate": 100.0},
        new_level, parent_id, request.description or source.get('description'),
        source.get('template_type', 'crm')
    )

    logger.info(f"Branched template {template_id} -> {new_id} ({request.action})")
    return row_to_template_response(row)


@router.post("", response_model=TemplateResponse)
async def create_template(
    request: TemplateCreate,
    tenant=Depends(get_tenant_connection)
):
    """Create a new template."""
    conn, user = tenant
    user_email = user.get('email')

    emp_result = await conn.fetchrow(
        "SELECT employee_id FROM employee_info WHERE email = $1", user_email
    )
    employee_id = emp_result['employee_id'] if emp_result else None

    all_tokens = list(set(extract_tokens(request.subject) + extract_tokens(request.body)))
    validation = validate_tokens(all_tokens, request.template_type)
    if validation['invalid']:
        raise HTTPException(400, f"Invalid tokens: {validation['invalid']}. Valid tokens: {list(validation['valid_token_set'])}")

    row = await conn.fetchrow(
        """
        INSERT INTO templates
        (id, name, channel, subject, body, tokens, created_by, performance_stats, generation_level, description, template_type, is_shared, template_category, prompt_instructions)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 0, $9, $10, $11, $12, $13)
        RETURNING *
        """,
        uuid4(), request.name, request.channel, request.subject, request.body,
        all_tokens, employee_id,
        {"total_sends": 0, "successful_sends": 0, "failed_sends": 0, "success_rate": 100.0},
        request.description, request.template_type, request.is_shared,
        request.template_category, request.prompt_instructions
    )

    logger.info(f"Created template '{request.name}' by {user_email}")
    return row_to_template_response(row)


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    tenant=Depends(get_tenant_connection)
):
    """Get a single template by ID"""
    conn, user = tenant

    row = await conn.fetchrow("SELECT * FROM templates WHERE id = $1", template_id)
    if not row:
        raise HTTPException(404, "Template not found")

    return row_to_template_response(row)


@router.patch("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    request: TemplateUpdate,
    tenant=Depends(get_tenant_connection)
):
    """Update an existing template - only personal templates can be edited"""
    conn, user = tenant
    user_email = user.get('email')

    emp_result = await conn.fetchrow(
        "SELECT employee_id FROM employee_info WHERE email = $1", user_email
    )
    employee_id = emp_result['employee_id'] if emp_result else None

    template = await conn.fetchrow(
        "SELECT created_by, is_shared FROM templates WHERE id = $1", template_id
    )
    if not template:
        raise HTTPException(404, "Template not found")
    if template['is_shared']:
        raise HTTPException(403, "Cannot edit shared templates. Shared templates are read-only.")
    if template['created_by'] != employee_id:
        raise HTTPException(403, "Can only edit your own templates")

    # Build dynamic UPDATE
    updates = []
    params = []
    param_idx = 1

    if request.name:
        updates.append(f"name = ${param_idx}")
        params.append(request.name)
        param_idx += 1
    if request.subject:
        updates.append(f"subject = ${param_idx}")
        params.append(request.subject)
        param_idx += 1
    if request.body:
        updates.append(f"body = ${param_idx}")
        params.append(request.body)
        param_idx += 1
    if request.description is not None:
        updates.append(f"description = ${param_idx}")
        params.append(request.description)
        param_idx += 1
    if request.is_active is not None:
        updates.append(f"is_active = ${param_idx}")
        params.append(request.is_active)
        param_idx += 1

    if not updates:
        raise HTTPException(400, "No fields to update")

    # Re-extract tokens if subject/body changed
    if request.subject or request.body:
        current = await conn.fetchrow(
            "SELECT subject, body, template_type FROM templates WHERE id = $1", template_id
        )
        if not current:
            raise HTTPException(404, "Template not found")

        subj = request.subject or current['subject']
        bod = request.body or current['body']
        tokens = list(set(extract_tokens(subj) + extract_tokens(bod)))

        template_type = current.get('template_type', 'crm')
        validation = validate_tokens(tokens, template_type)
        if validation['invalid']:
            raise HTTPException(400, f"Invalid tokens: {validation['invalid']}. Valid tokens: {list(validation['valid_token_set'])}")

        updates.append(f"tokens = ${param_idx}")
        params.append(tokens)
        param_idx += 1

    updates.append("updated_at = NOW()")
    params.append(template_id)

    row = await conn.fetchrow(
        f"UPDATE templates SET {', '.join(updates)} WHERE id = ${param_idx} RETURNING *",
        *params
    )

    logger.info(f"Updated template {template_id}")
    return row_to_template_response(row)


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    tenant=Depends(get_tenant_connection)
):
    """Delete a template (only user's own templates, not shared)"""
    conn, user = tenant
    user_email = user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    emp = await conn.fetchrow("SELECT employee_id, access FROM employee_info WHERE email = $1", user_email)
    employee_id = emp['employee_id'] if emp else None

    is_admin = emp and emp.get('access') == 'admin'

    template = await conn.fetchrow(
        "SELECT created_by, is_shared FROM templates WHERE id = $1", template_id
    )
    if not template:
        raise HTTPException(404, "Template not found")
    if not is_admin:
        if template['is_shared']:
            raise HTTPException(403, "Cannot delete shared templates")
        if template['created_by'] != employee_id:
            raise HTTPException(403, "Can only delete your own templates")

    await conn.execute(
        "UPDATE templates SET is_archived = true, is_active = false, updated_at = NOW() WHERE id = $1",
        template_id
    )
    logger.info(f"Deleted template {template_id} by {user_email}")
    return {"success": True}


@router.post("/{template_id}/preview")
async def preview_template(
    template_id: str,
    request: PreviewRequest,
    tenant=Depends(get_tenant_connection)
):
    """Preview template with actual client data"""
    conn, user = tenant

    template = await conn.fetchrow(
        "SELECT subject, body FROM templates WHERE id = $1", template_id
    )
    if not template:
        raise HTTPException(404, "Template not found")

    client = await conn.fetchrow(
        "SELECT name, phone FROM clients WHERE client_id = $1",
        request.client_id
    )
    if not client:
        raise HTTPException(404, "Client not found")

    primary_personnel = await conn.fetchrow(
        "SELECT full_name, email, phone FROM personnel WHERE client_id = $1 AND is_primary = true LIMIT 1",
        request.client_id
    )

    client_data = {
        'name': client['name'],
        'primary_contact': primary_personnel['full_name'] if primary_personnel else '',
        'email': primary_personnel['email'] if primary_personnel else '',
        'phone': primary_personnel['phone'] if primary_personnel else client['phone'] or ''
    }

    return {
        "subject": render_template(template['subject'], client_data),
        "body": render_template(template['body'], client_data)
    }


@router.post("/{template_id}/track-send")
async def track_send(
    template_id: str,
    request: SendTrackingRequest,
    tenant=Depends(get_tenant_connection)
):
    """Update template performance statistics"""
    conn, user = tenant

    row = await conn.fetchrow(
        "SELECT performance_stats FROM templates WHERE id = $1", template_id
    )
    if not row:
        raise HTTPException(404, "Template not found")

    current_stats = row['performance_stats'] or {}
    if isinstance(current_stats, str):
        current_stats = json.loads(current_stats)

    new_total = current_stats.get('total_sends', 0) + request.total_sends
    new_successful = current_stats.get('successful_sends', 0) + request.successful_sends
    new_failed = current_stats.get('failed_sends', 0) + request.failed_sends
    success_rate = (new_successful / new_total * 100) if new_total > 0 else 100.0

    await conn.execute(
        "UPDATE templates SET performance_stats = $1, updated_at = NOW() WHERE id = $2",
        {
            "total_sends": new_total,
            "successful_sends": new_successful,
            "failed_sends": new_failed,
            "success_rate": round(success_rate, 1),
            "last_used_at": datetime.now(timezone.utc).isoformat()
        },
        template_id
    )

    logger.info(f"Updated stats for template {template_id}: {new_total} total sends")
    return {"success": True}


@router.post("/generate", response_model=TemplateGenerateResponse)
async def generate_template(
    request: TemplateGenerateRequest,
    template_type: str = Query(default="crm", description="Template type: crm or leadgen"),
    authenticated_user: dict = Depends(verify_auth_token)
):
    """Generate email template using AI based on user's prompt and type."""
    user_email = authenticated_user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        logger.info(f"Generating {template_type} template for {user_email} with prompt length: {len(request.prompt)}")

        from services.writing_style_service import fetch_writing_style_by_email, format_writing_style_for_prompt

        writing_style_data = await fetch_writing_style_by_email(user_email)
        writing_style_text = format_writing_style_for_prompt(writing_style_data)

        if template_type == "leadgen":
            prompt = build_leadgen_template_generation_prompt(request.prompt, writing_style_text)
        else:
            prompt = build_template_generation_prompt(request.prompt, writing_style_text)

        result = await generate_email_with_ai(prompt)
        all_tokens = list(set(extract_tokens(result['subject']) + extract_tokens(result['body'])))

        logger.info(f"Generated template with {len(all_tokens)} tokens: {all_tokens}")

        return TemplateGenerateResponse(
            subject=result['subject'],
            body=result['body'],
            tokens=all_tokens
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating template: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate template: {str(e)}")
