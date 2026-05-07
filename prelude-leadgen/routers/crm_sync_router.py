"""
CRM sync router for lead-to-customer resolution endpoints.
"""

from fastapi import APIRouter, Body, Depends, HTTPException
from service_core.db import get_tenant_connection
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/{lead_id}/add-to-crm")
async def add_lead_to_crm(
    lead_id: str,
    request_body: dict = Body(default={}),
    tenant=Depends(get_tenant_connection)
):
    """Add a lead to the CRM system."""
    try:
        from uuid import UUID
        from crm_integration.integration_service import LeadToCRMIntegrationService

        conn, user = tenant
        user_email = user.get("email", "unknown")
        personnel_id = request_body.get("personnel_id")

        # Validate lead_id format
        try:
            lead_uuid = UUID(lead_id)
        except (ValueError, AttributeError) as e:
            logger.warning(f"Invalid lead_id format: {lead_id} - {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid lead_id format: {lead_id}. Must be a valid UUID."
            )

        # Validate personnel_id format if provided
        personnel_uuid = None
        if personnel_id:
            try:
                personnel_uuid = UUID(personnel_id)
            except (ValueError, AttributeError) as e:
                logger.warning(f"Invalid personnel_id format: {personnel_id} - {e}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid personnel_id format: {personnel_id}. Must be a valid UUID."
                )

        # Initialize integration service
        logger.info(f"Initializing CRM integration service for user: {user_email}")
        integration_service = LeadToCRMIntegrationService(user_email=user_email)

        # Execute sync
        logger.info(f"Executing CRM sync for lead_id={lead_id}, personnel_id={personnel_id}")
        result = await integration_service.add_lead_to_crm(
            lead_id=lead_uuid,
            personnel_id=personnel_uuid
        )

        # Handle result from service
        if not result.get("success"):
            error_message = result.get("message", "Unknown error")

            if "not found" in error_message.lower():
                logger.warning(f"Lead not found: {lead_id}")
                raise HTTPException(status_code=404, detail=error_message)
            else:
                logger.error(f"CRM sync failed: {error_message}")
                raise HTTPException(status_code=500, detail=error_message)

        logger.info(f"CRM sync successful: lead_id={lead_id} -> client_id={result.get('crm_customer_id')}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in add_lead_to_crm endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/bulk-add-to-crm")
async def bulk_add_to_crm(
    request_body: dict = Body(...),
    tenant=Depends(get_tenant_connection)
):
    """Batch add multiple leads to the CRM system.

    Accepts {"lead_ids": ["uuid1", "uuid2", ...]} and resolves each lead
    to a CRM customer. Individual failures don't block the batch.
    """
    try:
        from uuid import UUID
        from crm_integration.integration_service import LeadToCRMIntegrationService

        conn, user = tenant
        user_email = user.get("email", "unknown")
        lead_ids = request_body.get("lead_ids", [])

        if not isinstance(lead_ids, list):
            raise HTTPException(status_code=400, detail="lead_ids must be a list")

        if not lead_ids:
            raise HTTPException(status_code=400, detail="lead_ids is required and must be non-empty")

        if len(lead_ids) > 50:
            raise HTTPException(status_code=400, detail="Maximum 50 leads per batch")

        integration_service = LeadToCRMIntegrationService(user_email=user_email)
        results = []

        # Sequential: integration_service uses get_current_conn() contextvar
        # which is a single request-scoped asyncpg connection (not safe for concurrent use)
        for lead_id_str in lead_ids:
            try:
                lead_uuid = UUID(str(lead_id_str))
                result = await integration_service.add_lead_to_crm(
                    lead_id=lead_uuid,
                    personnel_id=None,
                )
                results.append({
                    "lead_id": lead_id_str,
                    "customer_id": result.get("crm_customer_id"),
                    "status": "created" if result.get("success") and not result.get("already_exists") else
                              "existing" if result.get("already_exists") else "failed",
                    "message": result.get("message", ""),
                })
            except Exception as e:
                logger.error(f"bulk-add-to-crm failed for lead {lead_id_str}: {e}")
                results.append({
                    "lead_id": lead_id_str,
                    "customer_id": None,
                    "status": "failed",
                    "message": str(e),
                })

        successful = sum(1 for r in results if r["status"] in ("created", "existing"))
        failed = sum(1 for r in results if r["status"] == "failed")

        return {
            "total": len(lead_ids),
            "successful": successful,
            "failed": failed,
            "results": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in bulk_add_to_crm: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
