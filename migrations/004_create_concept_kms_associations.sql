-- Links concepts (collections, variables, citations) to KMS terms
-- Enables finding concepts by KMS term similarity without duplicating embeddings

CREATE TABLE IF NOT EXISTS concept_kms_associations (
    concept_type VARCHAR(50) NOT NULL,
    concept_id VARCHAR(100) NOT NULL,
    kms_uuid VARCHAR(100) NOT NULL REFERENCES kms_embeddings(kms_uuid) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (concept_type, concept_id, kms_uuid)
);

-- Index for finding all KMS terms for a concept
CREATE INDEX IF NOT EXISTS idx_concept_kms_assoc_concept
    ON concept_kms_associations(concept_type, concept_id);

-- Index for finding all concepts for a KMS term
CREATE INDEX IF NOT EXISTS idx_concept_kms_assoc_kms
    ON concept_kms_associations(kms_uuid);
