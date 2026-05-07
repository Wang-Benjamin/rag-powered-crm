"""
Apollo.io lead generation service.

High-quality lead generation using Apollo.io API focused on essential business data:
- Company name
- Contact name  
- Contact email
- Website URL
"""

from .client import ApolloClient
from .service import ApolloLeadService
from .schemas import ApolloSearchRequest, ApolloLead, ApolloSearchResponse

__all__ = [
    "ApolloClient",
    "ApolloLeadService", 
    "ApolloSearchRequest",
    "ApolloLead",
    "ApolloSearchResponse"
]