"""
Lead Repository for Lead Generation Service (asyncpg).

Handles CRUD operations, advanced search, filtering, and lead management
functionality. All methods are async and take an asyncpg connection as first parameter.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

from data.repositories.base import BaseRepository, QueryResult, SQLBuilder, JSONFieldMixin
from utils.background_tasks import fire_tracked
from service_core.activity import ActivityLogger
from config.constants import (
    LeadStatus,
    LeadSource,
    get_lead_status_options,
    get_lead_source_options,
    is_valid_lead_status,
    is_valid_lead_source,
    DEFAULT_PAGE_SIZE
)

logger = logging.getLogger(__name__)


class LeadRepository(BaseRepository, JSONFieldMixin):
    """Repository for lead data operations."""

    def __init__(self):
        super().__init__(
            table_name="leads",
            primary_key="lead_id",
        )

    async def create_lead(self, conn, lead_data: Dict[str, Any], user_id: str = "system",
                          user_email: Optional[str] = None, auth_token: Optional[str] = None) -> Optional[str]:
        """
        Create a new lead with validation and personnel handling.

        Args:
            conn: asyncpg connection
            lead_data: Lead data dictionary
            user_id: User creating the lead
            user_email: User email for internal sync
            auth_token: Auth token for internal sync

        Returns:
            Lead ID if successful, None if failed
        """
        try:
            # Validate required fields
            if not lead_data.get("company"):
                raise ValueError("Company name is required")

            # Location is optional - set default if empty
            if not lead_data.get("location"):
                lead_data["location"] = "Unknown"

            # Validate status and source
            if "status" in lead_data and not is_valid_lead_status(lead_data["status"]):
                lead_data["status"] = LeadStatus.NEW.value

            if "source" in lead_data and not is_valid_lead_source(lead_data["source"]):
                raise ValueError(f"Invalid lead source: {lead_data['source']}")

            # Set defaults
            lead_data.setdefault("status", LeadStatus.NEW.value)
            lead_data.setdefault("source", LeadSource.MANUAL_ENTRY.value)

            # Default score if not provided (BoL leads arrive pre-scored)
            if lead_data.get("score", 0) == 0:
                lead_data["score"] = 0

            # Extract personnel data if present
            personnel_data = lead_data.pop("personnel", None)

            # Map and filter fields to match database schema
            db_fields = {
                'lead_id', 'company', 'location', 'industry', 'company_size', 'revenue',
                'employees_count', 'website',
                'status', 'score', 'source',
                'created_at', 'updated_at',
                'import_context', 'supplier_context', 'bol_detail_context', 'ready_to_crm'
            }

            # Filter out fields that don't exist in the database
            filtered_data = {}
            for key, value in lead_data.items():
                if key in db_fields:
                    filtered_data[key] = value
                else:
                    logger.debug(f"Ignoring field not in database schema: {key}")

            lead_data = filtered_data

            # Use transaction for lead + personnel creation
            async with conn.transaction():
                # Create lead
                lead_data["created_at"] = datetime.now(timezone.utc)
                lead_data["updated_at"] = datetime.now(timezone.utc)

                # Generate UUID if not provided
                if self.primary_key not in lead_data:
                    lead_data[self.primary_key] = str(uuid.uuid4())

                # Build INSERT query with only valid fields
                fields = list(lead_data.keys())
                placeholders = [f"${i+1}" for i in range(len(fields))]
                values = list(lead_data.values())

                logger.debug(f"Inserting lead with fields: {fields}")
                logger.debug(f"Values: {values}")

                query = f"""
                    INSERT INTO {self.table_name} ({', '.join(fields)})
                    VALUES ({', '.join(placeholders)})
                    RETURNING {self.primary_key}
                """

                result = await conn.fetchrow(query, *values)

                if result:
                    lead_id = str(result[0])

                    # Create personnel records if provided
                    if personnel_data and isinstance(personnel_data, list) and len(personnel_data) > 0:
                        logger.info(f"DEBUG: Creating {len(personnel_data)} personnel records for lead {lead_id}")
                        await self._create_personnel_in_transaction(conn, lead_id, personnel_data, lead_data.get("company"))
                    else:
                        logger.warning(f"DEBUG: No personnel to create for lead {lead_id} (personnel_data={personnel_data})")

                    logger.info(f"Created lead: {lead_id} for company: {lead_data.get('company')}")
                    await ActivityLogger.log("create", "lead", str(lead_id), {"status": "success", "service": "leadgen", "company": lead_data.get("company"), "source": lead_data.get("source")})

                    # Silently copy to internal leads database via HTTP (background sync)
                    try:
                        from clients.internal_leads_client import sync_lead_to_internal_db
                        from data.connection import lookup_db_name

                        # Get user's tenant database name
                        user_tenant_db = await lookup_db_name(user_email) if user_email else 'unknown'

                        # Prepare complete lead data for internal sync
                        complete_lead_data = lead_data.copy()
                        complete_lead_data['lead_id'] = lead_id

                        logger.info(f"Starting internal DB sync for lead: {lead_data.get('company')}")

                        fire_tracked("sync_lead_to_internal_db", lambda: sync_lead_to_internal_db(
                            lead_data=complete_lead_data,
                            personnel_data=personnel_data,
                            user_email=user_email,
                            user_tenant_db=user_tenant_db,
                            auth_token=auth_token or ''
                        ), retries=1, context={"lead_id": lead_id, "company": lead_data.get("company")})
                    except Exception as sync_error:
                        # Log but don't fail the user's operation
                        logger.warning(f"Internal sync failed (non-critical): {sync_error}")

                    return lead_id

            return None

        except Exception as e:
            err_str = str(e)
            if "unique_company_location" in err_str or "duplicate key" in err_str.lower():
                logger.warning(f"Duplicate lead skipped: {e}")
            else:
                logger.error(f"Error creating lead: {e}")
                logger.error(f"Lead data was: {lead_data}")
            raise

    async def get_lead_with_personnel(self, conn, lead_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a lead with its associated personnel.

        Args:
            conn: asyncpg connection
            lead_id: Lead ID to retrieve

        Returns:
            Lead data with personnel list or None if not found
        """
        try:
            # Get lead data using the base repository method
            query = f"SELECT * FROM {self.table_name} WHERE {self.primary_key} = $1"
            lead_result = await conn.fetchrow(query, lead_id)

            if not lead_result:
                return None

            lead_data = self._row_to_dict(lead_result)

            # Get personnel data
            personnel_query = """
                SELECT * FROM personnel
                WHERE lead_id = $1
                ORDER BY created_at DESC
            """
            personnel_results = await conn.fetch(personnel_query, lead_id)

            # Process personnel data
            personnel_list = []
            if personnel_results:
                for row in personnel_results:
                    personnel_dict = dict(row)
                    # Parse JSON fields
                    personnel_dict["skills"] = self.safe_json_parse(personnel_dict.get("skills"), [])
                    personnel_dict["education"] = self.safe_json_parse(personnel_dict.get("education"), {})
                    personnel_dict["other_social_profiles"] = self.safe_json_parse(
                        personnel_dict.get("other_social_profiles"), {}
                    )
                    personnel_list.append(personnel_dict)

            # Add personnel to lead data
            lead_data["personnel"] = personnel_list

            # Ensure 'id' field is available for frontend compatibility
            lead_data.setdefault('id', lead_data.get('lead_id'))

            # Convert datetime fields to ISO strings for JSON serialization
            for key in ['created_at', 'updated_at']:
                if key in lead_data and isinstance(lead_data[key], datetime):
                    lead_data[key] = lead_data[key].isoformat()

            return lead_data

        except Exception as e:
            logger.error(f"Error getting lead with personnel {lead_id}: {e}")
            return None

    async def get_leads_with_personnel_optimized(
        self,
        conn,
        skip: int = 0,
        limit: int = 10,
        company: Optional[str] = None,
        location: Optional[str] = None,
        industry: Optional[str] = None,
        include_synced: bool = True,
        assigned_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get leads with their personnel data using a single optimized JOIN query.
        This eliminates the N+1 query problem.

        Args:
            conn: asyncpg connection
            skip: Number of records to skip (for pagination)
            limit: Maximum number of leads to return
            company: Company name filter (optional)
            location: Location filter (optional)
            industry: Industry filter (optional)
            include_synced: Include leads synced to CRM (optional, default False)
            assigned_to: Filter by assigned employee ID (uses employee_lead_links table)

        Returns:
            Dictionary with leads (including personnel and assigned employees), total count, and personnel stats
        """
        try:
            from config.constants import LeadStatus

            # Build WHERE conditions
            where_conditions = []
            params = []
            idx = 1

            if company:
                where_conditions.append(f"l.company ILIKE ${idx}")
                params.append(f"%{company}%")
                idx += 1

            if location:
                where_conditions.append(f"l.location ILIKE ${idx}")
                params.append(f"%{location}%")
                idx += 1

            if industry:
                where_conditions.append(f"l.industry ILIKE ${idx}")
                params.append(f"%{industry}%")
                idx += 1

            # Filter by assigned employee using employee_lead_links table
            if assigned_to:
                where_conditions.append(f"""
                    EXISTS (
                        SELECT 1 FROM employee_lead_links ell
                        WHERE ell.lead_id = l.lead_id
                        AND ell.employee_id = ${idx}
                        AND ell.status = 'active'
                    )
                """)
                params.append(int(assigned_to))
                idx += 1

            # Exclude synced leads by default
            if not include_synced:
                where_conditions.append(f"l.status != ${idx}")
                params.append(LeadStatus.SYNCED_TO_CRM.value)
                idx += 1

            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

            # Single optimized query using JSON aggregation
            query = f"""
                WITH lead_personnel AS (
                    SELECT
                        l.lead_id,
                        l.company,
                        l.location,
                        l.industry,
                        l.company_size,
                        l.revenue,
                        l.website,
                        l.status,
                        l.score,
                        l.source,
                        l.created_at,
                        l.updated_at,
                        l.import_context,
                        l.supplier_context,
                        l.bol_detail_context,
                        COALESCE(
                            json_agg(
                                json_build_object(
                                    'personnel_id', p.personnel_id,
                                    'lead_id', p.lead_id,
                                    'first_name', p.first_name,
                                    'last_name', p.last_name,
                                    'full_name', p.full_name,
                                    'email', p.email,
                                    'phone', p.phone,
                                    'position', p.position,
                                    'linkedin_url', p.linkedin_url,
                                    'created_at', p.created_at,
                                    'updated_at', p.updated_at
                                ) ORDER BY p.created_at DESC
                            ) FILTER (WHERE p.personnel_id IS NOT NULL),
                            '[]'::json
                        ) as personnel,
                        COUNT(DISTINCT p.personnel_id) as personnel_count
                    FROM leads l
                    LEFT JOIN personnel p ON l.lead_id = p.lead_id
                    WHERE {where_clause}
                    GROUP BY l.lead_id
                    ORDER BY l.created_at DESC
                ),
                -- Separate CTE for assigned employees from employee_lead_links
                lead_employees AS (
                    SELECT
                        ell.lead_id,
                        json_agg(
                            json_build_object(
                                'employeeId', e.employee_id,
                                'employeeName', e.name,
                                'email', e.email,
                                'role', e.role,
                                'department', e.department,
                                'assignedAt', ell.assigned_at
                            ) ORDER BY ell.assigned_at DESC
                        ) as assigned_employees,
                        -- Get primary (most recent) employee for backward compatibility
                        (SELECT e2.employee_id FROM employee_lead_links ell2
                         JOIN employee_info e2 ON ell2.employee_id = e2.employee_id
                         WHERE ell2.lead_id = ell.lead_id AND ell2.status = 'active'
                         ORDER BY ell2.assigned_at DESC LIMIT 1) as primary_employee_id,
                        (SELECT e2.name FROM employee_lead_links ell2
                         JOIN employee_info e2 ON ell2.employee_id = e2.employee_id
                         WHERE ell2.lead_id = ell.lead_id AND ell2.status = 'active'
                         ORDER BY ell2.assigned_at DESC LIMIT 1) as primary_employee_name
                    FROM employee_lead_links ell
                    JOIN employee_info e ON ell.employee_id = e.employee_id
                    WHERE ell.status = 'active'
                    GROUP BY ell.lead_id
                )
                SELECT
                    lp.*,
                    le.assigned_employees,
                    le.primary_employee_id as assigned_employee_id,
                    le.primary_employee_name as assigned_employee_name,
                    COUNT(*) OVER() as total_count,
                    SUM(lp.personnel_count) OVER() as total_personnel
                FROM lead_personnel lp
                LEFT JOIN lead_employees le ON lp.lead_id = le.lead_id
                ORDER BY lp.created_at DESC
            """
            query += f" LIMIT ${idx} OFFSET ${idx + 1}"

            # Add limit and offset to params
            params.extend([limit, skip])
            idx += 2

            # Execute query
            results = await conn.fetch(query, *params)

            if not results:
                return {
                    "leads": [],
                    "total": 0,
                    "total_personnel": 0
                }

            # Process results
            leads = []
            total_count = 0
            total_personnel = 0

            for row in results:
                # Convert row to dict
                lead_dict = dict(row)

                # Extract metadata
                total_count = lead_dict.pop('total_count', 0)
                total_personnel = lead_dict.pop('total_personnel', 0)
                lead_dict.pop('personnel_count', None)

                # Personnel data is already in JSON format from json_agg
                personnel_json = lead_dict.get("personnel", "[]")
                if isinstance(personnel_json, str):
                    personnel_list = json.loads(personnel_json)
                else:
                    personnel_list = personnel_json if personnel_json else []

                lead_dict["personnel"] = personnel_list

                # Parse assigned_employees JSON
                assigned_employees_json = lead_dict.get("assigned_employees")
                if assigned_employees_json:
                    if isinstance(assigned_employees_json, str):
                        lead_dict["assignedEmployees"] = json.loads(assigned_employees_json)
                    else:
                        lead_dict["assignedEmployees"] = assigned_employees_json
                else:
                    lead_dict["assignedEmployees"] = []

                # Convert datetime fields to strings for JSON serialization
                for field in ['created_at', 'updated_at']:
                    if field in lead_dict and lead_dict[field]:
                        if hasattr(lead_dict[field], 'isoformat'):
                            lead_dict[field] = lead_dict[field].isoformat()

                # Ensure required fields for frontend compatibility
                lead_dict['id'] = lead_dict.get('lead_id')

                # Add camelCase employee fields for frontend (backward compatibility - primary employee)
                lead_dict['assignedEmployeeId'] = lead_dict.get('assigned_employee_id')
                lead_dict['assignedEmployeeName'] = lead_dict.get('assigned_employee_name')

                leads.append(lead_dict)

            return {
                "leads": leads,
                "total": total_count,
                "total_personnel": total_personnel
            }

        except Exception as e:
            logger.error(f"Error getting leads with personnel (optimized): {e}")
            return {
                "leads": [],
                "total": 0,
                "total_personnel": 0
            }

    async def get_leads(
        self,
        conn,
        skip: int = 0,
        limit: int = 10,
        company: Optional[str] = None,
        location: Optional[str] = None,
        industry: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get leads with simple filtering (wrapper around search method).
        Compatible with service.py interface.
        """
        page = (skip // limit) + 1
        result = await self.search(
            conn,
            company=company,
            location=location,
            industry=industry,
            page=page,
            page_size=limit
        )

        if result.success:
            # Convert datetime objects to strings for serialization
            leads = []
            for lead_data in result.data:
                converted_lead = lead_data.copy()

                # Handle datetime fields
                for field in ['created_at', 'updated_at']:
                    if field in converted_lead and converted_lead[field]:
                        if hasattr(converted_lead[field], 'isoformat'):
                            converted_lead[field] = converted_lead[field].isoformat()

                # Set name field from company if name is missing
                if 'name' not in converted_lead or not converted_lead['name']:
                    converted_lead['name'] = converted_lead.get('company', 'Unknown')

                # Ensure required fields have defaults
                converted_lead.setdefault('id', converted_lead.get('lead_id'))
                converted_lead.setdefault('company', converted_lead.get('name', 'Unknown'))
                converted_lead.setdefault('location', 'Unknown')

                leads.append(converted_lead)

            return leads
        else:
            return []

    async def search(
        self,
        conn,
        company: Optional[str] = None,
        location: Optional[str] = None,
        industry: Optional[str] = None,
        status: Optional[str] = None,
        source: Optional[str] = None,
        min_score: Optional[int] = None,
        max_score: Optional[int] = None,
        text_search: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        has_website: Optional[bool] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        order_by: Optional[str] = None,
        **kwargs
    ) -> QueryResult:
        """
        Advanced lead search with multiple filter options.

        Args:
            conn: asyncpg connection
            company: Company name filter (partial match)
            location: Location filter (partial match)
            industry: Industry filter (partial match)
            status: Lead status filter (exact match)
            source: Lead source filter (exact match)
            min_score: Minimum score filter
            max_score: Maximum score filter
            text_search: Full-text search across company
            created_after: Filter leads created after this date
            created_before: Filter leads created before this date
            has_website: Filter leads that have/don't have website
            page: Page number for pagination
            page_size: Number of results per page
            order_by: Field to order by

        Returns:
            QueryResult with matching leads
        """
        try:
            conditions = {}

            # Text filters (partial match)
            if company:
                conditions["company__ilike"] = company
            if location:
                conditions["location__ilike"] = location
            if industry:
                conditions["industry__ilike"] = industry

            # Exact match filters
            if status and is_valid_lead_status(status):
                conditions["status"] = status
            if source and is_valid_lead_source(source):
                conditions["source"] = source

            # Score filters
            if min_score is not None:
                conditions["score__gte"] = min_score
            if max_score is not None:
                conditions["score__lte"] = max_score

            # Date filters
            if created_after:
                conditions["created_at__gte"] = created_after
            if created_before:
                conditions["created_at__lte"] = created_before

            # Contact info filters
            if has_website is not None:
                conditions["website__is_null"] = not has_website

            # Handle additional kwargs (like status__ne from router)
            for key, value in kwargs.items():
                if key == 'status__ne':
                    conditions[key] = value

            # Build base query
            where_clause, where_params, next_idx = SQLBuilder.build_where_clause(conditions)

            # Handle complex filters that need custom SQL
            additional_conditions = []
            additional_params = []

            # Full-text search
            if text_search:
                additional_conditions.append(
                    f"(to_tsvector('english', company) @@ plainto_tsquery('english', ${next_idx}))"
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
            leads = []
            if results:
                for row in results:
                    lead_dict = dict(row)
                    leads.append(lead_dict)

            return QueryResult(
                data=leads,
                total_count=total_count,
                page=page,
                page_size=page_size or DEFAULT_PAGE_SIZE,
                success=True,
                message="Search completed successfully"
            )

        except Exception as e:
            logger.error(f"Error searching leads: {e}")
            return QueryResult(
                data=[],
                success=False,
                error=str(e),
                message="Search failed"
            )

    async def update_lead(self, conn, lead_id: str, updates: Dict[str, Any], user_id: str = "system") -> Optional[Dict[str, Any]]:
        """
        Update a lead with validation and return updated lead data.

        Args:
            conn: asyncpg connection
            lead_id: ID of lead to update
            updates: Dictionary of fields to update
            user_id: User making the update

        Returns:
            Updated lead data dictionary or None if failed
        """
        try:
            if not updates:
                # No updates provided, just return current lead data
                return await self.get_lead_with_employee_info(conn, lead_id)

            # Validate status if provided
            if "status" in updates and not is_valid_lead_status(updates["status"]):
                raise ValueError(f"Invalid lead status: {updates['status']}")

            # Validate source if provided
            if "source" in updates and not is_valid_lead_source(updates["source"]):
                raise ValueError(f"Invalid lead source: {updates['source']}")

            # Add updated_at timestamp
            updates["updated_at"] = datetime.now(timezone.utc)

            # Use base class update method
            success = await self.update(conn, lead_id, updates, user_id)

            if success:
                await ActivityLogger.log("update", "lead", str(lead_id), {"status": "success", "service": "leadgen", "fields": list(updates.keys())})
                # Return updated lead data with employee info
                return await self.get_lead_with_employee_info(conn, lead_id)

            return None

        except Exception as e:
            logger.error(f"Error updating lead {lead_id}: {e}")
            return None

    async def get_lead_with_employee_info(self, conn, lead_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a lead with employee assignment information included.
        Uses employee_lead_links table for many-to-many employee assignments.

        Args:
            conn: asyncpg connection
            lead_id: Lead ID to retrieve

        Returns:
            Lead data with assignedEmployees array and backward-compatible
            assignedEmployeeId/assignedEmployeeName fields (primary employee)
        """
        try:
            # First get the lead data
            lead_query = """
                SELECT l.*
                FROM leads l
                WHERE l.lead_id = $1
            """
            lead_result = await conn.fetchrow(lead_query, lead_id)

            if not lead_result:
                return None

            lead_data = self._row_to_dict(lead_result)

            # Get all assigned employees from employee_lead_links
            employees_query = """
                SELECT
                    e.employee_id,
                    e.name,
                    e.email,
                    e.role,
                    e.department,
                    ell.assigned_at,
                    ell.notes,
                    ell.matched_by,
                    ell.status
                FROM employee_lead_links ell
                JOIN employee_info e ON ell.employee_id = e.employee_id
                WHERE ell.lead_id = $1 AND ell.status = 'active'
                ORDER BY ell.assigned_at DESC
            """
            employees_result = await conn.fetch(employees_query, lead_id)

            # Build assigned employees list
            assigned_employees = []
            primary_employee_id = None
            primary_employee_name = None

            if employees_result:
                for emp in employees_result:
                    emp_dict = dict(emp)
                    assigned_employees.append({
                        "employeeId": emp_dict.get("employee_id"),
                        "employeeName": emp_dict.get("name"),
                        "email": emp_dict.get("email"),
                        "role": emp_dict.get("role"),
                        "department": emp_dict.get("department"),
                        "assignedAt": emp_dict.get("assigned_at").isoformat() if emp_dict.get("assigned_at") else None,
                        "notes": emp_dict.get("notes"),
                        "matchedBy": emp_dict.get("matched_by"),
                        "status": emp_dict.get("status")
                    })

                # Primary employee is the most recently assigned (first in list)
                if assigned_employees:
                    primary_employee_id = assigned_employees[0]["employeeId"]
                    primary_employee_name = assigned_employees[0]["employeeName"]

            # Add assigned employees array (new many-to-many format)
            lead_data["assignedEmployees"] = assigned_employees

            # Add camelCase aliases for frontend backward compatibility (primary employee)
            lead_data["assignedEmployeeId"] = primary_employee_id
            lead_data["assignedEmployeeName"] = primary_employee_name
            lead_data["assigned_employee_id"] = primary_employee_id
            lead_data["assigned_employee_name"] = primary_employee_name

            # Add id field for frontend compatibility (frontend uses both id and lead_id)
            lead_data["id"] = lead_data.get("lead_id")

            return lead_data

        except Exception as e:
            logger.error(f"Error getting lead with employee info {lead_id}: {e}")
            return None

    async def delete_lead(self, conn, lead_id: str, user_id: str = "system") -> bool:
        """
        Delete a lead and all associated data including foreign key references.

        Args:
            conn: asyncpg connection
            lead_id: ID of lead to delete
            user_id: User deleting the lead

        Returns:
            True if successful
        """
        try:
            # Get lead info before deletion for logging
            lead_data = await self.get_by_id(conn, lead_id)
            if not lead_data:
                return False

            # Delete related records first to avoid foreign key constraint violations
            async with conn.transaction():
                # 1. Delete personnel associated with lead
                await conn.execute("DELETE FROM personnel WHERE lead_id = $1", lead_id)

                # 2. Finally delete the lead itself
                result = await conn.execute(
                    f"DELETE FROM {self.table_name} WHERE {self.primary_key} = $1", lead_id
                )

            if result and not result.endswith(' 0'):
                logger.info(f"Deleted lead: {lead_id} - {lead_data.get('company')} and all associated data")
                await ActivityLogger.log("delete", "lead", str(lead_id), {"status": "success", "service": "leadgen", "company": lead_data.get("company")})
                return True

            return False

        except Exception as e:
            logger.error(f"Error deleting lead {lead_id}: {e}")
            return False

    async def _create_personnel_in_transaction(self, conn, lead_id: str, personnel_list: List[Dict[str, Any]], company_name: str = None) -> bool:
        """Create personnel records within an existing transaction. Silently skip duplicates."""
        created_count = 0
        skipped_count = 0

        try:
            for person in personnel_list:
                try:
                    # Add metadata
                    person["lead_id"] = lead_id
                    person["created_at"] = datetime.now(timezone.utc)
                    person["updated_at"] = datetime.now(timezone.utc)

                    # Generate UUID for personnel
                    if "personnel_id" not in person:
                        person["personnel_id"] = str(uuid.uuid4())

                    # Set default source if not provided (required field)
                    if "source" not in person or person["source"] is None:
                        person["source"] = "api_import"

                    # Add company_name from parent lead if missing (required field)
                    if "company_name" not in person and company_name:
                        person["company_name"] = company_name

                    # Handle empty first_name (required field)
                    if not person.get("first_name") or person.get("first_name") == "":
                        person["first_name"] = "Unknown"

                    # Handle empty last_name (required field)
                    if not person.get("last_name") or person.get("last_name") == "":
                        person["last_name"] = "N/A"

                    # Generate full_name if not present
                    if "full_name" not in person:
                        first_name = person.get("first_name", "")
                        last_name = person.get("last_name", "")
                        person["full_name"] = f"{first_name} {last_name}".strip()

                    # Handle JSON fields
                    if "skills" in person:
                        person["skills"] = self.prepare_json_field(person["skills"])
                    if "education" in person:
                        person["education"] = self.prepare_json_field(person["education"])
                    if "other_social_profiles" in person:
                        person["other_social_profiles"] = self.prepare_json_field(person["other_social_profiles"])

                    # Build INSERT query
                    fields = list(person.keys())
                    placeholders = [f"${i+1}" for i in range(len(fields))]
                    values = list(person.values())

                    query = f"""
                        INSERT INTO personnel ({', '.join(fields)})
                        VALUES ({', '.join(placeholders)})
                    """

                    await conn.execute(query, *values)
                    created_count += 1

                except Exception as person_error:
                    error_msg = str(person_error)
                    # If duplicate, skip silently - personnel already exists
                    if "unique_person_company" in error_msg.lower():
                        logger.info(f"Personnel {person.get('full_name')} already exists for lead {lead_id}, skipping")
                        skipped_count += 1
                    else:
                        # For other errors, re-raise to rollback transaction
                        raise

            logger.info(f"Personnel for lead {lead_id}: {created_count} created, {skipped_count} skipped (already exist)")
            return True

        except Exception as e:
            logger.error(f"Error creating personnel for lead {lead_id}: {e}")
            # Re-raise the exception to rollback the transaction
            raise

    async def get_lead_by_id(self, conn, lead_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a lead by ID (alias for get_by_id for email service compatibility).

        Args:
            conn: asyncpg connection
            lead_id: Lead ID to retrieve

        Returns:
            Lead data or None if not found
        """
        lead_data = await self.get_by_id(conn, lead_id)
        if lead_data:
            # Ensure 'id' field is available for frontend compatibility
            lead_data.setdefault('id', lead_data.get('lead_id'))
        return lead_data
