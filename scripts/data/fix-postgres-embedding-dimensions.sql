-- Fix PostgreSQL embedding dimensions after model change
-- Changes embedding column from 2560 to 1024 dimensions
-- Run as: psql -U aidb -h 127.0.0.1 -d aidb -f scripts/data/fix-postgres-embedding-dimensions.sql

\echo 'Fixing PostgreSQL embedding dimensions...'

-- Drop existing HNSW indexes (they don't support dimension changes)
DROP INDEX IF EXISTS imported_documents_embedding_idx;
DROP INDEX IF EXISTS imported_documents_embedding_hnsw_idx;

\echo 'Dropped existing indexes'

-- Clear all existing embeddings (they have wrong dimensions)
UPDATE imported_documents SET embedding = NULL WHERE embedding IS NOT NULL;

\echo 'Cleared existing embeddings'

-- Alter the column to accept 1024 dimensions
-- Note: pgvector doesn't support ALTER COLUMN for dimensions,
-- so we need to drop and recreate
ALTER TABLE imported_documents DROP COLUMN IF EXISTS embedding CASCADE;
ALTER TABLE imported_documents ADD COLUMN IF NOT EXISTS embedding vector(1024);

\echo 'Recreated embedding column with 1024 dimensions'

-- Create HNSW index for fast similarity search
-- HNSW max is 2000 dimensions, so 1024 is safe
CREATE INDEX IF NOT EXISTS imported_documents_embedding_hnsw_idx
ON imported_documents
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

\echo 'Created HNSW index'

-- Verify
SELECT
    column_name,
    data_type,
    character_maximum_length
FROM information_schema.columns
WHERE table_name = 'imported_documents'
AND column_name = 'embedding';

\echo 'PostgreSQL embedding dimension fix complete!'
\echo 'Run scripts/data/rebuild-qdrant-collections.sh to re-index documents'
