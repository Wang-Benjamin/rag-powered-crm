"""Employee service for CRM - handles employee-related business logic"""

import logging
from typing import Optional, Dict, Any, List

import asyncpg
from fastapi import HTTPException

from data.repositories.employee_repository import EmployeeRepository

logger = logging.getLogger(__name__)

# Initialize repository
employee_repo = EmployeeRepository()


async def get_employee_id_by_email(conn: asyncpg.Connection, email: str) -> int:
    """
    Get employee_id by email from employee_info table.

    Args:
        conn: asyncpg connection
        email: Email to lookup

    Returns:
        employee_id if found

    Raises:
        HTTPException: If employee not found or database error
    """
    try:
        employee_id = await employee_repo.find_id_by_email(conn, email)

        if not employee_id:
            raise HTTPException(status_code=404, detail=f"Employee with email {email} not found")

        logger.info(f"Found employee_id {employee_id} for email {email}")
        return employee_id

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching employee_id for email {email}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching employee information: {str(e)}")


async def get_employee_info_by_email(conn: asyncpg.Connection, email: str) -> Dict[str, Any]:
    """
    Get employee information (name, role, department) by email from employee_info table.

    Args:
        conn: asyncpg connection
        email: Email to lookup

    Returns:
        Dictionary with employee info (name, role, department)

    Raises:
        HTTPException: If employee not found or database error
    """
    try:
        employee_info = await employee_repo.find_info_by_email(conn, email)

        if not employee_info:
            raise HTTPException(status_code=404, detail=f"Employee with email {email} not found")

        logger.info(f"Found employee info for email {email}: {employee_info['name']} - {employee_info['role']}")
        return employee_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching employee info for email {email}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching employee information: {str(e)}")


async def get_employee_id_by_email_safe(conn: asyncpg.Connection, email: str) -> Optional[int]:
    """
    Get employee_id by email from employee_info table.
    Returns None if not found (safe version for auto-assignment).

    Args:
        conn: asyncpg connection
        email: Email to lookup

    Returns:
        employee_id if found, None otherwise
    """
    try:
        employee_id = await employee_repo.find_id_by_email(conn, email)

        if employee_id:
            logger.info(f"Auto-assignment: Found employee_id {employee_id} for email {email}")
            return employee_id
        else:
            logger.warning(f"Auto-assignment: No employee found for email {email}")
            return None

    except Exception as e:
        logger.error(f"Error fetching employee_id for email {email}: {e}")
        return None


async def get_all_employees(conn: asyncpg.Connection) -> List[Dict[str, Any]]:
    """
    Get all employees.

    Args:
        conn: asyncpg connection

    Returns:
        List of employee dictionaries

    Raises:
        HTTPException: If database error
    """
    try:
        employees = await employee_repo.get_all_employees(conn)
        logger.info(f"Retrieved {len(employees)} employees")
        return employees

    except Exception as e:
        logger.error(f"Error fetching all employees: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching employees: {str(e)}")


async def get_employee_access_role(conn: asyncpg.Connection, email: str) -> Optional[str]:
    """
    Get employee access role (admin/user).

    Args:
        conn: asyncpg connection
        email: Employee email to lookup

    Returns:
        Access role ('admin' or 'user') or None if not found
    """
    try:
        access_role = await employee_repo.get_access_role(conn, email)
        logger.info(f"Employee {email} has access role: {access_role}")
        return access_role

    except Exception as e:
        logger.error(f"Error fetching access role for {email}: {e}")
        return None
