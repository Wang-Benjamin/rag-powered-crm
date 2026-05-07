"""Pydantic models for CRM service"""

import math
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, validator


# ============================================================================
# Deal Activity Models
# ============================================================================

class DealNoteCreate(BaseModel):
    """Model for creating a note linked to a deal"""
    title: Optional[str] = ""
    body: str
    star: Optional[str] = None

class DealCallSummaryCreate(BaseModel):
    """Model for creating a call summary linked to a deal"""
    content: str
    theme: Optional[str] = None
    source: Optional[str] = "deal_activity"

class DealMeetingCreate(BaseModel):
    """Model for creating a meeting linked to a deal"""
    title: str
    description: Optional[str] = None
    start_time: str  # ISO 8601 format
    end_time: str    # ISO 8601 format
    attendees: List[str] = []
    location: Optional[str] = None
    timezone: str = "UTC"

class DealActivityResponse(BaseModel):
    """Response model for deal activities"""
    notes: List[Dict[str, Any]]
    interactions: List[Dict[str, Any]]
    timeline: List[Dict[str, Any]]


# ============================================================================
# Calendar Models
# ============================================================================

class GoogleCalendarSyncRequest(BaseModel):
    time_min: Optional[str] = None  # ISO format, default to 30 days ago
    time_max: Optional[str] = None  # ISO format, default to 90 days future


def paginated_response(items, total, page, per_page, key="data"):
    """Build a paginated response envelope."""
    return {
        key: items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": math.ceil(total / per_page) if per_page > 0 else 0,
    }


# ============================================================================
# Contact / Personnel Models
# ============================================================================

class Contact(BaseModel):
    """Legacy contact model -- kept for CreateCustomerRequest backward compat."""
    id: Optional[str] = None
    name: str
    email: str
    phone: Optional[str] = ""
    title: Optional[str] = ""
    is_primary: bool = False
    notes: Optional[str] = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PersonnelResponse(BaseModel):
    """Response model for personnel records linked to a customer."""
    personnelId: str  # UUID
    firstName: Optional[str] = ""
    lastName: Optional[str] = ""
    fullName: Optional[str] = ""
    companyName: Optional[str] = ""
    email: Optional[str] = ""
    phone: Optional[str] = ""
    position: Optional[str] = ""
    department: Optional[str] = ""
    seniorityLevel: Optional[str] = ""
    linkedinUrl: Optional[str] = ""
    isPrimary: Optional[bool] = False
    source: Optional[str] = ""


# ============================================================================
# Customer Models
# ============================================================================

class Customer(BaseModel):
    id: int
    company: str
    phone: Optional[str] = ""
    location: Optional[str] = ""
    website: Optional[str] = ""
    status: str
    clientType: str
    arr: Optional[float] = 0
    totalDealValue: Optional[float] = 0
    healthScore: Optional[float] = 75
    productUsage: Optional[Dict] = {}
    recentActivities: Optional[List[Dict]] = []
    lastInteraction: Optional[str] = ""
    totalInteractions: Optional[int] = 0
    supportTickets: Optional[int] = 0
    onboardingComplete: Optional[bool] = True
    currentStage: Optional[str] = "active"
    progress: Optional[int] = 0
    renewalProbability: Optional[int] = 80
    lastContact: Optional[str] = ""
    productUsagePercentage: Optional[int] = 85
    funnelStage: str = "qualified"
    nextFollowUp: Optional[str] = ""
    recent_notes: str = ""
    recent_timeline: str = ""

    assignedEmployeeId: Optional[int] = None
    assignedEmployeeName: Optional[str] = None

    # Personnel records (replaces legacy contacts JSONB + primaryContact/email)
    personnel: Optional[List[PersonnelResponse]] = []

    # Derived from primary personnel for backward compat (email composer, meetings, etc.)
    clientEmail: Optional[str] = ""
    clientName: Optional[str] = ""

    # New columns: volume, signal, stage, lastActivity
    volume: Optional[int] = None
    signal: Optional[Dict] = None  # { "level": "red"|"purple"|"green"|"none", "label": "..." }
    stage: Optional[str] = "new"  # new, contacted, replied, engaged, quoting
    lastActivity: Optional[str] = None  # ISO 8601 timestamp

    # Trade intelligence (BoL data bridged during lead conversion + deal aggregation)
    tradeIntel: Optional[Dict] = None


class CreateCustomerRequest(BaseModel):
    name: str
    phone: Optional[str] = ""
    location: Optional[str] = ""
    website: Optional[str] = ""
    preferred_language: Optional[str] = "en"
    source: Optional[str] = "website"
    notes: Optional[str] = ""
    client_type: Optional[str] = "lead"  # 'lead' or 'customer'

    # Optional fields for clients
    health_score: Optional[float] = 75.0
    status: Optional[str] = "active"  # Customer status in clients: 'active', 'inactive', 'lost'
    progress: Optional[int] = 0
    stage: Optional[str] = "new"  # Sales pipeline stage: new, contacted, replied, engaged, quoting

    # Personnel to create alongside the customer
    contacts: Optional[List[Contact]] = []  # Backward compat: creates personnel records


class UpdateCustomerRequest(BaseModel):
    """Model for updating customer fields - all fields are optional"""
    # Client profile fields
    company: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    preferred_language: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    clientType: Optional[str] = None

    # Client detail fields
    status: Optional[str] = None  # Customer status stored on clients
    healthScore: Optional[float] = None
    currentStage: Optional[str] = None
    progress: Optional[int] = None
    stage: Optional[str] = None  # Sales pipeline stage: new, contacted, replied, engaged, quoting

    # employee_client_links field
    assignedEmployeeId: Optional[int] = None  # For updating employee assignment


# ============================================================================
# Dashboard Models
# ============================================================================

class DashboardStats(BaseModel):
    totalCustomers: int
    activeCustomers: int
    atRiskCustomers: int
    totalDealValue: float
    averageHealthScore: float
    newCustomersThisMonth: int
    churnRate: float
    expansionOpportunities: int
    supportTicketsOpen: int


# ============================================================================
# Interaction Models
# ============================================================================

class InteractionSummary(BaseModel):
    id: int
    customerId: int
    type: str
    content: str
    employeeName: str
    employeeRole: str
    employeeDepartment: Optional[str] = None
    createdAt: str
    updatedAt: Optional[str] = None
    duration: Optional[int] = None
    outcome: Optional[str] = None
    subject: Optional[str] = None
    gmailMessageId: Optional[str] = None
    email_id: Optional[str] = None  # Gmail/Outlook message ID for opening specific email
    theme: Optional[str] = None
    source: Optional[str] = None
    sourceName: Optional[str] = None
    sourceType: Optional[str] = None
    direction: Optional[str] = None  # Email direction: 'sent' or 'received'
    fromEmail: Optional[str] = None  # Email sender address
    toEmail: Optional[str] = None    # Email recipient address
    threadId: Optional[str] = None   # Gmail thread ID for grouping


class InteractionSummaryRequest(BaseModel):
    days_back: Optional[int] = 30  # Default to last 30 days


class InteractionSummaryResponse(BaseModel):
    status: str
    summary_data: Dict
    customer_id: int
    customer_name: str
    interactions_analyzed: int
    period_analyzed: str
    generated_at: str
    # Enhanced tracking fields for agent and model information
    agent_used: Optional[str] = None
    ai_model_used: Optional[str] = None


# ============================================================================
# Feedback Models
# ============================================================================

class FeedbackCreate(BaseModel):
    """Request model for creating feedback."""
    customer_id: int
    deal_id: Optional[int] = None
    feedback_category: str  # 'churn_risk', 'ai_insights', 'stage_progression', 'deal_insights'
    rating: int  # 1-5
    feedback_text: Optional[str] = None

    @validator('feedback_category')
    def validate_feedback_category(cls, v, values):
        deal_id = values.get('deal_id')
        customer_categories = ['churn_risk', 'ai_insights']
        deal_categories = ['stage_progression', 'deal_insights']

        if deal_id is not None:
            # Deal feedback
            if v not in deal_categories:
                raise ValueError(f"Invalid feedback_category '{v}' for deal feedback. Must be one of: {', '.join(deal_categories)}")
        else:
            # Customer feedback
            if v not in customer_categories:
                raise ValueError(f"Invalid feedback_category '{v}' for customer feedback. Must be one of: {', '.join(customer_categories)}")
        return v

    @validator('rating')
    def validate_rating(cls, v):
        if v < 1 or v > 5:
            raise ValueError("rating must be between 1 and 5")
        return v


class FeedbackUpdate(BaseModel):
    """Request model for updating feedback."""
    rating: Optional[int] = None  # 1-5
    feedback_text: Optional[str] = None

    @validator('rating')
    def validate_rating(cls, v):
        if v is not None and (v < 1 or v > 5):
            raise ValueError("rating must be between 1 and 5")
        return v


class FeedbackResponse(BaseModel):
    """Response model for feedback."""
    feedback_id: int
    customer_id: int
    deal_id: Optional[int] = None
    feedback_category: str
    employee_id: int
    rating: int
    feedback_history: List[Dict[str, Any]] = []  # JSONB array of feedback entries
    ai_summary: Optional[Dict[str, Any]] = None  # AI-generated summary
    created_at: str
    updated_at: str
    employee_name: Optional[str] = None
    employee_email: Optional[str] = None
