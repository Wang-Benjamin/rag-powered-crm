"""
Leads Router for Lead Generation.
Handles CRUD operations, export, enrichment history, and scraping.
"""

from fastapi import APIRouter, Query, HTTPException, Depends, Body, Header
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel
from service_core.db import get_tenant_connection
from leads.schemas import LeadCreate, LeadUpdate, LeadsResponse, LeadWithPersonnelResponse
from database.queries import get_monthly_token_usage_by_leads, get_enrichment_history, get_enrichment_history_count, get_employee_id_by_email
from utils.redis_cache import get_cache
from config.services import get_user_repositories
import asyncio
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/token-usage/monthly")
async def get_monthly_token_usage(
    tenant=Depends(get_tenant_connection)
):
    """
    Get monthly token usage for the current user.

    Counts the number of leads created this month that have at least 1 personnel
    record with an email address. Each such lead counts as 1 token.

    Returns:
        dict: {
            "tokens_used": int,
            "tokens_limit": int,
            "tokens_remaining": int
        }
    """
    try:
        conn, user = tenant
        user_email = user.get("email", "unknown")

        # Get token count from database
        tokens_used = await get_monthly_token_usage_by_leads(conn, user_email)

        # Monthly limit is 300 tokens
        tokens_limit = 300
        tokens_remaining = max(0, tokens_limit - tokens_used)

        return {
            "tokens_used": tokens_used,
            "tokens_limit": tokens_limit,
            "tokens_remaining": tokens_remaining
        }
    except Exception as e:
        logger.error(f"Error getting monthly token usage: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("", response_model=LeadsResponse)
async def get_leads(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=1000),
    company: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    website: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    include_synced: bool = Query(True, description="Include leads that have been synced to CRM"),
    # Structured column filters (JSON string)
    column_filters: Optional[str] = Query(None, description="JSON object with structured column filters"),
    tenant=Depends(get_tenant_connection)
):
    """
    Get leads with filtering.

    Includes all leads by default, including those synced to CRM.
    Set include_synced=false to exclude synced leads.
    """
    try:
        from config.constants import LeadStatus

        conn, _user = tenant
        repos = get_user_repositories()

        # Build filter conditions
        filters = {}

        # Handle simple filters
        if company:
            filters['company'] = company
        if location:
            filters['location'] = location
        if industry:
            filters['industry'] = industry
        if website:
            filters['website'] = website
        if status:
            filters['status'] = status

        # Handle structured column filters
        if column_filters:
            try:
                parsed_filters = json.loads(column_filters)
                for column_id, filter_config in parsed_filters.items():
                    condition = filter_config.get('condition')
                    value = filter_config.get('value')

                    if not condition or not value:
                        continue

                    # Map filter conditions to database query operators
                    if condition == 'contains':
                        filters[f'{column_id}__icontains'] = value
                    elif condition == 'equals':
                        filters[column_id] = value
                    elif condition == 'starts_with':
                        filters[f'{column_id}__istartswith'] = value
                    elif condition == 'ends_with':
                        filters[f'{column_id}__iendswith'] = value
                    elif condition == 'not_contains':
                        filters[f'{column_id}__not_icontains'] = value
                    elif condition == 'is_empty':
                        filters[f'{column_id}__isnull'] = True
                    elif condition == 'not_empty':
                        filters[f'{column_id}__isnull'] = False

            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in column_filters: {column_filters}")

        # Exclude synced leads by default
        if not include_synced:
            filters['status__ne'] = LeadStatus.SYNCED_TO_CRM.value

        # Use search method for more flexible filtering
        result = await repos['lead_repo'].search(
            conn,
            page=page,
            page_size=per_page,
            **filters
        )

        total = result.total_count or len(result.data)
        total_pages = (total + per_page - 1) // per_page if total > 0 else 0

        return LeadsResponse(
            data=result.data,
            total=total,
            page=page,
            perPage=per_page,
            totalPages=total_pages
        )
    except Exception as e:
        logger.error(f"Error getting leads: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Keys the leads table / metrics cards / enrichment-split logic actually read from each row.
# Everything else (aiActionBrief, recentBols, timeSeries, full scoringSignals breakdown,
# topProducts, hsCodes, topSuppliers, full personnel records) is dropped here to keep the
# list payload small — detail modal refetches via /lead/{id}.
_LIST_IMPORT_CTX_KEYS = ("totalShipments", "totalSuppliers", "mostRecentShipment", "matchingShipments")
_LIST_SUPPLIER_KEYS = ("name", "trend", "share", "shipments12M", "shipments1224M")
_LIST_SUPPLIER_CTX_TOP_KEYS = ("enrichedAt",)
_LIST_BOL_KEYS = ("aiInsightCondensed",)
_LIST_PERSONNEL_KEYS = ("full_name", "email")


def _project_lead_for_list(lead: Dict[str, Any]) -> Dict[str, Any]:
    """Strip a lead dict down to the fields the table view actually renders."""
    out = dict(lead)

    import_ctx = out.get("import_context")
    if isinstance(import_ctx, dict):
        out["import_context"] = {k: import_ctx[k] for k in _LIST_IMPORT_CTX_KEYS if k in import_ctx}

    supplier_ctx = out.get("supplier_context")
    if isinstance(supplier_ctx, dict):
        lean_ctx: Dict[str, Any] = {
            k: supplier_ctx[k] for k in _LIST_SUPPLIER_CTX_TOP_KEYS if k in supplier_ctx
        }
        suppliers = supplier_ctx.get("suppliers") or []
        if isinstance(suppliers, list):
            lean_ctx["suppliers"] = [
                {k: s[k] for k in _LIST_SUPPLIER_KEYS if k in s}
                for s in suppliers
                if isinstance(s, dict)
            ]
        out["supplier_context"] = lean_ctx

    bol_ctx = out.get("bol_detail_context")
    if isinstance(bol_ctx, dict):
        # Preserve non-null so the frontend's `bolDetailContext == null` check still
        # distinguishes enriched vs pending-enrichment leads.
        lean_bol: Dict[str, Any] = {k: bol_ctx[k] for k in _LIST_BOL_KEYS if k in bol_ctx}
        # MetricsCards reads scoringSignals.reorderWindow.points — keep that one nested path only.
        signals = bol_ctx.get("scoringSignals")
        if isinstance(signals, dict):
            reorder = signals.get("reorderWindow")
            if isinstance(reorder, dict) and "points" in reorder:
                lean_bol["scoringSignals"] = {"reorderWindow": {"points": reorder["points"]}}
        out["bol_detail_context"] = lean_bol

    personnel = out.get("personnel")
    if isinstance(personnel, list) and personnel:
        first = personnel[0] if isinstance(personnel[0], dict) else {}
        out["personnel"] = [{k: first[k] for k in _LIST_PERSONNEL_KEYS if k in first}]

    return out


@router.get("/with-personnel", response_model=Dict[str, Any])
async def get_leads_with_personnel(
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=1000),
    company: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    include_synced: bool = Query(True, description="Include leads that have been synced to CRM"),
    tenant=Depends(get_tenant_connection)
):
    """
    Get all leads with their personnel data using optimized single-query approach.
    This eliminates the N+1 query problem by using a JOIN with JSON aggregation.

    Includes all leads by default, including those synced to CRM.
    Set include_synced=false to exclude synced leads.

    Also filters leads by assigned employee - only shows leads assigned to the current user.
    """
    try:
        conn, user = tenant
        user_email = user.get("email", "unknown")
        repos = get_user_repositories()

        # Get employee_id and access level for filtering
        assigned_to_filter = None
        try:
            employee_id = await get_employee_id_by_email(conn, user_email)
            if employee_id:
                # Check access level - only filter if access=user
                access_result = await conn.fetchrow(
                    "SELECT access FROM employee_info WHERE employee_id = $1",
                    employee_id
                )

                if access_result:
                    access_level = access_result.get('access', 'user')

                    if access_level == 'admin':
                        # Admin sees all leads - no filtering
                        logger.info(f"Admin user {user_email} - showing all leads")
                        assigned_to_filter = None
                    else:
                        # Regular user - filter by assignment
                        assigned_to_filter = str(employee_id)
                        logger.info(f"User access: filtering leads for employee {employee_id} (user: {user_email})")
                else:
                    # Default to user access if we can't determine
                    assigned_to_filter = str(employee_id)
                    logger.info(f"Could not determine access level - filtering leads for employee {employee_id} (user: {user_email})")
        except Exception as e:
            logger.warning(f"Could not get employee_id/access for filtering: {e}")

        # Calculate skip based on page
        skip = (page - 1) * per_page

        # Use optimized method that fetches leads + personnel in a single query
        result = await repos['lead_repo'].get_leads_with_personnel_optimized(
            conn,
            skip=skip,
            limit=per_page,
            company=company,
            location=location,
            industry=industry,
            include_synced=include_synced,
            assigned_to=assigned_to_filter
        )

        lean_leads = [_project_lead_for_list(lead) for lead in result.get("leads", [])]

        return {
            "leads": lean_leads,
            "total": result.get("total", 0),
            "total_personnel": result.get("total_personnel", 0),
            "page": page,
            "per_page": per_page,
            "success": True
        }
    except Exception as e:
        logger.error(f"Error getting leads with personnel: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/batch-check-exists")
async def batch_check_companies_exist(
    company_names: List[str] = Body(..., embed=True),
    tenant=Depends(get_tenant_connection)
):
    """
    Batch check which companies already exist in the database.

    Returns a dictionary mapping company names to boolean existence flags.
    This eliminates N+1 query problem when checking multiple companies.

    **Request Body:**
    ```json
    {
        "company_names": ["Company A", "Company B", "Company C"]
    }
    ```

    **Returns:**
    ```json
    {
        "Company A": true,
        "Company B": false,
        "Company C": true
    }
    ```
    """
    try:
        conn, _user = tenant
        repos = get_user_repositories()

        # Build result dictionary
        result = {}

        # Use a single query with IN clause for all companies
        if company_names:
            try:
                # Use ANY($1) for efficient batch checking
                query = """
                    SELECT DISTINCT company
                    FROM leads
                    WHERE company = ANY($1)
                """
                rows = await conn.fetch(query, company_names)
                existing_companies = {row['company'] for row in rows}

                # Build result dict
                result = {name: name in existing_companies for name in company_names}

            except Exception as e:
                logger.error(f"Error in batch company check: {e}")
                # Fallback to individual checks on error
                lead_repo = repos['lead_repo']
                for company_name in company_names:
                    try:
                        leads = await lead_repo.search(conn, company=company_name, page_size=1)
                        result[company_name] = len(leads.data) > 0
                    except Exception as check_error:
                        logger.debug(f"Error checking company {company_name}: {check_error}")
                        result[company_name] = False

        return result

    except Exception as e:
        logger.error(f"Error in batch check companies exist: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("", response_model=Dict[str, Any])
async def create_lead(
    lead: LeadCreate,
    tenant=Depends(get_tenant_connection),
    authorization: str = Header(None)
):
    """Create a new lead, or assign existing lead to current user if it already exists"""
    try:
        conn, user = tenant
        user_email = user.get("email", "unknown")
        # Extract token from Authorization header for internal service calls
        auth_token = authorization.replace("Bearer ", "") if authorization else None
        repos = get_user_repositories(user_email=user_email, auth_token=auth_token)

        # Extract personnel data BEFORE filtering
        lead_dict = lead.dict()
        personnel_data = lead_dict.pop('personnel', None)
        logger.info(f"DEBUG: Extracted personnel_data: {personnel_data}")

        # Define valid database columns based on actual table schema
        valid_db_columns = {
            'lead_id', 'company', 'location', 'industry', 'company_size', 'revenue',
            'employees_count', 'website',
            'status', 'score', 'source',
            'created_at', 'updated_at'
        }

        # Remove None values and invalid columns
        lead_data = {k: v for k, v in lead_dict.items() if v is not None and k in valid_db_columns}

        # Get employee_id for auto-assignment to employee_lead_links
        auto_assign_employee_id = None
        try:
            auto_assign_employee_id = await get_employee_id_by_email(conn, user_email)
            if auto_assign_employee_id:
                logger.info(f"Auto-assigned lead to employee {auto_assign_employee_id} for user {user_email}")
        except Exception as e:
            logger.warning(f"Could not auto-assign lead to employee: {e}")

        # Check if lead already exists (by company + location)
        company = lead_data.get('company')
        location = lead_data.get('location')
        existing_lead = None

        if company and location:
            existing_lead = await conn.fetchrow(
                """
                SELECT lead_id FROM leads
                WHERE LOWER(TRIM(company)) = LOWER(TRIM($1))
                AND LOWER(TRIM(location)) = LOWER(TRIM($2))
                """,
                company, location
            )

        if existing_lead:
            # Lead already exists - add employee assignment and personnel
            existing_lead_id = str(existing_lead['lead_id'])
            logger.info(f"Lead already exists (lead_id={existing_lead_id}), adding employee assignment and personnel")

            # Fix #1: Add personnel to existing lead (don't silently drop)
            if personnel_data and len(personnel_data) > 0:
                try:
                    # Get company name from existing lead for personnel records
                    existing_lead_full = await conn.fetchrow(
                        "SELECT company FROM leads WHERE lead_id = $1",
                        existing_lead_id
                    )
                    company_name = existing_lead_full.get('company') if existing_lead_full else lead_data.get('company')

                    for person in personnel_data:
                        try:
                            person['lead_id'] = existing_lead_id
                            person['company_name'] = company_name
                            await repos['personnel_repo'].create_personnel(conn, person, user_email)
                            logger.info(f"Added personnel to existing lead: {person.get('first_name')} {person.get('last_name')}")
                        except Exception as pe:
                            # Personnel might already exist, log and continue
                            logger.warning(f"Could not add personnel to existing lead (may already exist): {pe}")
                except Exception as e:
                    logger.warning(f"Could not add personnel to existing lead: {e}")

            # Fix #5: Add error handling for employee assignment
            if auto_assign_employee_id:
                try:
                    await conn.execute("""
                        INSERT INTO employee_lead_links (
                            employee_id, lead_id, assigned_at, notes, matched_by, status
                        ) VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (employee_id, lead_id) DO UPDATE SET
                            status = 'active',
                            assigned_at = EXCLUDED.assigned_at
                    """,
                        auto_assign_employee_id,
                        existing_lead_id,
                        datetime.now(timezone.utc),
                        "Assigned to existing lead",
                        "auto_assigned_existing",
                        "active"
                    )
                    logger.info(f"Added employee {auto_assign_employee_id} to existing lead {existing_lead_id}")
                except Exception as e:
                    logger.warning(f"Could not assign employee to existing lead (non-critical): {e}")

            return {
                "message": "Lead already exists, employee assignment added",
                "lead_id": existing_lead_id,
                "already_exists": True
            }

        # Add personnel back if it exists and has data
        if personnel_data is not None and len(personnel_data) > 0:
            lead_data['personnel'] = personnel_data
            logger.info(f"DEBUG: Added personnel to lead_data: {len(personnel_data)} records")
        else:
            logger.warning(f"DEBUG: No personnel_data to add! (personnel_data={personnel_data})")

        logger.info(f"Creating lead with data: {lead_data}")
        result = await repos['lead_repo'].create_lead(conn, lead_data, user_email)

        # Insert into employee_lead_links for the new many-to-many relationship
        if auto_assign_employee_id and result:
            try:
                await conn.execute("""
                    INSERT INTO employee_lead_links (
                        employee_id, lead_id, assigned_at, notes, matched_by, status
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (employee_id, lead_id) DO NOTHING
                """,
                    auto_assign_employee_id,
                    result,  # lead_id returned from create_lead
                    datetime.now(timezone.utc),
                    "Auto-assigned on lead creation",
                    "auto_assigned",
                    "active"
                )
                logger.info(f"Inserted employee_lead_link for employee {auto_assign_employee_id} -> lead {result}")
            except Exception as e:
                logger.warning(f"Could not insert employee_lead_link (non-critical): {e}")

        return {"message": "Lead created successfully", "lead_id": result, "already_exists": False}
    except Exception as e:
        logger.error(f"Error creating lead: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/lead/{lead_id}", response_model=Dict[str, Any])
async def update_lead(
    lead_id: str,
    lead: LeadUpdate,
    tenant=Depends(get_tenant_connection)
):
    """Update an existing lead and return updated lead data"""
    try:
        conn, user = tenant
        user_email = user.get("email", "unknown")
        repos = get_user_repositories()

        # Map frontend field names to backend field names
        update_data = lead.dict(exclude_unset=True)
        logger.info(f"Received update for lead {lead_id}: {update_data}")

        # Extract employee assignment data (no longer stored on leads table)
        # assigned_to column was removed — assignment is via employee_lead_links only
        new_employee_id = None
        is_unassignment = False
        raw_assigned = update_data.pop('assignedTo', update_data.pop('assigned_to', None))
        if raw_assigned is not None:
            if raw_assigned != '' and raw_assigned:
                try:
                    new_employee_id = int(raw_assigned)
                    logger.info(f"Employee assignment update: employee_id={new_employee_id}")
                except (ValueError, TypeError):
                    pass
            else:
                is_unassignment = True
                logger.info("Employee unassignment requested - will deactivate all employee links")

        logger.info(f"Final update_data: {update_data}")

        updated_lead = await repos['lead_repo'].update_lead(conn, lead_id, update_data, user_email)
        if not updated_lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        # Update employee_lead_links when assignment changes
        if new_employee_id is not None:
            try:
                # Deactivate any existing assignments for this lead
                await conn.execute("""
                    UPDATE employee_lead_links
                    SET status = 'inactive'
                    WHERE lead_id = $1 AND status = 'active'
                """, lead_id)

                # Insert/update the employee_lead_link for the new assignment
                await conn.execute("""
                    INSERT INTO employee_lead_links (
                        employee_id, lead_id, assigned_at, notes, matched_by, status
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (employee_id, lead_id) DO UPDATE SET
                        status = 'active',
                        assigned_at = EXCLUDED.assigned_at,
                        matched_by = EXCLUDED.matched_by
                """,
                    new_employee_id,
                    lead_id,
                    datetime.now(timezone.utc),
                    "Assigned via lead update",
                    "manual_assignment",
                    "active"
                )
                logger.info(f"Updated employee_lead_link for employee {new_employee_id} -> lead {lead_id}")
            except Exception as e:
                logger.warning(f"Could not update employee_lead_link (non-critical): {e}")

        # Fix #4: Deactivate all employee links when unassigning
        elif is_unassignment:
            try:
                await conn.execute("""
                    UPDATE employee_lead_links
                    SET status = 'inactive'
                    WHERE lead_id = $1 AND status = 'active'
                """, lead_id)
                logger.info(f"Deactivated employee_lead_links for lead {lead_id}")
            except Exception as e:
                logger.warning(f"Could not deactivate employee_lead_links (non-critical): {e}")

        # Re-fetch lead after employee_lead_links update so response includes current assignment
        if new_employee_id is not None or is_unassignment:
            updated_lead = await repos['lead_repo'].get_lead_with_employee_info(conn, lead_id) or updated_lead

        logger.info(f"Lead {lead_id} updated successfully")
        return updated_lead
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating lead: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Lead Employee Assignment Endpoints (employee_lead_links)
# ============================================================================

class AddLeadEmployeeRequest(BaseModel):
    employee_id: int


@router.get("/lead/{lead_id}/employees")
async def get_lead_employees(
    lead_id: str,
    tenant=Depends(get_tenant_connection)
):
    """Get all employees assigned to a specific lead via employee_lead_links."""
    try:
        conn, user = tenant

        query = """
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

        employees = await conn.fetch(query, lead_id)

        # Convert to list of dicts with camelCase for frontend
        result = []
        for emp in employees:
            result.append({
                "employeeId": emp['employee_id'],
                "employeeName": emp['name'],
                "email": emp['email'],
                "role": emp['role'],
                "department": emp['department'],
                "assignedAt": emp['assigned_at'].isoformat() if emp['assigned_at'] else None,
                "notes": emp['notes'],
                "matchedBy": emp['matched_by'],
                "status": emp['status']
            })

        return result
    except Exception as e:
        logger.error(f"Error getting lead employees: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lead/{lead_id}/employees")
async def add_lead_employee(
    lead_id: str,
    request: AddLeadEmployeeRequest,
    tenant=Depends(get_tenant_connection)
):
    """Assign an employee to a lead via employee_lead_links."""
    try:
        conn, user = tenant

        async with conn.transaction():
            # Verify lead exists
            lead_row = await conn.fetchrow("SELECT lead_id FROM leads WHERE lead_id = $1", lead_id)
            if not lead_row:
                raise HTTPException(status_code=404, detail="Lead not found")

            # Verify employee exists and get their info
            employee = await conn.fetchrow(
                "SELECT employee_id, name, email, role, department FROM employee_info WHERE employee_id = $1",
                request.employee_id
            )
            if not employee:
                raise HTTPException(status_code=404, detail="Employee not found")

            # Insert with ON CONFLICT DO UPDATE to reactivate if inactive
            await conn.execute("""
                INSERT INTO employee_lead_links (
                    employee_id, lead_id, assigned_at, notes, matched_by, status
                ) VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (employee_id, lead_id) DO UPDATE SET
                    status = 'active',
                    assigned_at = EXCLUDED.assigned_at,
                    notes = EXCLUDED.notes,
                    matched_by = EXCLUDED.matched_by
            """,
                request.employee_id,
                lead_id,
                datetime.now(timezone.utc),
                "Assigned via Lead dashboard",
                "manual_assignment",
                "active"
            )

        logger.info(f"Assigned employee {request.employee_id} to lead {lead_id}")

        return {
            "employeeId": employee['employee_id'],
            "employeeName": employee['name'],
            "email": employee['email'],
            "role": employee['role'],
            "department": employee['department']
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding employee to lead: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/lead/{lead_id}/employees/{employee_id}")
async def remove_lead_employee(
    lead_id: str,
    employee_id: int,
    tenant=Depends(get_tenant_connection)
):
    """Remove an employee from a lead. Cannot remove the last employee. Sets status to 'inactive' rather than deleting."""
    try:
        conn, user = tenant

        async with conn.transaction():
            # Lock all active links for this lead to prevent concurrent removals
            # from racing past the count check (TOCTOU prevention)
            rows = await conn.fetch(
                "SELECT employee_id FROM employee_lead_links WHERE lead_id = $1 AND status = 'active' FOR UPDATE",
                lead_id
            )

            if len(rows) <= 1:
                raise HTTPException(status_code=400, detail="Cannot remove the last assigned employee. Lead must have at least one employee.")

            # Update status to inactive (soft delete)
            result = await conn.execute("""
                UPDATE employee_lead_links
                SET status = 'inactive'
                WHERE employee_id = $1 AND lead_id = $2
            """, employee_id, lead_id)

            # Check if any row was updated
            affected = int(result.split()[-1]) if result else 0
            if affected == 0:
                raise HTTPException(status_code=404, detail="Employee-lead assignment not found")

        logger.info(f"Removed employee {employee_id} from lead {lead_id}")

        return {"success": True, "message": "Employee removed from lead successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing employee from lead: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export")
async def export_leads_csv(
    search: Optional[str] = Query(None, description="Search term to filter leads"),
    search_columns: Optional[str] = Query(None, description="Comma-separated list of columns to search in"),
    status: Optional[str] = Query(None, description="Filter by lead status"),
    column_filters: Optional[str] = Query(None, description="JSON string of column filters"),
    sort_by: Optional[str] = Query("company", description="Field to sort by"),
    sort_order: Optional[str] = Query("asc", description="Sort order: asc or desc"),
    include_synced: bool = Query(True, description="Include leads that have been synced to CRM"),
    tenant=Depends(get_tenant_connection)
):
    """
    Export filtered leads to CSV format.

    Applies the same filters as the frontend and returns a CSV file with all lead information,
    including contact name and contact email.
    """
    try:
        from fastapi.responses import Response
        import csv
        from io import StringIO
        from config.constants import LeadStatus

        conn, _user = tenant

        # Build optimized SQL query with JOIN for performance
        where_clauses = []
        query_params = []
        param_idx = 0

        # Exclude synced leads by default
        if not include_synced:
            param_idx += 1
            where_clauses.append(f"l.status != ${param_idx}")
            query_params.append(LeadStatus.SYNCED_TO_CRM.value)

        # Handle search filter
        if search and search_columns:
            search_cols = [col.strip() for col in search_columns.split(',')]
            if 'company' in search_cols:
                param_idx += 1
                where_clauses.append(f"l.company ILIKE ${param_idx}")
                query_params.append(f"%{search}%")

        # Handle status filter
        if status:
            param_idx += 1
            where_clauses.append(f"l.status = ${param_idx}")
            query_params.append(status)

        # Handle structured column filters
        if column_filters:
            try:
                parsed_filters = json.loads(column_filters)
                for column_id, filter_config in parsed_filters.items():
                    condition = filter_config.get('condition')
                    value = filter_config.get('value')

                    if not condition or value is None:
                        continue

                    # Map filter conditions to SQL operators
                    if condition == 'contains':
                        param_idx += 1
                        where_clauses.append(f"l.{column_id} ILIKE ${param_idx}")
                        query_params.append(f"%{value}%")
                    elif condition == 'equals':
                        param_idx += 1
                        where_clauses.append(f"l.{column_id} = ${param_idx}")
                        query_params.append(value)
                    elif condition == 'starts_with':
                        param_idx += 1
                        where_clauses.append(f"l.{column_id} ILIKE ${param_idx}")
                        query_params.append(f"{value}%")
                    elif condition == 'ends_with':
                        param_idx += 1
                        where_clauses.append(f"l.{column_id} ILIKE ${param_idx}")
                        query_params.append(f"%{value}")
                    elif condition == 'not_contains':
                        param_idx += 1
                        where_clauses.append(f"(l.{column_id} NOT ILIKE ${param_idx} OR l.{column_id} IS NULL)")
                        query_params.append(f"%{value}%")
                    elif condition == 'not_equals':
                        param_idx += 1
                        where_clauses.append(f"(l.{column_id} != ${param_idx} OR l.{column_id} IS NULL)")
                        query_params.append(value)
                    elif condition == 'is_empty':
                        where_clauses.append(f"(l.{column_id} IS NULL OR l.{column_id} = '')")
                    elif condition == 'not_empty':
                        where_clauses.append(f"(l.{column_id} IS NOT NULL AND l.{column_id} != '')")
            except json.JSONDecodeError:
                logger.warning(f"Invalid column_filters JSON: {column_filters}")

        # Build WHERE clause
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Build ORDER BY clause
        order_direction = "DESC" if sort_order.lower() == 'desc' else "ASC"
        order_column = sort_by if sort_by in ['company', 'location', 'industry', 'website', 'status', 'created_at'] else 'company'

        # Optimized query with LEFT JOIN to get personnel data efficiently
        # email/phone come from personnel records only (removed from leads table)
        query = f"""
            SELECT
                l.company,
                l.location,
                l.industry,
                p.full_name as contact_name,
                p.email as contact_email,
                p.phone as phone,
                l.website,
                l.status,
                l.source,
                l.created_at
            FROM leads l
            LEFT JOIN personnel p ON l.lead_id = p.lead_id
            WHERE {where_sql}
            ORDER BY l.{order_column} {order_direction}
        """

        # Execute query directly
        all_rows = await conn.fetch(query, *query_params)

        # Create CSV in memory
        output = StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            'Company',
            'Location',
            'Industry',
            'Contact Name',
            'Contact Email',
            'Phone',
            'Website',
            'Status',
            'Source',
            'Created Date'
        ])

        # Write data rows - already joined with personnel
        for row in all_rows:
            # Format created_at
            created_at = row.get('created_at', '') or ''
            if created_at:
                if hasattr(created_at, 'strftime'):
                    created_at = created_at.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    created_at = str(created_at)

            writer.writerow([
                row.get('company', '') or '',
                row.get('location', '') or '',
                row.get('industry', '') or '',
                row.get('contact_name', '') or '',
                row.get('contact_email', '') or '',
                row.get('phone', '') or '',
                row.get('website', '') or '',
                row.get('status', '') or 'new',
                row.get('source', '') or '',
                created_at
            ])

        csv_content = output.getvalue()
        output.close()

        # Return CSV as plain text response
        return Response(
            content=csv_content,
            media_type='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename="leads_export_{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}.csv"'
            }
        )

    except Exception as e:
        logger.error(f"Error exporting leads to CSV: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export leads: {str(e)}"
        )

@router.delete("/lead/{lead_id}", response_model=Dict[str, Any])
async def delete_lead(
    lead_id: str,
    tenant=Depends(get_tenant_connection)
):
    """Delete a lead"""
    try:
        conn, user = tenant
        user_email = user.get("email", "unknown")
        repos = get_user_repositories()

        success = await repos['lead_repo'].delete_lead(conn, lead_id, user_email)
        if not success:
            raise HTTPException(status_code=404, detail="Lead not found")

        return {"message": "Lead deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting lead: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/enrichment-history")
async def get_user_enrichment_history(
    limit: int = 20,
    offset: int = 0,
    tenant=Depends(get_tenant_connection)
):
    """
    Get enrichment history for the current user with pagination.

    Args:
        limit: Number of records to return (default: 20)
        offset: Number of records to skip (default: 0)

    Returns paginated enriched companies for the logged-in employee.
    Uses Redis caching with 60-second TTL for performance.
    """
    try:
        conn, user = tenant
        user_email = user.get("email")

        if not user_email:
            raise HTTPException(status_code=400, detail="Email not found in token")

        employee_id = await get_employee_id_by_email(conn, user_email)

        if not employee_id:
            raise HTTPException(status_code=404, detail="Employee not found for this email")

        # Try Redis cache first
        cache = get_cache()
        cache_key = f"enrichment_history:{employee_id}:{limit}:{offset}"

        if cache.is_available:
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.info(f"Redis CACHE HIT: {cache_key}")
                return cached_result

        # Cache miss - fetch from database
        history = await get_enrichment_history(conn, employee_id, limit, offset)
        total_count = await get_enrichment_history_count(conn, employee_id)

        result = {
            "status": "success",
            "count": len(history),
            "total": total_count,
            "offset": offset,
            "limit": limit,
            "has_more": offset + len(history) < total_count,
            "history": history
        }

        # Cache the result with 60-second TTL
        if cache.is_available:
            cache.set(cache_key, result, ttl=60)
            logger.info(f"Redis CACHE SET: {cache_key} (TTL: 60s)")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch enrichment history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _generate_and_cache_insight(
    db_name: str, lead_id: str,
    import_ctx: Optional[Dict], supplier_ctx: Optional[Dict],
    bol_ctx: Dict,
):
    """Background task: generate full AI insights for both locales and persist.

    Generates aiActionBrief for en + zh-CN in one batch. Also backfills
    condensed insights if the eager pipeline task missed them.
    Runs outside the request cycle so the GET response is never delayed.
    """
    try:
        from importyeti.domain.insight import generate_ai_insight, generate_condensed_insight
        from service_core.db import get_pool_manager

        # Generate full insights for both locales (+ backfill condensed if missing)
        full_zh, full_en, condensed_zh, condensed_en = await asyncio.gather(
            generate_ai_insight(import_ctx, supplier_ctx, bol_ctx, locale="zh-CN"),
            generate_ai_insight(import_ctx, supplier_ctx, bol_ctx, locale="en"),
            generate_condensed_insight(import_ctx, supplier_ctx, bol_ctx, locale="zh-CN"),
            generate_condensed_insight(import_ctx, supplier_ctx, bol_ctx, locale="en"),
        )
        if not full_zh and not full_en and not condensed_zh and not condensed_en:
            return

        pm = get_pool_manager()
        async with pm.acquire(db_name) as conn:
            # Re-read bol_detail_context to avoid clobbering concurrent writes
            row = await conn.fetchrow(
                "SELECT bol_detail_context FROM leads WHERE lead_id = $1", lead_id,
            )
            if not row:
                return
            current = row["bol_detail_context"]
            if isinstance(current, str):
                current = json.loads(current)
            if not isinstance(current, dict):
                return

            changed = False
            # Full insights
            if full_zh and not current.get("aiActionBrief_zh-CN"):
                current["aiActionBrief_zh-CN"] = full_zh
                current["aiActionBrief"] = full_zh
                changed = True
            if full_en and not current.get("aiActionBrief_en"):
                current["aiActionBrief_en"] = full_en
                if not current.get("aiActionBrief"):
                    current["aiActionBrief"] = full_en
                changed = True
            # Condensed backfill (normally set by eager pipeline, but cover edge cases)
            if condensed_zh and not current.get("aiInsightCondensed_zh-CN"):
                current["aiInsightCondensed_zh-CN"] = condensed_zh
                current["aiInsightCondensed"] = condensed_zh
                changed = True
            if condensed_en and not current.get("aiInsightCondensed_en"):
                current["aiInsightCondensed_en"] = condensed_en
                if not current.get("aiInsightCondensed"):
                    current["aiInsightCondensed"] = condensed_en
                changed = True

            if changed:
                # Pass dict; the pool's JSONB codec (encoder=json.dumps) handles
                # serialization. Passing json.dumps(current) here would double-encode
                # into a JSONB string.
                await conn.execute(
                    "UPDATE leads SET bol_detail_context = $1::jsonb WHERE lead_id = $2",
                    current, lead_id,
                )
    except Exception as e:
        logger.warning(f"Background AI insight generation failed for lead {lead_id}: {e}")


@router.get("/lead/{lead_id}", response_model=LeadWithPersonnelResponse)
async def get_lead_with_personnel(
    lead_id: str,
    tenant=Depends(get_tenant_connection),
    x_user_locale: str = Header(default="en", alias="X-User-Locale"),
):
    """Get a lead with associated personnel and employee assignment info"""
    try:
        conn, user = tenant
        repos = get_user_repositories()

        # Use get_lead_with_employee_info for assignment data, then merge personnel
        lead_data = await repos['lead_repo'].get_lead_with_employee_info(conn, lead_id)
        if not lead_data:
            raise HTTPException(status_code=404, detail="Lead not found")

        # Also fetch personnel data (get_lead_with_employee_info doesn't include it)
        personnel_data = await repos['lead_repo'].get_lead_with_personnel(conn, lead_id)
        if personnel_data and 'personnel' in personnel_data:
            lead_data['personnel'] = personnel_data['personnel']

        # Lazy AI insight generation: generate in background, serve cached if available
        bol_ctx = lead_data.get("bol_detail_context")
        if isinstance(bol_ctx, str):
            try:
                bol_ctx = json.loads(bol_ctx)
            except (json.JSONDecodeError, TypeError):
                bol_ctx = None
        if not isinstance(bol_ctx, dict):
            bol_ctx = None

        # Normalize locale to supported set — X-User-Locale is set by the frontend proxy
        raw_locale = x_user_locale.strip().lower()
        locale = "zh-CN" if raw_locale.startswith("zh") else "en"
        # Cache insights per locale: aiActionBrief_en, aiActionBrief_zh-CN
        full_locale_key = f"aiActionBrief_{locale}"
        condensed_locale_key = f"aiInsightCondensed_{locale}"
        has_cached_full = bol_ctx and bol_ctx.get(full_locale_key)
        has_cached_condensed = bol_ctx and bol_ctx.get(condensed_locale_key)
        needs_generation = (
            bol_ctx
            and bol_ctx.get("scoringSignals")
            and (not has_cached_full or not has_cached_condensed)
        )

        if needs_generation:
            # Fire background task — generates full insights for both locales,
            # backfills condensed if the eager pipeline task missed them
            import copy
            bol_snapshot = copy.deepcopy(bol_ctx)

            import_ctx = lead_data.get("import_context")
            supplier_ctx = lead_data.get("supplier_context")
            if isinstance(import_ctx, str):
                try:
                    import_ctx = json.loads(import_ctx)
                except (json.JSONDecodeError, TypeError):
                    import_ctx = None
            if not isinstance(import_ctx, dict):
                import_ctx = None
            if isinstance(supplier_ctx, str):
                try:
                    supplier_ctx = json.loads(supplier_ctx)
                except (json.JSONDecodeError, TypeError):
                    supplier_ctx = None
            if not isinstance(supplier_ctx, dict):
                supplier_ctx = None

            asyncio.create_task(_generate_and_cache_insight(
                db_name=user.get("db_name", "postgres"),
                lead_id=lead_id,
                import_ctx=import_ctx,
                supplier_ctx=supplier_ctx,
                bol_ctx=bol_snapshot,
            ))

        # Serve cached insights for this locale
        if bol_ctx:
            if has_cached_full:
                bol_ctx["aiActionBrief"] = bol_ctx[full_locale_key]
            if has_cached_condensed:
                bol_ctx["aiInsightCondensed"] = bol_ctx[condensed_locale_key]
            lead_data["bol_detail_context"] = bol_ctx

        return LeadWithPersonnelResponse(**lead_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting lead with personnel: {e}")
        raise HTTPException(status_code=500, detail=str(e))

