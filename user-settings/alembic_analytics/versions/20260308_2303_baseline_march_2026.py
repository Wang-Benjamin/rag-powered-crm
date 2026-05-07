"""baseline_march_2026

Revision ID: 6e0b4bf58f68
Revises: c8257193f253
Create Date: 2026-03-08 23:03:20.350851

Fresh baseline from prelude_user_analytics database as of March 8, 2026.
models.py regenerated from actual database schema using sqlacodegen.
"""
from alembic import op
import sqlalchemy as sa


revision = '6e0b4bf58f68'
down_revision = 'c8257193f253'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Empty migration - this is a baseline checkpoint.
    # prelude_user_analytics database is already at this state.
    pass


def downgrade() -> None:
    # No downgrade for baseline
    pass
