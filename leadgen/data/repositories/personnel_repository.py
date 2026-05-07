"""
Personnel Repository for Lead Generation Service (asyncpg).

Handles CRUD operations for personnel/contacts associated with leads.
Manages professional profiles, contact information, and lead associations.
All methods are async and take an asyncpg connection as first parameter.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

from data.repositories.base import BaseRepository, QueryResult, SQLBuilder
from config.constants import DEFAULT_PAGE_SIZE, LeadSource

logger = logging.getLogger(__name__)


class PersonnelRepository(BaseRepository):
    """Repository for personnel/contact data operations."""

    def __init__(self):
        super().__init__(
            table_name="personnel",
            primary_key="personnel_id",
        )

    async def create_personnel(self, conn, personnel_data: Dict[str, Any], user_id: str = "system") -> Optional[str]:
        """
        Create a new personnel record with validation.

        Args:
            conn: asyncpg connection
            personnel_data: Personnel data dictionary
            user_id: User creating the record

        Returns:
            Personnel ID if successful

        Raises:
            Exception: Re-raises exceptions from database layer for caller to handle
        """
        # Validate required fields
        if not personnel_data.get("first_name"):
            raise ValueError("First name is required")
        if not personnel_data.get("last_name"):
            raise ValueError("Last name is required")
        if not personnel_data.get("company_name"):
            raise ValueError("Company name is required")
        if not personnel_data.get("lead_id"):
            raise ValueError("Lead ID is required")

        # Set defaults
        personnel_data.setdefault("source", LeadSource.MANUAL_ENTRY.value)

        # Generate full name if not provided
        if not personnel_data.get("full_name"):
            first_name = personnel_data.get("first_name", "")
            last_name = personnel_data.get("last_name", "")
            personnel_data["full_name"] = f"{first_name} {last_name}".strip()

        # Add metadata
        personnel_data["created_at"] = datetime.now(timezone.utc)
        personnel_data["updated_at"] = datetime.now(timezone.utc)

        # Generate UUID if not provided
        if self.primary_key not in personnel_data:
            personnel_data[self.primary_key] = str(uuid.uuid4())

        # Build INSERT query - this will raise exception on duplicate constraint
        fields = list(personnel_data.keys())
        placeholders = [f"${i+1}" for i in range(len(fields))]
        values = list(personnel_data.values())

        query = f"""
            INSERT INTO {self.table_name} ({', '.join(fields)})
            VALUES ({', '.join(placeholders)})
            RETURNING {self.primary_key}
        """

        # Execute query - will raise exception on duplicate, which we want
        result = await conn.fetchrow(query, *values)

        if result:
            personnel_id = str(result[self.primary_key])
            logger.info(f"Created personnel: {personnel_id} - {personnel_data.get('full_name')}")
            return personnel_id

        # Should not reach here normally, but if we do, raise an error
        raise RuntimeError("Failed to create personnel: no result returned")

    async def get_personnel_by_lead(self, conn, lead_id: str) -> List[Dict[str, Any]]:
        """
        Get all personnel associated with a specific lead.

        Args:
            conn: asyncpg connection
            lead_id: Lead ID to find personnel for

        Returns:
            List of personnel dictionaries
        """
        try:
            query = f"""
                SELECT * FROM {self.table_name}
                WHERE lead_id = $1
                ORDER BY created_at DESC
            """

            results = await conn.fetch(query, lead_id)

            if results:
                return [dict(row) for row in results]

            return []

        except Exception as e:
            logger.error(f"Error getting personnel for lead {lead_id}: {e}")
            return []

    async def search(
        self,
        conn,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        full_name: Optional[str] = None,
        company_name: Optional[str] = None,
        position: Optional[str] = None,
        department: Optional[str] = None,
        seniority_level: Optional[str] = None,
        email: Optional[str] = None,
        country: Optional[str] = None,
        city: Optional[str] = None,
        lead_id: Optional[str] = None,
        source: Optional[str] = None,
        has_linkedin: Optional[bool] = None,
        has_email: Optional[bool] = None,
        has_phone: Optional[bool] = None,
        text_search: Optional[str] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        order_by: Optional[str] = None,
        **kwargs
    ) -> QueryResult:
        """
        Advanced personnel search with multiple filter options.

        Args:
            conn: asyncpg connection
            first_name: First name filter (partial match)
            last_name: Last name filter (partial match)
            full_name: Full name filter (partial match)
            company_name: Company name filter (partial match)
            position: Position filter (partial match)
            department: Department filter (partial match)
            seniority_level: Seniority level filter (exact match)
            email: Email filter (partial match)
            country: Country filter (partial match)
            city: City filter (partial match)
            lead_id: Lead ID filter (exact match)
            source: Source filter (exact match)
            has_linkedin: Filter by LinkedIn URL presence
            has_email: Filter by email presence
            has_phone: Filter by phone presence
            text_search: Full-text search across names and position
            page: Page number for pagination
            page_size: Number of results per page
            order_by: Field to order by

        Returns:
            QueryResult with matching personnel
        """
        try:
            conditions = {}

            # Text filters (partial match)
            if first_name:
                conditions["first_name__ilike"] = first_name
            if last_name:
                conditions["last_name__ilike"] = last_name
            if full_name:
                conditions["full_name__ilike"] = full_name
            if company_name:
                conditions["company_name__ilike"] = company_name
            if position:
                conditions["position__ilike"] = position
            if department:
                conditions["department__ilike"] = department
            if email:
                conditions["email__ilike"] = email
            if country:
                conditions["country__ilike"] = country
            if city:
                conditions["city__ilike"] = city

            # Exact match filters
            if seniority_level:
                conditions["seniority_level"] = seniority_level
            if lead_id:
                conditions["lead_id"] = lead_id
            if source:
                conditions["source"] = source

            # Contact info filters
            if has_linkedin is not None:
                conditions["linkedin_url__is_null"] = not has_linkedin
            if has_email is not None:
                conditions["email__is_null"] = not has_email
            if has_phone is not None:
                conditions["phone__is_null"] = not has_phone

            # Build base query
            where_clause, where_params, next_idx = SQLBuilder.build_where_clause(conditions)

            # Handle complex filters
            additional_conditions = []
            additional_params = []

            # Full-text search
            if text_search:
                additional_conditions.append(
                    f"(to_tsvector('english', full_name || ' ' || COALESCE(position, '')) @@ plainto_tsquery('english', ${next_idx}))"
                )
                additional_params.append(text_search)
                next_idx += 1

            # Combine conditions
            if additional_conditions:
                if where_clause:
                    where_clause += f" AND {' AND '.join(additional_conditions)}"
                else:
                    where_clause = f" WHERE {' AND '.join(additional_conditions)}"
                where_params.extend(additional_params)

            # Order clause
            order_clause = SQLBuilder.build_order_clause(order_by, "created_at DESC")

            # Pagination
            limit_clause, limit_params, _ = SQLBuilder.build_limit_offset(page, page_size, next_idx)

            # Main query
            query = f"SELECT * FROM {self.table_name}{where_clause}{order_clause}{limit_clause}"
            params = where_params + limit_params

            results = await conn.fetch(query, *params)

            # Get total count
            total_count = None
            if page is not None:
                count_query = f"SELECT COUNT(*) as count FROM {self.table_name}{where_clause}"
                count_params = where_params
                count_result = await conn.fetchrow(count_query, *count_params)
                total_count = count_result["count"] if count_result else 0

            # Process results
            personnel = [dict(row) for row in results] if results else []

            return QueryResult(
                data=personnel,
                total_count=total_count,
                page=page,
                page_size=page_size or DEFAULT_PAGE_SIZE,
                success=True,
                message="Personnel search completed successfully"
            )

        except Exception as e:
            logger.error(f"Error searching personnel: {e}")
            return QueryResult(
                data=[],
                success=False,
                error=str(e),
                message="Personnel search failed"
            )

    async def update_personnel(self, conn, personnel_id: str, updates: Dict[str, Any], user_id: str = "system") -> bool:
        """
        Update personnel with validation.

        Args:
            conn: asyncpg connection
            personnel_id: ID of personnel to update
            updates: Dictionary of fields to update
            user_id: User making the update

        Returns:
            True if successful
        """
        try:
            if not updates:
                return True

            # Update full name if first/last name changed
            if "first_name" in updates or "last_name" in updates:
                current_data = await self.get_by_id(conn, personnel_id)
                if current_data:
                    first_name = updates.get("first_name", current_data.get("first_name", ""))
                    last_name = updates.get("last_name", current_data.get("last_name", ""))
                    updates["full_name"] = f"{first_name} {last_name}".strip()

            # Use base class update method
            return await self.update(conn, personnel_id, updates, user_id)

        except Exception as e:
            logger.error(f"Error updating personnel {personnel_id}: {e}")
            return False
