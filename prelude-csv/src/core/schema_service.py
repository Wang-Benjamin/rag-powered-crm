"""
Schema service for database introspection and management.
Refactored for library use with flexible database connection support.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Union
from sqlalchemy import create_engine, MetaData, Table, Column, inspect, text, Engine
from sqlalchemy.exc import SQLAlchemyError
from ..models.mapping_models import DatabaseConfig, TableSchema, TableColumn

logger = logging.getLogger(__name__)


class SchemaService:
    """
    Enhanced schema management with multi-database support.
    
    Supports flexible database connection approaches:
    - Connection strings
    - Pre-configured SQLAlchemy Engine objects
    - DatabaseConfig objects for backwards compatibility
    """
    
    def __init__(
        self, 
        connection: Union[str, Engine, DatabaseConfig],
        schema_name: Optional[str] = None,
        database_type: Optional[str] = None,
        service_type: Optional[str] = None,
        pool_size: int = 5,
        timeout_seconds: int = 30
    ):
        """
        Initialize SchemaService with flexible connection options.
        
        Args:
            connection: Connection string, SQLAlchemy Engine, or DatabaseConfig object
            schema_name: Database schema name (default: "public")
            database_type: Database type ("postgresql", "mysql", "sqlite", etc.)
            service_type: Service context ("nl2sql", "employee", "crm", "lead-gen", etc.)
            pool_size: Connection pool size
            timeout_seconds: Connection timeout
        """
        self.engine = None
        self.metadata = None
        self._connection_pool = None
        self._is_external_engine = False
        
        # Handle different connection types
        if isinstance(connection, Engine):
            self.engine = connection
            self._is_external_engine = True
            self.schema_name = schema_name or "public"
            self.database_type = database_type or self._detect_database_type()
            self.service_type = service_type or "generic"
            
        elif isinstance(connection, str):
            self.connection_string = connection
            self.schema_name = schema_name or "public"
            self.database_type = database_type or self._detect_database_type_from_url(connection)
            self.service_type = service_type or "generic"
            self.pool_size = pool_size
            self.timeout_seconds = timeout_seconds
            
        elif isinstance(connection, DatabaseConfig):
            # Backwards compatibility with DatabaseConfig
            self.config = connection
            self.connection_string = connection.connection_string
            self.schema_name = connection.schema_name
            self.database_type = connection.database_type
            self.service_type = connection.service_type
            self.pool_size = connection.pool_size
            self.timeout_seconds = connection.timeout_seconds
            
        else:
            raise ValueError(
                "connection must be a connection string, SQLAlchemy Engine, or DatabaseConfig object"
            )
    
    def _detect_database_type(self) -> str:
        """Detect database type from existing engine."""
        if self.engine:
            return self.engine.dialect.name
        return "unknown"
    
    def _detect_database_type_from_url(self, connection_string: str) -> str:
        """Detect database type from connection string."""
        connection_string = connection_string.lower()
        if connection_string.startswith('postgresql://') or 'postgresql' in connection_string:
            return "postgresql"
        elif connection_string.startswith('mysql://') or 'mysql' in connection_string:
            return "mysql"
        elif connection_string.startswith('sqlite://') or 'sqlite' in connection_string:
            return "sqlite"
        elif connection_string.startswith('oracle://') or 'oracle' in connection_string:
            return "oracle"
        elif connection_string.startswith('mssql://') or 'sqlserver' in connection_string:
            return "mssql"
        return "unknown"
    
    def get_engine(self):
        """Get or create database engine."""
        if self.engine is None:
            if not hasattr(self, 'connection_string'):
                raise ValueError("No connection string available to create engine")
                
            try:
                # Base engine parameters
                engine_params = {
                    'echo': False  # Set to True for SQL debugging
                }
                
                # Apply pooling parameters only for databases that support them
                if self.database_type in ['postgresql', 'mysql']:
                    engine_params.update({
                        'pool_size': getattr(self, 'pool_size', 5),
                        'pool_timeout': getattr(self, 'timeout_seconds', 30),
                        'pool_pre_ping': True  # Validate connections
                    })
                
                self.engine = create_engine(
                    self.connection_string,
                    **engine_params
                )
                logger.info(f"Database engine created for {getattr(self, 'service_type', 'generic')} ({self.database_type})")
            except Exception as e:
                logger.error(f"Failed to create database engine: {e}")
                raise SQLAlchemyError(f"Database connection failed: {e}") from e
        return self.engine
    
    def validate_connection(self) -> Dict[str, Any]:
        """
        Validate database connection without raising exceptions.
        
        Returns:
            Dictionary with validation results
        """
        try:
            engine = self.get_engine()
            
            with engine.connect() as conn:
                # Simple query to test connection
                result = conn.execute(text("SELECT 1")).fetchone()
                
                if result:
                    return {
                        "valid": True,
                        "database_type": self.database_type,
                        "service_type": getattr(self, 'service_type', 'generic'),
                        "schema": self.schema_name,
                        "engine_info": {
                            "dialect": engine.dialect.name,
                            "driver": getattr(engine.dialect, 'driver', 'unknown'),
                            "pool_size": getattr(engine.pool, 'size', 'N/A')
                        }
                    }
                else:
                    return {
                        "valid": False, 
                        "error": "Connection test query returned no results",
                        "database_type": self.database_type
                    }
                    
        except Exception as e:
            logger.error(f"Database connection validation failed: {e}")
            return {
                "valid": False, 
                "error": str(e),
                "database_type": getattr(self, 'database_type', 'unknown')
            }
    
    def get_table_schema(self, table_name: str) -> Optional[TableSchema]:
        """
        Get detailed schema information for a table.
        
        Args:
            table_name: Name of the table to inspect
            
        Returns:
            TableSchema object or None if table doesn't exist
        """
        try:
            engine = self.get_engine()
            inspector = inspect(engine)
            
            # Check if table exists
            if not inspector.has_table(table_name, schema=self.schema_name):
                return None
            
            # Get column information
            columns_info = inspector.get_columns(table_name, schema=self.schema_name)
            
            columns = []
            for col_info in columns_info:
                column = TableColumn(
                    name=col_info['name'],
                    type=str(col_info['type']),
                    nullable=col_info.get('nullable', True),
                    description=col_info.get('comment'),
                    constraints=[]  # Could be enhanced to include constraints
                )
                columns.append(column)
            
            # Get row count estimate
            row_count = self._get_table_row_count(table_name)
            
            return TableSchema(
                table_name=table_name,
                columns=columns,
                exists=True,
                row_count=row_count
            )
            
        except Exception as e:
            logger.error(f"Failed to get table schema for {table_name}: {e}")
            return None
    
    def list_tables(self, schema_name: Optional[str] = None) -> List[str]:
        """
        List all tables in the database schema.
        
        Args:
            schema_name: Optional schema name override
            
        Returns:
            List of table names
        """
        try:
            engine = self.get_engine()
            inspector = inspect(engine)
            
            schema = schema_name or self.schema_name
            tables = inspector.get_table_names(schema=schema)
            
            return tables
            
        except Exception as e:
            logger.error(f"Failed to list tables: {e}")
            return []
    
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        try:
            engine = self.get_engine()
            inspector = inspect(engine)
            return inspector.has_table(table_name, schema=self.schema_name)
        except Exception as e:
            logger.error(f"Failed to check if table exists: {e}")
            return False
    
    def get_suggested_tables(self, context_hint: str = "") -> List[str]:
        """
        Get suggested tables based on service context.
        
        Args:
            context_hint: Hint about what type of data is being uploaded
            
        Returns:
            List of suggested table names
        """
        all_tables = self.list_tables()
        
        if not context_hint:
            return all_tables
        
        # Context-based table suggestions
        context_patterns = {
            "sales": ["sales", "revenue", "employee", "performance", "territory"],
            "crm": ["customer", "contact", "lead", "account", "deal"],
            "employee": ["employee", "staff", "person", "worker", "team"],
            "lead": ["lead", "prospect", "company", "contact"]
        }
        
        patterns = context_patterns.get(getattr(self, 'service_type', 'generic'), [])
        patterns.extend(context_patterns.get(context_hint.lower(), []))
        
        if not patterns:
            return all_tables
        
        # Score tables based on name similarity
        scored_tables = []
        for table in all_tables:
            score = 0
            table_lower = table.lower()
            
            for pattern in patterns:
                if pattern in table_lower:
                    score += 10
                elif any(word in table_lower for word in pattern.split('_')):
                    score += 5
            
            scored_tables.append((table, score))
        
        # Sort by score and return
        scored_tables.sort(key=lambda x: x[1], reverse=True)
        return [table for table, score in scored_tables if score > 0] + \
               [table for table, score in scored_tables if score == 0]
    
    
    def _get_table_row_count(self, table_name: str) -> Optional[int]:
        """Get approximate row count for a table."""
        try:
            engine = self.get_engine()
            
            if self.database_type == "postgresql":
                # Use PostgreSQL statistics for fast approximate count
                query = text("""
                    SELECT n_tup_ins - n_tup_del AS row_count
                    FROM pg_stat_user_tables 
                    WHERE schemaname = :schema AND relname = :table
                """)
                
                with engine.connect() as conn:
                    result = conn.execute(
                        query, 
                        {"schema": self.schema_name, "table": table_name}
                    ).fetchone()
                    
                    if result and result[0] is not None:
                        return int(result[0])
            
            # Fallback to COUNT query (slower but works for all databases)
            query = text(f"SELECT COUNT(*) FROM {self.schema_name}.{table_name}")
            with engine.connect() as conn:
                result = conn.execute(query).fetchone()
                return int(result[0]) if result else None
                
        except Exception as e:
            logger.warning(f"Failed to get row count for {table_name}: {e}")
            return None
    
    def create_table_from_analysis(
        self, 
        table_name: str, 
        column_analyses: List[Any],  # ColumnAnalysis objects
        if_not_exists: bool = True
    ) -> bool:
        """
        Create a new table based on column analysis.
        
        Args:
            table_name: Name of the table to create
            column_analyses: List of ColumnAnalysis objects
            if_not_exists: Whether to use IF NOT EXISTS clause
            
        Returns:
            True if successful, False otherwise
        """
        try:
            engine = self.get_engine()
            
            # Clean table name
            clean_table_name = self.clean_table_name(table_name)
            
            # Build CREATE TABLE DDL
            columns_ddl = []
            for analysis in column_analyses:
                clean_col_name = self.clean_column_name(analysis.name)
                columns_ddl.append(f"{clean_col_name} {analysis.detected_type}")
            
            if_not_exists_clause = "IF NOT EXISTS" if if_not_exists else ""
            
            ddl = f"""
            CREATE TABLE {if_not_exists_clause} {self.schema_name}.{clean_table_name} (
                {', '.join(columns_ddl)}
            )
            """
            
            with engine.connect() as conn:
                conn.execute(text(ddl))
                conn.commit()
                
            logger.info(f"Successfully created table: {clean_table_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create table {table_name}: {e}")
            return False
    
    def add_missing_columns(
        self, 
        table_name: str, 
        column_analyses: List[Any]  # ColumnAnalysis objects
    ) -> Dict[str, Any]:
        """
        Add missing columns to an existing table.
        
        Args:
            table_name: Name of the existing table
            column_analyses: List of ColumnAnalysis objects for new columns
            
        Returns:
            Dictionary with results
        """
        try:
            engine = self.get_engine()
            existing_schema = self.get_table_schema(table_name)
            
            if not existing_schema:
                return {"success": False, "error": "Table does not exist"}
            
            existing_columns = {col.name for col in existing_schema.columns}
            added_columns = []
            
            with engine.connect() as conn:
                for analysis in column_analyses:
                    clean_col_name = self.clean_column_name(analysis.name)
                    
                    if clean_col_name not in existing_columns:
                        alter_sql = text(f"""
                            ALTER TABLE {self.schema_name}.{table_name} 
                            ADD COLUMN IF NOT EXISTS {clean_col_name} {analysis.detected_type}
                        """)
                        
                        conn.execute(alter_sql)
                        added_columns.append(clean_col_name)
                        logger.info(f"Added column: {clean_col_name} ({analysis.detected_type})")
                
                conn.commit()
            
            return {
                "success": True,
                "added_columns": added_columns,
                "count": len(added_columns)
            }
            
        except Exception as e:
            logger.error(f"Failed to add columns to {table_name}: {e}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def clean_table_name(table_name: str) -> str:
        """Clean table name for database compatibility."""
        # Convert to lowercase
        clean = str(table_name).lower()
        
        # Replace special characters with underscores
        clean = re.sub(r'[^a-z0-9_]', '_', clean)
        
        # Remove multiple consecutive underscores
        clean = re.sub(r'_+', '_', clean)
        
        # Remove leading/trailing underscores
        clean = clean.strip('_')
        
        # Ensure it starts with a letter
        if clean and not clean[0].isalpha():
            clean = 'table_' + clean
        
        # Ensure it's not empty
        if not clean:
            clean = 'unnamed_table'
        
        return clean
    
    @staticmethod
    def clean_column_name(column_name: str) -> str:
        """Clean column name for database compatibility."""
        # Convert to lowercase
        clean = str(column_name).lower()
        
        # Replace special characters with underscores
        clean = re.sub(r'[^a-z0-9_]', '_', clean)
        
        # Remove multiple consecutive underscores
        clean = re.sub(r'_+', '_', clean)
        
        # Remove leading/trailing underscores
        clean = clean.strip('_')
        
        # Ensure it starts with a letter or underscore
        if clean and not (clean[0].isalpha() or clean[0] == '_'):
            clean = 'col_' + clean
        
        # Ensure it's not empty
        if not clean:
            clean = 'unnamed_column'
        
        # Avoid reserved words (basic list)
        reserved_words = {
            'select', 'from', 'where', 'group', 'order', 'by', 
            'insert', 'update', 'delete', 'create', 'drop', 'alter',
            'table', 'index', 'view', 'database', 'schema'
        }
        
        if clean.lower() in reserved_words:
            clean = clean + '_col'
        
        return clean
    
    def test_connection(self) -> Dict[str, Any]:
        """Test database connection and return status (legacy method, use validate_connection instead)."""
        result = self.validate_connection()
        return {
            "success": result["valid"],
            "database_type": result.get("database_type"),
            "service_type": result.get("service_type"),
            "schema": result.get("schema"),
            "error": result.get("error")
        }
    
    def close_connections(self):
        """Close database connections."""
        if self.engine and not self._is_external_engine:
            # Only dispose engine if we created it ourselves
            self.engine.dispose()
            self.engine = None
            logger.info("Database connections closed")
        elif self._is_external_engine:
            # Don't dispose external engines, just clear reference
            self.engine = None
            logger.info("External engine reference cleared")
    
    def get_connection_info(self) -> Dict[str, Any]:
        """
        Get information about the current database connection.
        
        Returns:
            Dictionary with connection details
        """
        info = {
            "database_type": getattr(self, 'database_type', 'unknown'),
            "service_type": getattr(self, 'service_type', 'generic'),
            "schema_name": getattr(self, 'schema_name', 'public'),
            "is_external_engine": self._is_external_engine,
            "engine_created": self.engine is not None
        }
        
        if hasattr(self, 'connection_string'):
            # Don't expose sensitive connection details, just the basic info
            info["has_connection_string"] = True
        
        if self.engine:
            info["engine_dialect"] = self.engine.dialect.name
            info["engine_driver"] = getattr(self.engine.dialect, 'driver', 'unknown')
            
        return info
    
    @classmethod
    def from_connection_string(
        cls, 
        connection_string: str, 
        schema_name: str = "public",
        **kwargs
    ):
        """
        Create SchemaService from connection string.
        
        Args:
            connection_string: Database connection string
            schema_name: Schema name
            **kwargs: Additional parameters for initialization
            
        Returns:
            SchemaService instance
        """
        return cls(
            connection=connection_string,
            schema_name=schema_name,
            **kwargs
        )
    
    @classmethod
    def from_engine(
        cls, 
        engine: Engine, 
        schema_name: str = "public",
        **kwargs
    ):
        """
        Create SchemaService from SQLAlchemy Engine.
        
        Args:
            engine: SQLAlchemy Engine object
            schema_name: Schema name
            **kwargs: Additional parameters for initialization
            
        Returns:
            SchemaService instance
        """
        return cls(
            connection=engine,
            schema_name=schema_name,
            **kwargs
        )