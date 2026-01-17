-- Concept associations table for linking related concepts
-- Supports bidirectional lookups (e.g., collection→variables, variable→collections)

CREATE TABLE IF NOT EXISTS concept_associations (
    left_concept_type VARCHAR(50) NOT NULL,
    left_concept_id VARCHAR(100) NOT NULL,
    right_concept_type VARCHAR(50) NOT NULL,
    right_concept_id VARCHAR(100) NOT NULL,
    PRIMARY KEY (left_concept_id, right_concept_id)
);

-- Index for reverse lookups (right → left)
CREATE INDEX IF NOT EXISTS idx_associations_right
    ON concept_associations(right_concept_id, left_concept_id);

-- Index for filtering by concept types
CREATE INDEX IF NOT EXISTS idx_associations_left_type
    ON concept_associations(left_concept_type, left_concept_id);

CREATE INDEX IF NOT EXISTS idx_associations_right_type
    ON concept_associations(right_concept_type, right_concept_id);
