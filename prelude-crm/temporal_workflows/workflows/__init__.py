"""
Temporal Workflows for CRM Service
===================================

Workflows orchestrate the execution of activities across multiple tenants.
Includes scheduled workflows (summaries, signals) and user-triggered workflows (mass email).
"""

from .multi_tenant_summary_workflow import MultiTenantSummaryWorkflow
from .multi_tenant_signal_workflow import MultiTenantSignalWorkflow
from .personalized_mass_email_workflow import PersonalizedMassEmailWorkflow, PersonalizedMassEmailWorkflowInput

__all__ = [
    'MultiTenantSummaryWorkflow',
    'MultiTenantSignalWorkflow',
    'PersonalizedMassEmailWorkflow',
    'PersonalizedMassEmailWorkflowInput',
]

