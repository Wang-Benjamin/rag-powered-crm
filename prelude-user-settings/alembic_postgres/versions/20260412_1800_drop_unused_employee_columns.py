"""drop_unused_employee_columns

Revision ID: a1b2c3d4e5f6
Revises: f0a1b2c3d4e5
Create Date: 2026-04-12 18:00:00.000000

Remove unused columns from employee_info: location, phone, hire_date, timezone.
These columns are never read or written by any backend or frontend code.

Uses IF EXISTS because the baseline migration builds tables from models.py via
`Base.metadata.create_all()` — so fresh DBs never had these columns in the
first place. The IF EXISTS makes this migration a no-op for fresh DBs while
still cleaning up older DBs that were created when models.py still had them.
"""
from alembic import op


revision = 'a1b2c3d4e5f6'
down_revision = 'f0a1b2c3d4e5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE employee_info DROP COLUMN IF EXISTS location")
    op.execute("ALTER TABLE employee_info DROP COLUMN IF EXISTS phone")
    op.execute("ALTER TABLE employee_info DROP COLUMN IF EXISTS hire_date")
    op.execute("ALTER TABLE employee_info DROP COLUMN IF EXISTS timezone")


def downgrade() -> None:
    op.execute("ALTER TABLE employee_info ADD COLUMN IF NOT EXISTS timezone VARCHAR(50)")
    op.execute("ALTER TABLE employee_info ADD COLUMN IF NOT EXISTS hire_date DATE")
    op.execute("ALTER TABLE employee_info ADD COLUMN IF NOT EXISTS phone VARCHAR(20)")
    op.execute("ALTER TABLE employee_info ADD COLUMN IF NOT EXISTS location JSON")
