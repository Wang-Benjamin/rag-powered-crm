import json
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Any
from datetime import datetime, timezone
import logging

from service_core.db import get_tenant_connection
from services.cache_service import clear_cache

from models.crm_models import DealNoteCreate, DealCallSummaryCreate, DealMeetingCreate, DealActivityResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# ============================================================================
# DEAL ACTIVITY ENDPOINTS
# ============================================================================

@router.post("/deals/{deal_id}/notes")
async def create_deal_note(
    deal_id: int,
    note_data: DealNoteCreate,
    tenant: tuple = Depends(get_tenant_connection)
) -> Dict[str, Any]:
    """Create a new note linked to a deal."""
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        logger.info(f"Creating note for deal {deal_id} by user {user_email}")

        async with conn.transaction():
            # Get employee_id for the authenticated user
            row = await conn.fetchrow(
                "SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email
            )
            employee_id = row["employee_id"] if row else None
            if not employee_id:
                raise HTTPException(status_code=404, detail="Employee not found")

            # Verify deal exists and get client_id
            deal = await conn.fetchrow("SELECT client_id FROM deals WHERE deal_id = $1", deal_id)
            if not deal:
                raise HTTPException(status_code=404, detail="Deal not found")

            client_id = deal['client_id']

            # Get customer name for error message
            customer = await conn.fetchrow("SELECT name FROM clients WHERE client_id = $1", client_id)
            customer_name = dict(customer).get('name', f'ID {client_id}') if customer else f'ID {client_id}'

            # Verify employee-client link exists and is active (authorization check)
            link = await conn.fetchrow("""
                SELECT 1 FROM employee_client_links
                WHERE employee_id = $1 AND client_id = $2 AND status = 'active'
            """, employee_id, client_id)
            if not link:
                raise HTTPException(
                    status_code=403,
                    detail=f"You don't have the right to add notes for customer '{customer_name}'."
                )

            # Insert new note with deal_id
            new_note = await conn.fetchrow("""
                INSERT INTO employee_client_notes (employee_id, client_id, deal_id, title, body, star)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING note_id, employee_id, client_id, deal_id, title, body,
                          created_at, updated_at, star, interaction_id
            """, employee_id, client_id, deal_id, note_data.title, note_data.body, note_data.star)

            logger.info(f"Note created for deal {deal_id}: note_id={new_note['note_id']}")

            # Fire-and-forget: generate embedding for RAG search
            try:
                import asyncio
                from services.rag.embedding_sync_service import embed_single_note
                asyncio.ensure_future(embed_single_note(user_email, new_note['note_id'], note_data.title, note_data.body))
            except Exception as embed_err:
                logger.debug(f"Note embedding skipped: {embed_err}")

        # Clear relevant caches
        clear_cache(f"customer_id={client_id}")
        clear_cache(f"deal_id={deal_id}")

        return {
            "note_id": new_note['note_id'],
            "employee_id": new_note['employee_id'],
            "client_id": new_note['client_id'],
            "deal_id": new_note['deal_id'],
            "title": new_note['title'],
            "body": new_note['body'],
            "star": new_note['star'],
            "interaction_id": new_note['interaction_id'],
            "created_at": new_note['created_at'].isoformat() if new_note['created_at'] else None,
            "updated_at": new_note['updated_at'].isoformat() if new_note['updated_at'] else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating deal note: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/deals/{deal_id}/call-summaries")
async def create_deal_call_summary(
    deal_id: int,
    call_data: DealCallSummaryCreate,
    tenant: tuple = Depends(get_tenant_connection)
) -> Dict[str, Any]:
    """Create a new call summary linked to a deal."""
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        logger.info(f"Creating call summary for deal {deal_id} by user {user_email}")

        async with conn.transaction():
            # Get employee_id for the authenticated user
            row = await conn.fetchrow(
                "SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email
            )
            employee_id = row["employee_id"] if row else None
            if not employee_id:
                raise HTTPException(status_code=404, detail="Employee not found")

            # Verify deal exists and get client_id
            deal = await conn.fetchrow("SELECT client_id FROM deals WHERE deal_id = $1", deal_id)
            if not deal:
                raise HTTPException(status_code=404, detail="Deal not found")

            customer_id = deal['client_id']

            # Insert call summary with deal_id
            now = datetime.now(timezone.utc)
            new_call = await conn.fetchrow("""
                INSERT INTO interaction_details
                (customer_id, employee_id, deal_id, type, content, theme, source, created_at, updated_at)
                VALUES ($1, $2, $3, 'call', $4, $5, $6, $7, $8)
                RETURNING interaction_id, customer_id, employee_id, deal_id, type, content, theme, source, created_at, updated_at
            """, customer_id, employee_id, deal_id, call_data.content, call_data.theme, call_data.source, now, now)

            logger.info(f"Call summary created for deal {deal_id}: interaction_id={new_call['interaction_id']}")

            # Fire-and-forget: generate embedding for RAG search
            try:
                import asyncio
                from services.rag.embedding_sync_service import embed_single_interaction
                asyncio.ensure_future(embed_single_interaction(user_email, interaction_id, call_data.content))
            except Exception as embed_err:
                logger.debug(f"Call embedding skipped: {embed_err}")

        # Clear relevant caches
        clear_cache(f"customer_id={customer_id}")
        clear_cache(f"deal_id={deal_id}")

        return {
            "interaction_id": new_call['interaction_id'],
            "customer_id": new_call['customer_id'],
            "employee_id": new_call['employee_id'],
            "deal_id": new_call['deal_id'],
            "type": new_call['type'],
            "content": new_call['content'],
            "theme": new_call['theme'],
            "source": new_call['source'],
            "created_at": new_call['created_at'].isoformat() if new_call['created_at'] else None,
            "updated_at": new_call['updated_at'].isoformat() if new_call['updated_at'] else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating deal call summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/deals/{deal_id}/meetings")
async def create_deal_meeting(
    deal_id: int,
    meeting_data: DealMeetingCreate,
    tenant: tuple = Depends(get_tenant_connection)
) -> Dict[str, Any]:
    """Create a new meeting linked to a deal."""
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        logger.info(f"Creating meeting for deal {deal_id} by user {user_email}")

        async with conn.transaction():
            # Get employee_id for the authenticated user
            row = await conn.fetchrow(
                "SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email
            )
            employee_id = row["employee_id"] if row else None
            if not employee_id:
                raise HTTPException(status_code=404, detail="Employee not found")

            # Verify deal exists and get client_id
            deal = await conn.fetchrow("SELECT client_id FROM deals WHERE deal_id = $1", deal_id)
            if not deal:
                raise HTTPException(status_code=404, detail="Deal not found")

            customer_id = deal['client_id']

            # Format meeting content as JSON
            meeting_content = json.dumps({
                "title": meeting_data.title,
                "description": meeting_data.description,
                "start_time": meeting_data.start_time,
                "end_time": meeting_data.end_time,
                "attendees": meeting_data.attendees,
                "location": meeting_data.location,
                "timezone": meeting_data.timezone
            })

            # Insert meeting with deal_id
            new_meeting = await conn.fetchrow("""
                INSERT INTO interaction_details
                (customer_id, employee_id, deal_id, type, content, theme, source, created_at, updated_at)
                VALUES ($1, $2, $3, 'meet', $4, $5, 'deal_activity', NOW(), NOW())
                RETURNING interaction_id, customer_id, employee_id, deal_id, type, content, theme, created_at, updated_at
            """, customer_id, employee_id, deal_id, meeting_content, meeting_data.title)

            logger.info(f"Meeting created for deal {deal_id}: interaction_id={new_meeting['interaction_id']}")

            # Fire-and-forget: generate embedding for RAG search
            try:
                import asyncio
                from services.rag.embedding_sync_service import embed_single_interaction
                asyncio.ensure_future(embed_single_interaction(user_email, interaction_id, meeting_content))
            except Exception as embed_err:
                logger.debug(f"Meeting embedding skipped: {embed_err}")

        # Clear relevant caches
        clear_cache(f"customer_id={customer_id}")
        clear_cache(f"deal_id={deal_id}")

        # Parse content back to dict for response
        content_dict = json.loads(new_meeting['content']) if isinstance(new_meeting['content'], str) else new_meeting['content']

        return {
            "interaction_id": new_meeting['interaction_id'],
            "customer_id": new_meeting['customer_id'],
            "employee_id": new_meeting['employee_id'],
            "deal_id": new_meeting['deal_id'],
            "type": new_meeting['type'],
            "title": content_dict.get('title'),
            "description": content_dict.get('description'),
            "start_time": content_dict.get('start_time'),
            "end_time": content_dict.get('end_time'),
            "attendees": content_dict.get('attendees', []),
            "location": content_dict.get('location'),
            "timezone": content_dict.get('timezone'),
            "created_at": new_meeting['created_at'].isoformat() if new_meeting['created_at'] else None,
            "updated_at": new_meeting['updated_at'].isoformat() if new_meeting['updated_at'] else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating deal meeting: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/deals/{deal_id}/activities")
async def get_deal_activities(
    deal_id: int,
    tenant: tuple = Depends(get_tenant_connection)
) -> DealActivityResponse:
    """Get all activities (notes, calls, meetings) for a specific deal."""
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        logger.info(f"Getting activities for deal {deal_id} by user {user_email}")

        # Verify deal exists
        deal = await conn.fetchrow("SELECT deal_id, client_id FROM deals WHERE deal_id = $1", deal_id)
        if not deal:
            raise HTTPException(status_code=404, detail="Deal not found")

        # Get notes for this deal
        notes_data = await conn.fetch("""
            SELECT n.note_id, n.employee_id, n.client_id, n.deal_id, n.title, n.body,
                   n.star, n.interaction_id, n.created_at, n.updated_at,
                   e.name as employee_name
            FROM employee_client_notes n
            LEFT JOIN employee_info e ON n.employee_id = e.employee_id
            WHERE n.deal_id = $1
            ORDER BY n.created_at DESC
        """, deal_id)

        # Get interactions (calls and meetings) for this deal
        interactions_data = await conn.fetch("""
            SELECT i.interaction_id, i.customer_id, i.employee_id, i.deal_id, i.type,
                   i.content, i.theme, i.source, i.created_at, i.updated_at,
                   e.name as employee_name
            FROM interaction_details i
            LEFT JOIN employee_info e ON i.employee_id = e.employee_id
            WHERE i.deal_id = $1 AND i.type != 'quote_request'
            ORDER BY i.created_at DESC
        """, deal_id)
        # Convert to list of dicts so we can append emails
        interactions_data = [dict(r) for r in interactions_data]

        # Get emails for this deal
        emails_data = await conn.fetch("""
            SELECT ce.email_id as interaction_id, ce.customer_id, ce.employee_id, ce.deal_id,
                   'email' as type, ce.body as content,
                   ce.subject as theme, NULL as source, ce.created_at, ce.updated_at,
                   ce.subject, ce.direction, ce.from_email, ce.to_email,
                   e.name as employee_name
            FROM crm_emails ce
            LEFT JOIN employee_info e ON ce.employee_id = e.employee_id
            WHERE ce.deal_id = $1
            ORDER BY ce.created_at DESC
        """, deal_id)

        # Format notes
        notes = []
        for note in notes_data:
            notes.append({
                "note_id": note['note_id'],
                "employee_id": note['employee_id'],
                "employee_name": note['employee_name'],
                "client_id": note['client_id'],
                "deal_id": note['deal_id'],
                "title": note['title'],
                "body": note['body'],
                "star": note['star'],
                "interaction_id": note['interaction_id'],
                "created_at": note['created_at'].isoformat() if note['created_at'] else None,
                "updated_at": note['updated_at'].isoformat() if note['updated_at'] else None,
                "activity_type": "note"
            })

        # Format emails as interactions
        for email in emails_data:
            interactions_data.append(dict(email))

        # Format interactions
        interactions = []
        for interaction in interactions_data:
            interaction_dict = {
                "interaction_id": interaction['interaction_id'],
                "customer_id": interaction['customer_id'],
                "employee_id": interaction['employee_id'],
                "employee_name": interaction['employee_name'],
                "deal_id": interaction['deal_id'],
                "type": interaction['type'],
                "theme": interaction['theme'],
                "source": interaction['source'],
                "created_at": interaction['created_at'].isoformat() if interaction['created_at'] else None,
                "updated_at": interaction['updated_at'].isoformat() if interaction['updated_at'] else None,
                "activity_type": interaction['type']
            }

            # Parse content if it's JSON (for meetings)
            if interaction['type'] == 'meet':
                try:
                    content = json.loads(interaction['content']) if isinstance(interaction['content'], str) else interaction['content']
                    interaction_dict.update({
                        "title": content.get('title'),
                        "description": content.get('description'),
                        "start_time": content.get('start_time'),
                        "end_time": content.get('end_time'),
                        "attendees": content.get('attendees', []),
                        "location": content.get('location')
                    })
                except Exception:
                    interaction_dict["content"] = interaction['content']
            else:
                interaction_dict["content"] = interaction['content']

            interactions.append(interaction_dict)

        # Create unified timeline (merge notes and interactions, sort by created_at)
        timeline = []
        for note in notes:
            timeline.append({**note, "timestamp": note['created_at']})
        for interaction in interactions:
            timeline.append({**interaction, "timestamp": interaction['created_at']})

        # Sort timeline by timestamp (most recent first)
        timeline.sort(key=lambda x: x['timestamp'] if x['timestamp'] else '', reverse=True)

        return DealActivityResponse(
            notes=notes,
            interactions=interactions,
            timeline=timeline
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting deal activities: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/deals/{deal_id}/notes/{note_id}")
async def delete_deal_note(
    deal_id: int,
    note_id: int,
    tenant: tuple = Depends(get_tenant_connection)
) -> Dict[str, Any]:
    """Delete a note linked to a deal."""
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        logger.info(f"Deleting note {note_id} from deal {deal_id} by user {user_email}")

        async with conn.transaction():
            # Get employee_id for the authenticated user
            row = await conn.fetchrow(
                "SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email
            )
            employee_id = row["employee_id"] if row else None
            if not employee_id:
                raise HTTPException(status_code=404, detail="Employee not found")

            # Verify note exists, belongs to this deal and employee
            note_record = await conn.fetchrow("""
                SELECT note_id, client_id FROM employee_client_notes
                WHERE note_id = $1 AND deal_id = $2 AND employee_id = $3
            """, note_id, deal_id, employee_id)

            if not note_record:
                raise HTTPException(status_code=404, detail="Note not found or access denied")

            client_id = note_record['client_id']

            # Delete the note
            await conn.execute("DELETE FROM employee_client_notes WHERE note_id = $1", note_id)

            logger.info(f"Note {note_id} deleted from deal {deal_id}")

        # Clear relevant caches
        clear_cache(f"customer_id={client_id}")
        clear_cache(f"deal_id={deal_id}")

        return {"success": True, "message": "Note deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting deal note: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/deals/{deal_id}/call-summaries/{interaction_id}")
async def delete_deal_call_summary(
    deal_id: int,
    interaction_id: int,
    tenant: tuple = Depends(get_tenant_connection)
) -> Dict[str, Any]:
    """Delete a call summary linked to a deal."""
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        logger.info(f"Deleting call summary {interaction_id} from deal {deal_id} by user {user_email}")

        async with conn.transaction():
            # Get employee_id for the authenticated user
            row = await conn.fetchrow(
                "SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email
            )
            employee_id = row["employee_id"] if row else None
            if not employee_id:
                raise HTTPException(status_code=404, detail="Employee not found")

            # Verify call summary exists, belongs to this deal and employee
            call_record = await conn.fetchrow("""
                SELECT interaction_id, customer_id FROM interaction_details
                WHERE interaction_id = $1 AND deal_id = $2 AND type = 'call' AND employee_id = $3
            """, interaction_id, deal_id, employee_id)

            if not call_record:
                raise HTTPException(status_code=404, detail="Call summary not found or access denied")

            customer_id = call_record['customer_id']

            # Delete the call summary
            await conn.execute("""
                DELETE FROM interaction_details
                WHERE interaction_id = $1 AND deal_id = $2 AND employee_id = $3 AND type = 'call'
            """, interaction_id, deal_id, employee_id)

            logger.info(f"Call summary {interaction_id} deleted from deal {deal_id}")

        # Clear relevant caches
        clear_cache(f"customer_id={customer_id}")
        clear_cache(f"deal_id={deal_id}")

        return {"success": True, "message": "Call summary deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting deal call summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
