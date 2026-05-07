"""Contact repository for CRM - handles contact operations via personnel table."""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

import asyncpg

from data.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class ContactRepository(BaseRepository):
    """Repository for contact database operations using the personnel table."""

    def __init__(self):
        super().__init__('personnel')

    async def get_contacts_for_customer(self, conn: asyncpg.Connection, customer_id: int) -> List[Dict[str, Any]]:
        """
        Get all personnel linked to a customer.

        Args:
            conn: asyncpg connection
            customer_id: Customer ID

        Returns:
            List of personnel dictionaries
        """
        query = """
            SELECT
                personnel_id, first_name, last_name, full_name,
                company_name, source, position, department,
                seniority_level, email, phone, linkedin_url,
                country, city, is_primary, created_at, updated_at
            FROM personnel
            WHERE client_id = $1
            ORDER BY is_primary DESC NULLS LAST, created_at ASC
        """
        return await self._execute_query(conn, query, customer_id)

    async def add_contact(self, conn: asyncpg.Connection, customer_id: int,
                          contact_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Insert a new personnel record linked to a customer.

        Args:
            conn: asyncpg connection
            customer_id: Customer ID
            contact_data: Dictionary with personnel fields

        Returns:
            Created personnel record or None
        """
        now = datetime.now(timezone.utc)
        query = """
            INSERT INTO personnel (
                first_name, last_name, full_name, company_name,
                source, position, department, seniority_level,
                email, phone, linkedin_url, client_id, is_primary,
                created_at, updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15
            )
            RETURNING personnel_id, first_name, last_name, full_name,
                      company_name, source, position, department,
                      seniority_level, email, phone, linkedin_url,
                      client_id, is_primary, created_at, updated_at
        """
        return await self._execute_write(
            conn, query,
            contact_data.get('first_name', ''),
            contact_data.get('last_name', ''),
            contact_data.get('full_name') or contact_data.get('name', ''),
            contact_data.get('company_name', ''),
            contact_data.get('source', ''),
            contact_data.get('position') or contact_data.get('title', ''),
            contact_data.get('department', ''),
            contact_data.get('seniority_level', ''),
            contact_data.get('email', ''),
            contact_data.get('phone', ''),
            contact_data.get('linkedin_url', ''),
            customer_id,
            contact_data.get('is_primary', False),
            now,
            now,
        )

    async def update_contact(self, conn: asyncpg.Connection, customer_id: int,
                             personnel_id: str, contact_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update a personnel record for a specific customer.

        Args:
            conn: asyncpg connection
            customer_id: Customer ID (for ownership check)
            personnel_id: Personnel UUID (string)
            contact_data: Dictionary with fields to update

        Returns:
            Updated personnel record or None
        """
        now = datetime.now(timezone.utc)

        # Build dynamic SET clause
        set_clauses = []
        params = []
        param_idx = 1

        updatable_fields = {
            'first_name': 'first_name',
            'last_name': 'last_name',
            'full_name': 'full_name',
            'name': 'full_name',
            'company_name': 'company_name',
            'source': 'source',
            'position': 'position',
            'title': 'position',
            'department': 'department',
            'seniority_level': 'seniority_level',
            'email': 'email',
            'phone': 'phone',
            'linkedin_url': 'linkedin_url',
            'is_primary': 'is_primary',
        }

        seen_db_fields = set()
        for input_key, db_field in updatable_fields.items():
            if input_key in contact_data and db_field not in seen_db_fields:
                seen_db_fields.add(db_field)
                set_clauses.append(f"{db_field} = ${param_idx}")
                params.append(contact_data[input_key])
                param_idx += 1

        if not set_clauses:
            return None

        # Always update updated_at
        set_clauses.append(f"updated_at = ${param_idx}")
        params.append(now)
        param_idx += 1

        # Add WHERE params
        params.append(personnel_id)
        params.append(customer_id)

        query = f"""
            UPDATE personnel
            SET {', '.join(set_clauses)}
            WHERE personnel_id = ${param_idx}::uuid AND client_id = ${param_idx + 1}
            RETURNING personnel_id, first_name, last_name, full_name,
                      company_name, source, position, department,
                      seniority_level, email, phone, linkedin_url,
                      client_id, is_primary, created_at, updated_at
        """

        return await self._execute_write(conn, query, *params)

    async def delete_contact(self, conn: asyncpg.Connection, customer_id: int,
                             personnel_id: str) -> bool:
        """
        Delete a personnel record for a specific customer.

        Args:
            conn: asyncpg connection
            customer_id: Customer ID (for ownership check)
            personnel_id: Personnel UUID (string)

        Returns:
            True if a row was deleted
        """
        query = """
            DELETE FROM personnel
            WHERE personnel_id = $1::uuid AND client_id = $2
        """
        try:
            result = await conn.execute(query, personnel_id, customer_id)
            return result and not result.endswith('0')
        except Exception as e:
            logger.error(f"Error deleting personnel {personnel_id}: {e}")
            return False

    async def set_primary_contact(self, conn: asyncpg.Connection, customer_id: int,
                                  personnel_id: str) -> bool:
        """
        Set a personnel record as primary for a customer.
        Clears is_primary on all other personnel for the same customer first.

        Args:
            conn: asyncpg connection
            customer_id: Customer ID
            personnel_id: Personnel UUID to set as primary

        Returns:
            True if successful
        """
        try:
            async with conn.transaction():
                now = datetime.now(timezone.utc)
                # Clear is_primary for all personnel of this customer
                await conn.execute(
                    "UPDATE personnel SET is_primary = false, updated_at = $1 WHERE client_id = $2",
                    now, customer_id
                )

                # Set the specified personnel as primary
                result = await conn.execute(
                    "UPDATE personnel SET is_primary = true, updated_at = $1 WHERE personnel_id = $2::uuid AND client_id = $3",
                    now, personnel_id, customer_id
                )

                if result.endswith('0'):
                    raise ValueError(f"Personnel {personnel_id} not found for customer {customer_id}")

                return True
        except Exception as e:
            logger.error(f"Error setting primary contact {personnel_id} for customer {customer_id}: {e}")
            return False

    async def clear_primary_for_customer(self, conn: asyncpg.Connection, customer_id: int) -> None:
        """
        Clear is_primary flag for all personnel of a customer.

        Args:
            conn: asyncpg connection
            customer_id: Customer ID
        """
        await conn.execute(
            "UPDATE personnel SET is_primary = false, updated_at = $1 WHERE client_id = $2",
            datetime.now(timezone.utc), customer_id
        )

    async def get_contact_by_id(self, conn: asyncpg.Connection, customer_id: int,
                                personnel_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a single personnel record by ID, scoped to a customer.

        Args:
            conn: asyncpg connection
            customer_id: Customer ID
            personnel_id: Personnel UUID

        Returns:
            Personnel dict or None
        """
        query = """
            SELECT
                personnel_id, first_name, last_name, full_name,
                company_name, source, position, department,
                seniority_level, email, phone, linkedin_url,
                country, city, is_primary, created_at, updated_at
            FROM personnel
            WHERE personnel_id = $1::uuid AND client_id = $2
        """
        return await self._execute_query_one(conn, query, personnel_id, customer_id)
