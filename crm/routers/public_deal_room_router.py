"""
Public Deal Room Router
=======================
Unauthenticated endpoints for buyer-facing deal room access.
Follows tracking_router.py pattern — uses get_pool_manager() directly, no auth dependency.
Token resolution via deal_room_tokens table in shared prelude_user_analytics DB.
"""

import json
import logging
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from service_core.db import get_pool_manager


def _snake_to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    components = name.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def _convert_keys_to_camel(obj):
    """Recursively convert dict keys from snake_case to camelCase."""
    if isinstance(obj, dict):
        return {_snake_to_camel(k): _convert_keys_to_camel(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_keys_to_camel(item) for item in obj]
    return obj

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/public/deal")


# Simple in-memory rate limiter for public endpoints
_rate_limit_store: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(client_ip: str, max_requests: int, window_seconds: int):
    """Raise 429 if client exceeds max_requests within window_seconds."""
    now = time.time()
    timestamps = _rate_limit_store[client_ip]
    # Prune expired entries
    _rate_limit_store[client_ip] = [t for t in timestamps if now - t < window_seconds]
    if not _rate_limit_store[client_ip]:
        del _rate_limit_store[client_ip]
    if len(_rate_limit_store.get(client_ip, [])) >= max_requests:
        raise HTTPException(status_code=429, detail="Too many requests")
    _rate_limit_store[client_ip].append(now)


class BuyerMessageRequest(BaseModel):
    buyer_email: str
    buyer_name: Optional[str] = None
    buyer_company: Optional[str] = None
    message: Optional[str] = None
    preferred_quantity: Optional[int] = None


class ViewTrackingRequest(BaseModel):
    visitor_id: str
    session_token: str
    duration_seconds: Optional[int] = None
    sections_viewed: Optional[list] = None
    viewer_email: Optional[str] = None


async def _resolve_token(share_token: str):
    """Resolve share_token to tenant DB info via shared analytics DB.

    Returns (db_name, deal_id, owner_email) or raises 404.
    """
    pm = get_pool_manager()
    analytics_pool = await pm.get_analytics_pool()

    row = await analytics_pool.fetchrow(
        "SELECT db_name, deal_id, owner_email FROM deal_room_tokens "
        "WHERE share_token = $1 "
        "AND revoked_at IS NULL "
        "AND (expires_at IS NULL OR expires_at > NOW())",
        share_token
    )
    if not row:
        raise HTTPException(status_code=404, detail="Deal room not found or expired")

    return row['db_name'], row['deal_id'], row['owner_email']


@router.get("/{share_token}")
async def get_public_deal_room(share_token: str, request: Request):
    """Get deal room data for buyer view. No auth required."""
    _check_rate_limit(request.client.host if request.client else "unknown", max_requests=30, window_seconds=60)
    try:
        db_name, deal_id, owner_email = await _resolve_token(share_token)
        pm = get_pool_manager()

        async with pm.acquire(db_name) as conn:
            # Get deal + buyer info (client_name only — no email to avoid PII leakage)
            deal_data = await conn.fetchrow(
                "SELECT d.deal_id, d.deal_name, d.product_name, d.quote_data, d.sample_timeline, "
                "d.room_settings, d.room_status, d.value_usd, d.view_count, "
                "d.fob_price, d.fob_currency, d.landed_price, d.hs_code, d.quantity, d.moq, "
                "c.name AS client_name "
                "FROM deals d "
                "JOIN clients c ON d.client_id = c.client_id "
                "WHERE d.deal_id = $1 AND d.room_status NOT IN ('closed-won', 'closed-lost')",
                deal_id
            )
            if not deal_data:
                raise HTTPException(status_code=404, detail="Deal room not found or closed")

            # Get factory profile
            factory_data = await conn.fetchrow(
                "SELECT company_profile, factory_details, hs_codes "
                "FROM tenant_subscription LIMIT 1",
            )

            # Get active certifications
            certs = await conn.fetch(
                "SELECT cert_type, cert_number, issuing_body, issue_date, expiry_date, "
                "status, document_url FROM factory_certifications "
                "WHERE email = $1 AND status = 'active'",
                owner_email
            )

        # Parse JSONB fields
        def parse_jsonb(val):
            if val is None:
                return {}
            if isinstance(val, str):
                return json.loads(val)
            return dict(val) if hasattr(val, 'keys') else val

        company_profile = _convert_keys_to_camel(parse_jsonb(factory_data['company_profile'])) if factory_data else {}
        factory_details = _convert_keys_to_camel(parse_jsonb(factory_data['factory_details'])) if factory_data else {}

        # Build quoteData from deal columns (single source of truth)
        fob = float(deal_data['fob_price']) if deal_data['fob_price'] else None
        landed = float(deal_data['landed_price']) if deal_data['landed_price'] else fob
        currency = deal_data['fob_currency'] or 'USD'
        qty_val = deal_data['quantity'] or 0
        moq_val = deal_data['moq'] or 0
        hs_code = deal_data['hs_code'] or ''

        product_name = deal_data['product_name'] or deal_data['deal_name'] or ''

        quote_data = {}
        if fob is not None:
            quote_data = {
                "productName": product_name,
                "hsCode": hs_code,
                "quantity": qty_val,
                "moq": moq_val,
                "options": [{
                    "label": product_name or 'Quote',
                    "origin": "",
                    "currency": currency,
                    "fobPrice": fob,
                    "landedPrice": landed,
                }],
            }

        return {
            "deal": {
                "dealId": deal_data['deal_id'],
                "dealName": deal_data['deal_name'],
                "quoteData": quote_data,
                "sampleTimeline": _convert_keys_to_camel(parse_jsonb(deal_data['sample_timeline'])),
                "roomSettings": _convert_keys_to_camel(parse_jsonb(deal_data['room_settings'])),
                "roomStatus": deal_data['room_status'],
                "valueUsd": float(deal_data['value_usd']) if deal_data['value_usd'] else None,
                "viewCount": deal_data['view_count'],
            },
            "buyer": {
                "clientName": deal_data['client_name'],
            },
            "factory": {
                "companyProfile": company_profile,
                "factoryDetails": factory_details,
            },
            "certifications": [
                {
                    "certType": c['cert_type'],
                    "certNumber": c['cert_number'],
                    "issuingBody": c['issuing_body'],
                    "issueDate": str(c['issue_date']) if c['issue_date'] else None,
                    "expiryDate": str(c['expiry_date']) if c['expiry_date'] else None,
                    "status": c['status'],
                    "documentUrl": c['document_url'],
                }
                for c in certs
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching public deal room: {e}")
        raise HTTPException(status_code=500, detail="Failed to load deal room")


@router.post("/{share_token}/track")
async def track_view(share_token: str, request: ViewTrackingRequest, raw_request: Request):
    """Record or update a buyer view session. Upserts by (deal_id, session_token)."""
    _check_rate_limit(raw_request.client.host if raw_request.client else "unknown", max_requests=30, window_seconds=60)
    try:
        db_name, deal_id, _ = await _resolve_token(share_token)
        pm = get_pool_manager()

        async with pm.acquire(db_name) as conn:
            # Reject tracking on closed rooms
            status = await conn.fetchval(
                "SELECT room_status FROM deals WHERE deal_id = $1", deal_id
            )
            if status in ('closed-won', 'closed-lost'):
                raise HTTPException(status_code=404, detail="Deal room is closed")

            async with conn.transaction():
                # Upsert view session
                result = await conn.fetchrow(
                    "INSERT INTO deal_room_views "
                    "(deal_id, visitor_id, session_token, viewer_email, duration_seconds, sections_viewed) "
                    "VALUES ($1, $2, $3, $4, $5, $6::jsonb) "
                    "ON CONFLICT (deal_id, session_token) DO UPDATE SET "
                    "duration_seconds = EXCLUDED.duration_seconds, "
                    "sections_viewed = EXCLUDED.sections_viewed "
                    "RETURNING view_id, (xmax = 0) AS is_insert",
                    deal_id,
                    request.visitor_id,
                    request.session_token,
                    request.viewer_email,
                    request.duration_seconds or 0,
                    request.sections_viewed or [],
                )

                # Only increment view_count on first insert (new session), not on heartbeat updates
                if result and result['is_insert']:
                    await conn.execute(
                        "UPDATE deals SET view_count = view_count + 1, "
                        "last_viewed_at = NOW(), updated_at = NOW(), "
                        "room_status = CASE WHEN room_status IN ('draft', 'sent') THEN 'viewed' ELSE room_status END "
                        "WHERE deal_id = $1",
                        deal_id
                    )

                    # Auto-qualify linked lead when deal room is viewed
                    client_id = await conn.fetchval(
                        "SELECT client_id FROM deals WHERE deal_id = $1", deal_id
                    )
                    if client_id:
                        updated = await conn.execute(
                            "UPDATE leads SET status = 'qualified', updated_at = NOW() "
                            "WHERE lead_id IN ("
                            "  SELECT DISTINCT lead_id FROM personnel "
                            "  WHERE client_id = $1 AND lead_id IS NOT NULL"
                            ") AND status != 'qualified'",
                            client_id,
                        )
                        try:
                            count = int(updated.split()[-1])
                        except (ValueError, IndexError, AttributeError):
                            count = 0
                        if count:
                            logger.info(f"Auto-qualified {count} lead(s) from deal room view (deal_id={deal_id}, client_id={client_id})")

                    logger.info(f"DEAL_ROOM_NOTIFICATION: New view on deal {deal_id} by visitor {request.visitor_id}")

        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error tracking view: {e}")
        return {"success": False}


@router.post("/{share_token}/message")
async def send_buyer_message(share_token: str, request: BuyerMessageRequest, raw_request: Request):
    """Buyer sends a message or quote request. Stored in interaction_details."""
    _check_rate_limit(raw_request.client.host if raw_request.client else "unknown", max_requests=5, window_seconds=60)
    try:
        db_name, deal_id, _ = await _resolve_token(share_token)
        pm = get_pool_manager()

        async with pm.acquire(db_name) as conn:
            # Get deal's employee_id, client_id, and room_status
            deal = await conn.fetchrow(
                "SELECT employee_id, client_id, room_status FROM deals WHERE deal_id = $1",
                deal_id
            )
            if not deal:
                raise HTTPException(status_code=404, detail="Deal not found")
            if deal['room_status'] in ('closed-won', 'closed-lost'):
                raise HTTPException(status_code=404, detail="Deal room is closed")

            content = json.dumps({
                "buyer_email": request.buyer_email,
                "buyer_name": request.buyer_name,
                "buyer_company": request.buyer_company,
                "message": request.message,
                "preferred_quantity": request.preferred_quantity,
            })

            # Insert message + advance status in a transaction
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO interaction_details "
                    "(customer_id, deal_id, employee_id, type, content, source, created_at) "
                    "VALUES ($1, $2, $3, 'quote_request', $4, 'deal_room', NOW())",
                    deal['client_id'],
                    deal_id,
                    deal['employee_id'],
                    content,
                )

                await conn.execute(
                    "UPDATE deals SET room_status = 'quote_requested', updated_at = NOW() "
                    "WHERE deal_id = $1 AND room_status NOT IN ('closed-won', 'closed-lost')",
                    deal_id
                )

            logger.info(f"DEAL_ROOM_NOTIFICATION: New message on deal {deal_id} from {request.buyer_email}")

            # Stage auto-progression (engaged → quoting)
            if deal.get('client_id'):
                try:
                    from services.stage_progression_service import apply_stage_progression
                    await apply_stage_progression(conn, deal['client_id'])
                except Exception as stage_err:
                    logger.debug(f"Stage progression skipped: {stage_err}")

        return {"success": True, "message": "Message sent"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending buyer message: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message")
