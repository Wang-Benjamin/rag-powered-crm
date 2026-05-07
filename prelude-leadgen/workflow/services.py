import asyncio
import uuid
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
import logging
import json
from copy import deepcopy

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

logger = logging.getLogger(__name__)

class WorkflowServiceError(Exception):
    """Workflow service specific errors"""
    pass

@dataclass
class WorkflowMetrics:
    """Metrics for workflow execution"""
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    cancelled_executions: int = 0
    average_duration: float = 0.0
    step_success_rates: Dict[str, float] = field(default_factory=dict)
    active_executions: int = 0
    
class StepExecutor:
    """Base class for step executors"""
    
    def __init__(self, step_type: StepType):
        self.step_type = step_type
        
    async def execute(self, step: WorkflowStep, context: ExecutionContext) -> Dict[str, Any]:
        """Execute a workflow step"""
        raise NotImplementedError("Subclasses must implement execute method")
        
    def validate_parameters(self, parameters: Dict[str, Any]) -> List[str]:
        """Validate step parameters"""
        return []  # No validation errors by default

class MockStepExecutor(StepExecutor):
    """Mock step executor for testing and demonstration"""
    
    async def execute(self, step: WorkflowStep, context: ExecutionContext) -> Dict[str, Any]:
        """Mock execution that simulates processing"""
        # Simulate processing time
        processing_time = step.parameters.get('processing_time', 1.0)
        await asyncio.sleep(processing_time)
        
        # Generate mock results based on step type
        if self.step_type == StepType.YELLOWPAGES_SEARCH:
            return {
                'leads_found': step.parameters.get('expected_leads', 25),
                'search_terms': step.parameters.get('search_terms', ['business']),
                'location': step.parameters.get('location', 'Toronto, ON'),
                'quality_score': 85.0
            }
        elif self.step_type == StepType.LINKEDIN_ENRICHMENT:
            return {
                'profiles_enriched': step.parameters.get('profiles_count', 10),
                'success_rate': 0.8,
                'data_completeness': 92.0
            }
        elif self.step_type == StepType.PERPLEXITY_RESEARCH:
            return {
                'research_completed': True,
                'insights_generated': 5,
                'confidence_score': 0.88
            }
        elif self.step_type == StepType.GOOGLEMAPS_ANALYSIS:
            return {
                'locations_analyzed': step.parameters.get('locations_count', 50),
                'density_score': 7.2,
                'competitive_analysis': {'competitors_found': 15}
            }
        elif self.step_type == StepType.CRM_INTEGRATION:
            return {
                'records_synced': step.parameters.get('records_count', 30),
                'sync_success_rate': 0.95,
                'duplicates_detected': 3
            }
        elif self.step_type == StepType.EMAIL_GENERATION:
            return {
                'emails_generated': step.parameters.get('email_count', 20),
                'personalization_score': 0.82
            }
        else:
            return {
                'status': 'completed',
                'message': f'Mock execution of {self.step_type}',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

class WorkflowEngine:
    """Core workflow execution engine"""
    
    def __init__(self):
        self.step_executors: Dict[StepType, StepExecutor] = {}
        self.active_executions: Dict[str, WorkflowExecution] = {}
        self.execution_tasks: Dict[str, asyncio.Task] = {}
        
        # Register mock executors for all step types
        for step_type in StepType:
            self.step_executors[step_type] = MockStepExecutor(step_type)
    
    def register_executor(self, step_type: StepType, executor: StepExecutor):
        """Register a custom step executor"""
        self.step_executors[step_type] = executor
    
    async def execute_step(self, step: WorkflowStep, context: ExecutionContext) -> StepExecution:
        """Execute a single workflow step"""
        step_execution = StepExecution(
            step_id=step.id,
            status=StepStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            input_data=deepcopy(step.parameters)
        )
        
        try:
            # Check if executor exists for step type
            if step.type not in self.step_executors:
                raise WorkflowServiceError(f"No executor registered for step type: {step.type}")
            
            executor = self.step_executors[step.type]
            
            # Validate step parameters
            validation_errors = executor.validate_parameters(step.parameters)
            if validation_errors:
                step_execution.status = StepStatus.FAILED
                step_execution.error_message = f"Parameter validation failed: {', '.join(validation_errors)}"
                return step_execution
            
            # Execute the step with timeout
            try:
                if step.timeout:
                    output_data = await asyncio.wait_for(
                        executor.execute(step, context),
                        timeout=step.timeout
                    )
                else:
                    output_data = await executor.execute(step, context)
                
                step_execution.output_data = output_data
                step_execution.status = StepStatus.COMPLETED
                
                # Update context variables with output mappings
                for output_key, variable_name in step.output_mappings.items():
                    if output_key in output_data:
                        context.variables[variable_name] = output_data[output_key]
                
            except asyncio.TimeoutError:
                step_execution.status = StepStatus.FAILED
                step_execution.error_message = f"Step timed out after {step.timeout} seconds"
            
        except Exception as e:
            step_execution.status = StepStatus.FAILED
            step_execution.error_message = str(e)
            logger.error(f"Step {step.id} execution failed: {e}")
        
        finally:
            step_execution.completed_at = datetime.now(timezone.utc)
            if step_execution.started_at:
                duration = step_execution.completed_at - step_execution.started_at
                step_execution.duration_seconds = duration.total_seconds()
        
        return step_execution
    
    def evaluate_condition(self, condition: WorkflowCondition, context: ExecutionContext) -> bool:
        """Evaluate a workflow condition"""
        variable_value = context.variables.get(condition.variable)
        
        if condition.operator == ConditionOperator.EQUALS:
            return variable_value == condition.value
        elif condition.operator == ConditionOperator.NOT_EQUALS:
            return variable_value != condition.value
        elif condition.operator == ConditionOperator.GREATER_THAN:
            return variable_value > condition.value if variable_value is not None else False
        elif condition.operator == ConditionOperator.LESS_THAN:
            return variable_value < condition.value if variable_value is not None else False
        elif condition.operator == ConditionOperator.CONTAINS:
            return condition.value in variable_value if variable_value else False
        elif condition.operator == ConditionOperator.NOT_CONTAINS:
            return condition.value not in variable_value if variable_value else True
        elif condition.operator == ConditionOperator.IS_NULL:
            return variable_value is None
        elif condition.operator == ConditionOperator.IS_NOT_NULL:
            return variable_value is not None
        elif condition.operator == ConditionOperator.IN:
            return variable_value in condition.value if isinstance(condition.value, (list, tuple)) else False
        elif condition.operator == ConditionOperator.NOT_IN:
            return variable_value not in condition.value if isinstance(condition.value, (list, tuple)) else True
        else:
            logger.warning(f"Unknown condition operator: {condition.operator}")
            return False
    
    def should_execute_step(self, step: WorkflowStep, context: ExecutionContext) -> bool:
        """Check if a step should be executed based on conditions"""
        if not step.conditions:
            return True
        
        # All conditions must be true for step to execute
        return all(self.evaluate_condition(condition, context) for condition in step.conditions)
    
    async def execute_workflow(self, workflow: WorkflowDefinition, context: ExecutionContext) -> WorkflowExecution:
        """Execute a complete workflow"""
        execution = WorkflowExecution(
            execution_id=context.execution_id,
            workflow_id=workflow.id,
            workflow_version=workflow.version,
            status=WorkflowStatus.RUNNING,
            context=context,
            total_steps=len(workflow.steps)
        )
        
        # Store active execution
        self.active_executions[execution.execution_id] = execution
        
        try:
            # Initialize workflow variables
            for variable in workflow.variables:
                if variable.name not in context.variables:
                    context.variables[variable.name] = variable.default_value
            
            # Create dependency graph
            step_map = {step.id: step for step in workflow.steps}
            completed_steps = set()
            failed_steps = set()
            
            # Execute steps based on dependencies
            while len(completed_steps) + len(failed_steps) < len(workflow.steps):
                # Find steps ready to execute
                ready_steps = []
                for step in workflow.steps:
                    if (
                        step.id not in completed_steps 
                        and step.id not in failed_steps
                        and all(dep in completed_steps for dep in step.depends_on)
                        and self.should_execute_step(step, context)
                    ):
                        ready_steps.append(step)
                
                if not ready_steps:
                    # Check if we're stuck due to failed dependencies
                    remaining_steps = [
                        step for step in workflow.steps 
                        if step.id not in completed_steps and step.id not in failed_steps
                    ]
                    
                    if remaining_steps:
                        # Mark remaining steps as skipped if their dependencies failed
                        for step in remaining_steps:
                            if any(dep in failed_steps for dep in step.depends_on):
                                step_execution = StepExecution(
                                    step_id=step.id,
                                    status=StepStatus.SKIPPED,
                                    started_at=datetime.now(timezone.utc),
                                    completed_at=datetime.now(timezone.utc),
                                    error_message="Skipped due to failed dependencies"
                                )
                                execution.step_executions.append(step_execution)
                                execution.skipped_steps += 1
                                failed_steps.add(step.id)
                    break
                
                # Execute ready steps (can be done in parallel)
                step_tasks = []
                for step in ready_steps:
                    task = asyncio.create_task(self.execute_step(step, context))
                    step_tasks.append((step.id, task))
                
                # Wait for all steps to complete
                for step_id, task in step_tasks:
                    try:
                        step_execution = await task
                        execution.step_executions.append(step_execution)
                        
                        if step_execution.status == StepStatus.COMPLETED:
                            completed_steps.add(step_id)
                            execution.completed_steps += 1
                        else:
                            failed_steps.add(step_id)
                            execution.failed_steps += 1
                            
                            # Check if workflow should continue on failure
                            step = step_map[step_id]
                            if not step.continue_on_failure:
                                # Stop workflow execution
                                execution.status = WorkflowStatus.FAILED
                                execution.error_message = f"Workflow failed at step {step_id}: {step_execution.error_message}"
                                break
                                
                    except Exception as e:
                        logger.error(f"Unexpected error executing step {step_id}: {e}")
                        failed_steps.add(step_id)
                        execution.failed_steps += 1
                
                # Check if workflow should stop due to failure
                if execution.status == WorkflowStatus.FAILED:
                    break
            
            # Determine final workflow status
            if execution.status != WorkflowStatus.FAILED:
                if execution.failed_steps == 0:
                    execution.status = WorkflowStatus.COMPLETED
                elif execution.completed_steps > 0:
                    execution.status = WorkflowStatus.COMPLETED  # Partial success still counts as completed
                else:
                    execution.status = WorkflowStatus.FAILED
            
            # Collect final outputs
            for step_execution in execution.step_executions:
                if step_execution.status == StepStatus.COMPLETED:
                    execution.final_output.update(step_execution.output_data)
            
        except Exception as e:
            execution.status = WorkflowStatus.FAILED
            execution.error_message = str(e)
            logger.error(f"Workflow {workflow.id} execution failed: {e}")
        
        finally:
            execution.completed_at = datetime.now(timezone.utc)
            if execution.started_at:
                duration = execution.completed_at - execution.started_at
                execution.duration_seconds = duration.total_seconds()
            
            # Remove from active executions
            self.active_executions.pop(execution.execution_id, None)
        
        return execution

class WorkflowService:
    """Service for managing and executing workflows"""
    
    def __init__(self, config: WorkflowConfig):
        self.config = config
        self.engine = WorkflowEngine()
        self.workflows: Dict[str, WorkflowDefinition] = {}
        self.executions: Dict[str, WorkflowExecution] = {}
        self.metrics = WorkflowMetrics()
        
    def register_workflow(self, workflow: WorkflowDefinition):
        """Register a workflow definition"""
        self.workflows[workflow.id] = workflow
        logger.info(f"Registered workflow: {workflow.id} v{workflow.version}")
    
    def get_workflow(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        """Get a workflow definition by ID"""
        return self.workflows.get(workflow_id)
    
    def list_workflows(self) -> List[WorkflowDefinition]:
        """List all registered workflows"""
        return list(self.workflows.values())
    
    async def execute_workflow(self, request: WorkflowExecutionRequest) -> WorkflowExecutionResponse:
        """Execute a workflow"""
        # Get workflow definition
        workflow = self.get_workflow(request.workflow_id)
        if not workflow:
            raise WorkflowServiceError(f"Workflow not found: {request.workflow_id}")
        
        if not workflow.enabled:
            raise WorkflowServiceError(f"Workflow is disabled: {request.workflow_id}")
        
        # Check concurrent execution limit
        active_count = len([e for e in self.executions.values() if e.status == WorkflowStatus.RUNNING])
        if active_count >= self.config.max_concurrent_workflows:
            raise WorkflowServiceError("Maximum concurrent workflows exceeded")
        
        # Create execution context
        execution_id = str(uuid.uuid4())
        context = ExecutionContext(
            execution_id=execution_id,
            trigger_type=request.trigger_type,
            variables=deepcopy(request.input_variables),
            global_context=deepcopy(request.context),
            priority=request.priority,
            timeout=request.timeout or self.config.default_workflow_timeout
        )
        
        # Create initial response
        response = WorkflowExecutionResponse(
            execution_id=execution_id,
            workflow_id=workflow.id,
            status=WorkflowStatus.CREATED,
            total_steps=len(workflow.steps),
            execution_url=f"/api/workflows/executions/{execution_id}"
        )
        
        if request.async_execution:
            # Start workflow execution asynchronously
            task = asyncio.create_task(self._execute_workflow_async(workflow, context))
            self.engine.execution_tasks[execution_id] = task
            response.status = WorkflowStatus.RUNNING
        else:
            # Execute workflow synchronously
            execution = await self.engine.execute_workflow(workflow, context)
            self.executions[execution_id] = execution
            self._update_metrics(execution)
            
            response.status = execution.status
            response.completed_steps = execution.completed_steps
            response.progress_percentage = (execution.completed_steps / execution.total_steps) * 100
            response.final_output = execution.final_output
            response.error_message = execution.error_message
        
        return response
    
    async def _execute_workflow_async(self, workflow: WorkflowDefinition, context: ExecutionContext):
        """Execute workflow asynchronously"""
        try:
            execution = await self.engine.execute_workflow(workflow, context)
            self.executions[execution.execution_id] = execution
            self._update_metrics(execution)
            
            # Clean up task reference
            self.engine.execution_tasks.pop(execution.execution_id, None)
            
            logger.info(f"Workflow {workflow.id} execution {execution.execution_id} completed with status: {execution.status}")
            
        except Exception as e:
            logger.error(f"Async workflow execution failed: {e}")
            self.engine.execution_tasks.pop(context.execution_id, None)
    
    def _update_metrics(self, execution: WorkflowExecution):
        """Update workflow metrics"""
        self.metrics.total_executions += 1
        
        if execution.status == WorkflowStatus.COMPLETED:
            self.metrics.successful_executions += 1
        elif execution.status == WorkflowStatus.FAILED:
            self.metrics.failed_executions += 1
        elif execution.status == WorkflowStatus.CANCELLED:
            self.metrics.cancelled_executions += 1
        
        # Update average duration
        if execution.duration_seconds:
            total_duration = (self.metrics.average_duration * (self.metrics.total_executions - 1)) + execution.duration_seconds
            self.metrics.average_duration = total_duration / self.metrics.total_executions
        
        # Update step success rates
        for step_execution in execution.step_executions:
            step_type = step_execution.step_id
            if step_type not in self.metrics.step_success_rates:
                self.metrics.step_success_rates[step_type] = 0.0
            
            # This is simplified - in practice you'd track successes vs total attempts
            if step_execution.status == StepStatus.COMPLETED:
                self.metrics.step_success_rates[step_type] = min(100.0, self.metrics.step_success_rates[step_type] + 1.0)
    
    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get workflow execution by ID"""
        return self.executions.get(execution_id)
    
    def list_executions(self, workflow_id: Optional[str] = None, status: Optional[WorkflowStatus] = None) -> List[WorkflowExecution]:
        """List workflow executions with optional filters"""
        executions = list(self.executions.values())
        
        if workflow_id:
            executions = [e for e in executions if e.workflow_id == workflow_id]
        
        if status:
            executions = [e for e in executions if e.status == status]
        
        return sorted(executions, key=lambda e: e.started_at, reverse=True)
    
    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel a running workflow execution"""
        # Cancel async task if exists
        task = self.engine.execution_tasks.get(execution_id)
        if task and not task.done():
            task.cancel()
            self.engine.execution_tasks.pop(execution_id, None)
        
        # Update execution status
        execution = self.executions.get(execution_id)
        if execution and execution.status == WorkflowStatus.RUNNING:
            execution.status = WorkflowStatus.CANCELLED
            execution.completed_at = datetime.now(timezone.utc)
            return True
        
        return False
    
    def get_metrics(self) -> WorkflowMetrics:
        """Get current workflow metrics"""
        # Update active executions count
        self.metrics.active_executions = len([e for e in self.executions.values() if e.status == WorkflowStatus.RUNNING])
        return self.metrics
    
    def register_step_executor(self, step_type: StepType, executor: StepExecutor):
        """Register a custom step executor"""
        self.engine.register_executor(step_type, executor)

# Service factory function
async def get_workflow_service(config: WorkflowConfig) -> WorkflowService:
    """Factory function to create workflow service instance"""
    return WorkflowService(config)