import asyncio
import uuid
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field
import logging
from difflib import SequenceMatcher
from copy import deepcopy

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

logger = logging.getLogger(__name__)

class OrchestratorServiceError(Exception):
    """Orchestrator service specific errors"""
    pass

@dataclass
class SourceResult:
    """Container for source execution results"""
    source_type: DataSourceType
    data: List[Dict[str, Any]]
    quality_scores: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    error: Optional[str] = None

class DataMerger:
    """Handles merging data from multiple sources"""
    
    def __init__(self, strategy: DataMergeStrategy, deduplication_threshold: float = 0.8):
        self.strategy = strategy
        self.deduplication_threshold = deduplication_threshold
    
    def merge_results(self, source_results: List[SourceResult], merge_rules: Optional[Dict[str, Any]] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Merge results from multiple sources"""
        if not source_results:
            return [], {}
        
        merged_data = []
        merge_metadata = {
            'sources_merged': len(source_results),
            'merge_strategy': self.strategy,
            'total_records_before_merge': sum(len(result.data) for result in source_results),
            'duplicates_removed': 0
        }
        
        if self.strategy == DataMergeStrategy.UNION:
            merged_data = self._merge_union(source_results)
        elif self.strategy == DataMergeStrategy.INTERSECTION:
            merged_data = self._merge_intersection(source_results)
        elif self.strategy == DataMergeStrategy.PRIORITIZED:
            merged_data = self._merge_prioritized(source_results)
        elif self.strategy == DataMergeStrategy.QUALITY_BASED:
            merged_data = self._merge_quality_based(source_results)
        elif self.strategy == DataMergeStrategy.CUSTOM_RULES:
            merged_data = self._merge_custom_rules(source_results, merge_rules or {})
        else:
            # Default to union
            merged_data = self._merge_union(source_results)
        
        # Perform deduplication
        deduplicated_data = self._deduplicate_records(merged_data)
        merge_metadata['duplicates_removed'] = len(merged_data) - len(deduplicated_data)
        merge_metadata['final_record_count'] = len(deduplicated_data)
        
        return deduplicated_data, merge_metadata
    
    def _merge_union(self, source_results: List[SourceResult]) -> List[Dict[str, Any]]:
        """Merge using union strategy (combine all records)"""
        merged = []
        for result in source_results:
            for i, record in enumerate(result.data):
                enriched_record = deepcopy(record)
                enriched_record['_source'] = result.source_type
                enriched_record['_quality_score'] = result.quality_scores[i] if i < len(result.quality_scores) else 0.0
                merged.append(enriched_record)
        return merged
    
    def _merge_intersection(self, source_results: List[SourceResult]) -> List[Dict[str, Any]]:
        """Merge using intersection strategy (only records found in multiple sources)"""
        if len(source_results) < 2:
            return self._merge_union(source_results)
        
        # Find records that appear in multiple sources
        # This is a simplified implementation - in practice, you'd use more sophisticated matching
        intersected = []
        first_result = source_results[0]
        
        for i, record in enumerate(first_result.data):
            company_name = record.get('company_name', '').lower()
            if not company_name:
                continue
            
            # Check if this record appears in other sources
            found_in_other_sources = False
            for other_result in source_results[1:]:
                for other_record in other_result.data:
                    other_company = other_record.get('company_name', '').lower()
                    if self._calculate_similarity(company_name, other_company) > self.deduplication_threshold:
                        found_in_other_sources = True
                        break
                if found_in_other_sources:
                    break
            
            if found_in_other_sources:
                enriched_record = deepcopy(record)
                enriched_record['_source'] = first_result.source_type
                enriched_record['_quality_score'] = first_result.quality_scores[i] if i < len(first_result.quality_scores) else 0.0
                intersected.append(enriched_record)
        
        return intersected
    
    def _merge_prioritized(self, source_results: List[SourceResult]) -> List[Dict[str, Any]]:
        """Merge using prioritized strategy (prefer data from higher priority sources)"""
        # Sort by source priority (this would need priority information passed in)
        # For now, we'll use the order as priority
        merged = []
        seen_companies = set()
        
        for result in source_results:
            for i, record in enumerate(result.data):
                company_name = record.get('company_name', '').lower()
                if company_name not in seen_companies:
                    enriched_record = deepcopy(record)
                    enriched_record['_source'] = result.source_type
                    enriched_record['_quality_score'] = result.quality_scores[i] if i < len(result.quality_scores) else 0.0
                    merged.append(enriched_record)
                    seen_companies.add(company_name)
        
        return merged
    
    def _merge_quality_based(self, source_results: List[SourceResult]) -> List[Dict[str, Any]]:
        """Merge using quality-based strategy (prefer higher quality data)"""
        # Group records by company name and pick the highest quality version
        company_records = {}
        
        for result in source_results:
            for i, record in enumerate(result.data):
                company_name = record.get('company_name', '').lower()
                quality_score = result.quality_scores[i] if i < len(result.quality_scores) else 0.0
                
                if company_name not in company_records or quality_score > company_records[company_name]['_quality_score']:
                    enriched_record = deepcopy(record)
                    enriched_record['_source'] = result.source_type
                    enriched_record['_quality_score'] = quality_score
                    company_records[company_name] = enriched_record
        
        return list(company_records.values())
    
    def _merge_custom_rules(self, source_results: List[SourceResult], merge_rules: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Merge using custom rules"""
        # This would implement custom merging logic based on provided rules
        # For now, fall back to union strategy
        logger.info(f"Custom merge rules not fully implemented, using union strategy")
        return self._merge_union(source_results)
    
    def _deduplicate_records(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate records based on similarity"""
        if not records:
            return records
        
        deduplicated = []
        for record in records:
            is_duplicate = False
            company_name = record.get('company_name', '').lower()
            
            for existing in deduplicated:
                existing_name = existing.get('company_name', '').lower()
                if self._calculate_similarity(company_name, existing_name) > self.deduplication_threshold:
                    # Check if current record has higher quality
                    current_quality = record.get('_quality_score', 0.0)
                    existing_quality = existing.get('_quality_score', 0.0)
                    
                    if current_quality > existing_quality:
                        # Replace existing with current (higher quality)
                        existing.update(record)
                    
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                deduplicated.append(record)
        
        return deduplicated
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two text strings"""
        if not text1 or not text2:
            return 0.0
        return SequenceMatcher(None, text1, text2).ratio()

class SourceExecutor:
    """Executes individual data sources"""
    
    def __init__(self):
        # In a real implementation, these would be injected dependencies
        self.source_services = {}
    
    async def execute_source(self, source_config: SourceConfiguration, search_params: Dict[str, Any]) -> SourceResult:
        """Execute a single data source"""
        start_time = datetime.now(timezone.utc)

        try:
            # Mock execution for different source types
            if source_config.source_type == DataSourceType.YELLOWPAGES:
                data, quality_scores = await self._execute_yellowpages(source_config, search_params)
            elif source_config.source_type == DataSourceType.LINKEDIN:
                data, quality_scores = await self._execute_linkedin(source_config, search_params)
            elif source_config.source_type == DataSourceType.PERPLEXITY:
                data, quality_scores = await self._execute_perplexity(source_config, search_params)
            elif source_config.source_type == DataSourceType.GOOGLEMAPS:
                data, quality_scores = await self._execute_googlemaps(source_config, search_params)
            elif source_config.source_type == DataSourceType.CRM_INTEGRATION:
                data, quality_scores = await self._execute_crm_integration(source_config, search_params)
            else:
                data, quality_scores = await self._execute_generic(source_config, search_params)
            
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()

            return SourceResult(
                source_type=source_config.source_type,
                data=data,
                quality_scores=quality_scores,
                execution_time=execution_time,
                metadata={'search_params': search_params}
            )
            
        except Exception as e:
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.error(f"Error executing {source_config.source_type}: {e}")
            
            return SourceResult(
                source_type=source_config.source_type,
                data=[],
                quality_scores=[],
                execution_time=execution_time,
                error=str(e)
            )
    
    async def _execute_yellowpages(self, config: SourceConfiguration, params: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[float]]:
        """Mock YellowPages execution"""
        await asyncio.sleep(2.0)  # Simulate API call
        
        search_query = params.get('search_query', 'business')
        location = params.get('location', 'Toronto, ON')
        max_results = config.max_results or 50
        
        # Generate mock data
        data = []
        quality_scores = []
        
        for i in range(min(max_results, 25)):
            record = {
                'company_name': f'{search_query.title()} Company {i+1}',
                'industry': params.get('industry', 'Business Services'),
                'location': location,
                'phone': f'416-555-{1000+i:04d}',
                'website': f'https://company{i+1}.example.com',
                'source_id': f'yp_{i+1}'
            }
            data.append(record)
            quality_scores.append(75.0 + (i % 20))  # Quality scores between 75-95
        
        return data, quality_scores
    
    async def _execute_linkedin(self, config: SourceConfiguration, params: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[float]]:
        """Mock LinkedIn execution"""
        await asyncio.sleep(3.0)  # Simulate API call
        
        search_query = params.get('search_query', 'business')
        max_results = config.max_results or 30
        
        data = []
        quality_scores = []
        
        for i in range(min(max_results, 15)):
            record = {
                'company_name': f'{search_query.title()} Corp {i+1}',
                'industry': params.get('industry', 'Technology'),
                'employee_count': (i + 1) * 50,
                'linkedin_url': f'https://linkedin.com/company/corp-{i+1}',
                'description': f'Leading {search_query} company providing innovative solutions.',
                'source_id': f'li_{i+1}'
            }
            data.append(record)
            quality_scores.append(80.0 + (i % 15))  # Quality scores between 80-95
        
        return data, quality_scores
    
    async def _execute_perplexity(self, config: SourceConfiguration, params: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[float]]:
        """Mock Perplexity execution"""
        await asyncio.sleep(4.0)  # Simulate AI research
        
        search_query = params.get('search_query', 'business')
        max_results = config.max_results or 20
        
        data = []
        quality_scores = []
        
        for i in range(min(max_results, 10)):
            record = {
                'company_name': f'{search_query.title()} Research Target {i+1}',
                'industry': params.get('industry', 'Research & Development'),
                'ai_insights': f'AI-generated insights about {search_query} market trends and opportunities.',
                'confidence_score': 0.85 + (i * 0.01),
                'research_depth': 'comprehensive',
                'source_id': f'px_{i+1}'
            }
            data.append(record)
            quality_scores.append(85.0 + (i % 10))  # Quality scores between 85-95
        
        return data, quality_scores
    
    async def _execute_googlemaps(self, config: SourceConfiguration, params: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[float]]:
        """Mock Google Maps execution"""
        await asyncio.sleep(2.5)  # Simulate Maps API calls
        
        search_query = params.get('search_query', 'business')
        location = params.get('location', 'Toronto, ON')
        max_results = config.max_results or 40
        
        data = []
        quality_scores = []
        
        for i in range(min(max_results, 20)):
            record = {
                'company_name': f'{search_query.title()} Location {i+1}',
                'address': f'{100+i} Main St, {location}',
                'latitude': 43.6532 + (i * 0.001),
                'longitude': -79.3832 + (i * 0.001),
                'rating': 4.0 + (i % 10) * 0.1,
                'review_count': (i + 1) * 25,
                'density_score': 7.5 + (i % 5) * 0.5,
                'source_id': f'gm_{i+1}'
            }
            data.append(record)
            quality_scores.append(70.0 + (i % 25))  # Quality scores between 70-95
        
        return data, quality_scores
    
    async def _execute_crm_integration(self, config: SourceConfiguration, params: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[float]]:
        """Mock CRM integration execution"""
        await asyncio.sleep(1.5)  # Simulate CRM API calls
        
        search_query = params.get('search_query', 'business')
        max_results = config.max_results or 35
        
        data = []
        quality_scores = []
        
        for i in range(min(max_results, 12)):
            record = {
                'company_name': f'{search_query.title()} CRM Entry {i+1}',
                'crm_id': f'crm_{1000+i}',
                'lead_score': 75 + (i % 20),
                'last_contact': (datetime.now(timezone.utc) - datetime.fromtimestamp(i * 86400, tz=timezone.utc)).isoformat(),
                'stage': 'qualified' if i % 3 == 0 else 'prospect',
                'owner': f'sales_rep_{i % 5 + 1}',
                'source_id': f'crm_{i+1}'
            }
            data.append(record)
            quality_scores.append(90.0 + (i % 8))  # Quality scores between 90-98
        
        return data, quality_scores
    
    async def _execute_generic(self, config: SourceConfiguration, params: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[float]]:
        """Generic mock execution for unknown source types"""
        await asyncio.sleep(1.0)
        
        return [
            {
                'company_name': f'Generic {config.source_type} Result',
                'source_type': config.source_type,
                'search_query': params.get('search_query', ''),
                'source_id': f'gen_1'
            }
        ], [60.0]

class ExecutionPlanner:
    """Creates execution plans for orchestrated lead generation"""
    
    def create_plan(self, request: OrchestratorRequest, config: OrchestratorConfig) -> ExecutionPlan:
        """Create an execution plan based on request and configuration"""
        plan_id = str(uuid.uuid4())
        
        # Determine which sources to use
        sources = self._select_sources(request, config)
        
        # Create execution order based on strategy
        execution_order, parallel_groups = self._plan_execution_order(sources, request.execution_strategy)
        
        # Estimate execution time
        estimated_duration = self._estimate_duration(sources, request.execution_strategy)
        
        return ExecutionPlan(
            plan_id=plan_id,
            strategy=request.execution_strategy,
            sources=sources,
            execution_order=execution_order,
            parallel_groups=parallel_groups,
            merge_strategy=request.merge_strategy,
            global_quality_threshold=request.quality_threshold,
            max_total_results=request.max_results,
            target_result_count=request.target_results,
            estimated_duration=estimated_duration
        )
    
    def _select_sources(self, request: OrchestratorRequest, config: OrchestratorConfig) -> List[SourceConfiguration]:
        """Select and configure sources for execution"""
        sources = []
        
        # Use explicitly enabled sources if provided
        enabled_types = request.enabled_sources if request.enabled_sources else list(DataSourceType)
        
        # Create configurations for each enabled source
        for source_type in enabled_types:
            # Check if specific configuration is provided
            specific_config = None
            for config_item in request.source_configurations:
                if config_item.source_type == source_type:
                    specific_config = config_item
                    break
            
            if specific_config:
                sources.append(specific_config)
            else:
                # Use default configuration
                default_config = config.default_source_configs.get(source_type)
                if default_config:
                    sources.append(default_config)
                else:
                    # Create basic configuration
                    sources.append(SourceConfiguration(
                        source_type=source_type,
                        max_results=request.max_results // len(enabled_types)  # Distribute max results
                    ))
        
        return sources
    
    def _plan_execution_order(self, sources: List[SourceConfiguration], strategy: ExecutionStrategy) -> Tuple[List[DataSourceType], List[List[DataSourceType]]]:
        """Plan execution order based on strategy"""
        source_types = [source.source_type for source in sources]
        
        if strategy == ExecutionStrategy.SEQUENTIAL:
            return source_types, []
        elif strategy == ExecutionStrategy.PARALLEL:
            return [], [source_types]  # All sources in one parallel group
        elif strategy == ExecutionStrategy.PRIORITIZED:
            # Order by priority (high to low)
            priority_order = {
                SourcePriority.CRITICAL: 0,
                SourcePriority.HIGH: 1,
                SourcePriority.MEDIUM: 2,
                SourcePriority.LOW: 3
            }
            sorted_sources = sorted(sources, key=lambda s: priority_order.get(s.priority, 4))
            return [s.source_type for s in sorted_sources], []
        elif strategy == ExecutionStrategy.WATERFALL:
            # Similar to prioritized but may stop early
            return self._plan_execution_order(sources, ExecutionStrategy.PRIORITIZED)
        else:
            # Default to parallel
            return [], [source_types]
    
    def _estimate_duration(self, sources: List[SourceConfiguration], strategy: ExecutionStrategy) -> int:
        """Estimate execution duration in seconds"""
        # Base estimates for each source type (in seconds)
        base_durations = {
            DataSourceType.YELLOWPAGES: 3,
            DataSourceType.LINKEDIN: 4,
            DataSourceType.PERPLEXITY: 5,
            DataSourceType.GOOGLEMAPS: 3,
            DataSourceType.CRM_INTEGRATION: 2,
            DataSourceType.EMAIL_GENERATION: 2,
            DataSourceType.CUSTOM_API: 3,
            DataSourceType.WEB_SCRAPING: 6
        }
        
        if strategy == ExecutionStrategy.PARALLEL:
            # Max duration of all sources
            return max(base_durations.get(source.source_type, 3) for source in sources) + 10  # +10 for merge/overhead
        else:
            # Sum of all durations
            return sum(base_durations.get(source.source_type, 3) for source in sources) + 10

class OrchestratorService:
    """Service for orchestrating multi-source lead generation"""
    
    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self.planner = ExecutionPlanner()
        self.executor = SourceExecutor()
        self.merger = DataMerger(DataMergeStrategy.UNION, config.deduplication_threshold)
        
        self.active_orchestrations: Dict[str, OrchestratorResponse] = {}
        self.orchestration_tasks: Dict[str, asyncio.Task] = {}
    
    async def orchestrate(self, request: OrchestratorRequest) -> OrchestratorResponse:
        """Orchestrate lead generation across multiple sources"""
        # Check concurrent execution limit
        active_count = len([o for o in self.active_orchestrations.values() if o.status == ExecutionStatus.EXECUTING])
        if active_count >= self.config.max_concurrent_orchestrations:
            raise OrchestratorServiceError("Maximum concurrent orchestrations exceeded")
        
        # Create execution plan
        execution_plan = self.planner.create_plan(request, self.config)
        
        if len(execution_plan.sources) > self.config.max_sources_per_orchestration:
            raise OrchestratorServiceError(f"Too many sources: {len(execution_plan.sources)} > {self.config.max_sources_per_orchestration}")
        
        # Create orchestration response
        execution_id = str(uuid.uuid4())
        response = OrchestratorResponse(
            execution_id=execution_id,
            status=ExecutionStatus.PLANNING,
            execution_plan=execution_plan
        )
        
        self.active_orchestrations[execution_id] = response
        
        if request.async_execution:
            # Start orchestration asynchronously
            task = asyncio.create_task(self._execute_orchestration(request, response))
            self.orchestration_tasks[execution_id] = task
            response.status = ExecutionStatus.EXECUTING
        else:
            # Execute orchestration synchronously
            await self._execute_orchestration(request, response)
        
        return response
    
    async def _execute_orchestration(self, request: OrchestratorRequest, response: OrchestratorResponse):
        """Execute the orchestration plan"""
        try:
            response.status = ExecutionStatus.EXECUTING
            
            # Prepare search parameters
            search_params = {
                'search_query': request.search_query,
                'industry': request.industry,
                'location': request.location,
                'company_size': request.company_size
            }
            
            # Execute sources based on strategy
            source_results = await self._execute_sources(response.execution_plan, search_params, response)
            
            # Update source executions in response
            response.source_executions = self._create_source_executions(source_results)
            
            # Merge results
            response.status = ExecutionStatus.MERGING
            merged_data, merge_metadata = self.merger.merge_results(source_results, response.execution_plan.merge_rules)
            
            # Apply quality filtering
            filtered_data = self._filter_by_quality(merged_data, request.quality_threshold)
            
            # Limit results if needed
            if request.max_results and len(filtered_data) > request.max_results:
                filtered_data = filtered_data[:request.max_results]
            
            # Populate response
            response.merged_results = filtered_data
            response.results_by_source = self._group_results_by_source(source_results)
            response.metrics = self._calculate_metrics(source_results, merge_metadata, filtered_data)
            response.status = ExecutionStatus.COMPLETED
            
        except Exception as e:
            logger.error(f"Orchestration {response.execution_id} failed: {e}")
            response.status = ExecutionStatus.FAILED
            response.error_message = str(e)
        
        finally:
            response.completed_at = datetime.now(timezone.utc)
            if response.started_at:
                duration = response.completed_at - response.started_at
                response.duration_seconds = duration.total_seconds()
            
            # Clean up task reference
            self.orchestration_tasks.pop(response.execution_id, None)
    
    async def _execute_sources(self, plan: ExecutionPlan, search_params: Dict[str, Any], response: OrchestratorResponse) -> List[SourceResult]:
        """Execute sources according to the execution plan"""
        source_results = []
        
        if plan.strategy == ExecutionStrategy.PARALLEL:
            # Execute all sources in parallel
            tasks = []
            for source_config in plan.sources:
                task = asyncio.create_task(self.executor.execute_source(source_config, search_params))
                tasks.append(task)
            
            source_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle exceptions
            for i, result in enumerate(source_results):
                if isinstance(result, Exception):
                    logger.error(f"Source {plan.sources[i].source_type} failed: {result}")
                    source_results[i] = SourceResult(
                        source_type=plan.sources[i].source_type,
                        data=[],
                        quality_scores=[],
                        error=str(result)
                    )
        
        else:
            # Execute sources sequentially
            for source_config in plan.sources:
                try:
                    result = await self.executor.execute_source(source_config, search_params)
                    source_results.append(result)
                    
                    # Update progress
                    response.progress_percentage = (len(source_results) / len(plan.sources)) * 80  # 80% for execution, 20% for merging
                    
                    # Check for early termination conditions
                    if plan.stop_on_sufficient_data and self._has_sufficient_data(source_results, plan):
                        logger.info(f"Stopping early - sufficient data collected")
                        break
                        
                except Exception as e:
                    logger.error(f"Source {source_config.source_type} failed: {e}")
                    source_results.append(SourceResult(
                        source_type=source_config.source_type,
                        data=[],
                        quality_scores=[],
                        error=str(e)
                    ))
                    
                    if plan.stop_on_first_failure:
                        logger.info(f"Stopping due to first failure: {e}")
                        break
        
        return source_results
    
    def _has_sufficient_data(self, source_results: List[SourceResult], plan: ExecutionPlan) -> bool:
        """Check if sufficient data has been collected for early termination"""
        total_records = sum(len(result.data) for result in source_results)
        
        if plan.target_result_count and total_records >= plan.target_result_count:
            return True
        
        # Could add other sufficiency criteria here
        return False
    
    def _create_source_executions(self, source_results: List[SourceResult]) -> List[SourceExecution]:
        """Create SourceExecution objects from SourceResult objects"""
        executions = []
        
        for result in source_results:
            status = ExecutionStatus.COMPLETED if not result.error else ExecutionStatus.FAILED
            avg_quality = sum(result.quality_scores) / len(result.quality_scores) if result.quality_scores else 0.0
            
            execution = SourceExecution(
                source_type=result.source_type,
                status=status,
                started_at=datetime.now(timezone.utc),  # Would track actual start time in real implementation
                completed_at=datetime.now(timezone.utc),
                duration_seconds=result.execution_time,
                records_found=len(result.data),
                records_accepted=len(result.data),  # Simplified - would apply quality filtering
                average_quality_score=avg_quality,
                results=result.data,
                metadata=result.metadata,
                error_message=result.error
            )
            
            executions.append(execution)
        
        return executions
    
    def _filter_by_quality(self, data: List[Dict[str, Any]], threshold: QualityThreshold) -> List[Dict[str, Any]]:
        """Filter results based on quality thresholds"""
        if not self.config.enable_quality_scoring:
            return data
        
        filtered = []
        for record in data:
            quality_score = record.get('_quality_score', 0.0)
            
            if quality_score >= threshold.minimum_score and quality_score >= threshold.reject_below:
                filtered.append(record)
        
        return filtered
    
    def _group_results_by_source(self, source_results: List[SourceResult]) -> Dict[DataSourceType, List[Dict[str, Any]]]:
        """Group results by data source type"""
        grouped = {}
        
        for result in source_results:
            grouped[result.source_type] = result.data
        
        return grouped
    
    def _calculate_metrics(self, source_results: List[SourceResult], merge_metadata: Dict[str, Any], final_data: List[Dict[str, Any]]) -> OrchestratorMetrics:
        """Calculate orchestration metrics"""
        metrics = OrchestratorMetrics()
        
        # Basic metrics
        metrics.total_sources_executed = len(source_results)
        metrics.successful_sources = len([r for r in source_results if not r.error])
        metrics.failed_sources = len([r for r in source_results if r.error])
        
        # Data metrics
        metrics.total_records_found = sum(len(r.data) for r in source_results)
        metrics.total_records_accepted = metrics.total_records_found  # Simplified
        metrics.duplicates_removed = merge_metadata.get('duplicates_removed', 0)
        metrics.final_record_count = len(final_data)
        
        # Quality metrics
        all_quality_scores = []
        for result in source_results:
            all_quality_scores.extend(result.quality_scores)
        
        if all_quality_scores:
            metrics.average_quality_score = sum(all_quality_scores) / len(all_quality_scores)
        
        # Performance metrics
        execution_times = [r.execution_time for r in source_results if r.execution_time > 0]
        if execution_times:
            metrics.total_execution_time = max(execution_times)  # For parallel execution
            metrics.fastest_source_time = min(execution_times)
            metrics.slowest_source_time = max(execution_times)
        
        # Source-specific metrics
        for result in source_results:
            metrics.source_performance[result.source_type] = {
                'records_found': len(result.data),
                'execution_time': result.execution_time,
                'average_quality': sum(result.quality_scores) / len(result.quality_scores) if result.quality_scores else 0.0,
                'error': result.error
            }
        
        return metrics
    
    def get_orchestration(self, execution_id: str) -> Optional[OrchestratorResponse]:
        """Get orchestration by execution ID"""
        return self.active_orchestrations.get(execution_id)
    
    def list_orchestrations(self, status: Optional[ExecutionStatus] = None) -> List[OrchestratorResponse]:
        """List orchestrations with optional status filter"""
        orchestrations = list(self.active_orchestrations.values())
        
        if status:
            orchestrations = [o for o in orchestrations if o.status == status]
        
        return sorted(orchestrations, key=lambda o: o.started_at, reverse=True)
    
    async def cancel_orchestration(self, execution_id: str) -> bool:
        """Cancel a running orchestration"""
        # Cancel async task if exists
        task = self.orchestration_tasks.get(execution_id)
        if task and not task.done():
            task.cancel()
            self.orchestration_tasks.pop(execution_id, None)
        
        # Update orchestration status
        orchestration = self.active_orchestrations.get(execution_id)
        if orchestration and orchestration.status == ExecutionStatus.EXECUTING:
            orchestration.status = ExecutionStatus.CANCELLED
            orchestration.completed_at = datetime.now(timezone.utc)
            return True
        
        return False

# Service factory function
async def get_orchestrator_service(config: OrchestratorConfig) -> OrchestratorService:
    """Factory function to create orchestrator service instance"""
    return OrchestratorService(config)