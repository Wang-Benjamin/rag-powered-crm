"""
Deal Room Router
================
Internal (authenticated) endpoints for deal room management.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import logging

from service_core.db import get_tenant_connection
from services.deal_room_service import (
    create_deal_room,
    update_deal_room,
    get_deal_room,
    list_deal_rooms,
    get_deal_room_analytics,
    update_room_status,
    revoke_deal_room,
)
from email_core.translation import adapt_to_western_b2b

logger = logging.getLogger(__name__)
router = APIRouter()


# Pydantic models

class CreateDealRoomRequest(BaseModel):
    quote_data: dict = {}
    sample_timeline: dict = {}
    room_settings: dict = {}
    fob_price: Optional[float] = None
    fob_currency: str = 'USD'


class UpdateDealRoomRequest(BaseModel):
    quote_data: Optional[dict] = None
    sample_timeline: Optional[dict] = None
    room_settings: Optional[dict] = None


class UpdateRoomStatusRequest(BaseModel):
    room_status: str


class TranslateMessageRequest(BaseModel):
    message_zh: str


# Endpoints

@router.post("/deals/{deal_id}/room")
async def create_room(
    deal_id: int,
    request: CreateDealRoomRequest,
    tenant=Depends(get_tenant_connection)
):
    """Create a deal room for an existing deal. Generates share_token and inserts into shared DB."""
    conn, user = tenant
    user_email = user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        result = await create_deal_room(
            conn,
            deal_id=deal_id,
            user_email=user_email,
            quote_data=request.quote_data,
            sample_timeline=request.sample_timeline,
            room_settings=request.room_settings,
            fob_price=request.fob_price,
            fob_currency=request.fob_currency,
        )
        return {"success": True, "deal_room": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating deal room: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create deal room: {str(e)}")


@router.put("/deals/{deal_id}/room")
async def update_room(
    deal_id: int,
    request: UpdateDealRoomRequest,
    tenant=Depends(get_tenant_connection)
):
    """Update deal room quote data, sample timeline, or settings."""
    conn, user = tenant

    try:
        result = await update_deal_room(
            conn,
            deal_id=deal_id,
            quote_data=request.quote_data,
            sample_timeline=request.sample_timeline,
            room_settings=request.room_settings,
        )
        return {"success": True, "deal_room": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating deal room: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update deal room: {str(e)}")


@router.get("/deals/{deal_id}/room")
async def get_room(
    deal_id: int,
    tenant=Depends(get_tenant_connection)
):
    """Get deal room data for a specific deal."""
    conn, user = tenant

    try:
        result = await get_deal_room(conn, deal_id)
        if not result:
            raise HTTPException(status_code=404, detail="Deal room not found")
        return {"success": True, "deal_room": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting deal room: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get deal room: {str(e)}")


@router.get("/deals/{deal_id}/room/analytics")
async def get_room_analytics(
    deal_id: int,
    tenant=Depends(get_tenant_connection)
):
    """Get view analytics for a deal room."""
    conn, user = tenant

    try:
        result = await get_deal_room_analytics(conn, deal_id)
        return {"success": True, "analytics": result}
    except Exception as e:
        logger.error(f"Error getting deal room analytics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get analytics: {str(e)}")


@router.get("/deal-rooms")
async def list_rooms(
    tenant=Depends(get_tenant_connection)
):
    """List all deal rooms for the Deal Rooms page."""
    conn, user = tenant

    try:
        rooms = await list_deal_rooms(conn)
        return {"success": True, "deal_rooms": rooms, "total": len(rooms)}
    except Exception as e:
        logger.error(f"Error listing deal rooms: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list deal rooms: {str(e)}")


@router.put("/deals/{deal_id}/room/status")
async def update_status(
    deal_id: int,
    request: UpdateRoomStatusRequest,
    tenant=Depends(get_tenant_connection)
):
    """Update deal room status (e.g., mark as sent, closed-won, closed-lost)."""
    conn, user = tenant

    try:
        await update_room_status(conn, deal_id, request.room_status)
        return {"success": True, "room_status": request.room_status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating room status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update status: {str(e)}")


@router.delete("/deals/{deal_id}/room")
async def revoke_room(
    deal_id: int,
    tenant=Depends(get_tenant_connection)
):
    """Revoke a deal room — disables the public URL."""
    conn, user = tenant
    user_email = user.get('email')
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        await revoke_deal_room(conn, deal_id)
        return {"success": True, "message": "Deal room revoked"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error revoking deal room: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to revoke deal room: {str(e)}")


@router.post("/deals/{deal_id}/room/translate-message")
async def translate_message(
    deal_id: int,
    request: TranslateMessageRequest,
    tenant=Depends(get_tenant_connection)
):
    """Culturally adapt a Chinese message to polished Western B2B English for the deal room."""
    conn, user = tenant

    try:
        message_en = await adapt_to_western_b2b(request.message_zh)
        if message_en is None:
            raise HTTPException(status_code=500, detail="Translation failed")

        return {"success": True, "message_zh": request.message_zh, "message_en": message_en}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error translating deal room message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to translate message: {str(e)}")
