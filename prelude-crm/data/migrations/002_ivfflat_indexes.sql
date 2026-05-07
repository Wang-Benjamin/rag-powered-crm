-- Migration: Create IVFFlat indexes for vector similarity search
-- Run AFTER embedding backfill is complete (Phase 2)
-- These indexes need data to build the clustering, so they must be created post-backfill

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_interaction_embedding
    ON interaction_details USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_crm_emails_embedding
    ON crm_emails USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notes_embedding
    ON employee_client_notes USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
