-- KMS embeddings table - normalized storage for KMS term embeddings
-- Stores one embedding per KMS term (platform, instrument, science keyword)
-- instead of duplicating across every concept that uses the term

CREATE TABLE IF NOT EXISTS kms_embeddings (
    kms_uuid VARCHAR(100) PRIMARY KEY,
    scheme VARCHAR(50) NOT NULL,
    term VARCHAR(500) NOT NULL,
    definition TEXT,
    embedding vector(1024) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for lookups by scheme (e.g., all platforms)
CREATE INDEX IF NOT EXISTS idx_kms_embeddings_scheme
    ON kms_embeddings(scheme);

-- Index for lookups by term within scheme
CREATE INDEX IF NOT EXISTS idx_kms_embeddings_scheme_term
    ON kms_embeddings(scheme, term);

-- HNSW index for approximate nearest neighbor search
CREATE INDEX IF NOT EXISTS idx_kms_embeddings_embedding
    ON kms_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
