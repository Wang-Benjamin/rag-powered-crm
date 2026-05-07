from typing import Any, Optional
import datetime
import decimal
import enum
import uuid

from sqlalchemy import ARRAY, BigInteger, Boolean, CheckConstraint, Date, DateTime, Double, Enum, ForeignKeyConstraint, Index, Integer, JSON, Numeric, PrimaryKeyConstraint, Sequence, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import INET, JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import UserDefinedType


class PgVector(UserDefinedType):
    """Minimal type for pgvector columns without requiring the pgvector package.

    ORM access intentionally unsupported — no bind/result processors. RAG code
    uses raw asyncpg with pgvector.asyncpg.register_vector for actual queries.
    This type only exists so Base.metadata.create_all() produces `vector` DDL
    for new tenant databases.
    """
    cache_ok = True
    def get_col_spec(self):
        return "vector"


class Base(DeclarativeBase):
    pass


class TemplateChannel(str, enum.Enum):
    EMAIL = 'email'
    SMS = 'sms'
    CHAT = 'chat'


class BatchJobStats(Base):
    __tablename__ = 'batch_job_stats'
    __table_args__ = (
        PrimaryKeyConstraint('job_id', name='batch_job_stats_pkey'),
        {'schema': 'public'}
    )

    job_id: Mapped[int] = mapped_column(Integer, Sequence('batch_job_stats_job_id_seq', schema='public'), primary_key=True, server_default=text("nextval('batch_job_stats_job_id_seq'::regclass)"))
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    start_time: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False)
    end_time: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    total_processed: Mapped[Optional[int]] = mapped_column(Integer)
    total_successful: Mapped[Optional[int]] = mapped_column(Integer)
    total_errors: Mapped[Optional[int]] = mapped_column(Integer)
    success_rate: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(5, 2))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('CURRENT_TIMESTAMP'))


class Campaigns(Base):
    __tablename__ = 'campaigns'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='campaigns_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'sending'::character varying"))
    email_type: Mapped[Optional[str]] = mapped_column(String(100))
    offer: Mapped[Optional[str]] = mapped_column(Text)
    ask: Mapped[Optional[str]] = mapped_column(Text)
    detail: Mapped[Optional[str]] = mapped_column(Text)
    custom_prompt: Mapped[Optional[str]] = mapped_column(Text)
    trade_context: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), comment='Trade fields used in generation: fob_price, certifications, moq, lead_time, etc.')
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    sent_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))

    campaign_emails: Mapped[list['CampaignEmails']] = relationship('CampaignEmails', back_populates='campaign')


class Clients(Base):
    __tablename__ = 'clients'
    __table_args__ = (
        PrimaryKeyConstraint('client_id', name='clients_info_pkey'),
        Index('idx_clients_status', 'status'),
        {'schema': 'public'}
    )

    client_id: Mapped[int] = mapped_column(Integer, Sequence('clients_info_client_id_seq', schema='public'), primary_key=True, server_default=text("nextval('clients_info_client_id_seq'::regclass)"))
    name: Mapped[Optional[str]] = mapped_column(String(150))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    location: Mapped[Optional[str]] = mapped_column(String(255))
    preferred_language: Mapped[Optional[str]] = mapped_column(String(50))
    source: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    website: Mapped[Optional[str]] = mapped_column(Text)
    health_score: Mapped[Optional[float]] = mapped_column(Double(53))
    status: Mapped[Optional[str]] = mapped_column(String(50))
    stage: Mapped[Optional[str]] = mapped_column(String(50), server_default=text("'new'"))
    signal: Mapped[Optional[dict]] = mapped_column(JSONB)
    trade_intel: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))

    crm_emails: Mapped[list['CrmEmails']] = relationship('CrmEmails', back_populates='customer')
    deals: Mapped[list['Deals']] = relationship('Deals', back_populates='client')
    employee_client_links: Mapped[list['EmployeeClientLinks']] = relationship('EmployeeClientLinks', back_populates='client')
    interaction_summaries: Mapped[list['InteractionSummaries']] = relationship('InteractionSummaries', back_populates='customer')
    interaction_details: Mapped[list['InteractionDetails']] = relationship('InteractionDetails', back_populates='customer')
    personnel: Mapped[list['Personnel']] = relationship('Personnel', back_populates='client')


class EmployeeInfo(Base):
    __tablename__ = 'employee_info'
    __table_args__ = (
        PrimaryKeyConstraint('employee_id', name='employee_info_pkey'),
        Index('idx_employee_info_signature_fields', 'email', postgresql_where='(signature_fields IS NOT NULL)'),
        Index('idx_employee_info_training_emails', 'training_emails', postgresql_using='gin'),
        {'schema': 'public'}
    )

    employee_id: Mapped[int] = mapped_column(Integer, Sequence('employee_info_employee_id_seq', schema='public'), primary_key=True, server_default=text("nextval('employee_info_employee_id_seq'::regclass)"))
    name: Mapped[Optional[str]] = mapped_column(String(100))
    role: Mapped[Optional[str]] = mapped_column(String(100))
    department: Mapped[Optional[str]] = mapped_column(String(100))
    email: Mapped[Optional[str]] = mapped_column(String(150))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    signature_fields: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, comment='Structured signature fields (name, title, email, phoneNumber, location, link, logoUrl). Validated by Pydantic at API layer; max 4 KB.')
    training_emails: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"), comment='Array of training email objects: [{"subject": "...", "body": "..."}]')
    access: Mapped[Optional[str]] = mapped_column(String(50), server_default=text("'user'::character varying"))
    writing_style: Mapped[Optional[dict]] = mapped_column(JSONB)

    crm_emails: Mapped[list['CrmEmails']] = relationship('CrmEmails', back_populates='employee')
    crm_feedback: Mapped[list['CrmFeedback']] = relationship('CrmFeedback', back_populates='employee')
    deals: Mapped[list['Deals']] = relationship('Deals', back_populates='employee')
    email_sync_state: Mapped[Optional['EmailSyncState']] = relationship('EmailSyncState', uselist=False, back_populates='employee')
    employee_client_links: Mapped[list['EmployeeClientLinks']] = relationship('EmployeeClientLinks', back_populates='employee')
    employee_lead_links: Mapped[list['EmployeeLeadLinks']] = relationship('EmployeeLeadLinks', back_populates='employee')
    enrichment_history: Mapped[list['EnrichmentHistory']] = relationship('EnrichmentHistory', back_populates='employee')
    oauth_tokens: Mapped[list['OauthTokens']] = relationship('OauthTokens', back_populates='employee')
    interaction_details_employee: Mapped[list['InteractionDetails']] = relationship('InteractionDetails', foreign_keys='[InteractionDetails.employee_id]', back_populates='employee')
    interaction_details_synced_by_employee: Mapped[list['InteractionDetails']] = relationship('InteractionDetails', foreign_keys='[InteractionDetails.synced_by_employee_id]', back_populates='synced_by_employee')


class Leads(Base):
    __tablename__ = 'leads'
    __table_args__ = (
        PrimaryKeyConstraint('lead_id', name='leads_pkey'),
        UniqueConstraint('company', 'location', name='unique_company_location'),
        Index('idx_leads_company', 'company'),
        # idx_leads_company_search is a functional GIN index: to_tsvector('english', company)
        # Created via raw SQL in migration, not expressible in SQLAlchemy Index()
        Index('idx_leads_created_at', 'created_at'),
        Index('idx_leads_industry', 'industry'),
        Index('idx_leads_location', 'location'),
        Index('idx_leads_ready_to_crm', 'ready_to_crm', postgresql_where='(ready_to_crm = true)'),
        Index('idx_leads_score', 'score'),
        Index('idx_leads_source', 'source'),
        Index('idx_leads_status', 'status'),
        Index('idx_leads_website', 'website'),
        {'schema': 'public'}
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    industry: Mapped[Optional[str]] = mapped_column(String(255))
    company_size: Mapped[Optional[str]] = mapped_column(String(100))
    revenue: Mapped[Optional[str]] = mapped_column(String(100))
    employees_count: Mapped[Optional[int]] = mapped_column(Integer)
    website: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[Optional[str]] = mapped_column(String(50), server_default=text("'new'::character varying"))
    score: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('CURRENT_TIMESTAMP'))
    ready_to_crm: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'), comment='AI-determined flag indicating lead is ready for CRM conversion based on email engagement analysis')
    supplier_context: Mapped[Optional[dict]] = mapped_column(JSONB, comment='Supplier breakdown from ImportYeti deep enrichment, copied on Add to Pipeline')
    import_context: Mapped[Optional[dict]] = mapped_column(JSONB, comment='Import profile (shipments, ports, products) for email compose context')
    bol_detail_context: Mapped[Optional[dict]] = mapped_column(JSONB, comment='Deep enrichment detail (timeSeries, recentBols, chinaConcentration, growth, scoring signals) for buyer detail view')

    employee_lead_links: Mapped[list['EmployeeLeadLinks']] = relationship('EmployeeLeadLinks', back_populates='lead')
    personnel: Mapped[list['Personnel']] = relationship('Personnel', back_populates='lead')


class ScheduledMassEmails(Base):
    __tablename__ = 'scheduled_mass_emails'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='scheduled_mass_emails_pkey'),
        UniqueConstraint('job_id', name='scheduled_mass_emails_job_id_key'),
        {'schema': 'public'}
    )

    id: Mapped[int] = mapped_column(Integer, Sequence('scheduled_mass_emails_id_seq', schema='public'), primary_key=True, server_default=text("nextval('scheduled_mass_emails_id_seq'::regclass)"))
    job_id: Mapped[str] = mapped_column(String(255), nullable=False)
    email_type: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'template'::character varying"))
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'scheduled'::character varying"))
    scheduled_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    total_recipients: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    cancelled_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    template_name: Mapped[Optional[str]] = mapped_column(String(255))
    provider: Mapped[Optional[str]] = mapped_column(String(50))
    sent: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))
    failed: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))



class Templates(Base):
    __tablename__ = 'templates'
    __table_args__ = (
        ForeignKeyConstraint(['created_by'], ['public.employee_info.employee_id'], ondelete='SET NULL', name='fk_templates_created_by'),
        PrimaryKeyConstraint('id', name='templates_pkey'),
        UniqueConstraint('name', 'channel', 'template_type', 'created_by', name='templates_name_channel_type_user_key'),
        Index('idx_templates_channel', 'channel'),
        Index('idx_templates_created_at', 'created_at'),
        Index('idx_templates_created_by', 'created_by'),
        Index('idx_templates_is_active', 'is_active'),
        Index('idx_templates_is_archived', 'is_archived'),
        Index('idx_templates_is_shared', 'is_shared'),
        {'comment': 'Email template system - NO AI generation, templates only',
     'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[TemplateChannel] = mapped_column(Enum(TemplateChannel, values_callable=lambda cls: [member.value for member in cls], name='template_channel'), nullable=False, server_default=text("'email'::template_channel"))
    subject: Mapped[Optional[str]] = mapped_column(Text)
    body: Mapped[Optional[str]] = mapped_column(Text)
    tokens: Mapped[Optional[dict]] = mapped_column(JSONB, comment='Valid tokens: name, primary_contact, industry, email, phone')
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('true'))
    is_archived: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'), comment='Soft delete flag - archived templates are hidden from active lists')
    performance_stats: Mapped[Optional[dict]] = mapped_column(JSONB, comment='Cached aggregate statistics: total_sends, successful_sends, failed_sends, success_rate, last_used_at')
    created_by: Mapped[Optional[int]] = mapped_column(Integer)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    description: Mapped[Optional[str]] = mapped_column(Text)
    version: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('1'))
    parent_template_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    generation_level: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))
    template_type: Mapped[Optional[str]] = mapped_column(Text, server_default=text("'base'::text"))
    is_shared: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    template_category: Mapped[Optional[str]] = mapped_column(Text, server_default=text("'user'::text"), comment="Template category: 'purpose' (system) or 'user' (user-created)")
    prompt_instructions: Mapped[Optional[str]] = mapped_column(Text, comment='AI generation instructions for this template')


class UserPreferences(Base):
    __tablename__ = 'user_preferences'
    __table_args__ = (
        CheckConstraint("email ~* '^[A-Za-z0-9._%%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'::text", name='valid_email'),
        PrimaryKeyConstraint('id', name='user_preferences_pkey'),
        UniqueConstraint('email', name='user_preferences_email_key'),
        Index('idx_user_preferences_additional_context', 'additional_context', postgresql_using='gin'),
        Index('idx_user_preferences_audience', 'audience', postgresql_using='gin'),
        Index('idx_user_preferences_created_at', 'created_at'),
        Index('idx_user_preferences_guardrails', 'guardrails', postgresql_using='gin'),
        Index('idx_user_preferences_is_complete', 'is_complete'),
        Index('idx_user_preferences_tone', 'tone', postgresql_using='gin'),
        Index('idx_user_prefs_ai_insights', 'crm_pref_ai_insights', postgresql_using='gin'),
        Index('idx_user_prefs_churn_risk', 'crm_pref_churn_risk', postgresql_using='gin'),
        Index('idx_user_prefs_deal_insights', 'crm_pref_deal_insights', postgresql_using='gin'),
        Index('idx_user_prefs_stage_progression', 'crm_pref_stage_progression', postgresql_using='gin'),
        {'comment': 'Stores user preferences for different agents', 'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    email: Mapped[str] = mapped_column(Text, nullable=False)
    tone: Mapped[Optional[dict]] = mapped_column(JSONB, comment='Step 1 responses: {formality, conciseness, proactiveness, onBrandPhrases, avoidPhrases}')
    guardrails: Mapped[Optional[dict]] = mapped_column(JSONB, comment='Step 2 responses: {topicsToAvoid, hardRestrictions, prohibitedStatements} — values are string arrays, custom entries prefixed with custom:')
    audience: Mapped[Optional[dict]] = mapped_column(JSONB, comment='Step 3 responses: {idealCustomers, roles, products}')
    additional_context: Mapped[Optional[dict]] = mapped_column(JSONB, comment='Step 4 responses: {additionalContext}')
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, comment='LLM-generated comprehensive summary of all user preferences')
    is_complete: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    crm_pref_churn_risk: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), comment='Learned user preferences for churn risk predictions based on feedback. Stores detail_level, tone, actionability, focus_areas, metrics_preference, and metadata.')
    crm_pref_ai_insights: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), comment='Learned user preferences for customer AI insights based on feedback. Stores detail_level, tone, actionability, focus_areas, metrics_preference, and metadata.')
    crm_pref_stage_progression: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), comment='Learned user preferences for deal stage progression predictions based on feedback. Stores detail_level, tone, actionability, focus_areas, metrics_preference, and metadata.')
    crm_pref_deal_insights: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), comment='Learned user preferences for deal-specific insights based on feedback. Stores detail_level, tone, actionability, focus_areas, metrics_preference, and metadata.')


class TenantSubscription(Base):
    __tablename__ = 'tenant_subscription'
    __table_args__ = (
        CheckConstraint('id = true', name='tenant_subscription_singleton'),
        {'schema': 'public'}
    )

    id: Mapped[bool] = mapped_column(Boolean, primary_key=True, server_default=text('true'))
    subscription_tier: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'trial'"))
    trial_started_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    credits_used_this_month: Mapped[decimal.Decimal] = mapped_column(Numeric(8, 2), nullable=False, server_default=text('0'))
    last_credit_reset: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    bol_onboarding_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    bol_onboarding_phase: Mapped[Optional[str]] = mapped_column(String(32))
    bol_buyers_target: Mapped[Optional[int]] = mapped_column(Integer)
    bol_buyers_ready: Mapped[Optional[int]] = mapped_column(Integer)
    bol_competitors_target: Mapped[Optional[int]] = mapped_column(Integer)
    bol_competitors_ready: Mapped[Optional[int]] = mapped_column(Integer)
    bol_warning_code: Mapped[Optional[str]] = mapped_column(String(64))
    bol_warning_meta: Mapped[Optional[dict]] = mapped_column(JSONB)
    bol_last_transition_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    bol_last_error_code: Mapped[Optional[str]] = mapped_column(String(64))
    bol_last_error_meta: Mapped[Optional[dict]] = mapped_column(JSONB)
    bol_attempt_count: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))
    bol_onboarding_deep_enrich_reserved: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))
    hs_codes: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    target_products: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    company_profile: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    factory_details: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    entitlement_overrides: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))


class FactoryCertifications(Base):
    __tablename__ = 'factory_certifications'
    __table_args__ = (
        PrimaryKeyConstraint('cert_id', name='factory_certifications_pkey'),
        CheckConstraint("status::text = ANY (ARRAY['active'::character varying, 'expired'::character varying, 'pending'::character varying]::text[])", name='factory_certifications_status_check'),
        Index('idx_factory_certs_email', 'email'),
        Index('idx_factory_certs_expiry', 'expiry_date', postgresql_where=text('expiry_date IS NOT NULL')),
        {'schema': 'public'}
    )

    cert_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    cert_type: Mapped[Optional[str]] = mapped_column(String(255))
    cert_number: Mapped[Optional[str]] = mapped_column(String(100))
    issuing_body: Mapped[Optional[str]] = mapped_column(String(255))
    issue_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    expiry_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    status: Mapped[Optional[str]] = mapped_column(String(50), server_default=text("'active'::character varying"))
    document_url: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))


class DealRoomViews(Base):
    __tablename__ = 'deal_room_views'
    __table_args__ = (
        ForeignKeyConstraint(['deal_id'], ['public.deals.deal_id'], ondelete='CASCADE', name='deal_room_views_deal_id_fkey'),
        PrimaryKeyConstraint('view_id', name='deal_room_views_pkey'),
        UniqueConstraint('deal_id', 'session_token', name='deal_room_views_deal_session_key'),
        Index('idx_deal_room_views_deal_id', 'deal_id'),
        Index('idx_deal_room_views_started_at', 'started_at'),
        {'schema': 'public'}
    )

    view_id: Mapped[int] = mapped_column(Integer, Sequence('deal_room_views_view_id_seq', schema='public'), primary_key=True, server_default=text("nextval('deal_room_views_view_id_seq'::regclass)"))
    deal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    visitor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    session_token: Mapped[str] = mapped_column(String(64), nullable=False)
    viewer_email: Mapped[Optional[str]] = mapped_column(String(255))
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    sections_viewed: Mapped[Optional[list]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))

    deal: Mapped['Deals'] = relationship('Deals', back_populates='deal_room_views')


class CampaignEmails(Base):
    __tablename__ = 'campaign_emails'
    __table_args__ = (
        ForeignKeyConstraint(['campaign_id'], ['public.campaigns.id'], ondelete='CASCADE', name='campaign_emails_campaign_id_fkey'),
        ForeignKeyConstraint(['customer_id'], ['public.clients.client_id'], ondelete='CASCADE', name='campaign_emails_customer_id_fkey'),
        ForeignKeyConstraint(['email_id'], ['public.crm_emails.email_id'], ondelete='SET NULL', name='campaign_emails_email_id_fkey'),
        PrimaryKeyConstraint('id', name='campaign_emails_pkey'),
        UniqueConstraint('campaign_id', 'customer_id', name='uq_campaign_customer'),
        Index('idx_campaign_emails_campaign_id', 'campaign_id'),
        Index('idx_campaign_emails_email_id', 'email_id'),
        {'schema': 'public'}
    )

    id: Mapped[int] = mapped_column(Integer, Sequence('campaign_emails_id_seq', schema='public'), primary_key=True, server_default=text("nextval('campaign_emails_id_seq'::regclass)"))
    campaign_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    customer_id: Mapped[Optional[int]] = mapped_column(Integer)
    email_id: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'queued'"))
    sent_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    campaign: Mapped['Campaigns'] = relationship('Campaigns', back_populates='campaign_emails')


class CrmEmails(Base):
    __tablename__ = 'crm_emails'
    __table_args__ = (
        ForeignKeyConstraint(['customer_id'], ['public.clients.client_id'], ondelete='CASCADE', name='fk_customer'),
        ForeignKeyConstraint(['deal_id'], ['public.deals.deal_id'], ondelete='SET NULL', name='fk_crm_emails_deal'),
        ForeignKeyConstraint(['employee_id'], ['public.employee_info.employee_id'], ondelete='SET NULL', name='fk_employee'),
        PrimaryKeyConstraint('email_id', name='crm_email_pkey'),
        UniqueConstraint('message_id', name='crm_email_message_id_key'),
        UniqueConstraint('tracking_token', name='crm_email_tracking_token_key'),
        Index('idx_crm_email_created_at', 'created_at'),
        Index('idx_crm_email_customer_id', 'customer_id'),
        Index('idx_crm_email_deal_id', 'deal_id'),
        Index('idx_crm_email_direction', 'direction'),
        Index('idx_crm_email_employee_id', 'employee_id'),
        Index('idx_crm_email_opened_at', 'opened_at'),
        Index('idx_crm_email_thread_id', 'thread_id', postgresql_where='(thread_id IS NOT NULL)'),
        Index('idx_crm_emails_thread', 'customer_id', 'thread_id'),
        {'schema': 'public'}
    )

    email_id: Mapped[int] = mapped_column(Integer, Sequence('crm_email_email_id_seq', schema='public'), primary_key=True, server_default=text("nextval('crm_email_email_id_seq'::regclass)"))
    from_email: Mapped[str] = mapped_column(String(255), nullable=False)
    to_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    customer_id: Mapped[Optional[int]] = mapped_column(Integer)
    deal_id: Mapped[Optional[int]] = mapped_column(Integer)
    employee_id: Mapped[Optional[int]] = mapped_column(Integer)
    message_id: Mapped[Optional[str]] = mapped_column(String(500))
    thread_id: Mapped[Optional[str]] = mapped_column(String(255))
    in_reply_to: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    tracking_token: Mapped[Optional[str]] = mapped_column(String(50))
    tracking_token_expires_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    opened_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    intent: Mapped[Optional[str]] = mapped_column(String(50), comment='Action type: objection, referral, meeting, status_update')
    draft_body: Mapped[Optional[str]] = mapped_column(Text, comment='AI-generated draft reply (NULL for informational emails)')
    rfc_message_id: Mapped[Optional[str]] = mapped_column(String(500), comment='RFC 2822 Message-ID header value')
    conversation_state: Mapped[Optional[dict]] = mapped_column(JSONB)
    embedding = mapped_column(PgVector(), nullable=True)
    text_search = mapped_column(TSVECTOR, nullable=True)

    customer: Mapped[Optional['Clients']] = relationship('Clients', back_populates='crm_emails')
    employee: Mapped[Optional['EmployeeInfo']] = relationship('EmployeeInfo', back_populates='crm_emails')


class CrmFeedback(Base):
    __tablename__ = 'crm_feedback'
    __table_args__ = (
        CheckConstraint('deal_id IS NULL OR deal_id IS NOT NULL AND customer_id IS NOT NULL', name='check_deal_feedback_has_customer'),
        CheckConstraint("feedback_category::text = ANY (ARRAY['churn_risk'::character varying, 'ai_insights'::character varying, 'stage_progression'::character varying, 'deal_insights'::character varying]::text[])", name='check_feedback_category'),
        CheckConstraint('rating >= 1 AND rating <= 5', name='crm_feedback_rating_check'),
        ForeignKeyConstraint(['employee_id'], ['public.employee_info.employee_id'], ondelete='CASCADE', name='crm_feedback_employee_id_fkey'),
        PrimaryKeyConstraint('feedback_id', name='crm_feedback_pkey'),
        UniqueConstraint('customer_id', 'deal_id', 'employee_id', 'feedback_category', name='crm_feedback_unique_constraint'),
        Index('idx_crm_feedback_ai_summary', 'ai_summary', postgresql_using='gin'),
        Index('idx_crm_feedback_category', 'feedback_category'),
        Index('idx_crm_feedback_created_at', 'created_at'),
        Index('idx_crm_feedback_customer_id', 'customer_id'),
        Index('idx_crm_feedback_deal_id', 'deal_id', postgresql_where='(deal_id IS NOT NULL)'),
        Index('idx_crm_feedback_employee_id', 'employee_id'),
        {'comment': 'CRM feedback system with category-specific feedback for customers '
                'and deals',
     'schema': 'public'}
    )

    feedback_id: Mapped[int] = mapped_column(Integer, Sequence('crm_feedback_feedback_id_seq', schema='public'), primary_key=True, server_default=text("nextval('crm_feedback_feedback_id_seq'::regclass)"))
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False, comment='Customer ID (always populated)')
    employee_id: Mapped[int] = mapped_column(Integer, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False, comment='Rating from 1 to 5 stars (current rating)')
    feedback_category: Mapped[str] = mapped_column(String(50), nullable=False, comment='Category: churn_risk, ai_insights (customer) or stage_progression, deal_insights (deal)')
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    deal_id: Mapped[Optional[int]] = mapped_column(Integer, comment='Deal ID (NULL for customer-only feedback, populated for deal feedback)')
    feedback_history: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"), comment='JSONB array of feedback entries with text, timestamp, and employee_id')
    ai_summary: Mapped[Optional[dict]] = mapped_column(JSONB, comment='AI-generated analysis of feedback history including summary, trends, sentiment, and insights')

    employee: Mapped['EmployeeInfo'] = relationship('EmployeeInfo', back_populates='crm_feedback')


class Deals(Base):
    __tablename__ = 'deals'
    __table_args__ = (
        CheckConstraint("room_status::text = ANY (ARRAY['draft'::character varying, 'sent'::character varying, 'viewed'::character varying, 'quote_requested'::character varying, 'closed-won'::character varying, 'closed-lost'::character varying]::text[])", name='deals_room_status_check'),
        CheckConstraint('value_usd >= 0::numeric', name='deals_value_usd_check'),
        ForeignKeyConstraint(['client_id'], ['public.clients.client_id'], ondelete='CASCADE', name='deals_client_id_fkey'),
        ForeignKeyConstraint(['employee_id'], ['public.employee_info.employee_id'], name='deals_employee_id_fkey'),
        PrimaryKeyConstraint('deal_id', name='deals_pkey'),
        UniqueConstraint('share_token', name='deals_share_token_key'),
        Index('idx_deals_client_id', 'client_id'),
        Index('idx_deals_created_at', 'created_at'),
        Index('idx_deals_employee_id', 'employee_id'),
        Index('idx_deals_room_status', 'room_status', postgresql_where=text('room_status IS NOT NULL')),
        {'schema': 'public'}
    )

    deal_id: Mapped[int] = mapped_column(Integer, Sequence('deals_deal_id_seq', schema='public'), primary_key=True, server_default=text("nextval('deals_deal_id_seq'::regclass)"))
    deal_name: Mapped[str] = mapped_column(Text, nullable=False)
    product_name: Mapped[Optional[str]] = mapped_column(Text)
    employee_id: Mapped[int] = mapped_column(Integer, nullable=False)
    client_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    description: Mapped[Optional[str]] = mapped_column(Text)
    value_usd: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(12, 2))
    completion_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    last_contact_date: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    expected_close_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    share_token: Mapped[Optional[str]] = mapped_column(String(32))
    room_status: Mapped[Optional[str]] = mapped_column(String(50), server_default=text("'draft'::character varying"))
    quote_data: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    sample_timeline: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    room_settings: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    hs_code: Mapped[Optional[str]] = mapped_column(String(10))
    fob_price: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(12, 2))
    fob_currency: Mapped[Optional[str]] = mapped_column(String(3), server_default=text("'USD'::character varying"))
    landed_price: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(12, 2))
    quantity: Mapped[Optional[int]] = mapped_column(Integer)
    moq: Mapped[Optional[int]] = mapped_column(Integer)
    view_count: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))
    last_viewed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))

    client: Mapped['Clients'] = relationship('Clients', back_populates='deals')
    employee: Mapped['EmployeeInfo'] = relationship('EmployeeInfo', back_populates='deals')
    employee_client_notes: Mapped[list['EmployeeClientNotes']] = relationship('EmployeeClientNotes', back_populates='deal')
    interaction_details: Mapped[list['InteractionDetails']] = relationship('InteractionDetails', back_populates='deal')
    deal_room_views: Mapped[list['DealRoomViews']] = relationship('DealRoomViews', back_populates='deal')


class EmailSyncState(Base):
    __tablename__ = 'email_sync_state'
    __table_args__ = (
        ForeignKeyConstraint(['employee_id'], ['public.employee_info.employee_id'], ondelete='CASCADE', name='fk_email_sync_employee'),
        PrimaryKeyConstraint('id', name='email_sync_state_pkey'),
        UniqueConstraint('employee_id', name='email_sync_state_employee_unique'),
        {'schema': 'public'}
    )

    id: Mapped[int] = mapped_column(Integer, Sequence('email_sync_state_id_seq', schema='public'), primary_key=True, server_default=text("nextval('email_sync_state_id_seq'::regclass)"))
    last_sync_timestamp: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    last_history_id: Mapped[Optional[str]] = mapped_column(String(255))
    emails_synced_count: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))
    employee_id: Mapped[Optional[int]] = mapped_column(Integer)

    employee: Mapped[Optional['EmployeeInfo']] = relationship('EmployeeInfo', back_populates='email_sync_state')


class EmployeeClientLinks(Base):
    __tablename__ = 'employee_client_links'
    __table_args__ = (
        ForeignKeyConstraint(['client_id'], ['public.clients.client_id'], ondelete='CASCADE', name='fk_client'),
        ForeignKeyConstraint(['employee_id'], ['public.employee_info.employee_id'], ondelete='CASCADE', name='fk_employee'),
        PrimaryKeyConstraint('employee_id', 'client_id', name='employee_client_links_pkey'),
        Index('idx_ecl_client_status', 'client_id', 'status'),
        {'schema': 'public'}
    )

    employee_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assigned_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('CURRENT_TIMESTAMP'))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    matched_by: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[Optional[str]] = mapped_column(String(20))
    client_type: Mapped[Optional[str]] = mapped_column(String(20), server_default=text("'lead'::character varying"))

    client: Mapped['Clients'] = relationship('Clients', back_populates='employee_client_links')
    employee: Mapped['EmployeeInfo'] = relationship('EmployeeInfo', back_populates='employee_client_links')
    employee_client_notes: Mapped[list['EmployeeClientNotes']] = relationship('EmployeeClientNotes', back_populates='employee_client_links')


class EmployeeLeadLinks(Base):
    __tablename__ = 'employee_lead_links'
    __table_args__ = (
        ForeignKeyConstraint(['employee_id'], ['public.employee_info.employee_id'], ondelete='CASCADE', name='employee_lead_links_employee_id_fkey'),
        ForeignKeyConstraint(['lead_id'], ['public.leads.lead_id'], ondelete='CASCADE', name='employee_lead_links_lead_id_fkey'),
        PrimaryKeyConstraint('employee_id', 'lead_id', name='employee_lead_links_pkey'),
        Index('idx_employee_lead_links_employee_id', 'employee_id'),
        Index('idx_employee_lead_links_lead_id', 'lead_id'),
        Index('idx_employee_lead_links_status', 'status', postgresql_where="((status)::text = 'active'::text)"),
        {'schema': 'public'}
    )

    employee_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    assigned_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('CURRENT_TIMESTAMP'))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    matched_by: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[Optional[str]] = mapped_column(String(20), server_default=text("'active'::character varying"))

    employee: Mapped['EmployeeInfo'] = relationship('EmployeeInfo', back_populates='employee_lead_links')
    lead: Mapped['Leads'] = relationship('Leads', back_populates='employee_lead_links')


class EnrichmentHistory(Base):
    __tablename__ = 'enrichment_history'
    __table_args__ = (
        ForeignKeyConstraint(['employee_id'], ['public.employee_info.employee_id'], name='enrichment_history_employee_id_fkey'),
        PrimaryKeyConstraint('id', name='enrichment_history_pkey'),
        Index('idx_enrichment_company_name', 'company_name'),
        Index('idx_enrichment_created_at', 'created_at'),
        Index('idx_enrichment_employee_created', 'employee_id', 'created_at'),
        Index('idx_enrichment_employee_id', 'employee_id'),
        Index('idx_enrichment_status', 'enrichment_status'),
        {'schema': 'public'}
    )

    id: Mapped[int] = mapped_column(Integer, Sequence('enrichment_history_id_seq', schema='public'), primary_key=True, server_default=text("nextval('enrichment_history_id_seq'::regclass)"))
    employee_id: Mapped[int] = mapped_column(Integer, nullable=False)
    company_name: Mapped[str] = mapped_column(String(500), nullable=False)
    session_id: Mapped[Optional[str]] = mapped_column(String(255))
    apollo_company_id: Mapped[Optional[str]] = mapped_column(String(255))
    website: Mapped[Optional[str]] = mapped_column(String(500))
    location: Mapped[Optional[str]] = mapped_column(String(500))
    industry: Mapped[Optional[str]] = mapped_column(String(255))
    company_size: Mapped[Optional[str]] = mapped_column(String(100))
    contact_name: Mapped[Optional[str]] = mapped_column(String(255))
    contact_title: Mapped[Optional[str]] = mapped_column(String(255))
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(100))
    enrichment_source: Mapped[Optional[str]] = mapped_column(String(100), server_default=text("'apollo'::character varying"))
    enrichment_status: Mapped[Optional[str]] = mapped_column(String(50), server_default=text("'success'::character varying"))
    enrichment_cost_credits: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))
    final_score: Mapped[Optional[int]] = mapped_column(Integer)
    search_intent_industry: Mapped[Optional[str]] = mapped_column(String(255))
    search_intent_location: Mapped[Optional[str]] = mapped_column(String(500))
    search_intent_keywords: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text()))
    workflow_id: Mapped[Optional[str]] = mapped_column(String(255))
    is_saved_to_leads: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('CURRENT_TIMESTAMP'))

    employee: Mapped['EmployeeInfo'] = relationship('EmployeeInfo', back_populates='enrichment_history')



class InteractionSummaries(Base):
    __tablename__ = 'interaction_summaries'
    __table_args__ = (
        ForeignKeyConstraint(['customer_id'], ['public.clients.client_id'], ondelete='CASCADE', name='interaction_summaries_customer_id_fkey'),
        PrimaryKeyConstraint('summary_id', name='interaction_summaries_pkey'),
        UniqueConstraint('customer_id', 'generated_at', name='interaction_summaries_customer_id_generated_at_key'),
        Index('idx_interaction_summaries_customer_id', 'customer_id'),
        Index('idx_interaction_summaries_customer_latest', 'customer_id', 'generated_at'),
        Index('idx_interaction_summaries_generated_at', 'generated_at'),
        Index('idx_interaction_summaries_generation_type', 'generation_type'),
        Index('idx_interaction_summaries_status', 'status'),
        {'comment': 'Stores pre-generated AI interaction summaries for customers to '
                'enable automated batch processing and caching',
     'schema': 'public'}
    )

    summary_id: Mapped[int] = mapped_column(Integer, Sequence('interaction_summaries_summary_id_seq', schema='public'), primary_key=True, server_default=text("nextval('interaction_summaries_summary_id_seq'::regclass)"))
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False)
    summary_data: Mapped[dict] = mapped_column(JSONB, nullable=False, comment='JSON data matching InteractionSummaryResponse format from the API')
    generated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('CURRENT_TIMESTAMP'))
    generated_by: Mapped[Optional[str]] = mapped_column(String(255), server_default=text("'automated_batch_job'::character varying"))
    generation_type: Mapped[Optional[str]] = mapped_column(String(50), server_default=text("'automated'::character varying"), comment='automated (midnight batch job) or manual (user-triggered)')
    period_analyzed_days: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('30'))
    interactions_analyzed: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))
    agent_used: Mapped[Optional[str]] = mapped_column(String(100), comment='AI agent class name used for generation (e.g., IcebreakerIntroAgent)')
    ai_model_used: Mapped[Optional[str]] = mapped_column(String(100))
    processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[Optional[str]] = mapped_column(String(20), server_default=text("'success'::character varying"))
    last_interaction_date: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    data_cutoff_date: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), comment='Latest interaction date considered in this summary')
    summary_data_zh: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, comment='Chinese (zh-CN) translation of summary_data, generated by gpt-5-nano')
    summary_data_zh_translated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), nullable=True)
    summary_data_zh_source_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    customer: Mapped['Clients'] = relationship('Clients', back_populates='interaction_summaries')



class OauthTokens(Base):
    __tablename__ = 'oauth_tokens'
    __table_args__ = (
        ForeignKeyConstraint(['employee_id'], ['public.employee_info.employee_id'], ondelete='CASCADE', name='oauth_tokens_employee_id_fkey'),
        PrimaryKeyConstraint('id', name='oauth_tokens_pkey'),
        UniqueConstraint('user_email', 'provider', name='oauth_tokens_user_email_provider_key'),
        Index('idx_oauth_tokens_employee_id', 'employee_id'),
        Index('idx_oauth_tokens_expiry', 'token_expiry'),
        Index('idx_oauth_tokens_provider', 'provider'),
        Index('idx_oauth_tokens_user_email', 'user_email'),
        {'schema': 'public'}
    )

    id: Mapped[int] = mapped_column(Integer, Sequence('oauth_tokens_id_seq', schema='public'), primary_key=True, server_default=text("nextval('oauth_tokens_id_seq'::regclass)"))
    user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    token_expiry: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False)
    employee_id: Mapped[Optional[int]] = mapped_column(Integer)
    scope: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('CURRENT_TIMESTAMP'))

    employee: Mapped[Optional['EmployeeInfo']] = relationship('EmployeeInfo', back_populates='oauth_tokens')


class Personnel(Base):
    __tablename__ = 'personnel'
    __table_args__ = (
        ForeignKeyConstraint(['lead_id'], ['public.leads.lead_id'], ondelete='CASCADE', name='personnel_lead_id_fkey'),
        ForeignKeyConstraint(['client_id'], ['public.clients.client_id'], ondelete='SET NULL', name='personnel_client_id_fkey'),
        PrimaryKeyConstraint('personnel_id', name='personnel_pkey'),
        UniqueConstraint('full_name', 'company_name', name='unique_person_company'),
        Index('idx_personnel_client_id', 'client_id'),
        Index('idx_personnel_company', 'company_name'),
        Index('idx_personnel_created_at', 'created_at'),
        Index('idx_personnel_email', 'email'),
        Index('idx_personnel_full_name', 'full_name'),
        Index('idx_personnel_lead_id', 'lead_id'),
        Index('idx_personnel_linkedin', 'linkedin_url'),
        # idx_personnel_name_search: functional GIN on to_tsvector('english', full_name) — created via raw SQL
        Index('idx_personnel_position', 'position'),
        # idx_personnel_position_search: functional GIN on to_tsvector('english', position) — created via raw SQL
        Index('idx_personnel_source', 'source'),
        {'schema': 'public'}
    )

    personnel_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(510), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    position: Mapped[Optional[str]] = mapped_column(String(255))
    department: Mapped[Optional[str]] = mapped_column(String(255))
    seniority_level: Mapped[Optional[str]] = mapped_column(String(100))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(500))
    country: Mapped[Optional[str]] = mapped_column(String(100))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    client_id: Mapped[Optional[int]] = mapped_column(Integer)
    is_primary: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('CURRENT_TIMESTAMP'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('CURRENT_TIMESTAMP'))
    scraped_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))

    lead: Mapped[Optional['Leads']] = relationship('Leads', back_populates='personnel')
    client: Mapped[Optional['Clients']] = relationship('Clients', back_populates='personnel')


class EmployeeClientNotes(Base):
    __tablename__ = 'employee_client_notes'
    __table_args__ = (
        ForeignKeyConstraint(['deal_id'], ['public.deals.deal_id'], ondelete='CASCADE', name='employee_client_notes_deal_id_fkey'),
        ForeignKeyConstraint(['employee_id', 'client_id'], ['public.employee_client_links.employee_id', 'public.employee_client_links.client_id'], ondelete='CASCADE', onupdate='CASCADE', name='employee_client_notes_employee_id_client_id_fkey'),
        PrimaryKeyConstraint('note_id', name='employee_client_notes_pkey'),
        Index('idx_employee_client_notes_deal_id', 'deal_id'),
        {'schema': 'public'}
    )

    note_id: Mapped[int] = mapped_column(BigInteger, Sequence('employee_client_notes_note_id_seq', schema='public'), primary_key=True, server_default=text("nextval('employee_client_notes_note_id_seq'::regclass)"))
    employee_id: Mapped[int] = mapped_column(Integer, nullable=False)
    client_id: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    title: Mapped[Optional[str]] = mapped_column(String(200))
    star: Mapped[Optional[str]] = mapped_column(String(50))
    interaction_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    deal_id: Mapped[Optional[int]] = mapped_column(Integer)
    embedding = mapped_column(PgVector(), nullable=True)
    text_search = mapped_column(TSVECTOR, nullable=True)

    deal: Mapped[Optional['Deals']] = relationship('Deals', back_populates='employee_client_notes')
    employee_client_links: Mapped['EmployeeClientLinks'] = relationship('EmployeeClientLinks', back_populates='employee_client_notes')


class BolCompetitors(Base):
    __tablename__ = 'bol_competitors'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='bol_competitors_pkey'),
        UniqueConstraint('supplier_slug', name='bol_competitors_supplier_slug_key'),
        Index('idx_bol_competitors_hs', 'hs_codes', postgresql_using='gin'),
        Index('idx_bol_competitors_threat', 'threat_level'),
        Index('idx_bol_competitors_tracked', 'is_tracked', postgresql_where=text('is_tracked = true')),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    supplier_slug: Mapped[str] = mapped_column(String(500), nullable=False)
    supplier_name: Mapped[str] = mapped_column(String(500), nullable=False)
    supplier_name_cn: Mapped[Optional[str]] = mapped_column(String(500))
    country: Mapped[Optional[str]] = mapped_column(String(100))
    country_code: Mapped[Optional[str]] = mapped_column(String(10))
    address: Mapped[Optional[str]] = mapped_column(Text)
    city: Mapped[Optional[str]] = mapped_column(String(100))
    hs_codes: Mapped[list[str]] = mapped_column(ARRAY(String(10)), nullable=False)
    total_shipments: Mapped[Optional[int]] = mapped_column(Integer)
    total_customers: Mapped[Optional[int]] = mapped_column(Integer)
    matching_shipments: Mapped[Optional[int]] = mapped_column(Integer)
    specialization: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(5, 2))
    weight_kg: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(15, 2))
    customer_companies: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text()))
    product_descriptions: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text()))
    overlap_count: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))
    overlap_buyer_slugs: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text()))
    threat_level: Mapped[Optional[str]] = mapped_column(String(20))
    threat_score: Mapped[Optional[int]] = mapped_column(Integer)
    trend_yoy: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(6, 2))
    time_series: Mapped[Optional[dict]] = mapped_column(JSONB)
    companies_table: Mapped[Optional[dict]] = mapped_column(JSONB)
    also_known_names: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text()))
    recent_bols: Mapped[Optional[dict]] = mapped_column(JSONB)
    carriers_per_country: Mapped[Optional[dict]] = mapped_column(JSONB)
    is_tracked: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    first_seen_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    last_updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))


class InteractionDetails(Base):
    __tablename__ = 'interaction_details'
    __table_args__ = (
        ForeignKeyConstraint(['customer_id'], ['public.clients.client_id'], ondelete='CASCADE', name='fk_customer'),
        ForeignKeyConstraint(['deal_id'], ['public.deals.deal_id'], ondelete='SET NULL', name='fk_interaction_details_deal_id'),
        ForeignKeyConstraint(['employee_id'], ['public.employee_info.employee_id'], ondelete='CASCADE', name='fk_employee'),
        ForeignKeyConstraint(['synced_by_employee_id'], ['public.employee_info.employee_id'], ondelete='SET NULL', name='synced_by_employee_id_fkey'),
        PrimaryKeyConstraint('interaction_id', name='interaction_details_pkey'),
        UniqueConstraint('gmail_message_id', name='interaction_details_gmail_message_id_key'),
        Index('idx_interaction_details_customer_id', 'customer_id'),
        Index('idx_interaction_details_deal_id', 'deal_id'),
        Index('idx_interaction_details_employee_id', 'employee_id'),
        Index('idx_interaction_details_google_event_id', 'google_calendar_event_id'),
        {'schema': 'public'}
    )

    interaction_id: Mapped[int] = mapped_column(BigInteger, Sequence('interaction_details_interaction_id_seq', schema='public'), primary_key=True, server_default=text("nextval('interaction_details_interaction_id_seq'::regclass)"))
    customer_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    employee_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    type: Mapped[Optional[str]] = mapped_column(String(50))
    content: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    gmail_message_id: Mapped[Optional[str]] = mapped_column(String(255))
    synced_by_employee_id: Mapped[Optional[int]] = mapped_column(Integer)
    source: Mapped[Optional[str]] = mapped_column(String(50))
    theme: Mapped[Optional[str]] = mapped_column(String(50))
    google_calendar_event_id: Mapped[Optional[str]] = mapped_column(String(255))
    deal_id: Mapped[Optional[int]] = mapped_column(Integer)
    embedding = mapped_column(PgVector(), nullable=True)
    text_search = mapped_column(TSVECTOR, nullable=True)

    customer: Mapped['Clients'] = relationship('Clients', back_populates='interaction_details')
    deal: Mapped[Optional['Deals']] = relationship('Deals', back_populates='interaction_details')
    employee: Mapped['EmployeeInfo'] = relationship('EmployeeInfo', foreign_keys=[employee_id], back_populates='interaction_details_employee')
    synced_by_employee: Mapped[Optional['EmployeeInfo']] = relationship('EmployeeInfo', foreign_keys=[synced_by_employee_id], back_populates='interaction_details_synced_by_employee')


class ActivityLog(Base):
    __tablename__ = 'activity_log'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='activity_log_pkey'),
        Index('idx_activity_log_user', 'user_id', 'created_at'),
        Index('idx_activity_log_resource', 'resource_type', 'resource_id'),
        Index('idx_activity_log_created', 'created_at'),
        {'schema': 'public'}
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


class ContextRetrievalRuns(Base):
    __tablename__ = 'context_retrieval_runs'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='context_retrieval_runs_pkey'),
        {'schema': 'public'}
    )

    id: Mapped[int] = mapped_column(Integer, Sequence('context_retrieval_runs_id_seq', schema='public'), primary_key=True, server_default=text("nextval('context_retrieval_runs_id_seq'::regclass)"))
    customer_id: Mapped[Optional[int]] = mapped_column(Integer)
    tool_name: Mapped[Optional[str]] = mapped_column(String(100))
    query: Mapped[Optional[str]] = mapped_column(Text)
    retrieval_params: Mapped[Optional[dict]] = mapped_column(JSONB)
    selected_refs: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    user_email: Mapped[Optional[str]] = mapped_column(String(255))


class IngestionJobs(Base):
    __tablename__ = 'ingestion_jobs'
    __table_args__ = (
        PrimaryKeyConstraint('job_id', name='ingestion_jobs_pkey'),
        CheckConstraint(
            "kind IN ('company_profile','product_csv','product_pdf','certification')",
            name='ingestion_jobs_kind_check',
        ),
        CheckConstraint(
            "status IN ('queued','processing','ready_for_review','committed','failed','discarded')",
            name='ingestion_jobs_status_check',
        ),
        Index('idx_ingestion_jobs_email_created', 'email', text('created_at DESC')),
        Index(
            'idx_ingestion_jobs_active',
            'status',
            postgresql_where=text("status IN ('queued','processing')"),
        ),
        {'schema': 'public'},
    )

    job_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'queued'::character varying"))
    draft_payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))


class ProductCatalog(Base):
    __tablename__ = 'product_catalog'
    __table_args__ = (
        ForeignKeyConstraint(
            ['source_job_id'],
            ['public.ingestion_jobs.job_id'],
            ondelete='SET NULL',
            name='product_catalog_source_job_id_fkey',
        ),
        PrimaryKeyConstraint('product_id', name='product_catalog_pkey'),
        Index('idx_product_catalog_email_name', 'email', 'name'),
        {'schema': 'public'},
    )

    product_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    specs: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    image_url: Mapped[Optional[str]] = mapped_column(Text)
    moq: Mapped[Optional[int]] = mapped_column(Integer)
    price_range: Mapped[Optional[dict]] = mapped_column(JSONB)
    hs_code: Mapped[Optional[str]] = mapped_column(String(16))
    source_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'pending'::character varying"))
    published_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
