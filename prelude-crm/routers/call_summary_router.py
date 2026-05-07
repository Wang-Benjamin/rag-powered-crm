"""
Call Summary Router - Handles all call summary related endpoints
Stores call summaries in interaction_details table with type='call'
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone

from service_core.db import get_tenant_connection
from services.cache_service import clear_cache

logger = logging.getLogger(__name__)
router = APIRouter()

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class CallSummaryCreate(BaseModel):
    """Model for creating a new call summary"""
    content: str = Field(..., min_length=1, max_length=5000, description="Call summary content")
    theme: Optional[str] = Field(None, max_length=50, description="Call topic/theme")
    source: Optional[str] = Field(None, max_length=50, description="Source identifier")
    duration_minutes: Optional[int] = Field(None, ge=0, description="Call duration in minutes")

class CallSummaryUpdate(BaseModel):
    """Model for updating a call summary"""
    content: Optional[str] = Field(None, min_length=1, max_length=5000, description="Call summary content")
    theme: Optional[str] = Field(None, max_length=50, description="Call topic/theme")

class CallSummaryResponse(BaseModel):
    """Model for call summary response"""
    interaction_id: int
    customer_id: int
    employee_id: int
    type: str
    content: str
    theme: Optional[str]
    source: Optional[str]
    created_at: datetime
    updated_at: datetime
    employee_name: Optional[str] = None
    employee_role: Optional[str] = None

# ============================================================================
# CALL SUMMARY ENDPOINTS
# ============================================================================

@router.post("/customers/{customer_id}/call-summaries", response_model=CallSummaryResponse)
async def create_call_summary(
    customer_id: int,
    call_data: CallSummaryCreate,
    tenant: tuple = Depends(get_tenant_connection)
) -> CallSummaryResponse:
    """
    Create a new call summary for a customer.
    Stores the call summary in interaction_details table with type='call'.
    """
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        logger.info(f"Creating call summary for customer {customer_id} by user {user_email}")

        async with conn.transaction():
            # Get employee_id for the authenticated user
            row = await conn.fetchrow(
                "SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email
            )
            employee_id = row["employee_id"] if row else None
            if not employee_id:
                raise HTTPException(status_code=404, detail="Employee not found")

            # Verify customer exists and get customer name
            customer = await conn.fetchrow(
                "SELECT client_id, name FROM clients WHERE client_id = $1", customer_id
            )
            if not customer:
                raise HTTPException(status_code=404, detail="Customer not found")

            customer_name = dict(customer).get('name', f'ID {customer_id}')

            # Verify employee-client link exists (required for foreign key constraint)
            link = await conn.fetchrow("""
                SELECT 1 FROM employee_client_links
                WHERE employee_id = $1 AND client_id = $2
            """, employee_id, customer_id)
            if not link:
                raise HTTPException(
                    status_code=403,
                    detail=f"You don't have the right to add call summaries for customer '{customer_name}'."
                )

            # Validate content
            if not call_data.content or not call_data.content.strip():
                raise HTTPException(status_code=400, detail="Call summary content cannot be empty")

            # Prepare current timestamp
            now = datetime.now(timezone.utc)

            # Insert call summary into interaction_details
            new_call_summary = await conn.fetchrow("""
                INSERT INTO interaction_details (
                    customer_id, employee_id, type, content, theme,
                    source, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING interaction_id, customer_id, employee_id, type, content,
                          theme, source, created_at, updated_at
            """, customer_id, employee_id, 'call',
                call_data.content.strip(), call_data.theme, call_data.source, now, now)

            # Get employee information for response
            employee_info = await conn.fetchrow("""
                SELECT name, role
                FROM employee_info
                WHERE employee_id = $1
            """, employee_id)

            logger.info(f"Call summary created successfully: interaction_id={new_call_summary['interaction_id']}")

            # Fire-and-forget: generate embedding for RAG search
            try:
                import asyncio
                from services.rag.embedding_sync_service import embed_single_interaction
                asyncio.ensure_future(embed_single_interaction(user_email, interaction_id, call_data.content.strip()))
            except Exception as embed_err:
                logger.debug(f"Call embedding skipped: {embed_err}")

        # Clear relevant caches - use correct pattern to match cache keys
        clear_cache(f"customer_id={customer_id}")
        clear_cache("get_recent_interactions")

        return CallSummaryResponse(
            interaction_id=new_call_summary['interaction_id'],
            customer_id=new_call_summary['customer_id'],
            employee_id=new_call_summary['employee_id'],
            type=new_call_summary['type'],
            content=new_call_summary['content'],
            theme=new_call_summary['theme'],
            source=new_call_summary['source'],
            created_at=new_call_summary['created_at'],
            updated_at=new_call_summary['updated_at'],
            employee_name=employee_info['name'] if employee_info else None,
            employee_role=employee_info['role'] if employee_info else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating call summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/customers/{customer_id}/call-summaries", response_model=List[CallSummaryResponse])
async def get_call_summaries(
    customer_id: int,
    employee_id: Optional[int] = None,
    tenant: tuple = Depends(get_tenant_connection)
) -> List[CallSummaryResponse]:
    """
    Get all call summaries for a specific customer.

    Optional employee_id param:
    - Absent: default to current user's employee_id
    - 0: all employees (no filter)
    - Positive int: specific employee

    Retrieves from interaction_details table where type='call'.
    """
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        logger.info(f"Getting call summaries for customer {customer_id} by user {user_email}")

        # Resolve employee_id based on param
        if employee_id is not None:
            if employee_id == 0:
                resolved_employee_id = None  # All employees
            else:
                resolved_employee_id = employee_id
        else:
            # Default: current user
            row = await conn.fetchrow(
                "SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email
            )
            resolved_employee_id = row["employee_id"] if row else None
            if not resolved_employee_id:
                raise HTTPException(status_code=404, detail="Employee not found")

        # Build query based on whether we filter by employee
        if resolved_employee_id is not None:
            call_summaries = await conn.fetch("""
                SELECT
                    i.interaction_id,
                    i.customer_id,
                    i.employee_id,
                    i.type,
                    i.content,
                    i.theme,
                    i.source,
                    i.created_at,
                    i.updated_at,
                    e.name as employee_name,
                    e.role as employee_role
                FROM interaction_details i
                LEFT JOIN employee_info e ON i.employee_id = e.employee_id
                WHERE i.customer_id = $1
                  AND i.type = 'call'
                  AND i.employee_id = $2
                ORDER BY i.created_at DESC
            """, customer_id, resolved_employee_id)
        else:
            call_summaries = await conn.fetch("""
                SELECT
                    i.interaction_id,
                    i.customer_id,
                    i.employee_id,
                    i.type,
                    i.content,
                    i.theme,
                    i.source,
                    i.created_at,
                    i.updated_at,
                    e.name as employee_name,
                    e.role as employee_role
                FROM interaction_details i
                LEFT JOIN employee_info e ON i.employee_id = e.employee_id
                WHERE i.customer_id = $1
                  AND i.type = 'call'
                ORDER BY i.created_at DESC
            """, customer_id)

        logger.info(f"Found {len(call_summaries)} call summaries for customer {customer_id}")

        return [
            CallSummaryResponse(
                interaction_id=call['interaction_id'],
                customer_id=call['customer_id'],
                employee_id=call['employee_id'],
                type=call['type'],
                content=call['content'],
                theme=call['theme'],
                source=call['source'],
                created_at=call['created_at'],
                updated_at=call['updated_at'],
                employee_name=call['employee_name'],
                employee_role=call['employee_role']
            )
            for call in call_summaries
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting call summaries: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/customers/{customer_id}/call-summaries/{interaction_id}", response_model=CallSummaryResponse)
async def get_call_summary_by_id(
    customer_id: int,
    interaction_id: int,
    tenant: tuple = Depends(get_tenant_connection)
) -> CallSummaryResponse:
    """Get a specific call summary by interaction_id."""
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        logger.info(f"Getting call summary {interaction_id} for customer {customer_id}")

        # Get employee_id for the authenticated user
        row = await conn.fetchrow(
            "SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email
        )
        employee_id = row["employee_id"] if row else None
        if not employee_id:
            raise HTTPException(status_code=404, detail="Employee not found")

        # Get specific call summary
        call_summary = await conn.fetchrow("""
            SELECT
                i.interaction_id,
                i.customer_id,
                i.employee_id,
                i.type,
                i.content,
                i.theme,
                i.source,
                i.created_at,
                i.updated_at,
                e.name as employee_name,
                e.role as employee_role
            FROM interaction_details i
            LEFT JOIN employee_info e ON i.employee_id = e.employee_id
            WHERE i.interaction_id = $1
              AND i.customer_id = $2
              AND i.type = 'call'
              AND i.employee_id = $3
        """, interaction_id, customer_id, employee_id)

        if not call_summary:
            raise HTTPException(status_code=404, detail="Call summary not found or access denied")

        return CallSummaryResponse(
            interaction_id=call_summary['interaction_id'],
            customer_id=call_summary['customer_id'],
            employee_id=call_summary['employee_id'],
            type=call_summary['type'],
            content=call_summary['content'],
            theme=call_summary['theme'],
            source=call_summary['source'],
            created_at=call_summary['created_at'],
            updated_at=call_summary['updated_at'],
            employee_name=call_summary['employee_name'],
            employee_role=call_summary['employee_role']
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting call summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/customers/{customer_id}/call-summaries/{interaction_id}", response_model=CallSummaryResponse)
async def update_call_summary(
    customer_id: int,
    interaction_id: int,
    call_data: CallSummaryUpdate,
    tenant: tuple = Depends(get_tenant_connection)
) -> CallSummaryResponse:
    """Update an existing call summary."""
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        logger.info(f"Updating call summary {interaction_id} for customer {customer_id}")

        # Get employee_id for the authenticated user
        row = await conn.fetchrow(
            "SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email
        )
        employee_id = row["employee_id"] if row else None
        if not employee_id:
            raise HTTPException(status_code=404, detail="Employee not found")

        # Verify call summary exists and belongs to this employee and customer
        existing = await conn.fetchrow("""
            SELECT interaction_id FROM interaction_details
            WHERE interaction_id = $1
              AND customer_id = $2
              AND type = 'call'
              AND employee_id = $3
        """, interaction_id, customer_id, employee_id)

        if not existing:
            raise HTTPException(status_code=404, detail="Call summary not found or access denied")

        # Verify employee-client link exists (authorization check)
        link = await conn.fetchrow("""
            SELECT 1 FROM employee_client_links
            WHERE employee_id = $1 AND client_id = $2
        """, employee_id, customer_id)
        if not link:
            raise HTTPException(
                status_code=403,
                detail="You don't have the right to modify call summaries for this customer."
            )

        # Build dynamic update query
        update_fields = []
        update_values = []
        param_idx = 1

        if call_data.content is not None:
            if not call_data.content.strip():
                raise HTTPException(status_code=400, detail="Call summary content cannot be empty")
            update_fields.append(f"content = ${param_idx}")
            update_values.append(call_data.content.strip())
            param_idx += 1

        if call_data.theme is not None:
            update_fields.append(f"theme = ${param_idx}")
            update_values.append(call_data.theme.strip() if call_data.theme else None)
            param_idx += 1

        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")

        # Add updated_at timestamp
        update_fields.append(f"updated_at = ${param_idx}")
        update_values.append(datetime.now(timezone.utc))
        param_idx += 1

        # Add WHERE clause parameters
        update_values.extend([interaction_id, customer_id, employee_id])

        # Update the call summary
        query = f"""
            UPDATE interaction_details
            SET {', '.join(update_fields)}
            WHERE interaction_id = ${param_idx} AND customer_id = ${param_idx + 1} AND employee_id = ${param_idx + 2} AND type = 'call'
            RETURNING interaction_id, customer_id, employee_id, type, content,
                      theme, source, created_at, updated_at
        """

        updated_summary = await conn.fetchrow(query, *update_values)

        if not updated_summary:
            raise HTTPException(status_code=404, detail="Failed to update call summary")

        # Get employee information for response
        employee_info = await conn.fetchrow("""
            SELECT name, role
            FROM employee_info
            WHERE employee_id = $1
        """, employee_id)

        logger.info(f"Call summary updated successfully: interaction_id={interaction_id}")

        # Clear relevant caches - use correct pattern to match cache keys
        clear_cache(f"customer_id={customer_id}")
        clear_cache("get_recent_interactions")

        return CallSummaryResponse(
            interaction_id=updated_summary['interaction_id'],
            customer_id=updated_summary['customer_id'],
            employee_id=updated_summary['employee_id'],
            type=updated_summary['type'],
            content=updated_summary['content'],
            theme=updated_summary['theme'],
            source=updated_summary['source'],
            created_at=updated_summary['created_at'],
            updated_at=updated_summary['updated_at'],
            employee_name=employee_info['name'] if employee_info else None,
            employee_role=employee_info['role'] if employee_info else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating call summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/customers/{customer_id}/call-summaries/{interaction_id}")
async def delete_call_summary(
    customer_id: int,
    interaction_id: int,
    tenant: tuple = Depends(get_tenant_connection)
) -> Dict[str, Any]:
    """Delete a call summary."""
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        logger.info(f"Deleting call summary {interaction_id} for customer {customer_id}")

        # Get employee_id for the authenticated user
        row = await conn.fetchrow(
            "SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email
        )
        employee_id = row["employee_id"] if row else None
        if not employee_id:
            raise HTTPException(status_code=404, detail="Employee not found")

        # Verify call summary exists and belongs to this employee and customer
        existing = await conn.fetchrow("""
            SELECT interaction_id FROM interaction_details
            WHERE interaction_id = $1
              AND customer_id = $2
              AND type = 'call'
              AND employee_id = $3
        """, interaction_id, customer_id, employee_id)

        if not existing:
            raise HTTPException(status_code=404, detail="Call summary not found or access denied")

        # Delete the call summary
        await conn.execute("""
            DELETE FROM interaction_details
            WHERE interaction_id = $1
              AND customer_id = $2
              AND employee_id = $3
              AND type = 'call'
        """, interaction_id, customer_id, employee_id)

        logger.info(f"Call summary deleted successfully: interaction_id={interaction_id}")

        # Clear relevant caches - use correct pattern to match cache keys
        clear_cache(f"customer_id={customer_id}")
        clear_cache("get_recent_interactions")

        return {"success": True, "message": "Call summary deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting call summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
