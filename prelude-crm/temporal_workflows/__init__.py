"""
Temporal Workflows for CRM Schedulers
======================================

This package contains Temporal workflows and activities that replace
Google Cloud Scheduler + Cloud Run Jobs for automated CRM tasks.

Architecture:
- Workflows: Orchestrate multi-tenant processing
- Activities: Execute business logic for each tenant
- Worker: Runs inside CRM service to execute workflows

Workflows:
- MultiTenantSummaryWorkflow: Generate interaction summaries for all tenants
- MultiTenantSignalWorkflow: Evaluate buying signals for all tenants

Activities:
- discover_all_tenants: Query user_profiles to find all tenant databases
- generate_summaries_for_tenant: Generate summaries for one tenant
- evaluate_signals_for_tenant: Evaluate signals for one tenant
"""

__version__ = "1.0.0"

