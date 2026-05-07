-- Migration: Enable pgvector and add embedding + text search columns
-- Must be run on every tenant database

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Add embedding columns (1536 dims for text-embedding-3-small)
ALTER TABLE interaction_details
    ADD COLUMN IF NOT EXISTS embedding vector(1536);

ALTER TABLE crm_emails
    ADD COLUMN IF NOT EXISTS embedding vector(1536);

ALTER TABLE employee_client_notes
    ADD COLUMN IF NOT EXISTS embedding vector(1536);

-- 3. Add tsvector columns for keyword search
ALTER TABLE interaction_details
    ADD COLUMN IF NOT EXISTS text_search tsvector;

ALTER TABLE crm_emails
    ADD COLUMN IF NOT EXISTS text_search tsvector;

ALTER TABLE employee_client_notes
    ADD COLUMN IF NOT EXISTS text_search tsvector;

-- 4. Create GIN indexes for full-text search
CREATE INDEX IF NOT EXISTS idx_interaction_details_text_search
    ON interaction_details USING gin(text_search);

CREATE INDEX IF NOT EXISTS idx_crm_emails_text_search
    ON crm_emails USING gin(text_search);

CREATE INDEX IF NOT EXISTS idx_employee_client_notes_text_search
    ON employee_client_notes USING gin(text_search);

-- 5. Triggers to auto-populate tsvector on INSERT/UPDATE

CREATE OR REPLACE FUNCTION update_interaction_text_search()
RETURNS trigger AS $$
BEGIN
    NEW.text_search := to_tsvector('english', COALESCE(NEW.content, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_interaction_text_search ON interaction_details;
CREATE TRIGGER trg_interaction_text_search
    BEFORE INSERT OR UPDATE OF content ON interaction_details
    FOR EACH ROW EXECUTE FUNCTION update_interaction_text_search();

CREATE OR REPLACE FUNCTION update_email_text_search()
RETURNS trigger AS $$
BEGIN
    NEW.text_search := to_tsvector('english',
        COALESCE(NEW.subject, '') || ' ' || COALESCE(NEW.body, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_email_text_search ON crm_emails;
CREATE TRIGGER trg_email_text_search
    BEFORE INSERT OR UPDATE OF subject, body ON crm_emails
    FOR EACH ROW EXECUTE FUNCTION update_email_text_search();

CREATE OR REPLACE FUNCTION update_note_text_search()
RETURNS trigger AS $$
BEGIN
    NEW.text_search := to_tsvector('english',
        COALESCE(NEW.title, '') || ' ' || COALESCE(NEW.body, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_note_text_search ON employee_client_notes;
CREATE TRIGGER trg_note_text_search
    BEFORE INSERT OR UPDATE OF title, body ON employee_client_notes
    FOR EACH ROW EXECUTE FUNCTION update_note_text_search();

-- 6. Backfill tsvector for existing rows
UPDATE interaction_details
SET text_search = to_tsvector('english', COALESCE(content, ''))
WHERE text_search IS NULL AND content IS NOT NULL;

UPDATE crm_emails
SET text_search = to_tsvector('english', COALESCE(subject, '') || ' ' || COALESCE(body, ''))
WHERE text_search IS NULL AND (subject IS NOT NULL OR body IS NOT NULL);

UPDATE employee_client_notes
SET text_search = to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(body, ''))
WHERE text_search IS NULL AND (title IS NOT NULL OR body IS NOT NULL);

-- 7. Context retrieval audit trail table
CREATE TABLE IF NOT EXISTS context_retrieval_runs (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER,
    tool_name VARCHAR(100),
    query TEXT,
    retrieval_params JSONB,
    selected_refs JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    user_email VARCHAR(255)
);
