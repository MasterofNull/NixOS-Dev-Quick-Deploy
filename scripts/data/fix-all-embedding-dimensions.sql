-- Fix all PostgreSQL embedding dimensions (1024 for BGE-M3)
-- Run as: PGPASSWORD=$(cat /run/secrets/postgres_password | tr -d '[:space:]') psql -U aidb -h 127.0.0.1 -d aidb -f scripts/data/fix-all-embedding-dimensions.sql

\echo '=== Fixing all PostgreSQL embedding dimensions to 1024 ==='

-- Fix imported_documents table
\echo 'Fixing imported_documents table...'
DROP INDEX IF EXISTS imported_documents_embedding_idx CASCADE;
DROP INDEX IF EXISTS imported_documents_embedding_hnsw_idx CASCADE;
UPDATE imported_documents SET embedding = NULL WHERE embedding IS NOT NULL;
ALTER TABLE imported_documents DROP COLUMN IF EXISTS embedding CASCADE;
ALTER TABLE imported_documents ADD COLUMN IF NOT EXISTS embedding vector(1024);
CREATE INDEX IF NOT EXISTS imported_documents_embedding_hnsw_idx ON imported_documents USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
\echo '✓ imported_documents fixed'

-- Fix document_embeddings table
\echo 'Fixing document_embeddings table...'
DROP INDEX IF EXISTS document_embeddings_embedding_idx CASCADE;
DROP INDEX IF EXISTS document_embeddings_embedding_hnsw_idx CASCADE;
TRUNCATE TABLE document_embeddings;
ALTER TABLE document_embeddings DROP COLUMN IF EXISTS embedding CASCADE;
ALTER TABLE document_embeddings ADD COLUMN IF NOT EXISTS embedding vector(1024);
CREATE INDEX IF NOT EXISTS document_embeddings_embedding_hnsw_idx ON document_embeddings USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
\echo '✓ document_embeddings fixed'

-- Verify
\echo ''
\echo 'Verification:'
SELECT
    table_name,
    column_name
FROM information_schema.columns
WHERE data_type = 'USER-DEFINED'
AND table_schema = 'public'
ORDER BY table_name;

\echo ''
\echo '✓ All embedding dimensions fixed to 1024'
\echo 'Next: Restart AI services and run scripts/data/rebuild-qdrant-collections.sh'
