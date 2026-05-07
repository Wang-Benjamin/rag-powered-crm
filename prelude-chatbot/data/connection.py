"""Database connection management for Chat Service."""

import logging
from typing import Dict
import psycopg2
from psycopg2.pool import SimpleConnectionPool
import threading

logger = logging.getLogger(__name__)


class PooledConnectionWrapper:
    """Wrapper for database connections that stores pool configuration."""

    def __init__(self, conn, pool_config: dict, pool_manager):
        self._conn = conn
        self._pool_config = pool_config
        self._pool_manager = pool_manager
        self._returned = False

    def __getattr__(self, name):
        """Delegate all attribute access to the wrapped connection."""
        return getattr(self._conn, name)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False

    def close(self):
        """Return connection to pool instead of closing it."""
        if not self._returned:
            self._returned = True
            logger.debug(f"Returning connection to pool for database: {self._pool_config.get('database', 'unknown')}")
            try:
                self._pool_manager.return_connection(self._pool_config, self._conn)
            except Exception as e:
                logger.warning(f"Could not return connection to pool: {e}, closing connection instead")
                try:
                    self._conn.close()
                except:
                    pass


class DatabaseConnectionPool:
    """Multi-database connection pool manager."""

    def __init__(self):
        self._pools: Dict[str, SimpleConnectionPool] = {}
        self._pools_lock = threading.Lock()

    def _get_pool_key(self, config: dict) -> str:
        """Generate unique key for connection pool based on database config."""
        return f"{config.get('host')}:{config.get('port')}/{config.get('database')}"

    def _create_pool(self, config: dict) -> SimpleConnectionPool:
        """Create a new connection pool for the given database config."""
        pool = SimpleConnectionPool(
            5, 50,
            host=config.get('host'),
            port=config.get('port'),
            user=config.get('user'),
            password=config.get('password'),
            database=config.get('database'),
            connect_timeout=10,
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=5
        )
        logger.info(f"Created connection pool for database: {config.get('database')}")
        return pool

    def get_connection(self, config: dict):
        """Get a connection from the pool for the specified database config."""
        pool_key = self._get_pool_key(config)

        with self._pools_lock:
            if pool_key not in self._pools:
                self._pools[pool_key] = self._create_pool(config)

        pool = self._pools[pool_key]
        conn = pool.getconn()

        # Validate connection
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            logger.debug(f"Acquired connection from pool for database: {config.get('database')}")
            return PooledConnectionWrapper(conn, config, self)
        except Exception as e:
            logger.error(f"Connection validation failed: {e}")
            try:
                conn.close()
            except:
                pass
            raise

    def return_connection(self, config: dict, conn):
        """Return a connection to the pool."""
        actual_conn = conn._conn if isinstance(conn, PooledConnectionWrapper) else conn
        pool_key = self._get_pool_key(config)

        if pool_key in self._pools:
            pool = self._pools[pool_key]
            try:
                pool.putconn(actual_conn)
            except Exception as e:
                logger.warning(f"Could not return connection to pool ({e}), closing instead")
                try:
                    actual_conn.close()
                except:
                    pass

    def close_all(self):
        """Close all connection pools."""
        with self._pools_lock:
            for pool_key, pool in self._pools.items():
                try:
                    pool.closeall()
                    logger.info(f"Closed connection pool: {pool_key}")
                except Exception as e:
                    logger.error(f"Error closing pool {pool_key}: {e}")
            self._pools.clear()


# Global database connection pool manager
global_connection_pool = DatabaseConnectionPool()
