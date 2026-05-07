# Setting Up New Customer Database with Alembic

## Quick Setup Guide

### Step 0: Navigate to User Settings Directory

```bash
cd /path/to/prelude/prelude-user-settings
```

### Step 1: Copy Schema from Postgres

```bash
# Set password from .env file
source .env
export PGPASSWORD="$SESSIONS_DB_PASSWORD"

# Dump current postgres schema (no data)
pg_dump -h 35.193.231.128 -U postgres -d postgres --schema-only -f postgres_schema.sql

# Create new customer database
createdb -h 35.193.231.128 -U postgres prelude-newcustomer

# Restore schema to customer database
psql -h 35.193.231.128 -U postgres -d prelude-newcustomer -f postgres_schema.sql
```

### Step 2: Stamp Customer DB at Current Version

```bash
# Edit alembic.ini - change database name
# FROM: sqlalchemy.url = postgresql://...@35.193.231.128:5432/postgres
# TO:   sqlalchemy.url = postgresql://...@35.193.231.128:5432/prelude-newcustomer

cd alembic_postgres

# Stamp at current head revision (creates alembic_version table)
alembic stamp head

# Verify
alembic current
# Should show: <revision_id> (head)
```

### Step 3: Restore Postgres DB Connection

```bash
# Revert alembic.ini back to postgres database
# Change /prelude-newcustomer back to /postgres
```

---

## Verification

```bash
# Check alembic_version table exists
psql -h 35.193.231.128 -U postgres -d prelude-newcustomer \
  -c "SELECT * FROM alembic_version;"

# Should return current revision ID
```

---

## Notes

- Only postgres schema gets replicated to customers
- Analytics DB (prelude_user_analytics) stays centralized - NO customer copies
- Each customer DB maintains independent alembic_version tracking
