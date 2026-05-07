"""
Deal Room Service
=================
Business logic for deal room creation, management, and cross-DB token handling.
"""

import secrets
import string
import logging
import json
from typing import Dict, Any, Optional, List

from service_core.db import get_pool_manager

logger = logging.getLogger(__name__)

NANOID_ALPHABET = string.ascii_lowercase + string.digits
NANOID_LENGTH = 21  # 128+ bits of entropy

VALID_ROOM_STATUSES = ('draft', 'sent', 'viewed', 'quote_requested', 'closed-won', 'closed-lost')
CLOSED_STATUSES = ('closed-won', 'closed-lost')


def generate_share_token() -> str:
    """Generate a cryptographically random nanoid for deal room URLs."""
    return ''.join(secrets.choice(NANOID_ALPHABET) for _ in range(NANOID_LENGTH))


async def create_deal_room(
    conn,
    deal_id: int,
    user_email: str,
    quote_data: dict,
    sample_timeline: dict,
    room_settings: dict,
    fob_price: Optional[float] = None,
    fob_currency: str = 'USD',
) -> Dict[str, Any]:
    """
    Create a deal room for an existing deal.

    Cross-DB write ordering (expand-and-contract):
    1. INSERT into deal_room_tokens (shared DB) first
    2. UPDATE deals (tenant DB) second
    3. If step 2 fails, DELETE the token (compensating write)
    """
    # Verify deal exists and has employee_id
    deal = await conn.fetchrow(
        "SELECT deal_id, employee_id, client_id, share_token FROM deals WHERE deal_id = $1",
        deal_id
    )
    if not deal:
        raise ValueError(f"Deal {deal_id} not found")
    if not deal['employee_id']:
        raise ValueError(f"Deal {deal_id} has no assigned employee — assign a salesperson before creating a deal room")
    if deal['share_token']:
        raise ValueError(f"Deal {deal_id} already has a deal room")

    share_token = generate_share_token()

    # Get the db_name for this tenant from the pool manager
    pm = get_pool_manager()
    db_name = await pm.lookup_db_name(user_email)

    # Step 1: Insert token into shared analytics DB
    analytics_pool = await pm.get_analytics_pool()
    try:
        await analytics_pool.execute(
            "INSERT INTO deal_room_tokens (share_token, db_name, deal_id, owner_email) "
            "VALUES ($1, $2, $3, $4)",
            share_token, db_name, deal_id, user_email
        )
    except Exception as e:
        logger.error(f"Failed to insert deal room token: {e}")
        raise

    # Step 2: Update deal in tenant DB
    try:
        await conn.execute(
            "UPDATE deals SET share_token = $1, room_status = 'draft', "
            "sample_timeline = $2, room_settings = $3, "
            "fob_price = COALESCE($4, fob_price), fob_currency = COALESCE($5, fob_currency), "
            "updated_at = NOW() WHERE deal_id = $6",
            share_token,
            sample_timeline,
            room_settings,
            fob_price,
            fob_currency,
            deal_id
        )
    except Exception as e:
        # Compensating write: remove token from shared DB
        logger.error(f"Failed to update deal, compensating: {e}")
        try:
            await analytics_pool.execute(
                "DELETE FROM deal_room_tokens WHERE share_token = $1",
                share_token
            )
        except Exception as cleanup_err:
            logger.error(f"Failed to cleanup token after deal update failure: {cleanup_err}")
        raise

    logger.info(f"Deal room created for deal {deal_id}, token: {share_token}")

    # Stage auto-progression (replied → engaged)
    if deal.get('client_id'):
        try:
            from services.stage_progression_service import apply_stage_progression
            await apply_stage_progression(conn, deal['client_id'])
        except Exception as stage_err:
            logger.debug(f"Stage progression skipped: {stage_err}")

    # Fetch the deal to build quoteData from columns
    deal_row = await conn.fetchrow(
        "SELECT deal_name, product_name, fob_price, fob_currency, landed_price, hs_code, quantity, moq "
        "FROM deals WHERE deal_id = $1", deal_id
    )
    fob_val = float(deal_row['fob_price']) if deal_row and deal_row['fob_price'] else fob_price
    landed_val = float(deal_row['landed_price']) if deal_row and deal_row['landed_price'] else fob_val
    cur = (deal_row['fob_currency'] if deal_row else None) or fob_currency or 'USD'
    qty_val = (deal_row['quantity'] if deal_row else None) or 0
    moq_val = (deal_row['moq'] if deal_row else None) or 0
    deal_name = deal_row['deal_name'] if deal_row else ''
    product_name = (deal_row['product_name'] if deal_row else None) or deal_name

    built_quote_data = {}
    if fob_val is not None:
        built_quote_data = {
            'productName': product_name,
            'hsCode': (deal_row['hs_code'] if deal_row else '') or '',
            'quantity': qty_val,
            'moq': moq_val,
            'options': [{
                'label': product_name or 'Quote',
                'origin': '',
                'currency': cur,
                'fobPrice': fob_val,
                'landedPrice': landed_val,
            }],
        }

    return {
        "deal_id": deal_id,
        "share_token": share_token,
        "room_status": "draft",
        "quote_data": built_quote_data,
        "sample_timeline": sample_timeline,
        "room_settings": room_settings,
        "fob_price": fob_val,
        "fob_currency": cur,
    }


async def update_deal_room(
    conn,
    deal_id: int,
    quote_data: Optional[dict] = None,
    sample_timeline: Optional[dict] = None,
    room_settings: Optional[dict] = None,
) -> Dict[str, Any]:
    """Update deal room data (quote, timeline, settings)."""
    sets = ["updated_at = NOW()"]
    params = []
    idx = 1

    if quote_data is not None:
        sets.append(f"quote_data = ${idx}")
        params.append(quote_data)
        idx += 1
    if sample_timeline is not None:
        sets.append(f"sample_timeline = ${idx}")
        params.append(sample_timeline)
        idx += 1
    if room_settings is not None:
        sets.append(f"room_settings = COALESCE(room_settings, '{{}}'::jsonb) || ${idx}::jsonb")
        params.append(room_settings)
        idx += 1

    params.append(deal_id)
    query = f"UPDATE deals SET {', '.join(sets)} WHERE deal_id = ${idx} RETURNING *"

    row = await conn.fetchrow(query, *params)
    if not row:
        raise ValueError(f"Deal {deal_id} not found")

    return dict(row)


async def get_deal_room(conn, deal_id: int) -> Optional[Dict[str, Any]]:
    """Get deal room data for a specific deal."""
    row = await conn.fetchrow(
        "SELECT deal_id, deal_name, product_name, share_token, room_status, quote_data, "
        "sample_timeline, room_settings, view_count, last_viewed_at, "
        "value_usd, client_id, employee_id, "
        "fob_price, fob_currency, landed_price, hs_code, quantity, moq "
        "FROM deals WHERE deal_id = $1 AND share_token IS NOT NULL",
        deal_id
    )
    if not row:
        return None

    result = dict(row)

    # Build quote_data from deal columns (single source of truth)
    fob = float(row['fob_price']) if row['fob_price'] else None
    landed = float(row['landed_price']) if row['landed_price'] else fob
    currency = row['fob_currency'] or 'USD'
    qty_val = row['quantity'] or 0
    moq_val = row['moq'] or 0

    product_name = row['product_name'] or row['deal_name'] or ''

    if fob is not None:
        result['quote_data'] = {
            'productName': product_name,
            'hsCode': row['hs_code'] or '',
            'quantity': qty_val,
            'moq': moq_val,
            'options': [{
                'label': product_name or 'Quote',
                'origin': '',
                'currency': currency,
                'fobPrice': fob,
                'landedPrice': landed,
            }],
        }

    return result


async def list_deal_rooms(conn) -> List[Dict[str, Any]]:
    """List all deals that have deal rooms."""
    rows = await conn.fetch(
        "SELECT d.deal_id, d.deal_name, d.product_name, d.share_token, d.room_status, "
        "d.quote_data, d.view_count, d.last_viewed_at, d.value_usd, "
        "d.fob_price, d.fob_currency, d.landed_price, d.quantity, d.moq, "
        "c.name as client_name, "
        "e.name as salesman_name "
        "FROM deals d "
        "LEFT JOIN clients c ON d.client_id = c.client_id "
        "LEFT JOIN employee_info e ON d.employee_id = e.employee_id "
        "WHERE d.share_token IS NOT NULL "
        "ORDER BY d.updated_at DESC"
    )
    return [dict(row) for row in rows]


async def get_deal_room_analytics(conn, deal_id: int) -> Dict[str, Any]:
    """Get view analytics for a deal room."""
    # Use deals.view_count as the authoritative total (incremented on new sessions)
    deal_row = await conn.fetchrow(
        "SELECT COALESCE(view_count, 0) AS view_count, client_id FROM deals WHERE deal_id = $1",
        deal_id
    )

    # Fetch target buyer info from clients
    target_buyer_name = None
    target_buyer_company = None
    if deal_row and deal_row['client_id']:
        client_row = await conn.fetchrow(
            "SELECT name FROM clients WHERE client_id = $1",
            deal_row['client_id']
        )
        if client_row:
            target_buyer_name = client_row['name']
            target_buyer_company = client_row['name']

    # Unique visitors from deal_room_views
    visitor_count = await conn.fetchrow(
        "SELECT COUNT(DISTINCT visitor_id) AS unique_visitors "
        "FROM deal_room_views WHERE deal_id = $1",
        deal_id
    )

    # Fetch recent views only (last 50)
    views = await conn.fetch(
        "SELECT visitor_id, session_token, viewer_email, started_at, "
        "duration_seconds, sections_viewed "
        "FROM deal_room_views "
        "WHERE deal_id = $1 ORDER BY started_at DESC LIMIT 50",
        deal_id
    )

    # Fetch recent quote requests from interaction_details
    quote_request_rows = await conn.fetch(
        "SELECT content, created_at FROM interaction_details "
        "WHERE deal_id = $1 AND type = 'quote_request' "
        "ORDER BY created_at DESC LIMIT 5",
        deal_id
    )
    quote_requests = []
    for qr in quote_request_rows:
        try:
            content = qr['content']
            if isinstance(content, str):
                parsed = json.loads(content)
            else:
                parsed = dict(content) if content else {}
            quote_requests.append({
                "buyer_name": parsed.get("buyer_name"),
                "buyer_company": parsed.get("buyer_company"),
                "buyer_email": parsed.get("buyer_email"),
                "message": parsed.get("message"),
                "preferred_quantity": parsed.get("preferred_quantity"),
                "created_at": qr['created_at'].isoformat() if qr['created_at'] else None,
            })
        except (json.JSONDecodeError, TypeError, AttributeError) as e:
            logger.warning(f"Failed to parse quote request content for deal {deal_id}: {e}")
            continue

    return {
        "deal_id": deal_id,
        "total_views": deal_row['view_count'] if deal_row else 0,
        "unique_visitors": visitor_count['unique_visitors'],
        "target_buyer_name": target_buyer_name,
        "target_buyer_company": target_buyer_company,
        "views": [dict(v) for v in views],
        "quote_requests": quote_requests,
    }


async def update_room_status(conn, deal_id: int, new_status: str) -> None:
    """Update room_status on a deal (event-driven)."""
    if new_status not in VALID_ROOM_STATUSES:
        raise ValueError(f"Invalid room_status: {new_status}")

    await conn.execute(
        "UPDATE deals SET room_status = $1, updated_at = NOW() WHERE deal_id = $2",
        new_status, deal_id
    )


async def revoke_deal_room(conn, deal_id: int) -> None:
    """Revoke a deal room (set revoked_at on the token, clear share_token on deal)."""
    deal = await conn.fetchrow(
        "SELECT share_token FROM deals WHERE deal_id = $1", deal_id
    )
    if not deal or not deal['share_token']:
        raise ValueError(f"Deal {deal_id} has no deal room")

    share_token = deal['share_token']
    pm = get_pool_manager()
    analytics_pool = await pm.get_analytics_pool()

    # Delete from shared DB first — kills the public URL immediately.
    # Then update tenant DB. If tenant update fails, the deal still has
    # share_token set but the public URL is already dead (token gone from
    # shared DB). A retry will find share_token and can re-attempt the
    # tenant update.
    await analytics_pool.execute(
        "DELETE FROM deal_room_tokens WHERE share_token = $1",
        share_token
    )

    try:
        await conn.execute(
            "UPDATE deals SET share_token = NULL, room_status = 'closed-lost', updated_at = NOW() "
            "WHERE deal_id = $1",
            deal_id
        )
    except Exception as e:
        logger.error(f"Revoke: shared token deleted but tenant update failed for deal {deal_id}: {e}")
        raise

    logger.info(f"Deal room revoked for deal {deal_id}")
