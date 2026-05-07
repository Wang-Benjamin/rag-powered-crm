from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone
from enum import Enum

class DataSourceType(str, Enum):
    """Types of data sources available for orchestration"""
    YELLOWPAGES = "yellowpages"
    LINKEDIN = "linkedin"
    PERPLEXITY = "perplexity"
    GOOGLEMAPS = "googlemaps"
    CRM_INTEGRATION = "crm_integration"
    EMAIL_GENERATION = "email_generation"
    CUSTOM_API = "custom_api"
    WEB_SCRAPING = "web_scraping"

class ExecutionStrategy(str, Enum):
    """Strategies for executing multiple data sources"""
    SEQUENTIAL = "sequential"  # Execute sources one after another
    PARALLEL = "parallel"     # Execute all sources simultaneously
    PRIORITIZED = "prioritized"  # Execute high-priority sources first
    ADAPTIVE = "adaptive"     # Adapt strategy based on results
    WATERFALL = "waterfall"   # Stop after sufficient data is collected

class ExecutionStatus(str, Enum):
    """Status of orchestrator execution"""
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    MERGING = "merging"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"

class SourcePriority(str, Enum):
    """Priority levels for data sources"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class DataMergeStrategy(str, Enum):
    """Strategies for merging data from multiple sources"""
    UNION = "union"           # Combine all unique records
    INTERSECTION = "intersection"  # Only records found in multiple sources
    PRIORITIZED = "prioritized"   # Prefer data from higher priority sources
    QUALITY_BASED = "quality_based"  # Prefer higher quality data
    CUSTOM_RULES = "custom_rules"    # Use custom merge rules

class QualityThreshold(BaseModel):
    """Quality thresholds for data acceptance"""
    minimum_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Minimum quality score")
    preferred_score: float = Field(default=70.0, ge=0.0, le=100.0, description="Preferred quality score")
    reject_below: float = Field(default=30.0, ge=0.0, le=100.0, description="Reject data below this score")
    
    @validator('preferred_score')
    def preferred_must_be_gte_minimum(cls, v, values):
        if 'minimum_score' in values and v < values['minimum_score']:
            raise ValueError('Preferred score must be >= minimum score')
        return v

class SourceConfiguration(BaseModel):
    """Configuration for a data source in orchestration"""
    source_type: DataSourceType = Field(..., description="Type of data source")
    enabled: bool = Field(default=True, description="Whether source is enabled")
    priority: SourcePriority = Field(default=SourcePriority.MEDIUM, description="Source priority")
    
    # Execution settings
    timeout_seconds: int = Field(default=300, ge=1, le=3600, description="Source timeout")
    retry_count: int = Field(default=3, ge=0, le=10, description="Number of retries")
    retry_delay: float = Field(default=5.0, ge=0.1, le=300.0, description="Retry delay in seconds")
    
    # Quality settings
    quality_threshold: QualityThreshold = Field(default_factory=QualityThreshold, description="Quality thresholds")
    
    # Source-specific parameters
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Source-specific parameters")
    
    # Output settings
    max_results: Optional[int] = Field(default=None, ge=1, description="Maximum results from this source")
    data_fields: List[str] = Field(default_factory=list, description="Specific fields to extract")
    
    # Dependencies
    depends_on: List[DataSourceType] = Field(default_factory=list, description="Sources this depends on")
    provides_input_to: List[DataSourceType] = Field(default_factory=list, description="Sources that use this output")

class SourceExecution(BaseModel):
    """Execution status and results for a data source"""
    source_type: DataSourceType = Field(..., description="Data source type")
    status: ExecutionStatus = Field(..., description="Execution status")
    
    # Timeline
    started_at: Optional[datetime] = Field(default=None, description="Execution start time")
    completed_at: Optional[datetime] = Field(default=None, description="Execution completion time")
    duration_seconds: Optional[float] = Field(default=None, ge=0, description="Execution duration")
    
    # Results
    records_found: int = Field(default=0, ge=0, description="Number of records found")
    records_accepted: int = Field(default=0, ge=0, description="Number of records meeting quality threshold")
    average_quality_score: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Average quality score")
    
    # Data
    results: List[Dict[str, Any]] = Field(default_factory=list, description="Extracted data results")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Source-specific metadata")
    
    # Error handling
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    warnings: List[str] = Field(default_factory=list, description="Warnings during execution")
    retry_count: int = Field(default=0, ge=0, description="Number of retries attempted")

class ExecutionPlan(BaseModel):
    """Plan for executing multiple data sources"""
    plan_id: str = Field(..., description="Unique plan identifier")
    strategy: ExecutionStrategy = Field(..., description="Execution strategy")
    
    # Source configuration
    sources: List[SourceConfiguration] = Field(..., description="Data sources to execute")
    execution_order: List[DataSourceType] = Field(default_factory=list, description="Order of execution")
    parallel_groups: List[List[DataSourceType]] = Field(default_factory=list, description="Groups for parallel execution")
    
    # Merge configuration
    merge_strategy: DataMergeStrategy = Field(default=DataMergeStrategy.UNION, description="Data merge strategy")
    merge_rules: Dict[str, Any] = Field(default_factory=dict, description="Custom merge rules")
    
    # Quality and limits
    global_quality_threshold: QualityThreshold = Field(default_factory=QualityThreshold, description="Global quality thresholds")
    max_total_results: Optional[int] = Field(default=None, ge=1, description="Maximum total results")
    target_result_count: Optional[int] = Field(default=None, ge=1, description="Target number of results")
    
    # Early termination
    stop_on_sufficient_data: bool = Field(default=False, description="Stop when sufficient data is collected")
    stop_on_first_failure: bool = Field(default=False, description="Stop on first source failure")
    
    # Timeline
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Plan creation time")
    estimated_duration: Optional[int] = Field(default=None, ge=1, description="Estimated execution time in seconds")

class OrchestratorRequest(BaseModel):
    """Request for orchestrated lead generation"""
    # Search criteria
    search_query: str = Field(..., description="Primary search query")
    industry: Optional[str] = Field(default=None, description="Target industry")
    location: Optional[str] = Field(default=None, description="Target location")
    company_size: Optional[str] = Field(default=None, description="Target company size")
    
    # Orchestration settings
    execution_strategy: ExecutionStrategy = Field(default=ExecutionStrategy.PARALLEL, description="Execution strategy")
    enabled_sources: List[DataSourceType] = Field(default_factory=list, description="Enabled data sources")
    source_configurations: List[SourceConfiguration] = Field(default_factory=list, description="Source-specific configurations")
    
    # Quality and limits
    quality_threshold: QualityThreshold = Field(default_factory=QualityThreshold, description="Quality requirements")
    max_results: int = Field(default=100, ge=1, le=10000, description="Maximum total results")
    target_results: Optional[int] = Field(default=None, ge=1, description="Target number of results")
    
    # Merge settings
    merge_strategy: DataMergeStrategy = Field(default=DataMergeStrategy.UNION, description="Data merge strategy")
    deduplicate: bool = Field(default=True, description="Remove duplicate records")
    
    # Execution options
    timeout_seconds: int = Field(default=1800, ge=60, le=7200, description="Total orchestration timeout")
    async_execution: bool = Field(default=True, description="Execute asynchronously")
    callback_url: Optional[str] = Field(default=None, description="Callback URL for completion notification")
    
    # Context and metadata
    user_id: Optional[str] = Field(default=None, description="User requesting orchestration")
    session_id: Optional[str] = Field(default=None, description="Session identifier")
    tags: List[str] = Field(default_factory=list, description="Request tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

class OrchestratorMetrics(BaseModel):
    """Metrics from orchestrated execution"""
    # Execution metrics
    total_sources_executed: int = Field(default=0, ge=0, description="Total sources executed")
    successful_sources: int = Field(default=0, ge=0, description="Successfully completed sources")
    failed_sources: int = Field(default=0, ge=0, description="Failed sources")
    
    # Data metrics
    total_records_found: int = Field(default=0, ge=0, description="Total records found across all sources")
    total_records_accepted: int = Field(default=0, ge=0, description="Total records meeting quality threshold")
    duplicates_removed: int = Field(default=0, ge=0, description="Duplicate records removed")
    final_record_count: int = Field(default=0, ge=0, description="Final deduplicated record count")
    
    # Quality metrics
    average_quality_score: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Average quality score")
    quality_distribution: Dict[str, int] = Field(default_factory=dict, description="Quality score distribution")
    
    # Performance metrics
    total_execution_time: Optional[float] = Field(default=None, ge=0, description="Total execution time in seconds")
    fastest_source_time: Optional[float] = Field(default=None, ge=0, description="Fastest source execution time")
    slowest_source_time: Optional[float] = Field(default=None, ge=0, description="Slowest source execution time")
    
    # Source-specific metrics
    source_performance: Dict[DataSourceType, Dict[str, Any]] = Field(default_factory=dict, description="Per-source performance metrics")

class OrchestratorResponse(BaseModel):
    """Response from orchestrated lead generation"""
    execution_id: str = Field(..., description="Unique execution identifier")
    status: ExecutionStatus = Field(..., description="Orchestration status")
    
    # Execution plan
    execution_plan: ExecutionPlan = Field(..., description="Execution plan used")
    
    # Source executions
    source_executions: List[SourceExecution] = Field(default_factory=list, description="Individual source executions")
    
    # Results
    merged_results: List[Dict[str, Any]] = Field(default_factory=list, description="Final merged and deduplicated results")
    results_by_source: Dict[DataSourceType, List[Dict[str, Any]]] = Field(default_factory=dict, description="Results grouped by source")
    
    # Metrics
    metrics: OrchestratorMetrics = Field(default_factory=OrchestratorMetrics, description="Execution metrics")
    
    # Timeline
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Orchestration start time")
    completed_at: Optional[datetime] = Field(default=None, description="Orchestration completion time")
    duration_seconds: Optional[float] = Field(default=None, ge=0, description="Total duration")
    
    # Error handling
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    warnings: List[str] = Field(default_factory=list, description="Warnings during execution")
    
    # Progress tracking
    progress_percentage: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Execution progress")
    current_phase: Optional[str] = Field(default=None, description="Current execution phase")
    
    # Callback info
    callback_sent: bool = Field(default=False, description="Whether callback notification was sent")
    
class OrchestratorConfig(BaseModel):
    """Configuration for orchestrator service"""
    # Execution limits
    max_concurrent_orchestrations: int = Field(default=5, ge=1, le=50, description="Maximum concurrent orchestrations")
    max_sources_per_orchestration: int = Field(default=10, ge=1, le=20, description="Maximum sources per orchestration")
    default_timeout: int = Field(default=1800, ge=60, le=7200, description="Default orchestration timeout")
    
    # Default source configurations
    default_source_configs: Dict[DataSourceType, SourceConfiguration] = Field(default_factory=dict, description="Default configurations for each source type")
    
    # Quality settings
    global_quality_threshold: QualityThreshold = Field(default_factory=QualityThreshold, description="Global quality thresholds")
    enable_quality_scoring: bool = Field(default=True, description="Enable quality scoring")
    
    # Merge and deduplication
    default_merge_strategy: DataMergeStrategy = Field(default=DataMergeStrategy.UNION, description="Default merge strategy")
    enable_deduplication: bool = Field(default=True, description="Enable automatic deduplication")
    deduplication_threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="Similarity threshold for deduplication")


# Simple API models for lead generation routers
class ScrapingRequest(BaseModel):
    """Simple scraping request for lead generation API"""
    source: str = Field(..., description="Scraping source (yellowpages, linkedin, etc.)")
    criteria: Dict[str, Any] = Field(..., description="Search criteria")
    max_results: Optional[int] = Field(default=100, ge=1, le=1000)
    location: Optional[str] = None
    industry: Optional[str] = None


class ScrapingResponse(BaseModel):
    """Simple scraping response for lead generation API"""
    session_id: str
    status: str
    message: str
    estimated_results: Optional[int] = None


class ScrapingSession(BaseModel):
    """Scraping session model"""
    session_id: str
    user_id: str
    source: str
    criteria: Dict[str, Any]
    status: str
    created_at: str
    completed_at: Optional[str] = None
    results_count: Optional[int] = None
    error_message: Optional[str] = None


class ScrapingSessionCreate(BaseModel):
    """Create scraping session request"""
    user_id: str
    source: str
    criteria: Dict[str, Any]


class ScrapingSessionUpdate(BaseModel):
    """Update scraping session request"""
    status: Optional[str] = None
    completed_at: Optional[str] = None
    results_count: Optional[int] = None
    error_message: Optional[str] = None


class WorkflowRequest(BaseModel):
    """Simple workflow request"""
    workflow_name: str = Field(..., description="Name of workflow to execute")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Workflow parameters")


class WorkflowResponse(BaseModel):
    """Simple workflow response"""
    workflow_id: str
    status: str
    message: str


class WorkflowStatus(BaseModel):
    """Workflow status response"""
    workflow_id: str
    status: str
    progress: Optional[float] = Field(None, ge=0, le=1)
    current_step: Optional[str] = None
    results: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None
    
    # Performance
    enable_caching: bool = Field(default=True, description="Enable result caching")
    cache_ttl_minutes: int = Field(default=60, ge=1, le=1440, description="Cache time-to-live in minutes")
    
    # Monitoring and logging
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    log_level: str = Field(default="INFO", description="Logging level")
    
    # Callbacks and notifications
    enable_callbacks: bool = Field(default=True, description="Enable callback notifications")
    callback_timeout: int = Field(default=30, ge=1, le=300, description="Callback request timeout")
    
    class Config:
        extra = "allow"