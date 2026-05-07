"""baseline_april_2026

Revision ID: f0a1b2c3d4e5
Revises: None
Create Date: 2026-04-11 12:00:00.000000

Clean baseline from postgres database as of April 11, 2026.
This replaces all prior migrations. New databases should start from this revision.
Uses metadata.create_all() from models.py to create all tables.
"""
from alembic import op
from models import Base
from sqlalchemy import text


revision = 'f0a1b2c3d4e5'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create all tables from models.py in one shot
    bind = op.get_bind()
    # Enable pgvector extension if available (non-fatal)
    try:
        bind.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception:
        pass
    Base.metadata.create_all(bind=bind)
    # Functional GIN indexes not expressible in SQLAlchemy Index()
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_leads_company_search ON public.leads USING gin (to_tsvector('english'::regconfig, (company)::text))",
        "CREATE INDEX IF NOT EXISTS idx_personnel_name_search ON public.personnel USING gin (to_tsvector('english'::regconfig, (full_name)::text))",
        "CREATE INDEX IF NOT EXISTS idx_personnel_position_search ON public.personnel USING gin (to_tsvector('english'::regconfig, (\"position\")::text))",
    ]:
        try:
            bind.execute(text(idx_sql))
        except Exception:
            pass


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
