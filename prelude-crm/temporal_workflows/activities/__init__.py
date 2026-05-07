"""
Temporal Activities for CRM Service
=====================================

Activities are the building blocks of Temporal workflows.
Each activity performs a specific task and can be retried independently.

Includes:
- Scheduler activities (tenant discovery, summary generation, signal evaluation)
- Email activities (imported separately in worker.py to avoid sandbox issues)

NOTE: Email activities are NOT imported here to avoid Temporal sandbox validation
issues. They are imported directly in worker.py instead.
"""

from .tenant_discovery import discover_all_tenants
from .summary_generation import generate_summaries_for_tenant
from .signal_evaluation import evaluate_signals_for_tenant

__all__ = [
    'discover_all_tenants',
    'generate_summaries_for_tenant',
    'evaluate_signals_for_tenant',
]

