"""
Notes Router - Handles all note-related endpoints (asyncpg)
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel
from datetime import datetime

import asyncpg
from service_core.db import get_tenant_connection

logger = logging.getLogger(__name__)
router = APIRouter()

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class NoteCreate(BaseModel):
    title: Optional[str] = ""
    body: str
    star: Optional[str] = None
    interaction_id: Optional[int] = None

class NoteUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    star: Optional[str] = None

class NoteResponse(BaseModel):
    note_id: int
    employee_id: int
    client_id: int
    title: Optional[str]
    body: str
    created_at: datetime
    updated_at: datetime
    star: Optional[str]
    interaction_id: Optional[int]
    employee_name: Optional[str] = None

# ============================================================================
# HELPERS
# ============================================================================

async def _get_employee_id(conn: asyncpg.Connection, email: str) -> Optional[int]:
    """Look up employee_id by email."""
    row = await conn.fetchrow(
        "SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1",
        email,
    )
    return row["employee_id"] if row else None


async def _get_employee_id_and_access(
    conn: asyncpg.Connection, email: str
) -> Tuple[Optional[int], Optional[str]]:
    """Look up employee_id + access tier by email."""
    row = await conn.fetchrow(
        "SELECT employee_id, access FROM employee_info WHERE email = $1 LIMIT 1",
        email,
    )
    if not row:
        return None, None
    return row["employee_id"], row["access"]

# ============================================================================
# NOTES ENDPOINTS
# ============================================================================

@router.get("/customers/{customer_id}/notes", response_model=List[NoteResponse])
async def get_customer_notes(
    customer_id: int,
    employee_id: Optional[int] = None,
    tenant: Tuple[asyncpg.Connection, dict] = Depends(get_tenant_connection),
) -> List[NoteResponse]:
    """
    Get all notes for a specific customer.

    Scoping:
    - Admin (employee_info.access = 'admin'): sees all notes by default; can pass
      employee_id=<n> to filter to a specific employee, or employee_id=0 to be
      explicit about "all employees".
    - Non-admin: always scoped to their own notes; the employee_id param is ignored.
    """
    conn, user = tenant
    try:
        user_email = user.get('email', '')
        logger.info(f"Getting notes for customer {customer_id} by user {user_email}")

        current_employee_id, access_role = await _get_employee_id_and_access(conn, user_email)
        if not current_employee_id:
            raise HTTPException(status_code=404, detail="Employee not found")

        is_admin = access_role == 'admin'

        if is_admin:
            if employee_id is None or employee_id == 0:
                resolved_employee_id = None
            else:
                resolved_employee_id = employee_id
        else:
            resolved_employee_id = current_employee_id

        if resolved_employee_id is not None:
            rows = await conn.fetch("""
                SELECT n.note_id, n.employee_id, n.client_id, n.title, n.body,
                       n.created_at, n.updated_at, n.star, n.interaction_id,
                       e.name as employee_name
                FROM employee_client_notes n
                LEFT JOIN employee_info e ON n.employee_id = e.employee_id
                WHERE n.client_id = $1 AND n.employee_id = $2
                ORDER BY n.created_at DESC
            """, customer_id, resolved_employee_id)
        else:
            rows = await conn.fetch("""
                SELECT n.note_id, n.employee_id, n.client_id, n.title, n.body,
                       n.created_at, n.updated_at, n.star, n.interaction_id,
                       e.name as employee_name
                FROM employee_client_notes n
                LEFT JOIN employee_info e ON n.employee_id = e.employee_id
                WHERE n.client_id = $1
                ORDER BY n.created_at DESC
            """, customer_id)

        return [
            NoteResponse(
                note_id=r["note_id"], employee_id=r["employee_id"], client_id=r["client_id"],
                title=r["title"], body=r["body"], created_at=r["created_at"],
                updated_at=r["updated_at"], star=r["star"], interaction_id=r["interaction_id"],
                employee_name=r.get("employee_name"),
            )
            for r in rows
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting customer notes: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/customers/{customer_id}/notes", response_model=NoteResponse)
async def create_customer_note(
    customer_id: int,
    note_data: NoteCreate,
    tenant: Tuple[asyncpg.Connection, dict] = Depends(get_tenant_connection),
) -> NoteResponse:
    """Create a new note for a customer."""
    conn, user = tenant
    try:
        user_email = user.get('email', '')
        logger.info(f"Creating note for customer {customer_id} by user {user_email}")

        emp_id = await _get_employee_id(conn, user_email)
        if not emp_id:
            raise HTTPException(status_code=404, detail="Employee not found")

        customer = await conn.fetchrow(
            "SELECT client_id, name FROM clients WHERE client_id = $1", customer_id,
        )
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

        link = await conn.fetchrow(
            "SELECT 1 FROM employee_client_links WHERE employee_id = $1 AND client_id = $2 AND status = 'active'",
            emp_id, customer_id,
        )
        if not link:
            raise HTTPException(
                status_code=403,
                detail=f"You don't have the right to add notes for customer '{customer.get('name', customer_id)}'.",
            )

        if note_data.interaction_id:
            interaction = await conn.fetchrow(
                "SELECT interaction_id FROM interaction_details WHERE interaction_id = $1 AND customer_id = $2",
                note_data.interaction_id, customer_id,
            )
            if not interaction:
                raise HTTPException(status_code=404, detail="Interaction not found or doesn't belong to this customer")

        new_note = await conn.fetchrow("""
            INSERT INTO employee_client_notes (employee_id, client_id, title, body, star, interaction_id)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING note_id, employee_id, client_id, title, body,
                      created_at, updated_at, star, interaction_id
        """, emp_id, customer_id, note_data.title, note_data.body, note_data.star, note_data.interaction_id)

        from services.cache_service import clear_cache
        clear_cache(f"customer_id={customer_id}")

        # Fire-and-forget: generate embedding for RAG search
        try:
            import asyncio
            from services.rag.embedding_sync_service import embed_single_note
            asyncio.ensure_future(embed_single_note(user_email, new_note['note_id'], note_data.title, note_data.body))
        except Exception as embed_err:
            logger.debug(f"Note embedding skipped: {embed_err}")

        return NoteResponse(
            note_id=new_note["note_id"], employee_id=new_note["employee_id"],
            client_id=new_note["client_id"], title=new_note["title"], body=new_note["body"],
            created_at=new_note["created_at"], updated_at=new_note["updated_at"],
            star=new_note["star"], interaction_id=new_note["interaction_id"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating customer note: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/notes/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: int,
    note_data: NoteUpdate,
    request: Request,
    tenant: Tuple[asyncpg.Connection, dict] = Depends(get_tenant_connection),
) -> NoteResponse:
    """Update an existing note."""
    conn, user = tenant
    try:
        user_email = user.get('email', '')
        logger.info(f"Updating note {note_id} by user {user_email}")

        request_body = await request.json()

        emp_id = await _get_employee_id(conn, user_email)
        if not emp_id:
            raise HTTPException(status_code=404, detail="Employee not found")

        note_record = await conn.fetchrow(
            "SELECT note_id, client_id FROM employee_client_notes WHERE note_id = $1 AND employee_id = $2",
            note_id, emp_id,
        )
        if not note_record:
            raise HTTPException(status_code=404, detail="Note not found or access denied")

        client_id = note_record["client_id"]

        link = await conn.fetchrow(
            "SELECT 1 FROM employee_client_links WHERE employee_id = $1 AND client_id = $2 AND status = 'active'",
            emp_id, client_id,
        )
        if not link:
            raise HTTPException(status_code=403, detail="You don't have the right to modify notes for this customer.")

        set_parts = []
        values = []
        idx = 1

        if "title" in request_body:
            set_parts.append(f"title = ${idx}")
            values.append(note_data.title)
            idx += 1
        if "body" in request_body:
            set_parts.append(f"body = ${idx}")
            values.append(note_data.body)
            idx += 1
        if "star" in request_body:
            set_parts.append(f"star = ${idx}")
            values.append(note_data.star)
            idx += 1

        if not set_parts:
            raise HTTPException(status_code=400, detail="No fields to update")

        values.append(note_id)

        updated_note = await conn.fetchrow(f"""
            UPDATE employee_client_notes
            SET {', '.join(set_parts)}
            WHERE note_id = ${idx}
            RETURNING note_id, employee_id, client_id, title, body,
                      created_at, updated_at, star, interaction_id
        """, *values)

        from services.cache_service import clear_cache
        clear_cache(f"customer_id={client_id}")

        return NoteResponse(
            note_id=updated_note["note_id"], employee_id=updated_note["employee_id"],
            client_id=updated_note["client_id"], title=updated_note["title"], body=updated_note["body"],
            created_at=updated_note["created_at"], updated_at=updated_note["updated_at"],
            star=updated_note["star"], interaction_id=updated_note.get("interaction_id"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating note: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/notes/{note_id}")
async def delete_note(
    note_id: int,
    tenant: Tuple[asyncpg.Connection, dict] = Depends(get_tenant_connection),
) -> Dict[str, Any]:
    """Delete a note."""
    conn, user = tenant
    try:
        user_email = user.get('email', '')
        logger.info(f"Deleting note {note_id} by user {user_email}")

        emp_id = await _get_employee_id(conn, user_email)
        if not emp_id:
            raise HTTPException(status_code=404, detail="Employee not found")

        note_record = await conn.fetchrow(
            "SELECT note_id, client_id FROM employee_client_notes WHERE note_id = $1 AND employee_id = $2",
            note_id, emp_id,
        )
        if not note_record:
            raise HTTPException(status_code=404, detail="Note not found or access denied")

        client_id = note_record["client_id"]

        await conn.execute("DELETE FROM employee_client_notes WHERE note_id = $1", note_id)

        from services.cache_service import clear_cache
        clear_cache(f"customer_id={client_id}")

        return {"success": True, "message": "Note deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting note: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
