-- Migration: Per-chunk embeddings for long-form CRM documents.
-- Sidecar table: parent rows in interaction_details / crm_emails /
-- employee_client_notes still keep their `embedding` column for
-- backwards-compatible single-vector retrieval, but new writes also
-- chunk the text and write per-chunk vectors here. The retriever
-- prefers chunk-level scores when chunks exist for a parent, falling
-- back to the parent embedding otherwise.

CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id        BIGSERIAL PRIMARY KEY,
    parent_type     VARCHAR(20) NOT NULL,         -- 'interaction' | 'email' | 'note'
    parent_id       BIGINT NOT NULL,
    customer_id     BIGINT NOT NULL,
    chunk_idx       INTEGER NOT NULL,
    content         TEXT NOT NULL,
    embedding       vector(1536),
    text_search     tsvector,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT document_chunks_parent_idx_uq UNIQUE (parent_type, parent_id, chunk_idx),
    CONSTRAINT document_chunks_parent_type_chk
        CHECK (parent_type IN ('interaction', 'email', 'note'))
);

CREATE INDEX IF NOT EXISTS idx_document_chunks_parent
    ON document_chunks (parent_type, parent_id);

CREATE INDEX IF NOT EXISTS idx_document_chunks_customer
    ON document_chunks (customer_id);

CREATE INDEX IF NOT EXISTS idx_document_chunks_text_search
    ON document_chunks USING gin(text_search);

-- ivfflat index for the chunk vectors. lists=100 is a safe default for
-- corpora up to ~1M chunks per tenant; tune higher if a tenant grows.
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding
    ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Auto-populate text_search from content on insert/update.
CREATE OR REPLACE FUNCTION update_document_chunks_text_search()
RETURNS trigger AS $$
BEGIN
    NEW.text_search := to_tsvector('english', COALESCE(NEW.content, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_document_chunks_text_search ON document_chunks;
CREATE TRIGGER trg_document_chunks_text_search
    BEFORE INSERT OR UPDATE OF content ON document_chunks
    FOR EACH ROW EXECUTE FUNCTION update_document_chunks_text_search();
