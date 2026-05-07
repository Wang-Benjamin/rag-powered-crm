"""
CRM Repository for Lead Generation Service (asyncpg).

Handles database operations for CRM integration, including:
- Creating customers in the clients table
- Checking for duplicate customers

All methods are async and take an asyncpg connection as first parameter.
Does NOT inherit from BaseRepository — standalone async repository.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CRMRepository:
    """Repository for CRM-related database operations."""

    def __init__(self):
        """Initialize CRM repository."""
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")

    async def create_customer(self, conn, customer_data: dict, customer_details: dict,
                              user_email: Optional[str] = None) -> int:
        """
        Create customer in the clients table.

        This method inserts the combined customer/profile fields into clients.

        Args:
            conn: asyncpg connection
            customer_data: Data for clients table
            customer_details: Data for clients table
            user_email: User email for employee lookup

        Returns:
            client_id: Auto-generated client ID from database sequence

        Raises:
            Exception: If database operation fails
        """
        try:
            self.logger.info(f"[DB_ROUTING] Creating customer in CRM for user: {user_email}")

            async with conn.transaction():
                # Insert into clients - DB auto-generates client_id
                trade_intel_value = customer_details.get('trade_intel', {})

                clients_query = """
                    INSERT INTO clients (
                        name, location, source, created_at, updated_at, notes,
                        health_score, status, stage, trade_intel
                    ) VALUES (
                        $1, $2, $3, NOW(), NOW(), $4,
                        $5, $6, $7, $8::jsonb
                    )
                    RETURNING client_id
                """

                result = await conn.fetchrow(
                    clients_query,
                    customer_data.get('name'),
                    customer_data.get('location'),
                    customer_data.get('source', 'lead_generation'),
                    customer_data.get('notes'),
                    customer_details.get('health_score', 0.0),
                    customer_details.get('current_stage', 'new'),
                    customer_details.get('current_stage', 'new'),
                    trade_intel_value,
                )
                client_id = result['client_id']

                self.logger.info(f"Created clients record: client_id={client_id}")

                # Assign customer to employees (CRITICAL for visibility in CRM)
                try:
                    from database.queries import get_employee_id_by_email
                    employee_id = await get_employee_id_by_email(conn, user_email)

                    if employee_id:
                        assign_query = """
                            INSERT INTO employee_client_links (
                                employee_id, client_id, assigned_at, notes, matched_by, status, client_type
                            ) VALUES (
                                $1, $2, NOW(), $3, $4, $5, $6
                            )
                            ON CONFLICT (employee_id, client_id) DO NOTHING
                        """
                        await conn.execute(
                            assign_query,
                            employee_id,
                            client_id,
                            'Auto-assigned from lead generation',
                            'auto_assigned_from_leadgen',
                            'active',
                            'customer'
                        )
                        self.logger.info(f"Assigned customer {client_id} to employee {employee_id}")
                    else:
                        self.logger.warning(f"Could not find employee_id for {user_email} - customer may not be visible in CRM")
                except Exception as e:
                    self.logger.warning(f"Failed to assign customer to employee (non-critical): {e}")

            return client_id

        except Exception as e:
            self.logger.error(f"Error creating customer: {e}", exc_info=True)
            raise

    async def check_duplicate_customer(self, conn, company: str, location: str) -> Optional[dict]:
        """
        Check if customer already exists by company + location.

        Uses case-insensitive exact match on company name and location.

        Args:
            conn: asyncpg connection
            company: Company name from leads table
            location: Location from leads table

        Returns:
            Dictionary with customer info if exists, None if no duplicate found
        """
        try:
            query = """
                SELECT client_id, name
                FROM clients
                WHERE LOWER(TRIM(name)) = LOWER(TRIM($1))
                  AND LOWER(TRIM(location)) = LOWER(TRIM($2))
                LIMIT 1
            """

            result = await conn.fetchrow(query, company, location)

            if result:
                customer_dict = dict(result)
                self.logger.info(f"Duplicate customer found: client_id={customer_dict['client_id']}")
                return customer_dict

            return None

        except Exception as e:
            self.logger.error(f"Error checking for duplicate customer: {e}")
            raise

    async def get_customer_by_id(self, conn, client_id: int) -> Optional[dict]:
        """
        Get customer info by client_id formatted for frontend (CRM Customer model).

        Args:
            conn: asyncpg connection
            client_id: CRM customer ID

        Returns:
            Dictionary with customer data formatted to match CRM frontend Customer model,
            or None if not found
        """
        try:
            # Query clients (matching CRM backend pattern)
            query = """
                SELECT
                    ci.client_id,
                    ci.name,
                    ci.phone,
                    ci.location,
                    ci.website,
                    ci.source,
                    ci.notes,
                    ci.created_at,
                    ci.updated_at,
                    ci.status,
                    COALESCE((SELECT SUM(value_usd) FROM deals WHERE client_id = ci.client_id), 0) as total_deal_value,
                    ci.health_score,
                    (SELECT full_name FROM personnel WHERE client_id = ci.client_id AND is_primary = true LIMIT 1) AS primary_contact,
                    (SELECT email FROM personnel WHERE client_id = ci.client_id AND is_primary = true LIMIT 1) AS primary_email,
                    (SELECT MAX(ts) FROM (
                        SELECT MAX(id2.created_at) AS ts FROM interaction_details id2 WHERE id2.customer_id = ci.client_id
                        UNION ALL
                        SELECT MAX(ce.created_at) AS ts FROM crm_emails ce WHERE ce.customer_id = ci.client_id
                    ) sub) AS last_activity
                FROM clients ci
                    WHERE ci.client_id = $1
            """

            result = await conn.fetchrow(query, client_id)

            if not result:
                return None

            result = dict(result)

            # Transform to match CRM frontend Customer model (camelCase)
            customer = {
                "id": result['client_id'],
                "company": result['name'] or "Unknown Company",
                "primaryContact": result.get('primary_contact') or "Unknown Contact",
                "email": result.get('primary_email') or "",
                "phone": result['phone'] or "",
                "location": result['location'] or "",
                "website": result.get('website') or "",
                "status": result['status'] or "active",
                "clientType": "customer",
                "totalDealValue": float(result.get('total_deal_value') or 0),
                "healthScore": float(result.get('health_score') or 75),
                "lastActivity": result['last_activity'].isoformat() if result.get('last_activity') else "",
                "currentStage": result.get('status') or "active",
                "renewalProbability": min(95, max(20, int((result.get('health_score') or 75) * 1.2))),
                "expansionProbability": 50,  # Default medium
                "lastContact": result['last_activity'].strftime("%Y-%m-%d") if result.get('last_activity') else ""
            }

            return customer

        except Exception as e:
            self.logger.error(f"Error getting customer by ID: {e}")
            raise

    async def sync_lead_employees_to_crm(self, conn, lead_id: str, client_id: int) -> int:
        """
        Sync all employee assignments from employee_lead_links to employee_client_links.

        This ensures that when a lead is converted to a CRM customer, all employees
        who were assigned to the lead are also assigned to the new customer.

        Args:
            conn: asyncpg connection
            lead_id: UUID of the lead
            client_id: CRM customer ID (from clients)

        Returns:
            Count of employee assignments synced
        """
        try:
            self.logger.info(f"[SYNC] Syncing employee assignments from lead {lead_id} to customer {client_id}")

            # Get all active employee assignments from employee_lead_links
            lead_employees = await conn.fetch("""
                SELECT employee_id, assigned_at, notes, matched_by
                FROM employee_lead_links
                WHERE lead_id = $1 AND status = 'active'
            """, lead_id)

            if not lead_employees:
                self.logger.info(f"[SYNC] No employee assignments found for lead {lead_id}")
                return 0

            synced_count = 0
            async with conn.transaction():
                for emp in lead_employees:
                    emp_dict = dict(emp)
                    employee_id = emp_dict['employee_id']
                    assigned_at = emp_dict['assigned_at']
                    notes = emp_dict.get('notes') or "Synced from lead assignment"
                    matched_by = emp_dict.get('matched_by') or "synced_from_lead"

                    # Insert into employee_client_links with ON CONFLICT DO NOTHING
                    result = await conn.execute("""
                        INSERT INTO employee_client_links (
                            employee_id, client_id, assigned_at, notes, matched_by, status, client_type
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (employee_id, client_id) DO NOTHING
                    """,
                        employee_id,
                        client_id,
                        assigned_at,
                        f"Synced from lead: {notes}",
                        f"synced_from_lead_{matched_by}",
                        "active",
                        "customer"
                    )

                    # Parse "INSERT 0 N" to check rows affected
                    if result:
                        parts = result.split()
                        if len(parts) >= 3 and int(parts[-1]) > 0:
                            synced_count += 1
                            self.logger.info(f"[SYNC] Synced employee {employee_id} to customer {client_id}")

            self.logger.info(f"[SYNC] Synced {synced_count} employee assignments to customer {client_id}")
            return synced_count

        except Exception as e:
            self.logger.error(f"Error syncing lead employees to CRM: {e}", exc_info=True)
            return 0
