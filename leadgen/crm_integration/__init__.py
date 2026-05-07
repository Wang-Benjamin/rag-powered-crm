"""
CRM Integration feature module.

Customer relationship management database integration,
lead synchronization, and duplicate detection capabilities.
"""

from .schemas import (
    CRMIntegrationRequest,
    CRMSyncRequest,
    CRMBatchSyncRequest,
    CRMIntegrationResponse,
    CRMSyncResponse,
    CRMBatchSyncResponse,
    CRMLeadData,
    CRMContactData,
    CRMDuplicateResult,
    SyncOperation,
    SyncStatus,
    DuplicateStrategy,
    CRMIntegrationConfig,
    SyncPriority,
    ConflictResolution
)

from .services import (
    CRMIntegrationService,
    CRMIntegrationServiceError,
    get_crm_integration_service as get_crm_batch_service
)

from .integration_service import (
    LeadToCRMIntegrationService,
    get_crm_integration_service
)

__all__ = [
    # Schemas
    "CRMIntegrationRequest",
    "CRMSyncRequest",
    "CRMBatchSyncRequest",
    "CRMIntegrationResponse",
    "CRMSyncResponse",
    "CRMBatchSyncResponse",
    "CRMLeadData",
    "CRMContactData",
    "CRMDuplicateResult",
    "SyncOperation",
    "SyncStatus",
    "DuplicateStrategy",
    "CRMIntegrationConfig",
    "SyncPriority",
    "ConflictResolution",

    # Services (legacy batch sync service)
    "CRMIntegrationService",
    "CRMIntegrationServiceError",
    "get_crm_batch_service",

    # Lead-to-CRM Integration Service (new)
    "LeadToCRMIntegrationService",
    "get_crm_integration_service"
]