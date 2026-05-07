"""
Pydantic models for CSV mapping library.
Defines core data models and library-specific response models.
"""

from typing import List, Optional, Dict, Any, Literal, Union
from pydantic import BaseModel, Field, validator
from enum import Enum
from datetime import datetime, timezone


class MappingType(str, Enum):
    """Types of column mapping."""
    EXACT = "exact"
    PATTERN = "pattern"
    AI = "ai"
    MANUAL = "manual"
    SEMANTIC = "semantic_ai"


class SuggestedAction(str, Enum):
    """Suggested actions for mappings."""
    AUTO = "auto"
    REVIEW = "review"
    MANUAL = "manual"


class UploadMode(str, Enum):
    """Upload modes for progressive disclosure."""
    QUICK = "quick"
    ADVANCED = "advanced"


class RecommendedFlow(str, Enum):
    """Recommended workflow based on analysis."""
    QUICK_UPLOAD = "quick_upload"
    SHOW_MAPPING_UI = "show_mapping_ui"
    REQUIRE_REVIEW = "require_review"


class DatabaseConfig(BaseModel):
    """Database connection configuration for multi-database support."""
    connection_string: str
    schema_name: str = "public"
    service_type: str = "generic"  # 'employee', 'crm', 'lead-gen'
    database_type: str = "postgresql"  # Future: 'mysql', 'sqlite'
    pool_size: int = 5
    timeout_seconds: int = 30


class PreviewConfig(BaseModel):
    """Configurable preview settings for data analysis."""
    sample_size: int = 25
    include_nulls: bool = True
    max_unique_values: int = 50
    show_data_types: bool = True
    analyze_patterns: bool = True
    max_string_preview: int = 100


class MappingConfig(BaseModel):
    """Configuration for mapping behavior and AI integration."""
    service_context: str = "generic"  # Domain context for AI
    confidence_threshold: float = 0.7
    use_ai_fallback: bool = True
    enable_semantic_matching: bool = True
    max_ai_retries: int = 1  # Reduced from 2 to 1 for faster failure
    ai_model: str = "gpt-4.1-mini"


class ColumnAnalysis(BaseModel):
    """Analysis of a source column."""
    name: str
    detected_type: str
    pandas_type: str
    sample_values: List[Any]
    null_percentage: float
    unique_count: int
    confidence_score: float
    data_quality_issues: List[str] = []
    original_position: int = Field(default=0, description="Original column position in CSV (0-indexed)")


class TableColumn(BaseModel):
    """Target table column schema."""
    name: str
    type: str
    nullable: bool = True
    description: Optional[str] = None
    constraints: List[str] = []


class TableSchema(BaseModel):
    """Target table schema information."""
    table_name: str
    columns: List[TableColumn]
    exists: bool
    row_count: Optional[int] = None


class MappingRule(BaseModel):
    """Column mapping rule with confidence and reasoning."""
    source_column: str
    target_column: Optional[str]
    confidence: float = Field(..., ge=0, le=100)
    mapping_type: MappingType
    suggested_action: SuggestedAction
    reasoning: Optional[str] = None


class DataIssue(BaseModel):
    """Data quality issue."""
    type: str  # 'null_values', 'type_mismatch', 'encoding_error', 'format_inconsistency'
    column: str
    description: str
    count: int
    percentage: float
    severity: Literal["low", "medium", "high"]
    suggested_action: Optional[str] = None


class PreviewStats(BaseModel):
    """Statistics about the preview data sample."""
    total_rows_analyzed: int
    columns_mapped: int
    columns_unmapped: int
    null_percentage: float
    unique_values_per_column: Dict[str, int]
    detected_patterns: Dict[str, str] = {}


class AnalysisOptions(BaseModel):
    """Options for file analysis."""
    target_table: Optional[str] = None
    database_config: Optional[DatabaseConfig] = None
    mapping_config: Optional[MappingConfig] = None
    preview_config: Optional[PreviewConfig] = None
    
    @validator('database_config', pre=True, always=True)
    def set_default_database_config(cls, v):
        return v or DatabaseConfig(connection_string="")
    
    @validator('mapping_config', pre=True, always=True)
    def set_default_mapping_config(cls, v):
        return v or MappingConfig()
    
    @validator('preview_config', pre=True, always=True)
    def set_default_preview_config(cls, v):
        return v or PreviewConfig()


class AnalysisResult(BaseModel):
    """Result from file analysis with mapping recommendations."""
    success: bool
    upload_mode: Optional[UploadMode] = None
    source_columns: List[ColumnAnalysis] = []
    existing_table_info: Optional[TableSchema] = None
    mapping_suggestions: List[MappingRule] = []
    missing_columns: List[str] = []  # In table but not in CSV
    new_columns: List[str] = []  # In CSV but not in table
    overall_confidence: float = 0.0
    recommended_flow: Optional[RecommendedFlow] = None
    analysis_metadata: Dict[str, Any] = {}
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PreviewOptions(BaseModel):
    """Options for mapping preview."""
    user_mappings: Dict[str, str]
    preview_config: Optional[PreviewConfig] = None
    include_data_quality: bool = True
    
    @validator('preview_config', pre=True, always=True)
    def set_default_preview_config(cls, v):
        return v or PreviewConfig()


class PreviewResult(BaseModel):
    """Result from mapping preview."""
    success: bool
    preview_data: List[Dict[str, Any]] = []
    mapping_summary: Dict[str, str] = {}
    data_issues: List[DataIssue] = []
    ready_for_upload: bool = False
    preview_stats: Optional[PreviewStats] = None
    data_quality_score: float = 0.0  # 0-100 based on issues found
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FileMetadata(BaseModel):
    """Metadata about uploaded file."""
    filename: str
    size_bytes: int
    encoding: str
    row_count: int
    column_count: int
    detected_separator: str = ","
    has_header: bool = True


class MappingSession(BaseModel):
    """Mapping session state for tracking the entire mapping workflow."""
    session_id: str
    file_metadata: FileMetadata
    analysis_result: Optional[AnalysisResult] = None
    preview_result: Optional[PreviewResult] = None
    upload_result: Optional["UploadResult"] = None
    user_mappings: Dict[str, str] = {}
    status: Literal["initialized", "analyzed", "previewed", "uploaded", "failed"] = "initialized"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def update_status(self, new_status: str) -> None:
        """Update session status and timestamp."""
        self.status = new_status
        self.updated_at = datetime.now(timezone.utc)


class UploadOptions(BaseModel):
    """Options for data upload."""
    user_mappings: Dict[str, str]
    target_table: str
    database_config: DatabaseConfig
    batch_size: int = 1000
    create_table_if_not_exists: bool = True
    truncate_before_insert: bool = False
    validate_data: bool = True
    skip_duplicates: bool = False


class UploadResult(BaseModel):
    """Result from data upload operation."""
    success: bool
    rows_processed: int = 0
    rows_inserted: int = 0
    rows_updated: int = 0
    rows_skipped: int = 0
    table_created: bool = False
    execution_time_seconds: float = 0.0
    error_message: Optional[str] = None
    validation_errors: List[DataIssue] = []
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ValidationResult(BaseModel):
    """Result from data validation."""
    is_valid: bool
    total_rows: int
    valid_rows: int
    invalid_rows: int
    validation_issues: List[DataIssue] = []
    quality_score: float = 0.0  # 0-100
    recommendations: List[str] = []
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LibraryError(BaseModel):
    """Error information from library operations."""
    error_type: str
    message: str
    details: Optional[str] = None
    error_code: Optional[str] = None
    context: Dict[str, Any] = {}
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OperationStatus(BaseModel):
    """Status of long-running operations."""
    operation_id: str
    status: Literal["pending", "running", "completed", "failed"]
    progress_percentage: float = 0.0
    current_step: Optional[str] = None
    total_steps: Optional[int] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[Union[AnalysisResult, PreviewResult, UploadResult]] = None
    error: Optional[LibraryError] = None


class MappingWorkflow(BaseModel):
    """Complete workflow configuration for CSV mapping."""
    file_path: str
    analysis_options: AnalysisOptions
    preview_options: Optional[PreviewOptions] = None
    upload_options: Optional[UploadOptions] = None
    auto_execute: bool = False  # If True, runs full workflow automatically
    validation_enabled: bool = True
    
    
class WorkflowResult(BaseModel):
    """Complete result from a mapping workflow execution."""
    success: bool
    workflow_id: str
    session: MappingSession
    steps_completed: List[str] = []
    total_execution_time: float = 0.0
    final_status: str
    summary: Dict[str, Any] = {}
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SchemaInfo(BaseModel):
    """Extended schema information for database integration."""
    database_name: str
    schema_name: str
    tables: List[TableSchema]
    supported_types: List[str] = []
    constraints: Dict[str, Any] = {}
    indexes: Dict[str, List[str]] = {}
    foreign_keys: Dict[str, Dict[str, str]] = {}
    

class DataTypeMapping(BaseModel):
    """Mapping between pandas/CSV types and database types."""
    pandas_type: str
    database_type: str
    nullable: bool = True
    max_length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None
    constraints: List[str] = []