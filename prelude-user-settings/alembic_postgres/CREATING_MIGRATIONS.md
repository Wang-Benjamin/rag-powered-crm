# Creating New Migrations

## Quick Reference

### Method 1: Auto-generate (Recommended)

```bash
cd alembic_postgres

# Auto-detect schema changes
alembic revision --autogenerate -m "add customer notes column"

# Review generated file in versions/
# File: YYYYMMDD_HHMM_add_customer_notes_column.py

# Apply to postgres
alembic upgrade head

# Test rollback
alembic downgrade -1
```

---

### Method 2: Manual Migration

```bash
cd alembic_postgres

# Create empty migration
alembic revision -m "add custom index"

# Edit the generated file in versions/
# Add your upgrade/downgrade code
```

**Example:**
```python
def upgrade() -> None:
    op.add_column('customers', sa.Column('notes', sa.Text()))
    op.create_index('ix_customers_notes', 'customers', ['notes'])

def downgrade() -> None:
    op.drop_index('ix_customers_notes', 'customers')
    op.drop_column('customers', 'notes')
```

**Apply:**
```bash
alembic upgrade head
```

---

## Common Commands

```bash
# Check current version
alembic current

# View migration history
alembic history

# Upgrade one step
alembic upgrade +1

# Downgrade one step
alembic downgrade -1

# Generate SQL without running
alembic upgrade head --sql
```

---

## Weekly Development Workflow

```bash
# Monday-Friday: Make changes and create migrations
cd alembic_postgres
alembic revision --autogenerate -m "your change"
alembic upgrade head

# Friday: Generate SQL for customer deployment
alembic upgrade <last_week_rev>:head --sql > weekly_migrations.sql

# Deploy to customers manually
```
