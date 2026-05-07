"""Prelude CSV Mapping Library

AI-powered intelligent column mapping for database uploads.
"""

__version__ = "1.0.0"

# Core functionality exports
from .core.mapping_engine import DynamicMappingEngine
from .core.file_analyzer import FileAnalyzer
from .core.schema_service import SchemaService
from .core.ai_service import AIServiceManager, create_ai_service
from .core.mismatch_advisor import LLMColumnAdvisor, create_llm_column_advisor

# Model exports
from .models.mapping_models import (
    MappingRule, ColumnAnalysis, DatabaseConfig, 
    MappingConfig, PreviewConfig, MappingType,
    SuggestedAction, UploadMode, RecommendedFlow,
    TableColumn, TableSchema, DataIssue, FileMetadata,
    AnalysisOptions, AnalysisResult, PreviewOptions, PreviewResult,
    UploadOptions, UploadResult, MappingWorkflow, WorkflowResult,
    ValidationResult, LibraryError, SchemaInfo, DataTypeMapping,
    MappingSession, OperationStatus
)
from .models.mismatch_models import (
    MismatchType, Severity, ColumnMismatchRecommendation, BusinessContext
)

# Utility exports
from .utils.confidence_scorer import ConfidenceScorer
from .utils.type_detector import TypeDetector

import asyncio
import logging
import pandas as pd
from typing import Union, Dict, List, Optional, Any
from pathlib import Path


class CSVMapper:
    """High-level interface for CSV mapping operations.
    
    This class provides a simplified interface for common CSV mapping workflows,
    combining the functionality of FileAnalyzer, SchemaService, and MappingEngine.
    """
    
    def __init__(
        self, 
        database_url: Union[str, DatabaseConfig], 
        ai_config: Optional[Dict[str, Any]] = None,
        schema_name: Optional[str] = None,
        service_type: str = "library"
    ):
        """Initialize CSVMapper with database connection and optional AI config.
        
        Args:
            database_url: Database connection string or DatabaseConfig object
            ai_config: Optional AI configuration dict with keys like 'openai_api_key'
            schema_name: Database schema name (default: 'public' for PostgreSQL)
            service_type: Service context for mapping optimization
        """
        self.logger = logging.getLogger(__name__)
        
        # Initialize core services
        if isinstance(database_url, str):
            self.db_config = DatabaseConfig(
                connection_string=database_url,
                schema_name=schema_name or "public",
                service_type=service_type
            )
        else:
            self.db_config = database_url
            
        self.schema_service = SchemaService(connection=self.db_config)
        
        # Initialize AI service if config provided
        self.ai_service = None
        if ai_config:
            self.ai_service = create_ai_service(**ai_config)
        
        # Initialize mapping engine
        mapping_config = MappingConfig(
            service_context=service_type,
            use_ai_fallback=ai_config is not None
        )
        self.mapping_engine = DynamicMappingEngine(
            config=mapping_config,
            ai_service=self.ai_service
        )
    
    def analyze_file(
        self, 
        file_input: Union[str, Path, pd.DataFrame],
        filename: Optional[str] = None,
        target_table: Optional[str] = None
    ) -> AnalysisResult:
        """Analyze CSV file and suggest mappings.
        
        Args:
            file_input: File path, DataFrame, or file-like object
            filename: Optional filename for DataFrame inputs
            target_table: Specific target table to map to
            
        Returns:
            AnalysisResult with DataFrame, metadata, mappings, and suggestions
        """
        try:
            # Analyze the file
            if isinstance(file_input, pd.DataFrame):
                df = file_input
                metadata = FileMetadata(
                    filename=filename or "dataframe.csv",
                    size_bytes=df.memory_usage(deep=True).sum(),
                    encoding="utf-8",  # Default for DataFrame
                    row_count=len(df),
                    column_count=len(df.columns)
                )
            else:
                df, metadata = FileAnalyzer.analyze_file(file_input, filename)
            
            # Get database schema
            if target_table:
                # First check if target table exists
                available_tables = self.schema_service.list_tables()
                if target_table not in available_tables:
                    return AnalysisResult(
                        success=False,
                        error_message=f"Target table '{target_table}' does not exist. Available tables: {', '.join(available_tables)}"
                    )
                table_schema = self.schema_service.get_table_schema(target_table)
            else:
                # For new table creation, no target schema needed
                table_schema = None
            
            # Build source columns analysis (needed for mapping engine)
            source_column_analyses = []
            for col in df.columns:
                dtype = str(df[col].dtype)
                unique_count = df[col].nunique()
                null_percentage = (df[col].isnull().sum() / len(df)) * 100 if len(df) > 0 else 0
                
                source_column_analyses.append(ColumnAnalysis(
                    name=col,
                    detected_type=dtype,
                    pandas_type=dtype,
                    sample_values=df[col].dropna().head(3).tolist(),
                    null_percentage=null_percentage,
                    unique_count=unique_count,
                    confidence_score=0.0  # Will be set by mapping engine
                ))
            
            # Generate mappings if target schema available
            mappings = []
            if table_schema:
                # Use async method for AI-enhanced mapping support
                try:
                    # Run async method in sync context
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    mappings = loop.run_until_complete(
                        self.mapping_engine.analyze_columns(
                            source_column_analyses,
                            table_schema,
                            {'target_table': target_table} if target_table else None
                        )
                    )
                    loop.close()
                except Exception as e:
                    self.logger.warning(f"AI-enhanced mapping failed, falling back to sync: {e}")
                    # Fallback to sync method
                    mappings = self.mapping_engine.analyze_columns_sync(
                        source_column_analyses,
                        table_schema,
                        {'target_table': target_table} if target_table else None
                    )
            
            # Use the source columns analysis we already built
            source_columns = source_column_analyses
            
            # Calculate overall confidence (0-100 range from library, convert to 0-1 for backend)
            overall_confidence = 0.0
            if mappings:
                mapped_columns = [m for m in mappings if m.target_column]
                if mapped_columns:
                    confidence_sum = sum(m.confidence for m in mapped_columns)
                    overall_confidence = (confidence_sum / len(mapped_columns)) / 100.0
                else:
                    overall_confidence = 0.0
            elif not target_table:
                # For new table creation, show high confidence since we're using columns as-is
                overall_confidence = 0.95
            else:
                # For existing tables with no good mappings, provide minimal confidence
                # This indicates the table exists but column matching is poor
                if table_schema and table_schema.columns:
                    # Some basic heuristic: if we have same number of columns, give minimal confidence
                    source_col_count = len(source_column_analyses)
                    target_col_count = len(table_schema.columns)
                    if source_col_count == target_col_count:
                        overall_confidence = 0.15  # 15% confidence for structural match
                    else:
                        overall_confidence = 0.05  # 5% confidence for size mismatch
            
            # Use the table schema we already fetched
            existing_table_info = table_schema
            
            # Determine recommended flow
            if overall_confidence >= 0.90:
                recommended_flow = RecommendedFlow.QUICK_UPLOAD
            elif overall_confidence >= 0.50:
                recommended_flow = RecommendedFlow.SHOW_MAPPING_UI
            else:
                recommended_flow = RecommendedFlow.REQUIRE_REVIEW
            
            # Identify missing and new columns
            if table_schema:
                target_col_names = [tc.name for tc in table_schema.columns]
                source_col_names = df.columns.tolist()
                missing_columns = [col for col in target_col_names if col not in source_col_names]
                new_columns = [col for col in source_col_names if col not in target_col_names]
            else:
                missing_columns = []
                new_columns = df.columns.tolist()
            
            return AnalysisResult(
                success=True,
                upload_mode=UploadMode.QUICK if overall_confidence >= 0.90 else UploadMode.ADVANCED,
                source_columns=source_columns,
                existing_table_info=existing_table_info,
                mapping_suggestions=mappings,
                missing_columns=missing_columns,
                new_columns=new_columns,
                overall_confidence=overall_confidence,
                recommended_flow=recommended_flow,
                analysis_metadata={
                    'filename': metadata.filename,
                    'row_count': metadata.row_count,
                    'column_count': metadata.column_count,
                    'encoding': metadata.encoding,
                    'file_size': metadata.size_bytes,
                    'available_tables': self.schema_service.list_tables()  # Populate with actual available tables
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing file: {e}")
            return AnalysisResult(
                success=False,
                error_message=str(e)
            )
    
    def apply_mappings(
        self, 
        df: pd.DataFrame, 
        mappings: List[MappingRule],
        validate_data: bool = True
    ) -> pd.DataFrame:
        """Apply column mappings to dataframe.
        
        Args:
            df: Source DataFrame
            mappings: List of mapping rules to apply
            validate_data: Whether to validate data during mapping
            
        Returns:
            Mapped DataFrame with target column names
        """
        try:
            mapped_df = df.copy()
            
            # Create mapping dictionary
            column_map = {}
            for rule in mappings:
                if rule.source_column in df.columns and rule.target_column:
                    column_map[rule.source_column] = rule.target_column
            
            # Apply column renaming
            if column_map:
                mapped_df = mapped_df.rename(columns=column_map)
            
            # Validate data if requested
            if validate_data:
                self._validate_mapped_data(mapped_df, mappings)
            
            return mapped_df
            
        except Exception as e:
            self.logger.error(f"Error applying mappings: {e}")
            raise
    
    def create_workflow(
        self, 
        file_input: Union[str, Path, pd.DataFrame],
        target_table: str,
        upload_mode: UploadMode = UploadMode.QUICK
    ) -> MappingWorkflow:
        """Create a complete mapping workflow.
        
        Args:
            file_input: Source file or DataFrame
            target_table: Target database table
            upload_mode: How to handle data upload
            
        Returns:
            MappingWorkflow object configured for the operation
        """
        return MappingWorkflow(
            source_file=str(file_input) if not isinstance(file_input, pd.DataFrame) else "dataframe",
            target_table=target_table,
            database_config=self.db_config,
            upload_mode=upload_mode,
            ai_enabled=self.ai_service is not None
        )
    
    def execute_workflow(self, workflow: MappingWorkflow) -> WorkflowResult:
        """Execute a complete mapping workflow.
        
        Args:
            workflow: Configured MappingWorkflow
            
        Returns:
            WorkflowResult with execution status and results
        """
        try:
            # This would implement the full workflow execution
            # For now, return a basic result structure
            return WorkflowResult(
                success=True,
                workflow_id=workflow.workflow_id,
                message="Workflow execution not yet implemented"
            )
        except Exception as e:
            self.logger.error(f"Error executing workflow: {e}")
            return WorkflowResult(
                success=False,
                workflow_id=workflow.workflow_id,
                error=str(e),
                message="Workflow execution failed"
            )
    
    def get_database_info(self) -> Dict[str, Any]:
        """Get information about the connected database.
        
        Returns:
            Dictionary with database connection info and available tables
        """
        try:
            return {
                "connection_info": self.schema_service.get_connection_info(),
                "available_tables": self.schema_service.list_tables(),
                "schema_name": self.db_config.schema_name,
                "ai_available": self.ai_service.is_any_ai_available() if self.ai_service else False
            }
        except Exception as e:
            self.logger.error(f"Error getting database info: {e}")
            return {"error": str(e)}
    
    def test_connection(self) -> bool:
        """Test database connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            return self.schema_service.test_connection()
        except Exception:
            return False
    
    def close(self):
        """Close database connections and cleanup resources."""
        try:
            if hasattr(self, 'schema_service'):
                self.schema_service.close_connections()
        except Exception as e:
            self.logger.error(f"Error closing connections: {e}")
    
    def _validate_mapped_data(self, df: pd.DataFrame, mappings: List[MappingRule]):
        """Validate mapped data against target schema."""
        # Basic validation - could be expanded
        for rule in mappings:
            if rule.target_column in df.columns:
                # Check for required columns, data types, etc.
                pass
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.close()


# Export main classes
__all__ = [
    # Main interface
    'CSVMapper',
    
    # Core classes
    'DynamicMappingEngine', 'FileAnalyzer', 'SchemaService', 'AIServiceManager', 'LLMColumnAdvisor',
    
    # Data models - mapping
    'MappingRule', 'ColumnAnalysis', 'DatabaseConfig', 'MappingConfig', 'PreviewConfig',
    'MappingType', 'SuggestedAction', 'UploadMode', 'RecommendedFlow',
    'TableColumn', 'TableSchema', 'DataIssue', 'FileMetadata',
    'AnalysisOptions', 'AnalysisResult', 'PreviewOptions', 'PreviewResult',
    'UploadOptions', 'UploadResult', 'MappingWorkflow', 'WorkflowResult',
    'ValidationResult', 'LibraryError', 'SchemaInfo', 'DataTypeMapping',
    'MappingSession', 'OperationStatus',
    
    # Data models - mismatch analysis
    'MismatchType', 'Severity', 'ColumnMismatchRecommendation', 'BusinessContext',
    
    # Utilities
    'ConfidenceScorer', 'TypeDetector',
    
    # Factory functions
    'create_ai_service', 'create_llm_column_advisor'
]