"""
Repository module for Lead Generation Service (asyncpg).

Provides async data access patterns and base repository functionality
for all database operations. All repository methods take an asyncpg
connection as first parameter.
"""

from .base import (
    BaseRepository,
    QueryResult,
    SQLBuilder,
    JSONFieldMixin
)

from .lead_repository import LeadRepository
from .personnel_repository import PersonnelRepository
from .crm_repository import CRMRepository
from .lead_email_repository import LeadEmailRepository

__all__ = [
    # Base classes
    'BaseRepository',
    'QueryResult',
    'SQLBuilder',
    'JSONFieldMixin',

    # Feature repositories
    'LeadRepository',
    'PersonnelRepository',
    'CRMRepository',
    'LeadEmailRepository'
]
