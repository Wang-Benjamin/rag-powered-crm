"""
Lead-related Pydantic models and schemas.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from config.constants import LeadStatus, LeadSource


class ContactInfo(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    linkedin: Optional[str] = None
    

class Lead(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., description="Lead's full name")
    company: str = Field(..., description="Company name")
    position: Optional[str] = None
    location: str = Field(..., description="Geographic location")
    industry: Optional[str] = None
    company_size: Optional[str] = None
    revenue: Optional[str] = None
    products_services: Optional[List[str]] = Field(default_factory=list, description="Products/services offered")
    employees_count: Optional[int] = Field(None, ge=0, description="Number of employees")

    # Individual contact fields (new structure)
    website: Optional[str] = Field(None, description="Company website URL")
    linkedin_url: Optional[str] = Field(None, description="Company LinkedIn URL")

    # Keep contact_info for backward compatibility
    contact_info: Optional[ContactInfo] = None

    # Lead management fields
    status: LeadStatus = Field(default=LeadStatus.NEW, description="Current lead status")
    source: LeadSource = Field(default=LeadSource.MANUAL_ENTRY, description="Lead source")
    score: Optional[int] = Field(default=0, ge=0, le=100, description="Lead score (0-100)")

    # Metadata
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None


class LeadCreate(BaseModel):
    name: Optional[str] = Field(None, description="Lead's full name")
    company: str = Field(..., description="Company name")
    position: Optional[str] = None
    location: Optional[str] = Field(None, description="Geographic location")
    industry: Optional[str] = None
    company_size: Optional[str] = None
    revenue: Optional[str] = None
    products_services: Optional[List[str]] = Field(default_factory=list)
    employees_count: Optional[int] = Field(None, ge=0)

    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    contact_info: Optional[ContactInfo] = None

    status: Optional[LeadStatus] = LeadStatus.NEW
    source: Optional[LeadSource] = LeadSource.MANUAL_ENTRY
    score: Optional[int] = Field(default=0, ge=0, le=100)

    # Personnel data for creating lead with associated contacts
    personnel: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Associated personnel")


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    position: Optional[str] = None
    location: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    revenue: Optional[str] = None
    products_services: Optional[List[str]] = None
    employees_count: Optional[int] = Field(None, ge=0)

    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    contact_info: Optional[ContactInfo] = None

    status: Optional[LeadStatus] = None
    source: Optional[LeadSource] = None
    score: Optional[int] = Field(None, ge=0, le=100)


class LeadsResponse(BaseModel):
    """Unified pagination response format."""
    data: List[Dict[str, Any]]
    total: int
    page: int
    perPage: int
    totalPages: int


class LeadWithPersonnelResponse(BaseModel):
    """Response model for a lead with its associated personnel - accepts any fields from database"""
    model_config = {"extra": "allow"}

    lead_id: Optional[str] = None
    id: Optional[str] = None
    company: Optional[str] = None
    personnel: List[Dict[str, Any]] = Field(default_factory=list)