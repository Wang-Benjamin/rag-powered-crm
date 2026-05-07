"""Repository pattern implementation for CRM data access layer."""

from .base import BaseRepository
from .customer_repository import CustomerRepository
from .employee_repository import EmployeeRepository
from .interaction_repository import InteractionRepository
from .email_sync_repository import EmailSyncRepository
from .contact_repository import ContactRepository
from .deal_repository import DealRepository

__all__ = [
    'BaseRepository',
    'CustomerRepository',
    'EmployeeRepository',
    'InteractionRepository',
    'EmailSyncRepository',
    'ContactRepository',
    'DealRepository',
]

