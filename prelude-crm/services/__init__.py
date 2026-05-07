"""
CRM Services Module.
Contains automated services for the CRM system.
"""

from .interaction_summary_scheduler import summary_scheduler
from .cached_summary_service import cached_summary_service

__all__ = ['summary_scheduler', 'cached_summary_service']
