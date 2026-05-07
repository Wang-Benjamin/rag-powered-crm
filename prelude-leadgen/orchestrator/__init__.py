"""
Orchestrator feature module.

Multi-source scraping coordination, parallel execution management,
and unified lead generation orchestration across all data sources.
"""

from .schemas import (
    OrchestratorRequest,
    OrchestratorResponse,
    SourceConfiguration,
    ExecutionPlan,
    SourceExecution,
    OrchestratorMetrics,
    DataSourceType,
    ExecutionStrategy,
    ExecutionStatus,
    SourcePriority,
    DataMergeStrategy,
    QualityThreshold,
    OrchestratorConfig
)

from .services import (
    OrchestratorService,
    OrchestratorServiceError,
    get_orchestrator_service
)

__all__ = [
    # Schemas
    "OrchestratorRequest",
    "OrchestratorResponse",
    "SourceConfiguration",
    "ExecutionPlan",
    "SourceExecution",
    "OrchestratorMetrics",
    "DataSourceType",
    "ExecutionStrategy",
    "ExecutionStatus",
    "SourcePriority",
    "DataMergeStrategy",
    "QualityThreshold",
    "OrchestratorConfig",
    
    # Services
    "OrchestratorService",
    "OrchestratorServiceError",
    "get_orchestrator_service"
]