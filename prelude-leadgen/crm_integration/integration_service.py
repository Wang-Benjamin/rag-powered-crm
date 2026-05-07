"""
Lead to CRM Integration Service

Orchestrates the complete workflow for syncing leads to the CRM system,
including duplicate detection, data transformation, customer creation,
and email transfer.
"""

import json
import logging
from typing import Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime

from data.repositories import LeadRepository, PersonnelRepository, CRMRepository
from service_core.db import get_current_conn

logger = logging.getLogger(__name__)


class LeadToCRMIntegrationService:
    """Service to handle lead-to-CRM synchronization.

    Uses get_current_conn() from contextvars to access the request-scoped
    DB connection set by get_tenant_connection dependency in the router.
    """

    def __init__(self, user_email: Optional[str] = None):
        self.lead_repo = LeadRepository()
        self.personnel_repo = PersonnelRepository()
        self.crm_repo = CRMRepository()
        self.user_email = user_email
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")

    async def add_lead_to_crm(
        self,
        lead_id: UUID,
        personnel_id: Optional[UUID] = None,
        skip_status_update: bool = False
    ) -> Dict[str, Any]:
        """
        Main method to sync a lead to CRM.

        This method orchestrates the complete workflow:
        1. Fetch lead data from leads table
        2. Check for duplicates in clients (by company + location)
        3. If duplicate exists, return existing client_id
        4. Fetch personnel data (first personnel or specified personnel_id)
        5. Transform lead data to CRM format (clients)
        6. Create customer in CRM
        7. Link personnel and employee assignments
        8. Mark the lead synced and return the CRM customer

        Args:
            lead_id: UUID of the lead to sync
            personnel_id: Optional UUID of specific personnel to use as primary contact

        Returns:
            {
                "success": bool,
                "crm_customer_id": int,
                "already_exists": bool,
                "message": str,
                "emails_transferred": int
            }
        """
        try:
            conn = get_current_conn()

            # Step 1: Fetch lead
            self.logger.info(f"Starting CRM sync for lead_id={lead_id}")
            lead = await self.lead_repo.get_lead_by_id(conn, str(lead_id))

            if not lead:
                self.logger.warning(f"Lead not found: {lead_id}")
                return {
                    "success": False,
                    "message": f"Lead with ID {lead_id} not found"
                }

            # Validate required fields
            if not lead.get('company'):
                self.logger.error(f"Lead {lead_id} is missing required field 'company'")
                return {
                    "success": False,
                    "message": "Lead is missing required field: company"
                }

            # Location is optional. BoL leads frequently arrive with no parsed
            # address; fall back to 'Unknown' so they can still sync.
            if not lead.get('location'):
                self.logger.info(f"Lead {lead_id} has no location; using 'Unknown'")
                lead['location'] = 'Unknown'

            # Step 2: Check for duplicates
            self.logger.info(f"Checking for duplicate customer: {lead['company']} @ {lead['location']}")
            existing_customer = await self.crm_repo.check_duplicate_customer(
                conn,
                company=lead.get('company'),
                location=lead.get('location')
            )

            if existing_customer:
                self.logger.info(
                    f"Duplicate found: {lead['company']} already exists as client_id={existing_customer['client_id']}"
                )

                # Update lead status to synced_to_crm even for duplicates (skip when auto-adding)
                if not skip_status_update:
                    self.logger.info(f"Updating lead status to 'synced_to_crm' for duplicate (lead_id={lead_id})")
                    from config.constants import LeadStatus

                    update_success = await self.lead_repo.update_lead(
                        conn,
                        lead_id=str(lead_id),
                        updates={"status": LeadStatus.SYNCED_TO_CRM.value},
                        user_id=self.user_email or "system"
                    )

                    if update_success:
                        self.logger.info(f"Lead status updated to 'synced_to_crm' for duplicate")
                    else:
                        self.logger.warning(f"Failed to update lead status for duplicate")

                return {
                    "success": True,
                    "crm_customer_id": existing_customer['client_id'],
                    "already_exists": True,
                    "message": f"Customer already exists in CRM (ID: {existing_customer['client_id']})",
                    "emails_transferred": 0
                }

            # Step 3: Fetch personnel (primary contact)
            primary_contact_name = None
            if personnel_id:
                # Use specified personnel
                self.logger.info(f"Using specified personnel_id={personnel_id}")
                personnel = await self.personnel_repo.get_by_id(conn, str(personnel_id))
                if personnel:
                    primary_contact_name = personnel.get('full_name')
                    self.logger.info(f"Primary contact: {primary_contact_name}")
                else:
                    self.logger.warning(f"Specified personnel_id={personnel_id} not found")
            else:
                # Get first personnel for this lead
                self.logger.info(f"Fetching personnel for lead_id={lead_id}")
                personnel_list = await self.personnel_repo.get_personnel_by_lead(conn, str(lead_id))
                if personnel_list and len(personnel_list) > 0:
                    primary_contact_name = personnel_list[0].get('full_name')
                    self.logger.info(f"Primary contact (first personnel): {primary_contact_name}")
                else:
                    self.logger.info("No personnel found for this lead - primary_contact will be NULL")

            # Step 4: Transform lead → CRM data
            # Contact info is no longer copied to clients — it stays on personnel records
            self.logger.info("Transforming lead data to CRM format")
            customer_data, customer_details = self._transform_lead_to_crm(
                lead,
            )

            # Step 5: Create customer in CRM
            self.logger.info(f"Creating CRM customer: {lead['company']}")
            client_id = await self.crm_repo.create_customer(
                conn,
                customer_data=customer_data,
                customer_details=customer_details,
                user_email=self.user_email
            )

            self.logger.info(f"✅ Created CRM customer: {lead['company']} → client_id={client_id}")

            # Step 5a: Link personnel to CRM customer — SET client_id on all personnel for this lead
            try:
                result_str = await conn.execute(
                    "UPDATE personnel SET client_id = $1 WHERE lead_id = $2",
                    client_id, str(lead_id)
                )
                linked_count = int(result_str.split()[-1]) if result_str else 0
                self.logger.info(f"✅ Linked {linked_count} personnel records to client_id={client_id}")
            except Exception as e:
                self.logger.warning(f"⚠️ Failed to link personnel to CRM customer (non-critical): {e}")

            # Step 5b: Sync all employee assignments from lead to CRM customer
            self.logger.info(f"Syncing employee assignments for lead_id={lead_id} to client_id={client_id}")
            employees_synced = await self.crm_repo.sync_lead_employees_to_crm(
                conn,
                lead_id=str(lead_id),
                client_id=client_id
            )
            self.logger.info(f"✅ Synced {employees_synced} employee assignments to CRM")

            # Step 5c: Deal creation intentionally disabled.
            #
            # Prelude's deal boundary is manual/storefront-only: lead → CRM
            # conversion should create/update the customer record and preserve
            # attribution, but must not create pipeline opportunities.
            deals_created = 0
            self.logger.info(
                "Deal auto-creation skipped for lead conversion "
                "(deals are manual/storefront-only)"
            )

            # Step 6: Email sync work is already handled at send time.

            # Step 7: Update lead status to "synced_to_crm" (skip when called from auto-add)
            if not skip_status_update:
                self.logger.info(f"Updating lead status to 'synced_to_crm' for lead_id={lead_id}")
                from config.constants import LeadStatus

                update_success = await self.lead_repo.update_lead(
                    conn,
                    lead_id=str(lead_id),
                    updates={"status": LeadStatus.SYNCED_TO_CRM.value},
                    user_id=self.user_email or "system"
                )

                if update_success:
                    self.logger.info(f"Lead status updated to 'synced_to_crm'")
                else:
                    self.logger.warning(f"Failed to update lead status (non-critical)")

            # Step 8: Fetch complete customer object to return (same as CRM does)
            customer_obj = None
            try:
                customer_obj = await self.crm_repo.get_customer_by_id(conn, client_id)
                self.logger.info(f"✅ Retrieved full customer object for client_id={client_id}")
            except Exception as e:
                self.logger.warning(f"⚠️ Failed to fetch customer object (non-critical): {e}")

            # Step 9: Return success with full customer object
            return {
                "success": True,
                "crm_customer_id": client_id,
                "already_exists": False,
                "message": f"Successfully added {lead['company']} to CRM",
                "emails_transferred": 0,
                "deals_created": deals_created,
                "customer": customer_obj  # Add full customer object for frontend optimistic update
            }

        except Exception as e:
            self.logger.error(f"❌ Error adding lead to CRM: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to add lead to CRM: {str(e)}"
            }

    # Deal auto-creation helpers removed: deals are created only manually
    # in CRM or by storefront quote requests. Lead conversion returns
    # deals_created=0 for compatibility.

    def _transform_lead_to_crm(
        self,
        lead: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Transform lead data to CRM format.

        Maps lead table fields to clients table fields.
        Contact info (email, phone, primary_contact) is NOT copied here — it lives
        on personnel records which are linked to the CRM customer via client_id.

        Args:
            lead: Lead dictionary from leads table

        Returns:
            Tuple of (customer_data, customer_details) dictionaries
        """
        try:
            # Build customer_data for clients table. Contact fields stay on
            # personnel; the combined clients row keeps location at varchar(255).
            location = lead.get('location') or 'Unknown'
            if len(location) > 255:
                location = location[:255]

            customer_data = {
                "name": lead.get('company'),
                "location": location,
                "source": lead.get('source', 'lead_generation'),
            }

            # Build customer_details for clients table
            # Convert score (int) to health_score (float)
            score = lead.get('score')
            health_score = float(score) if score is not None else 0.0

            # Extract BoL trade intelligence for the sidebar
            import_ctx = lead.get('import_context') or {}
            if isinstance(import_ctx, str):
                import_ctx = json.loads(import_ctx)
            bol_ctx = lead.get('bol_detail_context') or {}
            if isinstance(bol_ctx, str):
                bol_ctx = json.loads(bol_ctx)
            scoring = bol_ctx.get('scoringSignals') or {}

            trade_intel = {
                "topProducts": (import_ctx.get('topProducts') or [])[:5],
                "hsCodes": (import_ctx.get('hsCodes') or [])[:5],
                "totalShipments": import_ctx.get('totalShipments'),
                "totalSuppliers": import_ctx.get('totalSuppliers'),
                "reorderWindow": scoring.get('reorderWindow'),
                "chinaConcentration": bol_ctx.get('chinaConcentration'),
                "growth12mPct": bol_ctx.get('growth12mPct'),
                "enrichedAt": bol_ctx.get('enrichedAt'),
            }

            customer_details = {
                "health_score": health_score,
                "current_stage": lead.get('status', 'new'),
                "trade_intel": trade_intel,
            }

            self.logger.debug(f"Transformed customer_data: {customer_data}")
            self.logger.debug(f"Transformed customer_details: {customer_details}")

            return customer_data, customer_details

        except Exception as e:
            self.logger.error(f"Error transforming lead data: {e}", exc_info=True)
            raise


# Factory function for creating service instances
def get_crm_integration_service(user_email: Optional[str] = None) -> LeadToCRMIntegrationService:
    """
    Factory function to create CRM integration service instance.

    Args:
        user_email: Optional user email for database routing

    Returns:
        LeadToCRMIntegrationService instance
    """
    return LeadToCRMIntegrationService(user_email=user_email)
