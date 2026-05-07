"""Feedback repository for CRM feedback data access."""

import json
import logging
import asyncpg
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from data.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class FeedbackRepository(BaseRepository):
    """Repository for managing CRM feedback data."""

    def __init__(self):
        """Initialize feedback repository."""
        super().__init__("crm_feedback")

    async def create_feedback(
        self,
        conn: asyncpg.Connection,
        customer_id: int,
        employee_id: int,
        feedback_category: str,
        rating: int,
        feedback_text: Optional[str],
        deal_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create new feedback entry.

        Args:
            conn: asyncpg database connection
            customer_id: ID of the customer
            employee_id: ID of the employee providing feedback
            feedback_category: Category of feedback ('churn_risk', 'ai_insights', etc.)
            rating: Rating from 1 to 5
            feedback_text: Optional text feedback
            deal_id: Optional deal ID (for deal-specific feedback)

        Returns:
            Created feedback record or None
        """
        # Build feedback history entry
        feedback_entry = {
            'text': feedback_text or '',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'employee_id': employee_id
        }

        query = """
            INSERT INTO crm_feedback (
                customer_id, deal_id, employee_id, feedback_category, rating, feedback_history, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, NOW(), NOW())
            RETURNING feedback_id, customer_id, deal_id, employee_id, feedback_category, rating,
                      feedback_history, ai_summary, created_at, updated_at
        """

        try:
            result = await self._execute_write(
                conn, query,
                customer_id, deal_id, employee_id, feedback_category, rating, [feedback_entry]
            )
            entity_desc = f"deal {deal_id}" if deal_id else f"customer {customer_id}"
            logger.info(f"Created feedback {result.get('feedback_id')} for {entity_desc} category {feedback_category}")
            return result
        except Exception as e:
            logger.error(f"Error creating feedback: {e}")
            raise

    async def get_feedback_by_customer(
        self,
        conn: asyncpg.Connection,
        customer_id: int,
        feedback_category: Optional[str] = None,
        deal_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all feedback for a specific customer or deal.

        Args:
            conn: asyncpg database connection
            customer_id: ID of the customer
            feedback_category: Optional category filter
            deal_id: Optional deal ID (if None, gets customer-only feedback; if provided, gets deal feedback)

        Returns:
            List of feedback records
        """
        if deal_id is not None:
            # Get feedback for specific deal
            if feedback_category:
                query = """
                    SELECT f.feedback_id, f.customer_id, f.deal_id, f.employee_id, f.feedback_category,
                           f.rating, f.feedback_history, f.ai_summary, f.created_at, f.updated_at,
                           e.name as employee_name, e.email as employee_email
                    FROM crm_feedback f
                    LEFT JOIN employee_info e ON f.employee_id = e.employee_id
                    WHERE f.customer_id = $1 AND f.deal_id = $2 AND f.feedback_category = $3
                    ORDER BY f.created_at DESC
                """
                params = (customer_id, deal_id, feedback_category)
            else:
                query = """
                    SELECT f.feedback_id, f.customer_id, f.deal_id, f.employee_id, f.feedback_category,
                           f.rating, f.feedback_history, f.ai_summary, f.created_at, f.updated_at,
                           e.name as employee_name, e.email as employee_email
                    FROM crm_feedback f
                    LEFT JOIN employee_info e ON f.employee_id = e.employee_id
                    WHERE f.customer_id = $1 AND f.deal_id = $2
                    ORDER BY f.created_at DESC
                """
                params = (customer_id, deal_id)
        else:
            # Get customer-only feedback (deal_id IS NULL)
            if feedback_category:
                query = """
                    SELECT f.feedback_id, f.customer_id, f.deal_id, f.employee_id, f.feedback_category,
                           f.rating, f.feedback_history, f.ai_summary, f.created_at, f.updated_at,
                           e.name as employee_name, e.email as employee_email
                    FROM crm_feedback f
                    LEFT JOIN employee_info e ON f.employee_id = e.employee_id
                    WHERE f.customer_id = $1 AND f.deal_id IS NULL AND f.feedback_category = $2
                    ORDER BY f.created_at DESC
                """
                params = (customer_id, feedback_category)
            else:
                query = """
                    SELECT f.feedback_id, f.customer_id, f.deal_id, f.employee_id, f.feedback_category,
                           f.rating, f.feedback_history, f.ai_summary, f.created_at, f.updated_at,
                           e.name as employee_name, e.email as employee_email
                    FROM crm_feedback f
                    LEFT JOIN employee_info e ON f.employee_id = e.employee_id
                    WHERE f.customer_id = $1 AND f.deal_id IS NULL
                    ORDER BY f.created_at DESC
                """
                params = (customer_id,)

        try:
            results = await self._execute_query(conn, query, *params)
            entity_desc = f"deal {deal_id}" if deal_id else f"customer {customer_id}"
            category_info = f" category {feedback_category}" if feedback_category else ""
            logger.info(f"Retrieved {len(results)} feedback entries for {entity_desc}{category_info}")
            return results
        except Exception as e:
            logger.error(f"Error getting feedback by customer: {e}")
            raise

    async def get_feedback_by_id(
        self,
        conn: asyncpg.Connection,
        feedback_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get specific feedback by ID.

        Args:
            conn: asyncpg database connection
            feedback_id: Feedback ID

        Returns:
            Feedback record or None
        """
        query = """
            SELECT f.feedback_id, f.customer_id, f.deal_id, f.employee_id, f.feedback_category,
                   f.rating, f.feedback_history, f.ai_summary, f.created_at, f.updated_at,
                   e.name as employee_name, e.email as employee_email
            FROM crm_feedback f
            LEFT JOIN employee_info e ON f.employee_id = e.employee_id
            WHERE f.feedback_id = $1
        """

        try:
            return await self._execute_query_one(conn, query, feedback_id)
        except Exception as e:
            logger.error(f"Error getting feedback by ID: {e}")
            raise

    async def get_user_feedback(
        self,
        conn: asyncpg.Connection,
        customer_id: int,
        employee_id: int,
        feedback_category: str,
        deal_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get specific user's feedback for a customer/deal and category.

        Args:
            conn: asyncpg database connection
            customer_id: ID of the customer
            employee_id: ID of the employee
            feedback_category: Category of feedback
            deal_id: Optional deal ID

        Returns:
            Feedback record or None
        """
        if deal_id is not None:
            query = """
                SELECT f.feedback_id, f.customer_id, f.deal_id, f.employee_id, f.feedback_category,
                       f.rating, f.feedback_history, f.ai_summary, f.created_at, f.updated_at,
                       e.name as employee_name, e.email as employee_email
                FROM crm_feedback f
                LEFT JOIN employee_info e ON f.employee_id = e.employee_id
                WHERE f.customer_id = $1 AND f.deal_id = $2 AND f.employee_id = $3 AND f.feedback_category = $4
            """
            params = (customer_id, deal_id, employee_id, feedback_category)
        else:
            query = """
                SELECT f.feedback_id, f.customer_id, f.deal_id, f.employee_id, f.feedback_category,
                       f.rating, f.feedback_history, f.ai_summary, f.created_at, f.updated_at,
                       e.name as employee_name, e.email as employee_email
                FROM crm_feedback f
                LEFT JOIN employee_info e ON f.employee_id = e.employee_id
                WHERE f.customer_id = $1 AND f.deal_id IS NULL AND f.employee_id = $2 AND f.feedback_category = $3
            """
            params = (customer_id, employee_id, feedback_category)

        try:
            return await self._execute_query_one(conn, query, *params)
        except Exception as e:
            logger.error(f"Error getting user feedback: {e}")
            raise

    async def update_feedback(
        self,
        conn: asyncpg.Connection,
        feedback_id: int,
        employee_id: int,
        rating: Optional[int] = None,
        feedback_text: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update existing feedback. Appends new feedback text to history.

        Args:
            conn: asyncpg database connection
            feedback_id: Feedback ID to update
            employee_id: ID of the employee updating feedback
            rating: New rating (optional)
            feedback_text: New feedback text (optional, appended to history)

        Returns:
            Updated feedback record or None
        """
        # Build dynamic update query
        update_fields = []
        params = []
        param_idx = 1

        if rating is not None:
            update_fields.append(f"rating = ${param_idx}")
            params.append(rating)
            param_idx += 1

        if feedback_text is not None:
            # Append new feedback to history
            feedback_entry = {
                'text': feedback_text,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'employee_id': employee_id
            }
            update_fields.append(f"feedback_history = feedback_history || ${param_idx}::jsonb")
            params.append([feedback_entry])
            param_idx += 1

        if not update_fields:
            logger.warning("No fields to update")
            return None

        update_fields.append("updated_at = NOW()")
        params.append(feedback_id)

        query = f"""
            UPDATE crm_feedback
            SET {', '.join(update_fields)}
            WHERE feedback_id = ${param_idx}
            RETURNING feedback_id, customer_id, deal_id, employee_id, feedback_category, rating,
                      feedback_history, ai_summary, created_at, updated_at
        """

        try:
            result = await self._execute_write(conn, query, *params)
            logger.info(f"Updated feedback {feedback_id}")
            return result
        except Exception as e:
            logger.error(f"Error updating feedback: {e}")
            raise

    async def delete_feedback(
        self,
        conn: asyncpg.Connection,
        feedback_id: int
    ) -> bool:
        """
        Delete feedback by ID.

        Args:
            conn: asyncpg database connection
            feedback_id: Feedback ID to delete

        Returns:
            True if deleted, False otherwise
        """
        query = "DELETE FROM crm_feedback WHERE feedback_id = $1"

        try:
            await self._execute_write(conn, query, feedback_id)
            logger.info(f"Deleted feedback {feedback_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting feedback: {e}")
            raise

    async def get_feedback_by_employee(
        self,
        conn: asyncpg.Connection,
        employee_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get all feedback created by a specific employee.

        Args:
            conn: asyncpg database connection
            employee_id: Employee ID

        Returns:
            List of feedback records
        """
        query = """
            SELECT f.feedback_id, f.customer_id, f.deal_id, f.employee_id, f.feedback_category,
                   f.rating, f.feedback_history, f.ai_summary, f.created_at, f.updated_at,
                   e.name as employee_name, e.email as employee_email
            FROM crm_feedback f
            LEFT JOIN employee_info e ON f.employee_id = e.employee_id
            WHERE f.employee_id = $1
            ORDER BY f.created_at DESC
        """

        try:
            results = await self._execute_query(conn, query, employee_id)
            logger.info(f"Retrieved {len(results)} feedback entries for employee {employee_id}")
            return results
        except Exception as e:
            logger.error(f"Error getting feedback by employee: {e}")
            raise

    async def update_ai_summary(
        self,
        conn: asyncpg.Connection,
        feedback_id: int,
        ai_summary: Dict[str, Any]
    ) -> bool:
        """
        Update AI summary for a feedback entry.

        Args:
            conn: asyncpg database connection
            feedback_id: ID of the feedback entry
            ai_summary: AI-generated summary dict

        Returns:
            True if successful, False otherwise
        """
        query = """
            UPDATE crm_feedback
            SET ai_summary = $1::jsonb,
                updated_at = NOW()
            WHERE feedback_id = $2
        """

        try:
            await self._execute_write(conn, query, ai_summary, feedback_id)
            logger.info(f"Updated AI summary for feedback {feedback_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating AI summary for feedback {feedback_id}: {e}")
            return False
