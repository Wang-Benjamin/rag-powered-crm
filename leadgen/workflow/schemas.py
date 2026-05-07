from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone
from enum import Enum

class StepType(str, Enum):
    """Types of workflow steps"""
    YELLOWPAGES_SEARCH = "yellowpages_search"
    LINKEDIN_ENRICHMENT = "linkedin_enrichment"
    PERPLEXITY_RESEARCH = "perplexity_research"
    GOOGLEMAPS_ANALYSIS = "googlemaps_analysis"
    CRM_INTEGRATION = "crm_integration"
    EMAIL_GENERATION = "email_generation"
    DATA_VALIDATION = "data_validation"
    QUALITY_SCORING = "quality_scoring"
    DUPLICATE_DETECTION = "duplicate_detection"
    NOTIFICATION = "notification"
    CONDITIONAL = "conditional"
    PARALLEL = "parallel"
    LOOP = "loop"
    DELAY = "delay"
    WEBHOOK = "webhook"

class StepStatus(str, Enum):
    """Status of workflow step execution"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    RETRYING = "retrying"

class WorkflowStatus(str, Enum):
    """Status of entire workflow execution"""
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    RESUMED = "resumed"

class TriggerType(str, Enum):
    """Types of workflow triggers"""
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    EVENT_DRIVEN = "event_driven"
    API_CALL = "api_call"
    WEBHOOK = "webhook"
    FILE_UPLOAD = "file_upload"

class ConditionOperator(str, Enum):
    """Operators for workflow conditions"""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    IN = "in"
    NOT_IN = "not_in"
    REGEX_MATCH = "regex_match"

class ActionType(str, Enum):
    """Types of workflow actions"""
    SET_VARIABLE = "set_variable"
    SEND_EMAIL = "send_email"
    CALL_API = "call_api"
    LOG_MESSAGE = "log_message"
    TRIGGER_WORKFLOW = "trigger_workflow"
    PAUSE_WORKFLOW = "pause_workflow"
    STOP_WORKFLOW = "stop_workflow"
    RETRY_STEP = "retry_step"
    SKIP_STEP = "skip_step"

class VariableType(str, Enum):
    """Types of workflow variables"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    DICT = "dict"
    DATETIME = "datetime"
    JSON = "json"

class WorkflowVariable(BaseModel):
    """Workflow variable definition"""
    name: str = Field(..., description="Variable name")
    type: VariableType = Field(..., description="Variable type")
    value: Any = Field(default=None, description="Variable value")
    description: Optional[str] = Field(default=None, description="Variable description")
    required: bool = Field(default=False, description="Whether variable is required")
    default_value: Any = Field(default=None, description="Default value if not provided")

class WorkflowCondition(BaseModel):
    """Condition for workflow branching"""
    variable: str = Field(..., description="Variable to evaluate")
    operator: ConditionOperator = Field(..., description="Comparison operator")
    value: Any = Field(default=None, description="Value to compare against")
    description: Optional[str] = Field(default=None, description="Condition description")

class WorkflowAction(BaseModel):
    """Action to perform based on conditions"""
    type: ActionType = Field(..., description="Action type")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    description: Optional[str] = Field(default=None, description="Action description")

class WorkflowTrigger(BaseModel):
    """Workflow trigger configuration"""
    type: TriggerType = Field(..., description="Trigger type")
    schedule: Optional[str] = Field(default=None, description="Cron schedule (for scheduled triggers)")
    event_filter: Optional[Dict[str, Any]] = Field(default=None, description="Event filter criteria")
    webhook_url: Optional[str] = Field(default=None, description="Webhook URL")
    enabled: bool = Field(default=True, description="Whether trigger is enabled")

class WorkflowStep(BaseModel):
    """Individual step in a workflow"""
    id: str = Field(..., description="Unique step identifier")
    name: str = Field(..., description="Human-readable step name")
    type: StepType = Field(..., description="Step type")
    description: Optional[str] = Field(default=None, description="Step description")
    
    # Step configuration
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Step parameters")
    input_mappings: Dict[str, str] = Field(default_factory=dict, description="Input variable mappings")
    output_mappings: Dict[str, str] = Field(default_factory=dict, description="Output variable mappings")
    
    # Execution control
    depends_on: List[str] = Field(default_factory=list, description="Step dependencies")
    conditions: List[WorkflowCondition] = Field(default_factory=list, description="Execution conditions")
    retry_count: int = Field(default=0, ge=0, le=10, description="Number of retry attempts")
    retry_delay: int = Field(default=60, ge=1, description="Retry delay in seconds")
    timeout: Optional[int] = Field(default=None, ge=1, description="Step timeout in seconds")
    
    # Error handling
    on_failure: List[WorkflowAction] = Field(default_factory=list, description="Actions on failure")
    on_success: List[WorkflowAction] = Field(default_factory=list, description="Actions on success")
    continue_on_failure: bool = Field(default=False, description="Continue workflow if step fails")

class StepExecution(BaseModel):
    """Execution status and results of a workflow step"""
    step_id: str = Field(..., description="Step identifier")
    status: StepStatus = Field(..., description="Step execution status")
    started_at: Optional[datetime] = Field(default=None, description="Step start time")
    completed_at: Optional[datetime] = Field(default=None, description="Step completion time")
    duration_seconds: Optional[float] = Field(default=None, ge=0, description="Execution duration")
    
    # Results
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Step input data")
    output_data: Dict[str, Any] = Field(default_factory=dict, description="Step output data")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    retry_count: int = Field(default=0, ge=0, description="Number of retries attempted")
    
    # Metadata
    logs: List[str] = Field(default_factory=list, description="Step execution logs")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Step metrics")

class ExecutionContext(BaseModel):
    """Context for workflow execution"""
    execution_id: str = Field(..., description="Unique execution identifier")
    user_id: Optional[str] = Field(default=None, description="User who triggered execution")
    trigger_type: TriggerType = Field(..., description="How workflow was triggered")
    trigger_data: Dict[str, Any] = Field(default_factory=dict, description="Trigger-specific data")
    
    # Variables and state
    variables: Dict[str, Any] = Field(default_factory=dict, description="Workflow variables")
    global_context: Dict[str, Any] = Field(default_factory=dict, description="Global execution context")
    
    # Execution metadata
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Execution start time")
    priority: int = Field(default=5, ge=1, le=10, description="Execution priority (1=highest, 10=lowest)")
    timeout: Optional[int] = Field(default=None, ge=1, description="Total workflow timeout in seconds")

class WorkflowDefinition(BaseModel):
    """Complete workflow definition"""
    id: str = Field(..., description="Unique workflow identifier")
    name: str = Field(..., description="Human-readable workflow name")
    version: str = Field(default="1.0.0", description="Workflow version")
    description: Optional[str] = Field(default=None, description="Workflow description")
    
    # Workflow configuration
    steps: List[WorkflowStep] = Field(..., description="Workflow steps")
    variables: List[WorkflowVariable] = Field(default_factory=list, description="Workflow variables")
    triggers: List[WorkflowTrigger] = Field(default_factory=list, description="Workflow triggers")
    
    # Execution settings
    max_concurrent_executions: int = Field(default=1, ge=1, description="Maximum concurrent executions")
    default_timeout: Optional[int] = Field(default=None, ge=1, description="Default execution timeout")
    retry_policy: Dict[str, Any] = Field(default_factory=dict, description="Global retry policy")
    
    # Metadata
    tags: List[str] = Field(default_factory=list, description="Workflow tags")
    created_by: Optional[str] = Field(default=None, description="Workflow creator")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last update timestamp")
    enabled: bool = Field(default=True, description="Whether workflow is enabled")
    
    @validator('steps')
    def validate_steps(cls, v):
        """Validate workflow steps"""
        if not v:
            raise ValueError("Workflow must have at least one step")
        
        # Check for duplicate step IDs
        step_ids = [step.id for step in v]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Duplicate step IDs found")
        
        # Validate step dependencies
        for step in v:
            for dep in step.depends_on:
                if dep not in step_ids:
                    raise ValueError(f"Step {step.id} depends on non-existent step {dep}")
        
        return v

class WorkflowExecution(BaseModel):
    """Workflow execution instance"""
    execution_id: str = Field(..., description="Unique execution identifier")
    workflow_id: str = Field(..., description="Workflow definition ID")
    workflow_version: str = Field(..., description="Workflow version used")
    
    # Execution state
    status: WorkflowStatus = Field(..., description="Execution status")
    context: ExecutionContext = Field(..., description="Execution context")
    step_executions: List[StepExecution] = Field(default_factory=list, description="Step execution results")
    
    # Timeline
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Execution start time")
    completed_at: Optional[datetime] = Field(default=None, description="Execution completion time")
    duration_seconds: Optional[float] = Field(default=None, ge=0, description="Total execution duration")
    
    # Results
    final_output: Dict[str, Any] = Field(default_factory=dict, description="Final workflow output")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    
    # Metrics
    total_steps: int = Field(default=0, ge=0, description="Total number of steps")
    completed_steps: int = Field(default=0, ge=0, description="Number of completed steps")
    failed_steps: int = Field(default=0, ge=0, description="Number of failed steps")
    skipped_steps: int = Field(default=0, ge=0, description="Number of skipped steps")

class WorkflowExecutionRequest(BaseModel):
    """Request to execute a workflow"""
    workflow_id: str = Field(..., description="Workflow to execute")
    trigger_type: TriggerType = Field(default=TriggerType.MANUAL, description="Execution trigger type")
    input_variables: Dict[str, Any] = Field(default_factory=dict, description="Input variables")
    priority: int = Field(default=5, ge=1, le=10, description="Execution priority")
    timeout: Optional[int] = Field(default=None, ge=1, description="Execution timeout in seconds")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional execution context")
    
    # Execution options
    async_execution: bool = Field(default=True, description="Execute asynchronously")
    callback_url: Optional[str] = Field(default=None, description="Callback URL for completion notification")
    
class WorkflowExecutionResponse(BaseModel):
    """Response from workflow execution request"""
    execution_id: str = Field(..., description="Unique execution identifier")
    workflow_id: str = Field(..., description="Workflow definition ID")
    status: WorkflowStatus = Field(..., description="Current execution status")
    
    # Quick stats
    total_steps: int = Field(default=0, ge=0, description="Total number of steps")
    completed_steps: int = Field(default=0, ge=0, description="Completed steps count")
    progress_percentage: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Execution progress")
    
    # Timeline
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Execution start time")
    estimated_completion: Optional[datetime] = Field(default=None, description="Estimated completion time")
    
    # Results (for completed executions)
    final_output: Optional[Dict[str, Any]] = Field(default=None, description="Final workflow output")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    
    # Metadata
    execution_url: Optional[str] = Field(default=None, description="URL to monitor execution")
    callback_registered: bool = Field(default=False, description="Whether callback was registered")

class WorkflowConfig(BaseModel):
    """Configuration for workflow service"""
    max_concurrent_workflows: int = Field(default=10, ge=1, description="Maximum concurrent workflows")
    default_step_timeout: int = Field(default=300, ge=1, description="Default step timeout in seconds")
    default_workflow_timeout: int = Field(default=3600, ge=1, description="Default workflow timeout in seconds")
    
    # Retry configuration
    default_retry_count: int = Field(default=3, ge=0, le=10, description="Default retry count")
    default_retry_delay: int = Field(default=60, ge=1, description="Default retry delay in seconds")
    exponential_backoff: bool = Field(default=True, description="Use exponential backoff for retries")
    
    # Storage and logging
    persist_executions: bool = Field(default=True, description="Persist execution history")
    log_level: str = Field(default="INFO", description="Logging level")
    
    # Notifications
    enable_notifications: bool = Field(default=True, description="Enable workflow notifications")
    notification_webhook: Optional[str] = Field(default=None, description="Global notification webhook")
    
    class Config:
        extra = "allow"