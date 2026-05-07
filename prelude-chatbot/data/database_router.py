#!/usr/bin/env python3
"""
Database Router Utility for Chat Service
=========================================

Routes database connections based on user email by querying user_profiles table.
"""

import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any, Optional
import urllib.parse as urlparse
import time

logger = logging.getLogger(__name__)

# Cache settings
CACHE_TTL = 300  # 5 minutes
_cache = {}
_cache_timestamps = {}


class DatabaseRouter:
    """Handles email-based database routing."""

    def __init__(self):
        """Initialize the database router."""
        self.user_management_config = self._get_user_management_db_config()
        self.base_db_config = self._get_base_db_config()

    def _get_user_management_db_config(self) -> Dict[str, Any]:
        """Get configuration for the user management database."""
        database_url = os.getenv('DATABASE_URL')

        if database_url:
            parsed = urlparse.urlparse(database_url)
            return {
                'host': parsed.hostname,
                'port': parsed.port or 5432,
                'user': parsed.username,
                'password': parsed.password,
                'database': 'prelude_user_analytics'
            }
        else:
            return {
                'host': os.getenv('SESSIONS_DB_HOST'),
                'port': int(os.getenv('SESSIONS_DB_PORT', '5432')),
                'user': os.getenv('SESSIONS_DB_USER'),
                'password': os.getenv('SESSIONS_DB_PASSWORD'),
                'database': 'prelude_user_analytics'
            }

    def _get_base_db_config(self) -> Dict[str, Any]:
        """Get base database configuration (without database name)."""
        config = self.user_management_config.copy()
        config.pop('database', None)
        return config

    def _is_cache_valid(self, email: str) -> bool:
        """Check if cached result is still valid."""
        if email not in _cache_timestamps:
            return False
        return (time.time() - _cache_timestamps[email]) < CACHE_TTL

    def _get_cached_result(self, email: str) -> Optional[str]:
        """Get cached database name for email."""
        if self._is_cache_valid(email):
            return _cache.get(email)
        return None

    def _cache_result(self, email: str, database_name: str):
        """Cache the database name for email."""
        _cache[email] = database_name
        _cache_timestamps[email] = time.time()

    def get_database_name_for_user(self, email: str) -> str:
        """Get the database name for a given user email."""
        if not email:
            logger.warning("No email provided, using default database 'postgres'")
            return 'postgres'

        if isinstance(email, dict):
            if 'email' in email:
                email = email['email']
            else:
                logger.error("Dict doesn't contain 'email' key, using default database")
                return 'postgres'

        # Check cache
        cached_result = self._get_cached_result(email)
        if cached_result:
            return cached_result

        conn = None
        try:
            conn = psycopg2.connect(
                host=self.user_management_config['host'],
                port=self.user_management_config['port'],
                user=self.user_management_config['user'],
                password=self.user_management_config['password'],
                database=self.user_management_config['database']
            )

            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT db_name
                FROM user_profiles
                WHERE email = %s
                LIMIT 1
            """, (email,))

            result = cursor.fetchone()
            cursor.close()

            if result and result['db_name']:
                database_name = result['db_name']
                self._cache_result(email, database_name)
                return database_name
            else:
                self._cache_result(email, 'postgres')
                return 'postgres'

        except Exception as e:
            logger.error(f"Failed to query user database for {email}: {e}")
            return 'postgres'
        finally:
            if conn:
                conn.close()

    def get_database_config_for_user(self, email: str) -> Dict[str, Any]:
        """Get complete database configuration for a user."""
        database_name = self.get_database_name_for_user(email)
        config = self.base_db_config.copy()
        config['database'] = database_name
        return config

    def get_database_url_for_user(self, email: str, async_driver: bool = True) -> str:
        """Get database URL for a user.

        Args:
            email: User email to look up
            async_driver: If True, use asyncpg driver (for DatabaseSessionService)
        """
        config = self.get_database_config_for_user(email)
        driver = "postgresql+asyncpg" if async_driver else "postgresql"
        return (
            f"{driver}://{config['user']}:{config['password']}"
            f"@{config['host']}:{config['port']}/{config['database']}"
        )

    @staticmethod
    def clear_cache():
        """Clear the database name cache."""
        global _cache, _cache_timestamps
        _cache.clear()
        _cache_timestamps.clear()
        logger.info("Database router cache cleared")


# Global instance
_router_instance = None


def get_database_router() -> DatabaseRouter:
    """Get the global database router instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = DatabaseRouter()
    return _router_instance


# Convenience functions
def get_database_for_user(email: str) -> str:
    """Get database name for a user email."""
    return get_database_router().get_database_name_for_user(email)


def get_database_url_for_user(email: str) -> str:
    """Get database URL for a user email."""
    return get_database_router().get_database_url_for_user(email)


def clear_database_cache():
    """Clear the database routing cache."""
    DatabaseRouter.clear_cache()
