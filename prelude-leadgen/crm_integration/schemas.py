from pydantic import BaseModel, Field, HttpUrl, validator
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone
from enum import Enum

class SyncOperation(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    MERGE = "merge"
    DELETE = "delete"
    UPSERT = "upsert"

class SyncStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"

class DuplicateStrategy(str, Enum):
    SKIP = "skip"
    MERGE = "merge"
    REPLACE = "replace"
    CREATE_NEW = "create_new"
    MANUAL_REVIEW = "manual_review"

class SyncPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class ConflictResolution(str, Enum):
    NEWEST_WINS = "newest_wins"
    OLDEST_WINS = "oldest_wins"
    MANUAL_REVIEW = "manual_review"
    FIELD_LEVEL_MERGE = "field_level_merge"

class CRMContactData(BaseModel):
    first_name: Optional[str] = Field(default=None, description="Contact first name")
    last_name: Optional[str] = Field(default=None, description="Contact last name")
    email: Optional[str] = Field(default=None, description="Primary email address")
    phone: Optional[str] = Field(default=None, description="Primary phone number")
    mobile: Optional[str] = Field(default=None, description="Mobile phone number")
    title: Optional[str] = Field(default=None, description="Job title")
    department: Optional[str] = Field(default=None, description="Department")
    linkedin_url: Optional[HttpUrl] = Field(default=None, description="LinkedIn profile URL")
    
    @validator('email')
    def validate_email(cls, v):
        if v and '@' not in v:
            raise ValueError('Invalid email format')
        return v

class CRMLeadData(BaseModel):
    lead_id: Optional[str] = Field(default=None, description="External CRM lead ID")
    company_name: str = Field(..., description="Company name")
    industry: Optional[str] = Field(default=None, description="Company industry")
    company_size: Optional[str] = Field(default=None, description="Company size category")
    website: Optional[HttpUrl] = Field(default=None, description="Company website")
    phone: Optional[str] = Field(default=None, description="Company phone")
    address: Optional[str] = Field(default=None, description="Company address")
    city: Optional[str] = Field(default=None, description="City")
    state: Optional[str] = Field(default=None, description="State/Province")
    country: Optional[str] = Field(default=None, description="Country")
    postal_code: Optional[str] = Field(default=None, description="Postal code")
    revenue: Optional[float] = Field(default=None, ge=0, description="Annual revenue")
    employee_count: Optional[int] = Field(default=None, ge=0, description="Number of employees")
    
    # Lead source and quality
    lead_source: Optional[str] = Field(default=None, description="Lead generation source")
    lead_score: Optional[int] = Field(default=None, ge=0, le=100, description="Lead score (0-100)")
    quality_score: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Quality score")
    
    # Contact information
    primary_contact: Optional[CRMContactData] = Field(default=None, description="Primary contact")
    additional_contacts: List[CRMContactData] = Field(default_factory=list, description="Additional contacts")
    
    # Custom fields and metadata
    custom_fields: Dict[str, Any] = Field(default_factory=dict, description="Custom CRM fields")
    tags: List[str] = Field(default_factory=list, description="Lead tags")
    notes: Optional[str] = Field(default=None, description="Additional notes")
    
    # Tracking fields
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")
    last_activity: Optional[datetime] = Field(default=None, description="Last activity timestamp")

class CRMDuplicateResult(BaseModel):
    is_duplicate: bool = Field(..., description="Whether a duplicate was found")
    duplicate_id: Optional[str] = Field(default=None, description="ID of duplicate record")
    similarity_score: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Similarity score")
    matching_fields: List[str] = Field(default_factory=list, description="Fields that matched")
    confidence_level: Optional[str] = Field(default=None, description="Confidence level")
    suggested_action: Optional[DuplicateStrategy] = Field(default=None, description="Suggested duplicate handling")

class CRMIntegrationRequest(BaseModel):
    lead_data: CRMLeadData = Field(..., description="Lead data to integrate")
    operation: SyncOperation = Field(default=SyncOperation.UPSERT, description="Sync operation type")
    duplicate_strategy: DuplicateStrategy = Field(default=DuplicateStrategy.SKIP, description="Duplicate handling strategy")
    priority: SyncPriority = Field(default=SyncPriority.NORMAL, description="Sync priority")
    validate_data: bool = Field(default=True, description="Whether to validate data before sync")
    custom_mapping: Optional[Dict[str, str]] = Field(default=None, description="Custom field mappings")

class CRMSyncRequest(BaseModel):
    leads: List[CRMIntegrationRequest] = Field(..., description="Leads to synchronize")
    batch_id: Optional[str] = Field(default=None, description="Batch identifier")
    conflict_resolution: ConflictResolution = Field(default=ConflictResolution.NEWEST_WINS, description="Conflict resolution strategy")
    rollback_on_error: bool = Field(default=False, description="Whether to rollback on any error")
    notify_on_completion: bool = Field(default=True, description="Send notification on completion")

class CRMBatchSyncRequest(BaseModel):
    batches: List[CRMSyncRequest] = Field(..., description="Multiple sync batches")
    parallel_processing: bool = Field(default=True, description="Process batches in parallel")
    max_concurrent_batches: int = Field(default=3, ge=1, le=10, description="Maximum concurrent batches")

class CRMIntegrationResponse(BaseModel):
    success: bool = Field(..., description="Whether the integration was successful")
    operation: SyncOperation = Field(..., description="Operation performed")
    crm_record_id: Optional[str] = Field(default=None, description="CRM record ID")
    duplicate_result: Optional[CRMDuplicateResult] = Field(default=None, description="Duplicate detection result")
    validation_errors: List[str] = Field(default_factory=list, description="Data validation errors")
    warnings: List[str] = Field(default_factory=list, description="Warnings during processing")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Processing timestamp")

class CRMSyncResponse(BaseModel):
    batch_id: str = Field(..., description="Batch identifier")
    total_records: int = Field(..., ge=0, description="Total records in batch")
    successful_syncs: int = Field(..., ge=0, description="Successfully synced records")
    failed_syncs: int = Field(..., ge=0, description="Failed sync records")
    duplicates_found: int = Field(..., ge=0, description="Duplicates detected")
    skipped_records: int = Field(..., ge=0, description="Skipped records")
    
    results: List[CRMIntegrationResponse] = Field(default_factory=list, description="Individual sync results")
    errors: List[str] = Field(default_factory=list, description="Batch-level errors")
    
    status: SyncStatus = Field(..., description="Overall batch status")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Batch start time")
    completed_at: Optional[datetime] = Field(default=None, description="Batch completion time")
    duration_seconds: Optional[float] = Field(default=None, ge=0, description="Processing duration")

class CRMBatchSyncResponse(BaseModel):
    total_batches: int = Field(..., ge=0, description="Total number of batches")
    completed_batches: int = Field(..., ge=0, description="Completed batches")
    failed_batches: int = Field(..., ge=0, description="Failed batches")
    
    batch_results: List[CRMSyncResponse] = Field(default_factory=list, description="Individual batch results")
    overall_status: SyncStatus = Field(..., description="Overall processing status")
    
    total_records_processed: int = Field(default=0, ge=0, description="Total records across all batches")
    total_successful_syncs: int = Field(default=0, ge=0, description="Total successful syncs")
    total_failed_syncs: int = Field(default=0, ge=0, description="Total failed syncs")
    
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Processing start time")
    completed_at: Optional[datetime] = Field(default=None, description="Processing completion time")

class CRMIntegrationConfig(BaseModel):
    crm_endpoint: HttpUrl = Field(..., description="CRM API endpoint")
    api_key: str = Field(..., description="CRM API key")
    organization_id: Optional[str] = Field(default=None, description="CRM organization ID")
    
    # Connection settings
    timeout_seconds: int = Field(default=30, ge=1, le=300, description="Request timeout")
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    retry_delay: float = Field(default=1.0, ge=0.1, le=60.0, description="Retry delay in seconds")
    
    # Batch processing
    batch_size: int = Field(default=100, ge=1, le=1000, description="Batch processing size")
    max_concurrent_requests: int = Field(default=5, ge=1, le=20, description="Maximum concurrent API requests")
    
    # Duplicate detection
    duplicate_threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="Duplicate similarity threshold")
    enable_fuzzy_matching: bool = Field(default=True, description="Enable fuzzy string matching")
    
    # Field mappings
    field_mappings: Dict[str, str] = Field(default_factory=dict, description="Custom field mappings")
    required_fields: List[str] = Field(default_factory=list, description="Required fields for sync")
    
    # Validation settings
    strict_validation: bool = Field(default=True, description="Enable strict data validation")
    skip_invalid_records: bool = Field(default=False, description="Skip invalid records instead of failing")
    
    class Config:
        extra = "allow"