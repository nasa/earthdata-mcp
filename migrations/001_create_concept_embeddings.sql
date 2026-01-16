-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create concept embeddings table - pure embedding chunks
CREATE TABLE IF NOT EXISTS concept_embeddings (
    id UUID PRIMARY KEY,
    concept_type VARCHAR(50) NOT NULL,
    concept_id VARCHAR(100) NOT NULL,
    attribute VARCHAR(50) NOT NULL,
    text_content TEXT NOT NULL,
    embedding vector(1024) NOT NULL
);

-- Index for fast concept lookups and deletes
CREATE INDEX IF NOT EXISTS idx_concept_embeddings_concept_id
    ON concept_embeddings(concept_id);

-- Index for filtering by concept type
CREATE INDEX IF NOT EXISTS idx_concept_embeddings_concept_type
    ON concept_embeddings(concept_type);

-- Composite index for common query pattern
CREATE INDEX IF NOT EXISTS idx_concept_embeddings_type_attribute
    ON concept_embeddings(concept_type, attribute);

-- HNSW index for approximate nearest neighbor search
CREATE INDEX IF NOT EXISTS idx_concept_embeddings_embedding
    ON concept_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Unique constraint to prevent duplicate chunks
CREATE UNIQUE INDEX IF NOT EXISTS idx_concept_embeddings_unique_chunk
    ON concept_embeddings(concept_id, attribute);
