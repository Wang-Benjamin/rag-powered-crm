"""
Workflow feature module.

Unified lead generation workflow orchestration,
multi-step processes, and pipeline management.
"""

from .schemas import (
    WorkflowDefinition,
    WorkflowStep,
    WorkflowExecution,
    WorkflowExecutionRequest,
    WorkflowExecutionResponse,
    StepExecution,
    WorkflowTrigger,
    WorkflowCondition,
    WorkflowAction,
    WorkflowVariable,
    StepType,
    StepStatus,
    WorkflowStatus,
    TriggerType,
    ConditionOperator,
    ActionType,
    VariableType,
    ExecutionContext,
    WorkflowConfig
)

from .services import (
    WorkflowService,
    WorkflowServiceError,
    get_workflow_service
)

__all__ = [
    # Schemas
    "WorkflowDefinition",
    "WorkflowStep",
    "WorkflowExecution",
    "WorkflowExecutionRequest",
    "WorkflowExecutionResponse",
    "StepExecution",
    "WorkflowTrigger",
    "WorkflowCondition",
    "WorkflowAction",
    "WorkflowVariable",
    "StepType",
    "StepStatus",
    "WorkflowStatus",
    "TriggerType",
    "ConditionOperator",
    "ActionType",
    "VariableType",
    "ExecutionContext",
    "WorkflowConfig",
    
    # Services
    "WorkflowService",
    "WorkflowServiceError",
    "get_workflow_service"
]