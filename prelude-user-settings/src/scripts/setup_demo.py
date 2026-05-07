#!/usr/bin/env python3
"""
Demo Database & User Setup Script
==================================

Sets up a demo environment by cloning the postgres database and creating
a demo user account with all necessary relations (employee_info, etc.).

Usage:
    python setup_demo.py setup                  # Full setup (clone + create-user)
    python setup_demo.py clone                  # Clone postgres → prelude_demo
    python setup_demo.py create-user            # Create demo user + sync employee
    python setup_demo.py create-user --password mypass  # Custom password
"""

import argparse
import os
import sys
from datetime import datetime

import bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEMO_DB_NAME = "prelude_demo"
SOURCE_DB_NAME = "postgres"
ANALYTICS_DB_NAME = "prelude_user_analytics"
CONNECT_DB = "template1"  # Safe DB to connect to when cloning

DEMO_EMAIL = "demo@preludeos.com"
DEMO_USERNAME = "demo"
DEMO_NAME = "Demo User"
DEMO_COMPANY = "prelude"
DEMO_ROLE = "admin"
DEFAULT_PASSWORD = "prelude-demo-2026"
LINK_SOURCE_EMAIL = "james@preludeos.com"  # Employee whose record the demo user inherits


def load_env():
    """Load .env file from the prelude-user-settings root (two levels up)."""
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    env_path = os.path.normpath(env_path)
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def get_db_config(database: str = ANALYTICS_DB_NAME) -> dict:
    """Return psycopg2 connection kwargs using SESSIONS_DB_* env vars."""
    return {
        "host": os.getenv("SESSIONS_DB_HOST"),
        "port": int(os.getenv("SESSIONS_DB_PORT", 5432)),
        "user": os.getenv("SESSIONS_DB_USER"),
        "password": os.getenv("SESSIONS_DB_PASSWORD"),
        "database": database,
    }


# ---------------------------------------------------------------------------
# clone
# ---------------------------------------------------------------------------

def clone_database():
    """Clone postgres → prelude_demo using CREATE DATABASE ... TEMPLATE."""
    print(f"Cloning '{SOURCE_DB_NAME}' → '{DEMO_DB_NAME}' ...")

    cfg = get_db_config(database=CONNECT_DB)
    conn = psycopg2.connect(**cfg)
    conn.autocommit = True
    cur = conn.cursor()

    # Terminate connections to both source and target so clone can proceed
    for db in (DEMO_DB_NAME, SOURCE_DB_NAME):
        cur.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = %s AND pid <> pg_backend_pid()
            """,
            (db,),
        )
        terminated = cur.rowcount
        if terminated:
            print(f"  Terminated {terminated} connection(s) to '{db}'")

    # Drop existing demo DB
    cur.execute(f"DROP DATABASE IF EXISTS {DEMO_DB_NAME}")
    print(f"  Dropped existing '{DEMO_DB_NAME}' (if any)")

    # Clone
    cur.execute(f"CREATE DATABASE {DEMO_DB_NAME} TEMPLATE {SOURCE_DB_NAME}")
    print(f"  Created '{DEMO_DB_NAME}' from template '{SOURCE_DB_NAME}'")

    cur.close()
    conn.close()

    # Verify by counting tables
    verify_cfg = get_db_config(database=DEMO_DB_NAME)
    verify_conn = psycopg2.connect(**verify_cfg)
    verify_cur = verify_conn.cursor()
    verify_cur.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'"
    )
    table_count = verify_cur.fetchone()[0]
    verify_cur.close()
    verify_conn.close()

    print(f"\nSUCCESS: '{DEMO_DB_NAME}' created with {table_count} table(s).")


# ---------------------------------------------------------------------------
# create-user  (user_profiles + employee_info sync)
# ---------------------------------------------------------------------------

def create_user(password: str):
    """Create or update demo user in user_profiles, then sync employee_info."""
    print(f"Setting up demo user '{DEMO_USERNAME}' ({DEMO_EMAIL}) ...")

    password_hash = bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")

    # ---- 1. Upsert user_profiles in prelude_user_analytics ----
    cfg = get_db_config(database=ANALYTICS_DB_NAME)
    conn = psycopg2.connect(**cfg)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT email FROM user_profiles WHERE email = %s", (DEMO_EMAIL,))
    existing = cur.fetchone()

    if existing:
        cur.execute(
            """
            UPDATE user_profiles
            SET db_name = %s,
                username = %s,
                password_hash = %s,
                name = %s,
                company = %s,
                role = %s,
                has_real_email = TRUE,
                updated_at = %s
            WHERE email = %s
            """,
            (
                DEMO_DB_NAME,
                DEMO_USERNAME,
                password_hash,
                DEMO_NAME,
                DEMO_COMPANY,
                DEMO_ROLE,
                datetime.utcnow(),
                DEMO_EMAIL,
            ),
        )
        print(f"  Updated existing user_profiles row for '{DEMO_EMAIL}'")
    else:
        cur.execute(
            """
            INSERT INTO user_profiles
                (email, username, password_hash, has_real_email,
                 name, company, role, db_name, created_at)
            VALUES (%s, %s, %s, TRUE, %s, %s, %s, %s, %s)
            """,
            (
                DEMO_EMAIL,
                DEMO_USERNAME,
                password_hash,
                DEMO_NAME,
                DEMO_COMPANY,
                DEMO_ROLE,
                DEMO_DB_NAME,
                datetime.utcnow(),
            ),
        )
        print(f"  Inserted new user_profiles row for '{DEMO_EMAIL}'")

    conn.commit()
    cur.close()
    conn.close()

    # ---- 2. Link demo user to existing employee in prelude_demo ----
    _link_employee()

    # ---- Summary ----
    print(f"\nSUCCESS: Demo user ready.")
    print(f"  Username : {DEMO_USERNAME}")
    print(f"  Password : {password}")
    print(f"  Email    : {DEMO_EMAIL}")
    print(f"  Database : {DEMO_DB_NAME}")
    print(f"  Role     : {DEMO_ROLE}")


def _link_employee():
    """Re-point james@preludeos.com's employee_info record to the demo email.

    This makes the demo user inherit all of James's existing relationships:
    deals, employee_client_notes, employee_client_links, interaction_details,
    enrichment_history, etc.  Also ensures access='admin' for full visibility.

    When sync_user_to_employee_info() runs on login it will find the record
    by DEMO_EMAIL and skip creating a new empty one.
    """
    print(f"  Linking employee_info '{LINK_SOURCE_EMAIL}' → '{DEMO_EMAIL}' in '{DEMO_DB_NAME}' ...")

    cfg = get_db_config(database=DEMO_DB_NAME)
    conn = psycopg2.connect(**cfg)
    cur = conn.cursor()

    # Check if employee_info table exists
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'employee_info'
        )
        """
    )
    if not cur.fetchone()[0]:
        print("  WARNING: employee_info table does not exist in demo DB — skipping link")
        cur.close()
        conn.close()
        return

    # Already linked?
    cur.execute("SELECT employee_id FROM employee_info WHERE email = %s", (DEMO_EMAIL,))
    already = cur.fetchone()
    if already:
        # Ensure admin access even if already linked
        cur.execute(
            "UPDATE employee_info SET access = 'admin' WHERE email = %s",
            (DEMO_EMAIL,),
        )
        conn.commit()
        print(f"  Already linked (employee_id={already[0]}), ensured access='admin'")
        cur.close()
        conn.close()
        return

    # Find source employee
    cur.execute(
        "SELECT employee_id, name, access FROM employee_info WHERE email = %s",
        (LINK_SOURCE_EMAIL,),
    )
    source = cur.fetchone()

    if not source:
        print(f"  WARNING: No employee_info record found for '{LINK_SOURCE_EMAIL}' — skipping link")
        cur.close()
        conn.close()
        return

    emp_id, emp_name, emp_access = source

    # Re-point the employee record to demo email with admin access
    cur.execute(
        """
        UPDATE employee_info
        SET email = %s, access = 'admin', updated_at = %s
        WHERE employee_id = %s
        """,
        (DEMO_EMAIL, datetime.utcnow(), emp_id),
    )

    conn.commit()
    cur.close()
    conn.close()

    print(f"  Linked employee_id={emp_id} (was: {emp_name}, access={emp_access}) "
          f"→ {DEMO_EMAIL} with access='admin'")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    load_env()

    parser = argparse.ArgumentParser(
        description="Set up a demo database and user for Prelude Platform"
    )
    sub = parser.add_subparsers(dest="command")

    # clone
    sub.add_parser("clone", help="Clone postgres → prelude_demo")

    # create-user
    cu = sub.add_parser("create-user", help="Create demo user (user_profiles + employee_info)")
    cu.add_argument("--password", default=DEFAULT_PASSWORD, help="Demo user password")

    # setup (convenience)
    sp = sub.add_parser("setup", help="Run clone + create-user")
    sp.add_argument("--password", default=DEFAULT_PASSWORD, help="Demo user password")

    args = parser.parse_args()

    if args.command == "clone":
        clone_database()
    elif args.command == "create-user":
        create_user(args.password)
    elif args.command == "setup":
        clone_database()
        print()
        create_user(args.password)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
