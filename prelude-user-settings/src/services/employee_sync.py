"""
Employee Sync Service
=====================
Syncs user_profiles data to employee_info in the user's tenant database.
"""

import logging
from datetime import datetime, timezone

from service_core.db import get_pool_manager
from email_core.generation.trade_voice import TRADE_VOICE_PRESET, TRADE_EMAIL_SAMPLES

logger = logging.getLogger(__name__)


async def sync_user_to_employee_info(user_data: dict) -> dict:
    """Sync user_profiles data to employee_info table in user's dedicated database.

    Returns dict with 'synced' bool and 'reason' string.
    """
    try:
        user_db_name = user_data.get('database_name') or user_data.get('db_name')
        user_email = user_data.get('email', 'unknown')

        if not user_db_name or user_db_name == 'prelude_visitor':
            return {"synced": False, "reason": "No dedicated database for user"}

        pm = get_pool_manager()
        async with pm.acquire(user_db_name) as conn:
            table_exists = await conn.fetchval(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'employee_info')"
            )
            if not table_exists:
                return {"synced": False, "reason": f"employee_info table does not exist in '{user_db_name}'"}

            existing = await conn.fetchval(
                "SELECT employee_id FROM employee_info WHERE email = $1", user_email
            )
            if existing:
                return {"synced": True, "reason": "Employee record already exists"}

            parsed_name = user_data.get('name') or user_data.get('username') or user_email.split('@')[0]
            access_level = user_data.get('role', 'user')

            result = await conn.fetchrow(
                """
                INSERT INTO employee_info (
                    name, role, department, email,
                    access,
                    writing_style, training_emails,
                    created_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    $6, $7,
                    $8, $9
                )
                RETURNING employee_id
                """,
                parsed_name, 'Unknown', user_data.get('company', 'General'),
                user_email, access_level,
                TRADE_VOICE_PRESET, TRADE_EMAIL_SAMPLES,
                datetime.now(timezone.utc), datetime.now(timezone.utc)
            )
            logger.info(f"Created employee_info for {user_email} in {user_db_name}, id={result['employee_id']}")
            return {"synced": True, "reason": "Successfully created employee_info record"}

    except Exception as e:
        logger.error(f"Error syncing user to employee_info: {e}")
        return {"synced": False, "reason": f"Error: {str(e)}"}
