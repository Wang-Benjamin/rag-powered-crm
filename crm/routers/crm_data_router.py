import os
import sys
import asyncio
import time
import asyncpg
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, timezone
import logging
import json
from pydantic import BaseModel

from service_core.db import get_tenant_connection

# Avoid per-module stdio re-wrapping; handled centrally in app startup

# Import service functions
from services.cache_service import clear_cache
from services.interaction_service import (
    get_customer_interactions_all,
    get_recent_customer_interactions,
    get_interaction_summary_options,
    get_comprehensive_customer_data
)
from services.email_sync_service import (
    get_email_sync_state,
    update_email_sync_state,
    get_all_customer_emails,
    get_all_employee_emails,
    get_customer_by_email,
    create_email_interaction,
    batch_create_email_interactions,
    get_employee_id_by_email_optional
)
from email_service.data.fetchers import fetch_customer_interactions_enriched

# Import new service modules
from services import customer_service, deal_service

# Import contact helpers
from utils.contact_helpers import (
    generate_contact_id,
    validate_contact,
    add_timestamps_to_contact,
)

# Import contact repository for personnel queries
from data.repositories.contact_repository import ContactRepository

# Import models
from models.crm_models import (
    Customer,
    PersonnelResponse,
    CreateCustomerRequest,
    UpdateCustomerRequest,
    DashboardStats,
    InteractionSummary,
    paginated_response
)

_contact_repo = ContactRepository()

logger = logging.getLogger(__name__)
router = APIRouter()

# Helper function for JSON parsing
def safe_json_loads(json_str, default=None):
    """Safely parse JSON string"""
    if json_str is None:
        return default or {}
    try:
        if isinstance(json_str, str):
            return json.loads(json_str)
        return json_str
    except (json.JSONDecodeError, TypeError):
        return default or {}


def _personnel_rows_to_response(rows: list) -> List[PersonnelResponse]:
    """Convert personnel DB rows to PersonnelResponse list."""
    result = []
    for r in rows:
        result.append(PersonnelResponse(
            personnelId=str(r['personnel_id']),
            firstName=r.get('first_name') or "",
            lastName=r.get('last_name') or "",
            fullName=r.get('full_name') or "",
            companyName=r.get('company_name') or "",
            email=r.get('email') or "",
            phone=r.get('phone') or "",
            position=r.get('position') or "",
            department=r.get('department') or "",
            seniorityLevel=r.get('seniority_level') or "",
            linkedinUrl=r.get('linkedin_url') or "",
            isPrimary=r.get('is_primary') or False,
            source=r.get('source') or "",
        ))
    return result


def _parse_signal(val) -> Optional[dict]:
    """Unwrap signal JSONB — handles both dicts and legacy double-encoded strings."""
    if val is None:
        return None
    while isinstance(val, str):
        val = json.loads(val)
    return val if isinstance(val, dict) else None


# Signal merge: real-time SQL signals + persisted LLM signals
_SIGNAL_PRIORITY = {"red": 1, "purple": 2, "green": 3, "none": 99}


def _merge_signals(llm_signal: Optional[dict], sql_signal: Optional[dict]) -> Optional[dict]:
    """Merge persisted LLM signal with real-time SQL signal. Higher urgency wins."""
    # Normalize: LLM signal with level=None is treated as absent
    if llm_signal and llm_signal.get("level") is None:
        llm_signal = None

    # LLM "Not interested" always wins (semantic judgment SQL can't make)
    if llm_signal and llm_signal.get("level") == "none":
        return {"level": llm_signal["level"], "label": llm_signal.get("label", "Not interested")}

    # If only one source has a signal, use it
    if sql_signal and not llm_signal:
        return {"level": sql_signal["level"], "label": sql_signal["label"]}
    if llm_signal and not sql_signal:
        return {"level": llm_signal["level"], "label": llm_signal.get("label", "")}
    if not sql_signal and not llm_signal:
        return None

    # Both exist: lower priority number wins (higher urgency)
    sql_pri = _SIGNAL_PRIORITY.get(sql_signal.get("level"), 99)
    llm_pri = _SIGNAL_PRIORITY.get(llm_signal.get("level"), 99)

    if sql_pri <= llm_pri:
        return {"level": sql_signal["level"], "label": sql_signal["label"]}
    return {"level": llm_signal["level"], "label": llm_signal.get("label", "")}


def _build_customer_response(
    customer_data: dict,
    personnel_list: List[PersonnelResponse],
    signal: Optional[dict],
    trade_intel: Optional[dict] = None,
) -> Customer:
    """Build a Customer response from a DB row + derived data.

    Centralises the ~30 shared fields so the list and detail endpoints
    stay in sync without duplicating the construction logic.
    """
    primary_p = next(
        (p for p in personnel_list if p.isPrimary),
        personnel_list[0] if personnel_list else None,
    )
    client_email = primary_p.email if primary_p else ""
    client_name = primary_p.fullName if primary_p else ""

    total_deal_value = float(customer_data.get('total_deal_value', 0) or 0)
    health_score = customer_data.get('health_score') or 75
    renewal_prob = min(95, max(20, int(health_score * 1.2)))

    last_activity_raw = customer_data.get('last_activity')
    last_activity = last_activity_raw.isoformat() if last_activity_raw else None

    return Customer(
        id=customer_data['client_id'],
        company=customer_data['name'] or "Unknown Company",
        phone=customer_data['phone'] or "",
        location=customer_data['location'] or "",
        website=customer_data.get('website') or "",
        status=customer_data['status'] or "active",
        clientType="customer",
        arr=total_deal_value,
        totalDealValue=total_deal_value,
        healthScore=float(health_score),
        productUsage={},
        recentActivities=[],
        lastInteraction="",
        totalInteractions=0,
        supportTickets=0,
        onboardingComplete=True,
        currentStage=customer_data.get('status') or "active",
        progress=0,
        renewalProbability=renewal_prob,
        lastContact="",
        productUsagePercentage=85,
        funnelStage="qualified" if customer_data['status'] == 'active' else "lead",
        nextFollowUp=(datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d"),
        recent_notes=customer_data['notes'] or "",
        recent_timeline="",
        assignedEmployeeId=customer_data.get('assigned_employee_id'),
        assignedEmployeeName=customer_data.get('assigned_employee_name'),
        personnel=personnel_list,
        clientEmail=client_email,
        clientName=client_name,
        volume=None,
        signal=signal,
        stage=customer_data.get('stage') or "new",
        lastActivity=last_activity,
        tradeIntel=trade_intel,
    )


async def _fetch_realtime_signals(conn, client_ids: list) -> dict:
    """Fetch SQL-based signals with 100ms timeout. Falls back to empty on timeout."""
    if not client_ids:
        return {}
    start = time.perf_counter()
    try:
        result = await asyncio.wait_for(
            customer_service.compute_signals_batch(conn, client_ids),
            timeout=0.1,
        )
        elapsed = time.perf_counter() - start
        logger.info(f"compute_signals_batch: {elapsed:.4f}s for {len(client_ids)} customers")
        return result
    except asyncio.TimeoutError:
        elapsed = time.perf_counter() - start
        logger.warning(f"compute_signals_batch timed out after {elapsed:.4f}s, falling back to LLM-only signals")
        return {cid: None for cid in client_ids}


@router.get("/dashboard/stats")
async def get_dashboard_stats_endpoint(tenant: Tuple[asyncpg.Connection, dict] = Depends(get_tenant_connection)) -> DashboardStats:
    """Get CRM dashboard statistics from real database data"""
    conn, user = tenant
    user_email = user.get('email', '')
    stats = await customer_service.get_dashboard_stats(conn)

    # Calculate churn rate (mock calculation based on at-risk customers)
    churn_rate = (stats.get('at_risk_customers', 0) / max(stats.get('total_customers', 1), 1)) * 100

    return DashboardStats(
        totalCustomers=stats.get('total_customers', 0),
        activeCustomers=stats.get('active_customers', 0),
        atRiskCustomers=stats.get('at_risk_customers', 0),
        totalDealValue=float(stats.get('total_deal_value', 0)),
        averageHealthScore=float(stats.get('avg_health_score', 75)),
        newCustomersThisMonth=stats.get('new_customers_month', 0),
        churnRate=round(churn_rate, 1),
        expansionOpportunities=stats.get('expansion_opportunities', 0),
        supportTicketsOpen=0
    )

@router.get("/customers")
async def get_all_customers_endpoint(
    search: Optional[str] = None,
    status: Optional[str] = None,
    page: Optional[int] = None,
    per_page: Optional[int] = None,
    tenant: Tuple[asyncpg.Connection, dict] = Depends(get_tenant_connection)
):
    """Get all customers with optional filtering, search, and pagination"""
    conn, user = tenant
    user_email = user.get('email', '')

    total = None
    if page is not None and per_page is not None:
        customers_data, total = await customer_service.get_all_customers(
            conn, user_email, search, status, page=page, per_page=per_page
        )
    else:
        customers_data = await customer_service.get_all_customers(conn, user_email, search, status)

    customers = []

    # Batch-fetch personnel and real-time signals for all returned customer IDs
    client_ids = [cd['client_id'] for cd in customers_data]
    realtime_signals = await _fetch_realtime_signals(conn, client_ids)
    personnel_by_client: Dict[int, list] = {cid: [] for cid in client_ids}
    if client_ids:
        p_rows = await conn.fetch(
            """
            SELECT personnel_id, first_name, last_name, full_name,
                   company_name, source, position, department,
                   seniority_level, email, phone, linkedin_url,
                   client_id, is_primary
            FROM personnel
            WHERE client_id = ANY($1::int[])
            ORDER BY is_primary DESC NULLS LAST, created_at ASC
            """,
            client_ids,
        )
        for pr in p_rows:
            cid = pr['client_id']
            if cid in personnel_by_client:
                personnel_by_client[cid].append(dict(pr))

    for customer_data in customers_data:
        personnel_rows = personnel_by_client.get(customer_data['client_id'], [])
        personnel_list = _personnel_rows_to_response(personnel_rows)

        signal = _merge_signals(
            _parse_signal(customer_data.get('signal')),
            realtime_signals.get(customer_data['client_id']),
        )
        customer = _build_customer_response(customer_data, personnel_list, signal)
        customers.append(customer)

    if total is not None:
        return paginated_response(customers, total, page, per_page, key="customers")

    return customers

@router.get("/customers/{customer_id}")
async def get_customer_by_id_endpoint(customer_id: int, tenant: Tuple[asyncpg.Connection, dict] = Depends(get_tenant_connection)) -> Customer:
    """Get specific customer by ID with complete details"""
    conn, user = tenant
    user_email = user.get('email', '')
    customer_data = await customer_service.get_customer_by_id(conn, customer_id)

    # Fetch personnel from personnel table
    personnel_rows = await _contact_repo.get_contacts_for_customer(conn, customer_id)
    personnel_list = _personnel_rows_to_response(personnel_rows)

    # Merge stored LLM signal with real-time SQL signal
    llm_signal = _parse_signal(customer_data.get('signal'))
    rt_signals = await _fetch_realtime_signals(conn, [customer_id])
    signal = _merge_signals(llm_signal, rt_signals.get(customer_id))

    # Build trade intel from BoL data (bridged during conversion) + deal aggregation
    trade_intel_raw = safe_json_loads(customer_data.get('trade_intel'), {})
    deal_agg = await conn.fetchrow("""
        SELECT
            array_agg(DISTINCT hs_code) FILTER (WHERE hs_code IS NOT NULL) as hs_codes,
            array_agg(DISTINCT product_name) FILTER (WHERE product_name IS NOT NULL) as products,
            MIN(fob_price) as fob_min, MAX(fob_price) as fob_max,
            MIN(moq) as moq_min,
            COUNT(*) FILTER (WHERE room_status NOT IN ('closed-won','closed-lost')) as active_deals
        FROM deals WHERE client_id = $1
    """, customer_id)
    trade_intel = {**(trade_intel_raw or {})}
    if deal_agg:
        da = dict(deal_agg)
        trade_intel["dealProducts"] = da.get("products") or []
        trade_intel["dealHsCodes"] = da.get("hs_codes") or []
        trade_intel["fobMin"] = float(da["fob_min"]) if da.get("fob_min") is not None else None
        trade_intel["fobMax"] = float(da["fob_max"]) if da.get("fob_max") is not None else None
        trade_intel["moqMin"] = int(da["moq_min"]) if da.get("moq_min") is not None else None
        trade_intel["activeDeals"] = da.get("active_deals") or 0

    return _build_customer_response(
        customer_data,
        personnel_list,
        signal,
        trade_intel=trade_intel if any(v for v in trade_intel.values()) else None,
    )

@router.get("/customers/{customer_id}/interactions")
async def get_customer_interactions(customer_id: int, employee_id: Optional[int] = None, tenant: Tuple[asyncpg.Connection, dict] = Depends(get_tenant_connection)) -> List[InteractionSummary]:
    """
    Get interactions for a specific customer.

    Scoping:
    - Admin (employee_info.access = 'admin'): sees all interactions by default; can pass
      employee_id=<n> to filter to one employee, or employee_id=0 for explicit "all".
    - Non-admin: always scoped to their own interactions; employee_id param ignored.

    Fetches emails from crm_emails table and other interactions (calls, meetings) from interaction_details table.
    """
    try:
        conn, user = tenant
        user_email = user.get('email', '')

        # Look up current user's employee_id + access tier
        current_employee_id = None
        access_role = None
        if user_email:
            try:
                row = await conn.fetchrow(
                    "SELECT employee_id, access FROM employee_info WHERE email = $1 LIMIT 1",
                    user_email,
                )
                if row:
                    current_employee_id = row["employee_id"]
                    access_role = row["access"]
                else:
                    logger.warning(f"Employee not found for email {user_email}, using all interactions")
            except Exception:
                logger.warning(f"Employee lookup failed for email {user_email}, using all interactions")

        is_admin = access_role == 'admin'

        if is_admin:
            if employee_id is None or employee_id == 0:
                resolved_employee_id = None
            else:
                resolved_employee_id = employee_id
        else:
            # Non-admin: ignore param, hard-scope to self.
            # If employee lookup failed, fall back to None (no filter) to avoid blank UI.
            resolved_employee_id = current_employee_id

        # Fetch enriched interactions using email_service data fetcher
        all_interactions_data = await fetch_customer_interactions_enriched(
            customer_id=customer_id,
            employee_id=resolved_employee_id,
            conn=conn,
        )

        # Transform to InteractionSummary objects
        interactions = []
        for interaction_data in all_interactions_data:
            interaction = InteractionSummary(
                id=interaction_data['interaction_id'],
                customerId=interaction_data['customer_id'],
                type=interaction_data['type'],
                content=interaction_data['content'],
                employeeName=interaction_data['employee_name'] or "Unknown Employee",
                employeeRole=interaction_data['employee_role'] or "Unknown Role",
                employeeDepartment=interaction_data.get('employee_department'),
                createdAt=interaction_data['created_at'].isoformat() if interaction_data['created_at'] else "",
                updatedAt=interaction_data['updated_at'].isoformat() if interaction_data.get('updated_at') else None,
                duration=interaction_data.get('duration'),
                fromEmail=interaction_data.get('from_email'),
                toEmail=interaction_data.get('to_email'),
                outcome=interaction_data.get('outcome'),
                subject=interaction_data.get('subject'),
                gmailMessageId=interaction_data.get('gmail_message_id'),
                email_id=interaction_data.get('email_id'),  # Add email_id for notification links
                theme=interaction_data.get('theme'),
                source=interaction_data.get('source'),
                sourceName=interaction_data.get('source_name'),
                sourceType=interaction_data.get('source_type'),
                direction=interaction_data.get('direction'),
                threadId=interaction_data.get('thread_id'),
            )
            interactions.append(interaction)

        return interactions
    except Exception as e:
        logger.error(f"Error getting interactions for customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/customers/{customer_id}/employees")
async def get_customer_employees(customer_id: int, tenant: Tuple[asyncpg.Connection, dict] = Depends(get_tenant_connection)):
    """Get all employees linked to a specific customer via employee_client_links."""
    try:
        conn, user = tenant

        rows = await conn.fetch("""
            SELECT
                e.employee_id,
                e.name,
                e.email,
                e.role,
                e.department
            FROM employee_client_links ecl
            JOIN employee_info e ON ecl.employee_id = e.employee_id
            WHERE ecl.client_id = $1 AND ecl.status = 'active'
            ORDER BY e.name
        """, customer_id)

        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error getting customer employees: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

class AddCustomerEmployeeRequest(BaseModel):
    employee_id: int

@router.post("/customers/{customer_id}/employees")
async def add_customer_employee(customer_id: int, request: AddCustomerEmployeeRequest, tenant: Tuple[asyncpg.Connection, dict] = Depends(get_tenant_connection)):
    """Add an employee to a customer via employee_client_links."""
    try:
        conn, user = tenant

        # Verify customer exists
        row = await conn.fetchrow("SELECT client_id FROM clients WHERE client_id = $1", customer_id)
        if not row:
            raise HTTPException(status_code=404, detail={"code": "CUSTOMER_NOT_FOUND", "message": "Customer not found"})

        # Verify employee exists
        employee = await conn.fetchrow(
            "SELECT employee_id, name, email, role, department FROM employee_info WHERE employee_id = $1",
            request.employee_id
        )
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")

        # Insert with ON CONFLICT DO UPDATE to reactivate if previously soft-deleted
        await conn.execute("""
            INSERT INTO employee_client_links (
                employee_id, client_id, assigned_at, notes, matched_by, status, client_type
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (employee_id, client_id) DO UPDATE SET
                status = 'active',
                assigned_at = EXCLUDED.assigned_at,
                notes = EXCLUDED.notes,
                matched_by = EXCLUDED.matched_by
        """,
            request.employee_id,
            customer_id,
            datetime.now(timezone.utc),
            "Assigned via CRM dashboard",
            "manual_assignment",
            "active",
            "customer"
        )

        return dict(employee)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding employee to customer: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/customers/{customer_id}/employees/{employee_id}")
async def remove_customer_employee(customer_id: int, employee_id: int, tenant: Tuple[asyncpg.Connection, dict] = Depends(get_tenant_connection)):
    """Remove an employee from a customer. Cannot remove the last employee."""
    try:
        conn, user = tenant

        async with conn.transaction():
            # Lock all active links for this customer to prevent concurrent removals
            # from racing past the count check (TOCTOU prevention)
            rows = await conn.fetch(
                "SELECT employee_id FROM employee_client_links WHERE client_id = $1 AND status = 'active' FOR UPDATE",
                customer_id
            )

            if len(rows) <= 1:
                raise HTTPException(status_code=400, detail="Cannot remove the last assigned employee. Customer must have at least one employee.")

            # Soft delete: set status to 'inactive' instead of hard delete
            await conn.execute(
                "UPDATE employee_client_links SET status = 'inactive' WHERE employee_id = $1 AND client_id = $2",
                employee_id, customer_id
            )

        return {"success": True, "message": "Employee removed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing employee from customer: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/employees")
async def get_all_employees(tenant: Tuple[asyncpg.Connection, dict] = Depends(get_tenant_connection)):
    """Get all employees"""
    try:
        conn, user = tenant

        rows = await conn.fetch("""
            SELECT
                employee_id,
                name,
                role,
                department,
                email
            FROM employee_info
            ORDER BY name
        """)

        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error getting employees: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/customers")
async def create_customer(customer_data: CreateCustomerRequest, tenant: Tuple[asyncpg.Connection, dict] = Depends(get_tenant_connection)) -> Customer:
    """Create a new customer in the clients table."""
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        logger.info(f"CREATE customer request: user_email={user_email}, customer_name={customer_data.name}")

        async with conn.transaction():
            current_time = datetime.now(timezone.utc)

            # Insert into clients table - DB auto-generates client_id
            result = await conn.fetchrow("""
                INSERT INTO clients (
                    name, phone, location,
                    website, preferred_language, source, created_at, updated_at,
                    notes, health_score, stage, status
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12
                )
                RETURNING client_id
            """,
                customer_data.name,
                customer_data.phone,
                customer_data.location,
                customer_data.website,
                customer_data.preferred_language,
                customer_data.source,
                current_time,
                current_time,
                customer_data.notes,
                customer_data.health_score,
                'new',
                customer_data.status,
            )
            client_id = result['client_id']

            # Insert personnel records from contacts list
            if customer_data.contacts and len(customer_data.contacts) > 0:
                logger.info(f"Creating {len(customer_data.contacts)} personnel records")
                for i, contact in enumerate(customer_data.contacts):
                    contact_dict = contact.dict() if hasattr(contact, 'dict') else contact

                    # Validate contact
                    is_valid, error_msg = validate_contact(contact_dict)
                    if not is_valid:
                        raise HTTPException(status_code=400, detail=f"Invalid contact data: {error_msg}")

                    contact_dict['is_primary'] = (i == 0)
                    await _contact_repo.add_contact(conn, client_id, contact_dict)

            # AUTO-LINKING LOGIC: Link customer to creating employee
            assignment_status = "not_attempted"
            assigned_employee_id = None

            try:
                logger.info(f"Auto-linking triggered for customer {client_id} created by user: {user_email}")

                # Get employee_id for the authenticated user using the SAME connection/transaction
                try:
                    employee_result = await conn.fetchrow(
                        "SELECT employee_id FROM employee_info WHERE LOWER(email) = LOWER($1)",
                        user_email
                    )

                    if employee_result:
                        auto_assigned_id = employee_result['employee_id']
                        logger.info(f"Found employee_id {auto_assigned_id} for user {user_email} in same transaction")
                    else:
                        auto_assigned_id = None
                        logger.warning(f"No employee found for user {user_email} in employee_info table")
                except Exception as emp_error:
                    logger.error(f"Error querying employee_info: {emp_error}")
                    auto_assigned_id = None

                if auto_assigned_id is not None:
                    assigned_employee_id = auto_assigned_id

                    # Determine client_type based on customer status
                    client_type = 'lead' if customer_data.status.lower() in ['lead', 'prospect'] else 'customer'

                    logger.info(f"Client type determined: '{client_type}' based on status '{customer_data.status}'")

                    try:
                        # Check if assignment already exists
                        existing = await conn.fetchrow(
                            "SELECT * FROM employee_client_links WHERE employee_id = $1 AND client_id = $2",
                            assigned_employee_id, client_id
                        )

                        if existing:
                            assignment_status = "already_linked"
                            logger.info(f"Customer {client_id} already linked to employee {assigned_employee_id} - skipping")
                        else:
                            # Insert into employee_client_links table
                            logger.info(f"Attempting to insert into employee_client_links: employee_id={assigned_employee_id}, client_id={client_id}, client_type={client_type}")

                            await conn.execute("""
                                INSERT INTO employee_client_links (
                                    employee_id, client_id, assigned_at,
                                    notes, matched_by, status, client_type
                                ) VALUES (
                                    $1, $2, $3, $4, $5, $6, $7
                                )
                            """,
                                assigned_employee_id,
                                client_id,
                                current_time,
                                "Auto-assigned to creator",
                                "auto_assigned_to_creator",
                                "active",
                                client_type
                            )

                            assignment_status = "linked_successfully"
                            logger.info(f"Customer {client_id} auto-linked to employee {assigned_employee_id} as '{client_type}'")

                    except Exception as link_table_error:
                        if 'does not exist' in str(link_table_error).lower():
                            assignment_status = "table_not_found"
                            logger.warning(f"employee_client_links table not found - skipping auto-linking")
                        else:
                            raise
                else:
                    assignment_status = "user_not_employee"
                    logger.info(f"User {user_email} not found in employee_info - customer created without assignment")

            except Exception as link_error:
                # Log error but don't fail customer creation
                assignment_status = "linking_failed"
                logger.error(f"Error during auto-linking (customer creation will continue): {link_error}", exc_info=True)

        # Log final result
        logger.info(f"Customer {client_id} created successfully | Assignment: {assignment_status} | Employee: {assigned_employee_id}")

        # Clear cache since we added a new customer
        clear_cache("get_all_customers")
        clear_cache("get_dashboard_stats")

        # Small delay to ensure transaction is fully committed and visible to new connections
        import asyncio
        await asyncio.sleep(0.05)  # 50ms delay

        # Return the created customer by fetching it
        return await get_customer_by_id_endpoint(client_id, tenant)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating customer: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/customers/{customer_id}")
async def update_customer(customer_id: int, update_data: UpdateCustomerRequest, tenant: Tuple[asyncpg.Connection, dict] = Depends(get_tenant_connection)) -> Customer:
    """Update a customer in the clients table."""
    try:
        conn, user = tenant
        user_email = user.get('email', '')

        async with conn.transaction():
            # First check if customer exists
            row = await conn.fetchrow("SELECT client_id FROM clients WHERE client_id = $1", customer_id)
            if not row:
                raise HTTPException(status_code=404, detail={"code": "CUSTOMER_NOT_FOUND", "message": "Customer not found"})

            # Build one clients update. The info/detail fields now live on the same row.
            client_update_values = {}
            client_field_mapping = (
                ('company', 'name'),
                ('phone', 'phone'),
                ('location', 'location'),
                ('website', 'website'),
                ('preferred_language', 'preferred_language'),
                ('source', 'source'),
                ('notes', 'notes'),
                ('status', 'status'),
                ('healthScore', 'health_score'),
                ('currentStage', 'status'),
                ('stage', 'stage'),
            )

            for frontend_field, db_field in client_field_mapping:
                value = getattr(update_data, frontend_field, None)
                if value is not None:
                    # Backward-compatible aliases can target the same DB field; the
                    # later frontend field wins while still producing one SET clause.
                    client_update_values[db_field] = value
                    logger.info(f"Updating clients: {db_field} = {value}")

            if client_update_values:
                client_updates = []
                client_params = []
                for param_idx, (db_field, value) in enumerate(client_update_values.items(), start=1):
                    client_updates.append(f"{db_field} = ${param_idx}")
                    client_params.append(value)

                updated_at_param = len(client_params) + 1
                customer_id_param = updated_at_param + 1
                client_updates.append(f"updated_at = ${updated_at_param}")
                client_params.extend([datetime.now(timezone.utc), customer_id])

                client_query = f"""
                    UPDATE clients
                    SET {', '.join(client_updates)}
                    WHERE client_id = ${customer_id_param}
                """
                logger.info(f"Executing clients query: {client_query}")
                logger.info(f"With params: {client_params}")
                await conn.execute(client_query, *client_params)
                logger.info("clients updated successfully")
            else:
                logger.info("No client fields to update")

            # Handle employee assignment update (employee_client_links)
            if update_data.assignedEmployeeId is not None:
                new_employee_id = update_data.assignedEmployeeId
                logger.info(f"Updating employee assignment for customer {customer_id} to employee {new_employee_id}")

                try:
                    # Check if there's an existing active assignment for this client
                    existing_link = await conn.fetchrow("""
                        SELECT employee_id FROM employee_client_links
                        WHERE client_id = $1 AND status = 'active'
                        ORDER BY assigned_at DESC
                        LIMIT 1
                        FOR UPDATE
                    """, customer_id)

                    if existing_link:
                        old_employee_id = existing_link['employee_id']

                        # Soft delete the old link
                        await conn.execute(
                            "UPDATE employee_client_links SET status = 'inactive' WHERE employee_id = $1 AND client_id = $2",
                            old_employee_id, customer_id
                        )
                        logger.info(f"Soft-deleted old employee_client_link: employee {old_employee_id} -> client {customer_id}")

                    # Create new link with the new employee_id
                    await conn.execute("""
                        INSERT INTO employee_client_links (
                            employee_id, client_id, assigned_at,
                            notes, matched_by, status, client_type
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7
                        )
                        ON CONFLICT (employee_id, client_id)
                        DO UPDATE SET
                            assigned_at = EXCLUDED.assigned_at,
                            notes = EXCLUDED.notes,
                            matched_by = EXCLUDED.matched_by,
                            status = EXCLUDED.status
                    """,
                        new_employee_id,
                        customer_id,
                        datetime.now(timezone.utc),
                        "Assigned via CRM dashboard",
                        "manual_assignment",
                        "active",
                        "customer"
                    )

                    if existing_link:
                        logger.info(f"Updated employee_client_link: client {customer_id} reassigned from employee {existing_link['employee_id']} -> employee {new_employee_id}")
                    else:
                        logger.info(f"Created new employee_client_link: client {customer_id} -> employee {new_employee_id}")

                except Exception as link_error:
                    logger.error(f"Error updating employee_client_link: {link_error}")

        logger.info(f"Transaction committed for customer {customer_id}")

        # Clear relevant caches
        logger.info(f"Clearing caches for customer {customer_id}")
        clear_cache("get_all_customers")
        clear_cache("get_dashboard_stats")
        clear_cache(f"get_customer_by_id:{customer_id}")

        # Return the updated customer
        logger.info(f"Fetching updated customer {customer_id} to return")
        updated_customer = await get_customer_by_id_endpoint(customer_id, tenant)
        logger.info(f"Customer {customer_id} update completed successfully")
        return updated_customer

    except HTTPException:
        logger.error(f"HTTP exception during customer update: {customer_id}")
        raise
    except Exception as e:
        logger.error(f"Error updating customer {customer_id}: {e}")
        logger.error(f"Stack trace:", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update customer: {str(e)}")

@router.delete("/customers/{customer_id}")
async def delete_customer(customer_id: int, tenant: Tuple[asyncpg.Connection, dict] = Depends(get_tenant_connection)) -> Dict[str, Any]:
    """Delete a customer and all related data (cascade delete)"""
    try:
        conn, user = tenant
        user_email = user.get('email', '')
        logger.info(f"DELETE customer request: customer_id={customer_id}, user_email={user_email}")

        # First check if customer exists
        result = await conn.fetchrow("SELECT client_id FROM clients WHERE client_id = $1", customer_id)

        if not result:
            logger.warning(f"Customer {customer_id} not found in database for user {user_email}")
            raise HTTPException(status_code=404, detail={"code": "CUSTOMER_NOT_FOUND", "message": "Customer not found"})

        # Delete from clients (will cascade to other tables)
        status = await conn.execute("DELETE FROM clients WHERE client_id = $1", customer_id)

        # asyncpg execute returns a status string like "DELETE 1"
        deleted_count = int(status.split()[-1]) if status else 0

        # Clear cache since we deleted a customer
        clear_cache("get_all_customers")
        clear_cache("get_dashboard_stats")

        logger.info(f"Deleted customer {customer_id} successfully")

        return {
            "success": True,
            "message": f"Customer {customer_id} and all related data deleted successfully",
            "deleted_count": deleted_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting customer {customer_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
