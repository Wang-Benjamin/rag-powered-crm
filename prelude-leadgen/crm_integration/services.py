import asyncio
import aiohttp
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass
from difflib import SequenceMatcher
import json
import logging
from urllib.parse import urljoin

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

logger = logging.getLogger(__name__)

class CRMIntegrationServiceError(Exception):
    """CRM Integration service specific errors"""
    pass

@dataclass
class SyncMetrics:
    """Metrics for CRM synchronization operations"""
    total_requests: int = 0
    successful_syncs: int = 0
    failed_syncs: int = 0
    duplicates_detected: int = 0
    records_skipped: int = 0
    api_calls_made: int = 0
    average_response_time: float = 0.0
    
class CRMIntegrationService:
    """Service for integrating with CRM systems"""
    
    def __init__(self, config: CRMIntegrationConfig):
        self.config = config
        self.metrics = SyncMetrics()
        self._session: Optional[aiohttp.ClientSession] = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            headers = {
                'Authorization': f'Bearer {self.config.api_key}',
                'Content-Type': 'application/json',
                'User-Agent': 'PreludeLeadGen-CRM/1.0'
            }
            if self.config.organization_id:
                headers['X-Organization-ID'] = self.config.organization_id
                
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers=headers
            )
        return self._session
        
    async def close(self):
        """Close HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()
            
    async def check_duplicate(self, lead_data: CRMLeadData) -> CRMDuplicateResult:
        """Check for duplicate records in CRM"""
        try:
            # In a real implementation, this would query the CRM API
            # For now, we'll simulate duplicate detection
            
            # Mock duplicate detection logic
            company_name_lower = lead_data.company_name.lower()
            
            # Simulate some duplicates based on company name patterns
            duplicate_indicators = ['test', 'demo', 'sample', 'example']
            is_likely_duplicate = any(indicator in company_name_lower for indicator in duplicate_indicators)
            
            if is_likely_duplicate:
                return CRMDuplicateResult(
                    is_duplicate=True,
                    duplicate_id=f"crm_{hash(company_name_lower) % 10000}",
                    similarity_score=85.0,
                    matching_fields=['company_name'],
                    confidence_level='high',
                    suggested_action=DuplicateStrategy.MERGE
                )
            
            # Check for potential duplicates based on email/phone
            similarity_score = 0.0
            matching_fields = []
            
            if lead_data.primary_contact and lead_data.primary_contact.email:
                # Simulate email-based duplicate detection
                if 'duplicate' in lead_data.primary_contact.email.lower():
                    similarity_score = 75.0
                    matching_fields.append('email')
            
            if similarity_score > self.config.duplicate_threshold * 100:
                return CRMDuplicateResult(
                    is_duplicate=True,
                    duplicate_id=f"crm_{hash(lead_data.company_name) % 10000}",
                    similarity_score=similarity_score,
                    matching_fields=matching_fields,
                    confidence_level='medium',
                    suggested_action=DuplicateStrategy.MANUAL_REVIEW
                )
            
            return CRMDuplicateResult(
                is_duplicate=False,
                similarity_score=similarity_score,
                matching_fields=matching_fields,
                confidence_level='low'
            )
            
        except Exception as e:
            logger.error(f"Error checking for duplicates: {e}")
            return CRMDuplicateResult(
                is_duplicate=False,
                similarity_score=0.0,
                confidence_level='unknown'
            )
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two text strings"""
        if not text1 or not text2:
            return 0.0
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio() * 100
    
    def _validate_lead_data(self, lead_data: CRMLeadData) -> List[str]:
        """Validate lead data before sync"""
        errors = []
        
        # Check required fields
        for field in self.config.required_fields:
            if not getattr(lead_data, field, None):
                errors.append(f"Required field '{field}' is missing or empty")
        
        # Validate email formats
        if lead_data.primary_contact and lead_data.primary_contact.email:
            if '@' not in lead_data.primary_contact.email:
                errors.append("Primary contact email format is invalid")
        
        # Validate phone numbers (basic check)
        if lead_data.phone and len(lead_data.phone.replace('-', '').replace(' ', '')) < 10:
            errors.append("Phone number appears to be too short")
        
        # Validate revenue if present
        if lead_data.revenue is not None and lead_data.revenue < 0:
            errors.append("Revenue cannot be negative")
        
        # Validate employee count
        if lead_data.employee_count is not None and lead_data.employee_count < 0:
            errors.append("Employee count cannot be negative")
        
        return errors
    
    async def _make_crm_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make authenticated request to CRM API"""
        session = await self._get_session()
        url = urljoin(str(self.config.crm_endpoint), endpoint)
        
        start_time = datetime.now(timezone.utc)

        for attempt in range(self.config.max_retries + 1):
            try:
                async with session.request(method, url, json=data) as response:
                    self.metrics.api_calls_made += 1
                    
                    # Update response time metrics
                    response_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                    if self.metrics.total_requests > 0:
                        self.metrics.average_response_time = (
                            (self.metrics.average_response_time * (self.metrics.total_requests - 1) + response_time) 
                            / self.metrics.total_requests
                        )
                    else:
                        self.metrics.average_response_time = response_time
                    
                    if response.status >= 400:
                        error_text = await response.text()
                        logger.error(f"CRM API error {response.status}: {error_text}")
                        
                        if attempt < self.config.max_retries:
                            await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                            continue
                        
                        raise CRMIntegrationServiceError(
                            f"CRM API request failed with status {response.status}: {error_text}"
                        )
                    
                    return await response.json()
                    
            except aiohttp.ClientError as e:
                logger.error(f"HTTP client error on attempt {attempt + 1}: {e}")
                if attempt < self.config.max_retries:
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                    continue
                raise CRMIntegrationServiceError(f"HTTP client error: {e}")
        
        raise CRMIntegrationServiceError("Max retries exceeded")
    
    async def sync_lead(self, request: CRMIntegrationRequest) -> CRMIntegrationResponse:
        """Sync a single lead to CRM"""
        self.metrics.total_requests += 1
        
        try:
            # Validate data if requested
            validation_errors = []
            if request.validate_data:
                validation_errors = self._validate_lead_data(request.lead_data)
                
                if validation_errors and self.config.strict_validation:
                    self.metrics.failed_syncs += 1
                    return CRMIntegrationResponse(
                        success=False,
                        operation=request.operation,
                        validation_errors=validation_errors
                    )
            
            # Check for duplicates
            duplicate_result = None
            if request.duplicate_strategy != DuplicateStrategy.CREATE_NEW:
                duplicate_result = await self.check_duplicate(request.lead_data)
                
                if duplicate_result.is_duplicate:
                    if request.duplicate_strategy == DuplicateStrategy.SKIP:
                        self.metrics.records_skipped += 1
                        return CRMIntegrationResponse(
                            success=True,
                            operation=SyncOperation.UPSERT,
                            duplicate_result=duplicate_result,
                            warnings=["Record skipped due to duplicate detection"]
                        )
            
            # Prepare CRM data payload
            crm_payload = self._prepare_crm_payload(request.lead_data, request.custom_mapping)
            
            # Mock CRM API call - in real implementation, this would be actual API calls
            if request.operation == SyncOperation.CREATE:
                result = await self._create_crm_record(crm_payload)
            elif request.operation == SyncOperation.UPDATE:
                result = await self._update_crm_record(crm_payload, request.lead_data.lead_id)
            elif request.operation == SyncOperation.UPSERT:
                result = await self._upsert_crm_record(crm_payload)
            else:
                raise CRMIntegrationServiceError(f"Unsupported operation: {request.operation}")
            
            self.metrics.successful_syncs += 1
            
            return CRMIntegrationResponse(
                success=True,
                operation=request.operation,
                crm_record_id=result.get('id', f"mock_id_{hash(request.lead_data.company_name) % 10000}"),
                duplicate_result=duplicate_result,
                validation_errors=validation_errors,
                metadata=result.get('metadata', {})
            )
            
        except Exception as e:
            self.metrics.failed_syncs += 1
            logger.error(f"Error syncing lead {request.lead_data.company_name}: {e}")
            
            return CRMIntegrationResponse(
                success=False,
                operation=request.operation,
                validation_errors=[str(e)]
            )
    
    def _prepare_crm_payload(self, lead_data: CRMLeadData, custom_mapping: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Prepare data payload for CRM API"""
        payload = {
            'company_name': lead_data.company_name,
            'industry': lead_data.industry,
            'company_size': lead_data.company_size,
            'website': str(lead_data.website) if lead_data.website else None,
            'phone': lead_data.phone,
            'address': {
                'street': lead_data.address,
                'city': lead_data.city,
                'state': lead_data.state,
                'country': lead_data.country,
                'postal_code': lead_data.postal_code
            },
            'revenue': lead_data.revenue,
            'employee_count': lead_data.employee_count,
            'lead_source': lead_data.lead_source,
            'lead_score': lead_data.lead_score,
            'quality_score': lead_data.quality_score,
            'tags': lead_data.tags,
            'notes': lead_data.notes,
            'custom_fields': lead_data.custom_fields
        }
        
        # Add contact information
        if lead_data.primary_contact:
            payload['primary_contact'] = {
                'first_name': lead_data.primary_contact.first_name,
                'last_name': lead_data.primary_contact.last_name,
                'email': lead_data.primary_contact.email,
                'phone': lead_data.primary_contact.phone,
                'mobile': lead_data.primary_contact.mobile,
                'title': lead_data.primary_contact.title,
                'department': lead_data.primary_contact.department,
                'linkedin_url': str(lead_data.primary_contact.linkedin_url) if lead_data.primary_contact.linkedin_url else None
            }
        
        # Add additional contacts
        if lead_data.additional_contacts:
            payload['additional_contacts'] = [
                {
                    'first_name': contact.first_name,
                    'last_name': contact.last_name,
                    'email': contact.email,
                    'phone': contact.phone,
                    'mobile': contact.mobile,
                    'title': contact.title,
                    'department': contact.department,
                    'linkedin_url': str(contact.linkedin_url) if contact.linkedin_url else None
                }
                for contact in lead_data.additional_contacts
            ]
        
        # Apply custom field mappings
        if custom_mapping:
            mapped_payload = {}
            for key, value in payload.items():
                mapped_key = custom_mapping.get(key, key)
                mapped_payload[mapped_key] = value
            payload = mapped_payload
        
        # Apply default field mappings from config
        if self.config.field_mappings:
            for source_field, target_field in self.config.field_mappings.items():
                if source_field in payload:
                    payload[target_field] = payload.pop(source_field)
        
        return payload
    
    async def _create_crm_record(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create new CRM record"""
        # Mock implementation - replace with actual CRM API call
        record_id = f"crm_new_{hash(str(payload)) % 100000}"
        
        return {
            'id': record_id,
            'status': 'created',
            'metadata': {
                'created_at': datetime.now(timezone.utc).isoformat(),
                'source': 'prelude_lead_gen'
            }
        }
    
    async def _update_crm_record(self, payload: Dict[str, Any], record_id: Optional[str]) -> Dict[str, Any]:
        """Update existing CRM record"""
        if not record_id:
            raise CRMIntegrationServiceError("Record ID required for update operation")
        
        # Mock implementation - replace with actual CRM API call
        return {
            'id': record_id,
            'status': 'updated',
            'metadata': {
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'source': 'prelude_lead_gen'
            }
        }
    
    async def _upsert_crm_record(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update CRM record (upsert)"""
        # Mock implementation - replace with actual CRM API call
        record_id = f"crm_upsert_{hash(str(payload)) % 100000}"
        
        return {
            'id': record_id,
            'status': 'upserted',
            'metadata': {
                'upserted_at': datetime.now(timezone.utc).isoformat(),
                'source': 'prelude_lead_gen'
            }
        }
    
    async def sync_batch(self, request: CRMSyncRequest) -> CRMSyncResponse:
        """Sync a batch of leads to CRM"""
        batch_id = request.batch_id or f"batch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        started_at = datetime.now(timezone.utc)
        
        results = []
        successful_syncs = 0
        failed_syncs = 0
        duplicates_found = 0
        skipped_records = 0
        errors = []
        
        try:
            # Process leads in batches to avoid overwhelming the CRM API
            batch_size = min(self.config.batch_size, len(request.leads))
            
            for i in range(0, len(request.leads), batch_size):
                batch_leads = request.leads[i:i + batch_size]
                
                # Process batch concurrently with limited concurrency
                semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)
                
                async def process_lead(lead_request):
                    async with semaphore:
                        return await self.sync_lead(lead_request)
                
                batch_results = await asyncio.gather(
                    *[process_lead(lead) for lead in batch_leads],
                    return_exceptions=True
                )
                
                # Process batch results
                for result in batch_results:
                    if isinstance(result, Exception):
                        errors.append(str(result))
                        failed_syncs += 1
                    else:
                        results.append(result)
                        if result.success:
                            successful_syncs += 1
                            if result.duplicate_result and result.duplicate_result.is_duplicate:
                                duplicates_found += 1
                        else:
                            failed_syncs += 1
                        
                        if result.warnings and any('skipped' in warning.lower() for warning in result.warnings):
                            skipped_records += 1
            
            # Determine overall status
            if failed_syncs == 0:
                status = SyncStatus.COMPLETED
            elif successful_syncs == 0:
                status = SyncStatus.FAILED
            else:
                status = SyncStatus.PARTIAL
            
            completed_at = datetime.now(timezone.utc)
            duration_seconds = (completed_at - started_at).total_seconds()
            
            return CRMSyncResponse(
                batch_id=batch_id,
                total_records=len(request.leads),
                successful_syncs=successful_syncs,
                failed_syncs=failed_syncs,
                duplicates_found=duplicates_found,
                skipped_records=skipped_records,
                results=results,
                errors=errors,
                status=status,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration_seconds
            )
            
        except Exception as e:
            logger.error(f"Error processing batch {batch_id}: {e}")
            
            return CRMSyncResponse(
                batch_id=batch_id,
                total_records=len(request.leads),
                successful_syncs=successful_syncs,
                failed_syncs=len(request.leads),
                duplicates_found=duplicates_found,
                skipped_records=skipped_records,
                results=results,
                errors=[str(e)],
                status=SyncStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc)
            )
    
    async def sync_multiple_batches(self, request: CRMBatchSyncRequest) -> CRMBatchSyncResponse:
        """Sync multiple batches of leads"""
        started_at = datetime.now(timezone.utc)
        batch_results = []
        
        try:
            if request.parallel_processing:
                # Process batches concurrently
                semaphore = asyncio.Semaphore(request.max_concurrent_batches)
                
                async def process_batch(batch_request):
                    async with semaphore:
                        return await self.sync_batch(batch_request)
                
                batch_results = await asyncio.gather(
                    *[process_batch(batch) for batch in request.batches],
                    return_exceptions=True
                )
                
                # Handle exceptions
                for i, result in enumerate(batch_results):
                    if isinstance(result, Exception):
                        logger.error(f"Batch {i} failed: {result}")
                        # Create a failed batch response
                        batch_results[i] = CRMSyncResponse(
                            batch_id=f"failed_batch_{i}",
                            total_records=0,
                            successful_syncs=0,
                            failed_syncs=0,
                            duplicates_found=0,
                            skipped_records=0,
                            results=[],
                            errors=[str(result)],
                            status=SyncStatus.FAILED,
                            started_at=started_at
                        )
            else:
                # Process batches sequentially
                for batch_request in request.batches:
                    result = await self.sync_batch(batch_request)
                    batch_results.append(result)
            
            # Calculate overall statistics
            completed_batches = sum(1 for r in batch_results if r.status == SyncStatus.COMPLETED)
            failed_batches = sum(1 for r in batch_results if r.status == SyncStatus.FAILED)
            total_records_processed = sum(r.total_records for r in batch_results)
            total_successful_syncs = sum(r.successful_syncs for r in batch_results)
            total_failed_syncs = sum(r.failed_syncs for r in batch_results)
            
            # Determine overall status
            if failed_batches == 0:
                overall_status = SyncStatus.COMPLETED
            elif completed_batches == 0:
                overall_status = SyncStatus.FAILED
            else:
                overall_status = SyncStatus.PARTIAL
            
            return CRMBatchSyncResponse(
                total_batches=len(request.batches),
                completed_batches=completed_batches,
                failed_batches=failed_batches,
                batch_results=batch_results,
                overall_status=overall_status,
                total_records_processed=total_records_processed,
                total_successful_syncs=total_successful_syncs,
                total_failed_syncs=total_failed_syncs,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            logger.error(f"Error processing multiple batches: {e}")
            raise CRMIntegrationServiceError(f"Batch processing failed: {e}")
    
    def get_metrics(self) -> SyncMetrics:
        """Get current sync metrics"""
        return self.metrics
    
    def reset_metrics(self):
        """Reset sync metrics"""
        self.metrics = SyncMetrics()

# Service factory function
async def get_crm_integration_service(config: CRMIntegrationConfig) -> CRMIntegrationService:
    """Factory function to create CRM integration service instance"""
    return CRMIntegrationService(config)