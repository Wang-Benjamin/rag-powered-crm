"""
User Preferences Repository
Access user AI preferences and CRM category preferences from user_preferences table
"""
import json
import logging
import asyncpg
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from data.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class UserPreferencesRepository(BaseRepository):
    """Repository for accessing user AI preferences and CRM category preferences."""

    # Mapping from category name to database column
    CATEGORY_COLUMNS = {
        'churn_risk': 'crm_pref_churn_risk',
        'ai_insights': 'crm_pref_ai_insights',
        'stage_progression': 'crm_pref_stage_progression',
        'deal_insights': 'crm_pref_deal_insights'
    }

    def __init__(self):
        super().__init__("user_preferences")

    async def get_ai_preferences_summary(self, conn: asyncpg.Connection, user_email: str) -> Optional[Dict[str, Any]]:
        """
        Get AI summary from user preferences.

        Args:
            conn: asyncpg database connection
            user_email: User email for lookup

        Returns:
            Dictionary with ai_summary JSONB data or None if not found
        """
        query = """
            SELECT ai_summary, is_complete
            FROM user_preferences
            WHERE email = $1
        """

        try:
            result = await self._execute_query_one(conn, query, user_email)
            if result and result.get('is_complete'):
                logger.info(f"Retrieved AI preferences for {user_email}")
                return result.get('ai_summary')
            else:
                logger.info(f"No complete AI preferences found for {user_email}")
                return None
        except Exception as e:
            logger.warning(f"Error fetching AI preferences for {user_email}: {e}")
            return None

    # ============================================================================
    # CRM CATEGORY PREFERENCES METHODS
    # ============================================================================

    async def update_category_preference(
        self,
        conn: asyncpg.Connection,
        email: str,
        category: str,
        preferences: Dict[str, Any]
    ) -> Dict:
        """
        Update preferences for a specific CRM category.

        Args:
            conn: asyncpg database connection
            email: User email
            category: Category name ('churn_risk', 'ai_insights', etc.)
            preferences: Preference data dict

        Returns:
            Success status dict

        Raises:
            ValueError: If category is invalid
        """
        if category not in self.CATEGORY_COLUMNS:
            raise ValueError(f"Invalid category: {category}. Must be one of {list(self.CATEGORY_COLUMNS.keys())}")

        column_name = self.CATEGORY_COLUMNS[category]

        # Add timestamp
        preferences['last_updated'] = datetime.now(timezone.utc).isoformat()

        try:
            async with conn.transaction():
                # Check if user_preferences row exists
                existing = await conn.fetchrow(
                    "SELECT id FROM user_preferences WHERE email = $1",
                    email
                )

                if existing:
                    # Update specific category column
                    await conn.execute(f"""
                        UPDATE user_preferences
                        SET {column_name} = $1,
                            updated_at = NOW()
                        WHERE email = $2
                    """, preferences, email)
                    logger.info(f"Updated {category} preferences for {email}")
                else:
                    # Insert new row with this category
                    await conn.execute(f"""
                        INSERT INTO user_preferences (email, {column_name})
                        VALUES ($1, $2)
                    """, email, preferences)
                    logger.info(f"Created user_preferences with {category} for {email}")

            return {
                "success": True,
                "category": category,
                "feedback_count": preferences.get('feedback_count', 0)
            }

        except Exception as e:
            logger.error(f"Error updating {category} preference: {e}")
            raise

    async def get_category_preferences(
        self,
        conn: asyncpg.Connection,
        email: str,
        category: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Get category preferences for user.

        Args:
            conn: asyncpg database connection
            email: User email
            category: Specific category name (optional). If None, returns all categories.

        Returns:
            Preferences dict or None if not found
        """
        try:
            if category:
                # Get specific category
                if category not in self.CATEGORY_COLUMNS:
                    raise ValueError(f"Invalid category: {category}")

                column_name = self.CATEGORY_COLUMNS[category]

                result = await conn.fetchrow(f"""
                    SELECT {column_name} as preferences
                    FROM user_preferences
                    WHERE email = $1
                """, email)

                if not result or not result['preferences']:
                    return None

                return result['preferences']
            else:
                # Get all categories
                result = await conn.fetchrow("""
                    SELECT
                        crm_pref_churn_risk,
                        crm_pref_ai_insights,
                        crm_pref_stage_progression,
                        crm_pref_deal_insights
                    FROM user_preferences
                    WHERE email = $1
                """, email)

                if not result:
                    return None

                # Return dict with all categories
                all_prefs = {
                    'churn_risk': result['crm_pref_churn_risk'] or {},
                    'ai_insights': result['crm_pref_ai_insights'] or {},
                    'stage_progression': result['crm_pref_stage_progression'] or {},
                    'deal_insights': result['crm_pref_deal_insights'] or {}
                }

                # Return None if all categories are empty
                if all(not prefs for prefs in all_prefs.values()):
                    return None

                return all_prefs

        except Exception as e:
            logger.error(f"Error getting category preferences: {e}")
            raise

    async def delete_category_preference(
        self,
        conn: asyncpg.Connection,
        email: str,
        category: str
    ) -> bool:
        """
        Delete (reset) preference for a specific category.
        Sets the column to empty JSONB object.

        Args:
            conn: asyncpg database connection
            email: User email
            category: Category name to reset

        Returns:
            True if deleted, False if user not found
        """
        if category not in self.CATEGORY_COLUMNS:
            raise ValueError(f"Invalid category: {category}")

        column_name = self.CATEGORY_COLUMNS[category]

        try:
            result = await conn.fetchrow(f"""
                UPDATE user_preferences
                SET {column_name} = '{{}}'::jsonb,
                    updated_at = NOW()
                WHERE email = $1
                RETURNING id
            """, email)

            if result:
                logger.info(f"Reset {category} preferences for {email}")
                return True
            else:
                logger.warning(f"User not found: {email}")
                return False

        except Exception as e:
            logger.error(f"Error deleting {category} preference: {e}")
            raise
