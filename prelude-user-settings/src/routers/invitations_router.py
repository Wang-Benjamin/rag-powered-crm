"""
Invitations Router for User Management
======================================
Manages user invitations and team members via user_profiles in prelude_user_analytics.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any
import json
import logging
from datetime import datetime, timezone

from service_core.auth import verify_auth_token
from service_core.db import get_pool_manager
from services.employee_sync import sync_user_to_employee_info

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invitations")

# Pydantic models
class InvitationCreate(BaseModel):
    email: EmailStr
    company: str = Field(..., min_length=2, max_length=100)
    role: str = Field(..., min_length=2, max_length=50)
    database_name: Optional[str] = Field(default='prelude_visitor', min_length=2, max_length=100)

class InvitationUpdate(BaseModel):
    company: Optional[str] = Field(None, min_length=2, max_length=100)
    role: Optional[str] = Field(None, min_length=2, max_length=50)
    database_name: Optional[str] = Field(None, min_length=2, max_length=100)

VALID_ONBOARDING_STATUSES = {'not_started', 'in_progress', 'completed', 'skipped'}

class OnboardingUpdate(BaseModel):
    onboarding_status: Optional[str] = None
    onboarding_step: Optional[int] = Field(None, ge=0, le=5)
    onboarding_progress: Optional[Dict[str, Any]] = None

async def _get_analytics_conn():
    """Get a connection to the analytics pool."""
    pm = get_pool_manager()
    return await pm.get_analytics_pool()


@router.get("/user/{email}", response_model=Dict[str, Any])
async def get_user_invitations(email: str):
    """Get invitations for a specific user email and all team members in their company."""
    pool = await _get_analytics_conn()
    async with pool.acquire() as conn:
        user_info = await conn.fetchrow(
            """
            SELECT email, name, company, role, db_name as database_name, created_at, updated_at,
                   onboarding_status, onboarding_step, onboarding_progress, onboarding_completed_at
            FROM user_profiles WHERE email = $1
            """,
            email
        )

        if not user_info:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with email {email} not found")

        company_users = await conn.fetch(
            """
            SELECT email, name, company, role, db_name as database_name, created_at, updated_at
            FROM user_profiles WHERE company = $1 ORDER BY email
            """,
            user_info['company']
        )

        user_dict = dict(user_info)
        if user_dict.get('onboarding_progress') and isinstance(user_dict['onboarding_progress'], str):
            try:
                user_dict['onboarding_progress'] = json.loads(user_dict['onboarding_progress'])
            except (json.JSONDecodeError, TypeError):
                pass

        # Dynamically check tenant_subscription for existing company data
        progress = user_dict.get('onboarding_progress')
        if not isinstance(progress, dict):
            progress = {}
        db_name = user_dict.get('database_name')
        if db_name and db_name != 'prelude_visitor' and not progress.get('companyDataExists'):
            try:
                pm = get_pool_manager()
                async with pm.acquire(db_name) as tenant_conn:
                    ts = await tenant_conn.fetchrow(
                        "SELECT hs_codes, company_profile, factory_details FROM tenant_subscription LIMIT 1"
                    )
                    if ts:
                        # JSONB columns: asyncpg returns list/dict, not strings
                        has_data = (
                            bool(ts['hs_codes'] and ts['hs_codes'] not in ([], ['']))
                            or bool(ts['company_profile'] and ts['company_profile'] != {})
                            or bool(ts['factory_details'] and ts['factory_details'] != {})
                        )
                        if has_data:
                            progress['companyDataExists'] = True
                            user_dict['onboarding_progress'] = progress
            except Exception as e:
                logger.error(f"Could not check tenant_subscription for {db_name}: {type(e).__name__}: {e}")

        if user_dict.get('onboarding_completed_at'):
            user_dict['onboarding_completed_at'] = user_dict['onboarding_completed_at'].isoformat()

        users_list = []
        for u in company_users:
            row = dict(u)
            if row['created_at']:
                row['created_at'] = row['created_at'].isoformat()
            if row['updated_at']:
                row['updated_at'] = row['updated_at'].isoformat()
            users_list.append(row)

        return {"user": user_dict, "invitations": users_list}


@router.get("/company/{company}", response_model=Dict[str, Any])
async def get_company_invitations(company: str):
    """Get all invitations for a specific company."""
    pool = await _get_analytics_conn()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT email, name, company, role, db_name as database_name, created_at, updated_at
            FROM user_profiles WHERE company = $1 ORDER BY email
            """,
            company
        )

        invitations = []
        for r in rows:
            row = dict(r)
            if row['created_at']:
                row['created_at'] = row['created_at'].isoformat()
            if row['updated_at']:
                row['updated_at'] = row['updated_at'].isoformat()
            invitations.append(row)

        return {"invitations": invitations}


@router.post("", response_model=Dict[str, Any])
async def create_invitation(
    invitation: InvitationCreate,
    authenticated_user: dict = Depends(verify_auth_token)
):
    """Create a new invitation (add a new user). New users inherit the inviter's database_name."""
    pool = await _get_analytics_conn()
    async with pool.acquire() as conn:
        inviter_email = authenticated_user.get('email')
        inviter_db_name = 'prelude_visitor'

        if inviter_email:
            inviter_profile = await conn.fetchrow(
                "SELECT db_name, role FROM user_profiles WHERE email = $1", inviter_email
            )
            if inviter_profile and inviter_profile['db_name']:
                inviter_db_name = inviter_profile['db_name']

            if invitation.role == 'admin' and (not inviter_profile or inviter_profile['role'] != 'admin'):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can invite users with admin role")

        existing = await conn.fetchval(
            "SELECT email FROM user_profiles WHERE email = $1", invitation.email
        )
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"User with email {invitation.email} already exists")

        db_name_to_use = invitation.database_name if invitation.database_name and invitation.database_name != 'prelude_visitor' else inviter_db_name

        new_invitation = await conn.fetchrow(
            """
            INSERT INTO user_profiles (email, company, role, db_name, name, created_at)
            VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP)
            RETURNING email, company, role, db_name as database_name, created_at
            """,
            invitation.email, invitation.company, invitation.role,
            db_name_to_use, invitation.email.split('@')[0]
        )

    result = dict(new_invitation)
    if result['created_at']:
        result['created_at'] = result['created_at'].isoformat()

    sync_result = await sync_user_to_employee_info(result)

    # Company data lives in tenant_subscription — no need to copy between users.
    # If company data exists, flag it so frontend skips company onboarding steps.
    company_data_copied = False
    if db_name_to_use and db_name_to_use != 'prelude_visitor':
        try:
            pm = get_pool_manager()
            async with pm.acquire(db_name_to_use) as tenant_conn:
                ts = await tenant_conn.fetchrow(
                    "SELECT hs_codes, company_profile, factory_details FROM tenant_subscription LIMIT 1"
                )
                if ts and (
                    (ts.get('hs_codes') and str(ts['hs_codes']) != '[]')
                    or (ts.get('company_profile') and str(ts['company_profile']) != '{}')
                    or (ts.get('factory_details') and str(ts['factory_details']) != '{}')
                ):
                    company_data_copied = True

            if company_data_copied:
                async with pool.acquire() as analytics_conn:
                    await analytics_conn.execute(
                        """UPDATE user_profiles
                           SET onboarding_progress = '{"companyDataExists": true}'::jsonb
                           WHERE email = $1""",
                        invitation.email
                    )
        except Exception as e:
            logger.warning(f"Failed to check tenant data for {invitation.email}: {e}")

    return {
        "success": True,
        "message": f"Successfully invited {invitation.email}",
        "invitation": result,
        "employee_sync": sync_result,
        "company_data_copied": company_data_copied
    }


@router.put("/{email}", response_model=Dict[str, Any])
async def update_invitation(
    email: str,
    update_data: InvitationUpdate,
    authenticated_user: dict = Depends(verify_auth_token)
):
    """Update an existing invitation. Requires admin role."""
    pool = await _get_analytics_conn()
    async with pool.acquire() as conn:
        caller_email = authenticated_user.get('email')
        if caller_email:
            caller = await conn.fetchrow("SELECT role FROM user_profiles WHERE email = $1", caller_email)
            if not caller or caller['role'] != 'admin':
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can update members")

        target = await conn.fetchrow("SELECT role FROM user_profiles WHERE email = $1", email)
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with email {email} not found")
        if target['role'] == 'admin':
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot modify admin users")

        updates = []
        params = []
        param_idx = 1

        if update_data.company is not None:
            updates.append(f"company = ${param_idx}")
            params.append(update_data.company)
            param_idx += 1
        if update_data.role is not None:
            updates.append(f"role = ${param_idx}")
            params.append(update_data.role)
            param_idx += 1
        if update_data.database_name is not None:
            updates.append(f"db_name = ${param_idx}")
            params.append(update_data.database_name)
            param_idx += 1

        if not updates:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(email)

        updated = await conn.fetchrow(
            f"""
            UPDATE user_profiles SET {', '.join(updates)}
            WHERE email = ${param_idx}
            RETURNING email, company, role, db_name as database_name, created_at, updated_at
            """,
            *params
        )

    result = dict(updated)
    if result['created_at']:
        result['created_at'] = result['created_at'].isoformat()
    if result['updated_at']:
        result['updated_at'] = result['updated_at'].isoformat()

    return {"success": True, "message": f"Successfully updated {email}", "invitation": result}


@router.delete("/{email}", response_model=Dict[str, Any])
async def delete_invitation(
    email: str,
    authenticated_user: dict = Depends(verify_auth_token)
):
    """Delete an invitation (remove a user). Requires admin role."""
    pool = await _get_analytics_conn()
    async with pool.acquire() as conn:
        caller_email = authenticated_user.get('email')
        if caller_email:
            caller = await conn.fetchrow("SELECT role FROM user_profiles WHERE email = $1", caller_email)
            if not caller or caller['role'] != 'admin':
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can remove members")

        target = await conn.fetchrow("SELECT role FROM user_profiles WHERE email = $1", email)
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with email {email} not found")
        if target['role'] == 'admin':
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot remove admin users")

        await conn.execute("DELETE FROM user_profiles WHERE email = $1", email)

    return {"success": True, "message": f"Successfully deleted {email}"}


@router.get("/check/{email}", response_model=Dict[str, bool])
async def check_user_exists(email: str):
    """Check if a user exists in the database."""
    pool = await _get_analytics_conn()
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM user_profiles WHERE email = $1)", email
        )
    return {"exists": exists}


@router.patch("/{email}/onboarding", response_model=Dict[str, Any])
async def update_onboarding(
    email: str,
    update_data: OnboardingUpdate,
    authenticated_user: dict = Depends(verify_auth_token)
):
    """Update onboarding progress. Users can only update their own onboarding."""
    caller_email = authenticated_user.get('email')
    if caller_email != email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Can only update your own onboarding")

    if update_data.onboarding_status and update_data.onboarding_status not in VALID_ONBOARDING_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status. Must be one of: {VALID_ONBOARDING_STATUSES}")

    pool = await _get_analytics_conn()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT email FROM user_profiles WHERE email = $1", email)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {email} not found")

        updates = []
        params = []
        param_idx = 1

        if update_data.onboarding_status is not None:
            updates.append(f"onboarding_status = ${param_idx}")
            params.append(update_data.onboarding_status)
            param_idx += 1

        if update_data.onboarding_step is not None:
            updates.append(f"onboarding_step = ${param_idx}")
            params.append(update_data.onboarding_step)
            param_idx += 1

        if update_data.onboarding_progress is not None:
            updates.append(f"onboarding_progress = ${param_idx}")
            params.append(update_data.onboarding_progress)
            param_idx += 1

        # Auto-set completed_at when status transitions to completed
        if update_data.onboarding_status == 'completed':
            updates.append(f"onboarding_completed_at = ${param_idx}")
            params.append(datetime.now(timezone.utc))
            param_idx += 1

        if not updates:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(email)

        updated = await conn.fetchrow(
            f"""
            UPDATE user_profiles SET {', '.join(updates)}
            WHERE email = ${param_idx}
            RETURNING email, onboarding_status, onboarding_step, onboarding_progress, onboarding_completed_at
            """,
            *params
        )

    result = dict(updated)
    if result.get('onboarding_completed_at'):
        result['onboarding_completed_at'] = result['onboarding_completed_at'].isoformat()

    return {"success": True, "onboarding": result}
