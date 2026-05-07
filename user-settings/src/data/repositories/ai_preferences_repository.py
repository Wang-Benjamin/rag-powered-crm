"""
AI Preferences Repository
Handles all database operations for user AI preferences.
All methods take an asyncpg connection as the first parameter.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AIPreferencesRepository:
    """Repository for AI preferences database operations."""

    @staticmethod
    async def save_preferences(
        conn,
        email: str,
        tone_dict: dict,
        guardrails_dict: dict,
        audience_dict: dict,
        additional_context_dict: dict,
        ai_summary: dict
    ) -> dict:
        """Save or update user AI preferences."""
        existing = await conn.fetchrow(
            "SELECT id FROM user_preferences WHERE email = $1", email
        )

        if existing:
            await conn.fetchrow(
                """
                UPDATE user_preferences
                SET tone = $1, guardrails = $2, audience = $3,
                    additional_context = $4, ai_summary = $5,
                    is_complete = true, updated_at = NOW()
                WHERE email = $6
                RETURNING id
                """,
                tone_dict, guardrails_dict,
                audience_dict, additional_context_dict,
                json.dumps(ai_summary), email
            )
            logger.info(f"Updated existing preferences for {email}")
        else:
            await conn.fetchrow(
                """
                INSERT INTO user_preferences (
                    email, tone, guardrails, audience, additional_context,
                    ai_summary, is_complete
                )
                VALUES ($1, $2, $3, $4, $5, $6, true)
                RETURNING id
                """,
                email, tone_dict, guardrails_dict,
                audience_dict, additional_context_dict,
                json.dumps(ai_summary)
            )
            logger.info(f"Created new preferences for {email}")

        return {
            "success": True,
            "preferences": {
                "tone": tone_dict,
                "guardrails": guardrails_dict,
                "audience": audience_dict,
                "additional_context": additional_context_dict,
                "ai_summary": ai_summary
            }
        }

    @staticmethod
    async def get_preferences(conn, email: str) -> Optional[dict]:
        """Get user AI preferences by email."""
        result = await conn.fetchrow(
            """
            SELECT tone, guardrails, audience, additional_context, ai_summary,
                   is_complete, created_at, updated_at
            FROM user_preferences WHERE email = $1
            """,
            email
        )

        if not result:
            return None

        return {
            "tone": result['tone'],
            "guardrails": result['guardrails'],
            "audience": result['audience'],
            "additional_context": result['additional_context'],
            "ai_summary": result['ai_summary'],
            "is_complete": result['is_complete'],
            "created_at": result['created_at'].isoformat() if result['created_at'] else None,
            "updated_at": result['updated_at'].isoformat() if result['updated_at'] else None
        }

    @staticmethod
    async def delete_preferences(conn, email: str) -> bool:
        """Clear AI-specific columns without deleting the row (preserves factory profile data)."""
        result = await conn.fetchrow(
            "UPDATE user_preferences SET tone = NULL, guardrails = NULL, audience = NULL, "
            "additional_context = NULL, ai_summary = NULL, is_complete = false, "
            "updated_at = NOW() WHERE email = $1 RETURNING id",
            email
        )
        return result is not None
