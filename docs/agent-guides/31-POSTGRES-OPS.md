# PostgreSQL Operations

**Purpose**: Manage PostgreSQL database for MCP server and metrics storage

---

## Quick Access

```bash
# Connection info
Host: localhost
Port: 5432
Database: mcp
User: mcp
Password: (see ai-stack/compose/.env)

# Quick connect
podman exec -it local-ai-postgres psql -U mcp -d mcp
```

---

## Common Operations

### Database Management

```bash
# List databases
podman exec local-ai-postgres psql -U mcp -c '\l'

# Create database
podman exec local-ai-postgres psql -U mcp -c 'CREATE DATABASE mydb;'

# Drop database
podman exec local-ai-postgres psql -U mcp -c 'DROP DATABASE mydb;'

# Database size
podman exec local-ai-postgres psql -U mcp -d mcp \
  -c "SELECT pg_size_pretty(pg_database_size('mcp'));"
```

### Table Operations

```bash
# List tables
podman exec local-ai-postgres psql -U mcp -d mcp -c '\dt'

# Describe table
podman exec local-ai-postgres psql -U mcp -d mcp -c '\d table_name'

# Create table
podman exec local-ai-postgres psql -U mcp -d mcp -c '
CREATE TABLE interactions (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    response TEXT,
    value_score FLOAT,
    timestamp TIMESTAMP DEFAULT NOW()
);'

# Query data
podman exec local-ai-postgres psql -U mcp -d mcp \
  -c 'SELECT * FROM interactions LIMIT 10;'
```

---

## Python Integration

### Basic Connection

```python
import psycopg2

# Connect
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="mcp",
    user="mcp",
    password="your-password"  # From .env
)

cursor = conn.cursor()

# Query
cursor.execute("SELECT version();")
version = cursor.fetchone()
print(f"PostgreSQL version: {version}")

# Close
cursor.close()
conn.close()
```

### Store Interaction

```python
def store_interaction_postgres(query, response, value_score, metadata):
    """Store interaction in PostgreSQL"""

    import psycopg2
    import json

    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="mcp",
        user="mcp",
        password="your-password"
    )

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO interactions (query, response, value_score, metadata, timestamp)
        VALUES (%s, %s, %s, %s, NOW())
        RETURNING id;
    """, (query, response, value_score, json.dumps(metadata)))

    interaction_id = cursor.fetchone()[0]

    conn.commit()
    cursor.close()
    conn.close()

    return interaction_id
```

### Query Interactions

```python
def get_high_value_interactions(min_score=0.7):
    """Get high-value interactions from PostgreSQL"""

    import psycopg2

    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="mcp",
        user="mcp",
        password="your-password"
    )

    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, query, response, value_score, timestamp
        FROM interactions
        WHERE value_score >= %s
        ORDER BY value_score DESC
        LIMIT 100;
    """, (min_score,))

    interactions = cursor.fetchall()

    cursor.close()
    conn.close()

    return interactions
```

---

## pgvector Operations

PostgreSQL container includes pgvector extension for vector operations.

### Enable Extension

```bash
podman exec local-ai-postgres psql -U mcp -d mcp \
  -c 'CREATE EXTENSION IF NOT EXISTS vector;'
```

### Store Vectors

```python
import psycopg2
import numpy as np

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="mcp",
    user="mcp",
    password="your-password"
)

cursor = conn.cursor()

# Create table with vector column
cursor.execute("""
    CREATE TABLE IF NOT EXISTS embeddings (
        id SERIAL PRIMARY KEY,
        text TEXT,
        embedding vector(384)
    );
""")

# Insert vector
embedding = np.random.rand(384).tolist()
cursor.execute(
    "INSERT INTO embeddings (text, embedding) VALUES (%s, %s);",
    ("example text", embedding)
)

conn.commit()
```

### Vector Search

```python
# Search for similar vectors
query_vector = np.random.rand(384).tolist()

cursor.execute("""
    SELECT text, embedding <=> %s::vector AS distance
    FROM embeddings
    ORDER BY distance
    LIMIT 5;
""", (query_vector,))

results = cursor.fetchall()
```

---

## Backup & Restore

### Backup Database

```bash
# Full backup
podman exec local-ai-postgres pg_dump -U mcp mcp > backup-$(date +%Y%m%d).sql

# Compressed backup
podman exec local-ai-postgres pg_dump -U mcp mcp | gzip > backup-$(date +%Y%m%d).sql.gz

# Backup to container then copy out
podman exec local-ai-postgres pg_dump -U mcp -F c -f /tmp/backup.dump mcp
podman cp local-ai-postgres:/tmp/backup.dump ./
```

### Restore Database

```bash
# From SQL file
cat backup.sql | podman exec -i local-ai-postgres psql -U mcp -d mcp

# From compressed
gunzip -c backup.sql.gz | podman exec -i local-ai-postgres psql -U mcp -d mcp

# From custom format
podman cp backup.dump local-ai-postgres:/tmp/
podman exec local-ai-postgres pg_restore -U mcp -d mcp /tmp/backup.dump
```

---

## Monitoring

### Check Status

```bash
# Connection check
podman exec local-ai-postgres pg_isready -U mcp

# Active connections
podman exec local-ai-postgres psql -U mcp -d mcp -c '
SELECT count(*) FROM pg_stat_activity;'

# Database stats
podman exec local-ai-postgres psql -U mcp -d mcp -c '
SELECT * FROM pg_stat_database WHERE datname = '\''mcp'\'';'
```

### Performance

```bash
# Slow queries
podman exec local-ai-postgres psql -U mcp -d mcp -c '
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;'

# Table sizes
podman exec local-ai-postgres psql -U mcp -d mcp -c '
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'\''.'\''||tablename)) AS size
FROM pg_tables
ORDER BY pg_total_relation_size(schemaname||'\''.'\''||tablename) DESC;'
```

---

## Troubleshooting

### Connection Refused

```bash
# Check container running
podman ps | grep postgres

# Check port
ss -tlnp | grep 5432

# Check logs
podman logs local-ai-postgres --tail 50
```

### Out of Connections

```bash
# Check max connections
podman exec local-ai-postgres psql -U mcp -d mcp \
  -c 'SHOW max_connections;'

# Increase in docker-compose.yml:
# command: postgres -c max_connections=200
```

### Slow Queries

```bash
# Enable query logging
# Add to docker-compose.yml environment:
# POSTGRES_INITDB_ARGS: "-c log_statement=all"

# Create indexes
podman exec local-ai-postgres psql -U mcp -d mcp \
  -c 'CREATE INDEX idx_value_score ON interactions(value_score);'
```

---

## Next Steps

- [Qdrant Operations](30-QDRANT-OPERATIONS.md) - Vector database
- [Error Logging](32-ERROR-LOGGING.md) - Store errors
- [Continuous Learning](22-CONTINUOUS-LEARNING.md) - Use both databases
