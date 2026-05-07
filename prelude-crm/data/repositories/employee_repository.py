"""Employee repository for CRM - handles employee database operations."""

import logging
from typing import Optional, Dict, Any, List

import asyncpg

from data.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class EmployeeRepository(BaseRepository):
    """Repository for employee database operations."""

    def __init__(self):
        super().__init__('employee_info')

    async def find_by_email(self, conn: asyncpg.Connection, email: str) -> Optional[Dict[str, Any]]:
        """
        Find employee by email address.

        Args:
            conn: asyncpg connection
            email: Employee email to search for

        Returns:
            Employee dictionary or None if not found
        """
        query = """
            SELECT employee_id, name, email, role, department, access
            FROM employee_info
            WHERE email = $1
        """
        return await self._execute_query_one(conn, query, email)

    async def find_id_by_email(self, conn: asyncpg.Connection, email: str) -> Optional[int]:
        """
        Get employee ID by email address.

        Args:
            conn: asyncpg connection
            email: Employee email to search for

        Returns:
            Employee ID or None if not found
        """
        employee = await self.find_by_email(conn, email)
        return employee['employee_id'] if employee else None

    async def find_info_by_email(self, conn: asyncpg.Connection, email: str) -> Optional[Dict[str, Any]]:
        """
        Get employee information (name, role, department) by email.

        Args:
            conn: asyncpg connection
            email: Employee email to search for

        Returns:
            Dictionary with name, role, department or None if not found
        """
        query = """
            SELECT name, role, department
            FROM employee_info
            WHERE email = $1
        """
        return await self._execute_query_one(conn, query, email)

    async def get_all_employees(self, conn: asyncpg.Connection) -> List[Dict[str, Any]]:
        """
        Get all employees.

        Args:
            conn: asyncpg connection

        Returns:
            List of employee dictionaries
        """
        query = """
            SELECT employee_id, name, email, role, department, access
            FROM employee_info
            ORDER BY name
        """
        return await self._execute_query(conn, query)

    async def find_by_id(self, conn: asyncpg.Connection, employee_id: int) -> Optional[Dict[str, Any]]:
        """
        Find employee by ID.

        Args:
            conn: asyncpg connection
            employee_id: Employee ID to search for

        Returns:
            Employee dictionary or None if not found
        """
        return await super().find_by_id(conn, employee_id, id_column='employee_id')

    async def get_access_role(self, conn: asyncpg.Connection, email: str) -> Optional[str]:
        """
        Get employee access role (admin/user).

        Args:
            conn: asyncpg connection
            email: Employee email to search for

        Returns:
            Access role ('admin' or 'user') or None if not found
        """
        employee = await self.find_by_email(conn, email)
        return employee.get('access') if employee else None
