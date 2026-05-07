"""add_ingestion_tables

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-04-22 12:00:00.000000

Adds ingestion_jobs and product_catalog for the document-ingestion feature.
See src/docs/DOC_INGESTION_CODING_PLAN.md §2.2.

Uses CREATE ... IF NOT EXISTS throughout because the baseline migration
(f0a1b2c3d4e5) runs Base.metadata.create_all() from models.py — so any new
tenant DB created after these models were added will already have both
tables when this revision runs. The IF NOT EXISTS clause makes the migration
a no-op in that case while still creating the tables on existing DBs that
passed the baseline before these models existed.
"""
from alembic import op


revision = 'b2c3d4e5f6a1'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ingestion_jobs (
            job_id        UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            email         VARCHAR(255) NOT NULL,
            kind          VARCHAR(32)  NOT NULL,
            source_url    TEXT         NOT NULL,
            status        VARCHAR(32)  NOT NULL DEFAULT 'queued',
            draft_payload JSONB        NULL,
            error         TEXT         NULL,
            created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
            CONSTRAINT ingestion_jobs_kind_check
                CHECK (kind IN ('company_profile','product_csv','product_pdf','certification')),
            CONSTRAINT ingestion_jobs_status_check
                CHECK (status IN ('queued','processing','ready_for_review','committed','failed','discarded'))
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_email_created "
        "ON ingestion_jobs (email, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_active "
        "ON ingestion_jobs (status) WHERE status IN ('queued','processing')"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS product_catalog (
            product_id    UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            email         VARCHAR(255) NOT NULL,
            name          VARCHAR(500) NOT NULL,
            description   TEXT         NULL,
            specs         JSONB        NOT NULL DEFAULT '{}'::jsonb,
            image_url     TEXT         NULL,
            moq           INTEGER      NULL,
            price_range   JSONB        NULL,
            hs_code       VARCHAR(16)  NULL,
            source_job_id UUID         NULL
                REFERENCES ingestion_jobs(job_id) ON DELETE SET NULL,
            created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_product_catalog_email_name "
        "ON product_catalog (email, name)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS product_catalog")
    op.execute("DROP TABLE IF EXISTS ingestion_jobs")
