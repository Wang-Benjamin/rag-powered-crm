from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from datetime import datetime, timezone
import logging

from service_core.db import get_tenant_connection

# Import service functions
from services.cache_service import clear_cache
from services.deal_room_service import create_deal_room
from models.crm_models import paginated_response

logger = logging.getLogger(__name__)
router = APIRouter()

# Pydantic models
class Deal(BaseModel):
    """Deal model for API responses"""
    deal_id: int
    deal_name: str
    description: Optional[str] = None
    value_usd: Optional[float] = None
    hs_code: Optional[str] = None
    fob_price: Optional[float] = None
    fob_currency: Optional[str] = 'USD'
    landed_price: Optional[float] = None
    quantity: Optional[int] = None
    moq: Optional[int] = None
    room_status: Optional[str] = "draft"
    employee_id: int
    client_id: int
    created_at: str
    updated_at: str
    completion_time: Optional[str] = None
    last_contact_date: Optional[str] = None
    expected_close_date: Optional[str] = None
    product_name: Optional[str] = None
    share_token: Optional[str] = None
    view_count: Optional[int] = 0
    quote_data: Optional[Dict[str, Any]] = None
    # Additional computed fields for frontend
    salesman_name: Optional[str] = None
    client_name: Optional[str] = None
    client_email: Optional[str] = None

class CreateDealRequest(BaseModel):
    """Model for creating new deals"""
    deal_name: str
    product_name: Optional[str] = None
    description: Optional[str] = None
    value_usd: Optional[float] = 0.0
    hs_code: Optional[str] = None
    fob_price: Optional[float] = None
    fob_currency: str = 'USD'
    landed_price: Optional[float] = None
    quantity: Optional[int] = None
    moq: Optional[int] = None
    room_status: str = "draft"
    employee_id: Optional[int] = None  # Made optional - can be assigned later
    client_id: int
    expected_close_date: Optional[str] = None  # YYYY-MM-DD format

class UpdateDealRequest(BaseModel):
    """Model for updating deal fields - all fields are optional"""
    deal_name: Optional[str] = None
    product_name: Optional[str] = None
    description: Optional[str] = None
    value_usd: Optional[float] = None
    hs_code: Optional[str] = None
    fob_price: Optional[float] = None
    fob_currency: Optional[str] = None
    landed_price: Optional[float] = None
    quantity: Optional[int] = None
    moq: Optional[int] = None
    room_status: Optional[str] = None
    employee_id: Optional[int] = None
    client_id: Optional[int] = None
    expected_close_date: Optional[str] = None  # YYYY-MM-DD format
    last_contact_date: Optional[str] = None


def _row_to_deal(row) -> Deal:
    """Convert a database row to a Deal model."""
    return Deal(
        deal_id=row['deal_id'],
        deal_name=row['deal_name'] or "Untitled Deal",
        description=row['description'] or "",
        value_usd=float(row['value_usd']) if row['value_usd'] else 0.0,
        hs_code=row.get('hs_code'),
        fob_price=float(row['fob_price']) if row.get('fob_price') else None,
        fob_currency=row.get('fob_currency') or 'USD',
        landed_price=float(row['landed_price']) if row.get('landed_price') else None,
        quantity=row.get('quantity'),
        moq=row.get('moq'),
        product_name=row.get('product_name'),
        share_token=row.get('share_token'),
        room_status=row['room_status'] or "draft",
        employee_id=row['employee_id'],
        client_id=row['client_id'],
        created_at=row['created_at'].isoformat() if row.get('created_at') else "",
        updated_at=row['updated_at'].isoformat() if row.get('updated_at') else "",
        completion_time=row['completion_time'].isoformat() if row.get('completion_time') else None,
        last_contact_date=row['last_contact_date'].strftime("%Y-%m-%d") if row.get('last_contact_date') else None,
        expected_close_date=row['expected_close_date'].strftime("%Y-%m-%d") if row.get('expected_close_date') else None,
        view_count=row.get('view_count') or 0,
        quote_data=row.get('quote_data') or {},
        salesman_name=row['salesman_name'] or "Unknown Salesman",
        client_name=row['client_name'] or "Unknown Client",
        client_email=row.get('client_email')
    )


# DEALS CRUD ENDPOINTS

@router.get("/deals")
async def get_all_deals(
    page: Optional[int] = None,
    per_page: Optional[int] = None,
    tenant: tuple = Depends(get_tenant_connection)
):
    """Get all deals with employee and client names (admin sees all, regular users see only assigned deals)"""
    conn, user = tenant
    try:
        user_email = user.get('email', '')

        # Check if user is admin or regular user
        emp_row = await conn.fetchrow(
            "SELECT access FROM employee_info WHERE email = $1 LIMIT 1", user_email
        )
        access_role = emp_row['access'] if emp_row else None

        # Build query based on access role
        if access_role == 'admin':
            logger.info(f"Admin user {user_email} requesting all deals")
            base_query = """
            SELECT
                d.deal_id, d.deal_name, d.product_name, d.description, d.value_usd,
                d.hs_code, d.fob_price, d.fob_currency, d.landed_price, d.quantity, d.moq, d.room_status,
                d.employee_id, d.client_id, d.created_at, d.updated_at,
                d.completion_time, d.last_contact_date, d.expected_close_date,
                d.share_token, d.view_count, d.quote_data,
                e.name as salesman_name, c.name as client_name,
                p_primary.email as client_email
            FROM deals d
            LEFT JOIN employee_info e ON d.employee_id = e.employee_id
            LEFT JOIN clients c ON d.client_id = c.client_id
            LEFT JOIN LATERAL (
                SELECT email FROM personnel WHERE client_id = d.client_id AND is_primary = true LIMIT 1
            ) p_primary ON true
            ORDER BY d.created_at DESC
            """
            base_params = []
        else:
            emp_id_row = await conn.fetchrow(
                "SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email
            )
            employee_id = emp_id_row['employee_id'] if emp_id_row else None

            if not employee_id:
                logger.warning(f"Employee not found for email: {user_email}")
                if page is not None and per_page is not None:
                    return paginated_response([], 0, page, per_page, key="deals")
                return []

            logger.info(f"Regular user {user_email} (employee_id={employee_id}) requesting assigned deals")
            base_query = """
            SELECT
                d.deal_id, d.deal_name, d.product_name, d.description, d.value_usd,
                d.hs_code, d.fob_price, d.fob_currency, d.landed_price, d.quantity, d.moq, d.room_status,
                d.employee_id, d.client_id, d.created_at, d.updated_at,
                d.completion_time, d.last_contact_date, d.expected_close_date,
                d.share_token, d.view_count, d.quote_data,
                e.name as salesman_name, c.name as client_name,
                p_primary.email as client_email
            FROM deals d
            LEFT JOIN employee_info e ON d.employee_id = e.employee_id
            LEFT JOIN clients c ON d.client_id = c.client_id
            LEFT JOIN LATERAL (
                SELECT email FROM personnel WHERE client_id = d.client_id AND is_primary = true LIMIT 1
            ) p_primary ON true
            WHERE d.employee_id = $1
            ORDER BY d.created_at DESC
            """
            base_params = [employee_id]

        if page is not None and per_page is not None:
            offset = (page - 1) * per_page
            n = len(base_params)
            paginated_query = f"""
                SELECT *, COUNT(*) OVER() AS _total_count
                FROM ({base_query}) _sub
                LIMIT ${n + 1} OFFSET ${n + 2}
            """
            rows = await conn.fetch(paginated_query, *base_params, per_page, offset)
        else:
            rows = await conn.fetch(base_query, *base_params)

        total = None
        if page is not None and per_page is not None and rows:
            total = rows[0]['_total_count']

        deals = []
        for row in rows:
            row_dict = dict(row)
            row_dict.pop('_total_count', None)
            deals.append(_row_to_deal(row_dict))

        if total is not None:
            return paginated_response(deals, total, page, per_page, key="deals")

        return deals
    except Exception as e:
        logger.error(f"Error getting deals: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/customers/{client_id}/deals")
async def get_deals_by_customer(
    client_id: int,
    page: Optional[int] = None,
    per_page: Optional[int] = None,
    tenant: tuple = Depends(get_tenant_connection)
):
    """Get all deals for a specific customer"""
    conn, user = tenant
    try:
        base_query = """
        SELECT
            d.deal_id, d.deal_name, d.product_name, d.description, d.value_usd,
            d.hs_code, d.fob_price, d.fob_currency, d.landed_price, d.quantity, d.moq, d.room_status,
            d.employee_id, d.client_id, d.created_at, d.updated_at,
            d.completion_time, d.last_contact_date, d.expected_close_date,
            d.share_token, d.view_count, d.quote_data,
            e.name as salesman_name, c.name as client_name,
            p_primary.email as client_email
        FROM deals d
        LEFT JOIN employee_info e ON d.employee_id = e.employee_id
        LEFT JOIN clients c ON d.client_id = c.client_id
        LEFT JOIN LATERAL (
            SELECT email FROM personnel WHERE client_id = d.client_id AND is_primary = true LIMIT 1
        ) p_primary ON true
        WHERE d.client_id = $1
        ORDER BY d.created_at DESC
        """

        if page is not None and per_page is not None:
            offset = (page - 1) * per_page
            paginated_query = f"""
                SELECT *, COUNT(*) OVER() AS _total_count
                FROM ({base_query}) _sub
                LIMIT $2 OFFSET $3
            """
            rows = await conn.fetch(paginated_query, client_id, per_page, offset)
        else:
            rows = await conn.fetch(base_query, client_id)

        total = None
        if page is not None and per_page is not None and rows:
            total = rows[0]['_total_count']

        deals = []
        for row in rows:
            row_dict = dict(row)
            row_dict.pop('_total_count', None)
            deals.append(_row_to_deal(row_dict))

        if total is not None:
            return paginated_response(deals, total, page, per_page, key="deals")

        return deals
    except Exception as e:
        logger.error(f"Error getting deals for customer {client_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/deals/{deal_id}")
async def get_deal_by_id(deal_id: int, tenant: tuple = Depends(get_tenant_connection)) -> Deal:
    """Get specific deal by ID with employee and client names"""
    conn, user = tenant
    try:
        query = """
        SELECT
            d.deal_id,
            d.deal_name,
            d.product_name,
            d.description,
            d.value_usd,
            d.hs_code,
            d.fob_price,
            d.fob_currency,
            d.landed_price,
            d.quantity,
            d.moq,
            d.room_status,
            d.employee_id,
            d.client_id,
            d.created_at,
            d.updated_at,
            d.completion_time,
            d.last_contact_date,
            d.expected_close_date,
            d.share_token, d.view_count, d.quote_data,
            e.name as salesman_name,
            c.name as client_name,
            p_primary.email as client_email
        FROM deals d
        LEFT JOIN employee_info e ON d.employee_id = e.employee_id
        LEFT JOIN clients c ON d.client_id = c.client_id
        LEFT JOIN LATERAL (
            SELECT email FROM personnel WHERE client_id = d.client_id AND is_primary = true LIMIT 1
        ) p_primary ON true
        WHERE d.deal_id = $1
        """

        deal_data = await conn.fetchrow(query, deal_id)

        if not deal_data:
            raise HTTPException(status_code=404, detail={"code": "DEAL_NOT_FOUND", "message": "Deal not found"})

        return _row_to_deal(deal_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting deal {deal_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/deals")
async def create_deal(deal_data: CreateDealRequest, tenant: tuple = Depends(get_tenant_connection)) -> Deal:
    """Create a new deal with automatic employee assignment"""
    conn, user = tenant
    try:
        user_email = user.get('email', '')
        logger.info(f"CREATE deal request: user_email={user_email}, deal_name={deal_data.deal_name}")

        async with conn.transaction():
            # Auto-assignment logic
            assigned_employee_id = deal_data.employee_id
            assignment_method = "manual"  # Track how assignment was made

            if assigned_employee_id is None:
                # No employee specified - auto-assign to authenticated user
                logger.info(f"Auto-assignment triggered for user: {user_email}")

                row = await conn.fetchrow(
                    "SELECT employee_id FROM employee_info WHERE email = $1 LIMIT 1", user_email
                )
                auto_assigned_id = row["employee_id"] if row else None

                if auto_assigned_id is not None:
                    assigned_employee_id = auto_assigned_id
                    assignment_method = "auto_assigned_to_creator"
                    logger.info(f"Deal auto-assigned to employee_id {assigned_employee_id} (creator: {user_email})")
                else:
                    # User not found in employee_info table
                    logger.warning(f"Cannot auto-assign: User {user_email} not found in employee_info table")

                    # Allow deal creation without assignment (NULL employee_id)
                    assigned_employee_id = None
                    assignment_method = "unassigned_user_not_found"
                    logger.info(f"Deal will be created without assignment (employee_id = NULL)")
            else:
                # Employee explicitly specified by frontend (manual override)
                logger.info(f"Manual assignment: employee_id {assigned_employee_id} specified by user {user_email}")
                assignment_method = "manual_override"

            # Parse expected_close_date
            expected_close_date = None
            if deal_data.expected_close_date:
                try:
                    expected_close_date = datetime.strptime(deal_data.expected_close_date, "%Y-%m-%d").date()
                except ValueError:
                    pass

            # Auto-calculate value_usd = fob_price × quantity
            value_usd = deal_data.value_usd or 0.0
            if deal_data.fob_price is not None and deal_data.quantity is not None:
                value_usd = deal_data.fob_price * deal_data.quantity

            # Insert new deal
            current_time = datetime.now(timezone.utc)

            result = await conn.fetchrow("""
                INSERT INTO deals (
                    deal_name, product_name, description, value_usd, hs_code,
                    fob_price, fob_currency,
                    landed_price, quantity, moq, room_status, employee_id, client_id,
                    created_at, updated_at, expected_close_date
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16
                )
                RETURNING deal_id
            """,
                deal_data.deal_name,
                deal_data.product_name,
                deal_data.description,
                value_usd,
                deal_data.hs_code,
                deal_data.fob_price,
                deal_data.fob_currency,
                deal_data.landed_price,
                deal_data.quantity,
                deal_data.moq,
                deal_data.room_status,
                assigned_employee_id,
                deal_data.client_id,
                current_time,
                current_time,
                expected_close_date
            )
            deal_id = result['deal_id']

            # Log successful assignment
            logger.info(f"Deal {deal_id} created successfully | Assignment: {assignment_method} | Employee: {assigned_employee_id}")

        # Clear cache since we added a new deal
        clear_cache("get_all_deals")

        # Return the created deal by fetching it
        return await get_deal_by_id(deal_id, tenant)

    except Exception as e:
        logger.error(f"Error creating deal: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/deals/{deal_id}")
async def update_deal(deal_id: int, update_data: UpdateDealRequest, tenant: tuple = Depends(get_tenant_connection)) -> Deal:
    """Update a deal's information"""
    conn, user = tenant
    try:
        async with conn.transaction():
            # First check if deal exists
            existing = await conn.fetchrow("SELECT deal_id FROM deals WHERE deal_id = $1", deal_id)
            if not existing:
                raise HTTPException(status_code=404, detail={"code": "DEAL_NOT_FOUND", "message": "Deal not found"})

            # Build update query
            set_clauses = []
            params = []
            param_idx = 1

            # Map all possible update fields
            field_mapping = {
                'deal_name': 'deal_name',
                'product_name': 'product_name',
                'description': 'description',
                'value_usd': 'value_usd',
                'hs_code': 'hs_code',
                'fob_price': 'fob_price',
                'fob_currency': 'fob_currency',
                'landed_price': 'landed_price',
                'quantity': 'quantity',
                'moq': 'moq',
                'room_status': 'room_status',
                'employee_id': 'employee_id',
                'client_id': 'client_id',
                'expected_close_date': 'expected_close_date',
                'last_contact_date': 'last_contact_date'
            }

            for field_name, db_field in field_mapping.items():
                value = getattr(update_data, field_name, None)
                if value is not None:
                    # Handle date fields — convert empty strings to None
                    if field_name in ['expected_close_date', 'last_contact_date']:
                        if value:
                            try:
                                value = datetime.strptime(value, "%Y-%m-%d").date()
                            except ValueError:
                                value = None
                        else:
                            value = None

                    if value is not None:
                        set_clauses.append(f"{db_field} = ${param_idx}")
                        params.append(value)
                        param_idx += 1

            # Auto-calculate value_usd = fob_price × quantity
            if update_data.fob_price is not None or update_data.quantity is not None:
                # Fetch current values for fields not being updated
                current = await conn.fetchrow(
                    "SELECT fob_price, quantity FROM deals WHERE deal_id = $1", deal_id
                )
                fob = update_data.fob_price if update_data.fob_price is not None else (float(current['fob_price']) if current['fob_price'] else None)
                qty = update_data.quantity if update_data.quantity is not None else current['quantity']
                if fob is not None and qty is not None:
                    # Remove any manually-set value_usd from the clauses
                    for i, clause in enumerate(set_clauses):
                        if clause.startswith("value_usd"):
                            set_clauses.pop(i)
                            params.pop(i)
                            # Re-index params
                            param_idx = 1
                            new_clauses = []
                            for c in set_clauses:
                                db_col = c.split(" = ")[0]
                                new_clauses.append(f"{db_col} = ${param_idx}")
                                param_idx += 1
                            set_clauses = new_clauses
                            break
                    set_clauses.append(f"value_usd = ${param_idx}")
                    params.append(fob * qty)
                    param_idx += 1

            if set_clauses:
                set_clauses.append(f"updated_at = ${param_idx}")
                params.append(datetime.now(timezone.utc))
                param_idx += 1

                params.append(deal_id)

                query = f"""
                    UPDATE deals
                    SET {', '.join(set_clauses)}
                    WHERE deal_id = ${param_idx}
                """
                await conn.execute(query, *params)

            # Auto-generate deal room when FOB price is set on a deal without one.
            # Runs inside the transaction so the tenant-DB portion of room creation
            # rolls back atomically with the deal update if it fails.
            # Note: the cross-DB analytics write in create_deal_room uses a separate
            # pool connection and cannot participate in this transaction; its own
            # compensating-delete logic handles cleanup on failure.
            if update_data.fob_price is not None:
                deal_check = await conn.fetchrow(
                    "SELECT share_token, employee_id, deal_name, product_name, hs_code, fob_price, landed_price, fob_currency, quantity, moq "
                    "FROM deals WHERE deal_id = $1",
                    deal_id
                )
                if deal_check and not deal_check['share_token'] and deal_check['fob_price'] and deal_check['employee_id']:
                    user_email = user.get('email')
                    if user_email:
                        fob = float(deal_check['fob_price'])
                        landed = float(deal_check['landed_price']) if deal_check['landed_price'] else fob
                        currency = deal_check['fob_currency'] or 'USD'
                        qty = deal_check['moq'] or 0
                        quote_data = {
                            'productName': deal_check['product_name'] or deal_check['deal_name'] or '',
                            'hsCode': deal_check['hs_code'] or '',
                            'moq': qty,
                            'options': [{
                                'label': deal_check['product_name'] or deal_check['deal_name'] or 'Quote',
                                'origin': '',
                                'currency': currency,
                                'fobPrice': fob,
                                'landedPrice': landed,
                            }],
                        }
                        await create_deal_room(
                            conn,
                            deal_id=deal_id,
                            user_email=user_email,
                            quote_data=quote_data,
                            sample_timeline={},
                            room_settings={},
                            fob_price=fob,
                            fob_currency=currency,
                        )
                        logger.info(f"Auto-generated deal room for deal {deal_id} after FOB price set")

        # Clear relevant caches
        clear_cache("get_all_deals")
        clear_cache(f"get_deal_by_id:{deal_id}")

        # Return the updated deal
        return await get_deal_by_id(deal_id, tenant)

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error updating deal {deal_id}: {e}")
        raise HTTPException(status_code=500, detail={"code": "DEAL_UPDATE_FAILED", "message": "Failed to update deal"})

@router.delete("/deals/{deal_id}")
async def delete_deal(deal_id: int, tenant: tuple = Depends(get_tenant_connection)) -> Dict[str, Any]:
    """Delete a deal"""
    conn, user = tenant
    try:
        # First check if deal exists
        existing = await conn.fetchrow("SELECT deal_id FROM deals WHERE deal_id = $1", deal_id)
        if not existing:
            raise HTTPException(status_code=404, detail={"code": "DEAL_NOT_FOUND", "message": "Deal not found"})

        # Delete the deal
        result = await conn.execute("DELETE FROM deals WHERE deal_id = $1", deal_id)

        # asyncpg execute returns status string like 'DELETE 1'
        deleted_count = int(result.split()[-1])

        # Clear cache since we deleted a deal
        clear_cache("get_all_deals")

        logger.info(f"Deleted deal {deal_id} successfully")

        return {
            "success": True,
            "message": f"Deal {deal_id} deleted successfully",
            "deleted_count": deleted_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting deal {deal_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
