"""
Lead Info Router for Lead Generation.
Read-only endpoints used by the buyer dashboard (BuyerIntelligencePanel).
"""

import logging
from fastapi import APIRouter, HTTPException, Depends

from service_core.db import get_tenant_connection

from utils.bol_intelligence import build_bol_intelligence

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{lead_id}/bol-intelligence")
async def get_lead_bol_intelligence(
    lead_id: str,
    tenant=Depends(get_tenant_connection)
):
    """Get structured BoL buyer intelligence for a lead's email compose screen."""
    conn, user_claims = tenant
    try:
        row = await conn.fetchrow(
            "SELECT import_context, supplier_context FROM leads WHERE lead_id = $1",
            lead_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Lead not found")

        intelligence = build_bol_intelligence(
            row.get("import_context"),
            row.get("supplier_context"),
        )

        return {"intelligence": intelligence, "leadId": lead_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting BoL intelligence for lead {lead_id}: {e}")
        return {"intelligence": None, "leadId": lead_id}
