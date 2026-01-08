# AIDB Database Migrations
**Updated:** 2026-01-09

## Quick Start

From repo root:

```bash
alembic -c ai-stack/migrations/alembic.ini upgrade head
```

## Configuration

- `AIDB_CONFIG` (optional): path to config file (defaults to `ai-stack/mcp-servers/config/config.yaml`)
- `STACK_ENV` (optional): applies config overlays (`config.dev.yaml`, `config.staging.yaml`, `config.prod.yaml`)

Example:

```bash
STACK_ENV=staging alembic -c ai-stack/migrations/alembic.ini upgrade head
```

## Rollback Test

```bash
ai-stack/migrations/test-migrations.sh
```

## Existing Deployments

If the schema already exists, stamp the current state instead of re-creating tables:

```bash
alembic -c ai-stack/migrations/alembic.ini stamp head
```

## Testing in a Temporary Database

Use a separate database for upgrade/downgrade validation:

```bash
# Create a test database (inside Postgres container)
podman exec local-ai-postgres psql -U mcp -d postgres -c "CREATE DATABASE mcp_migrations_test"

# Minimal config for migrations
cat <<'EOF' >/tmp/aidb-migrations-config.yaml
database:
  postgres:
    host: postgres
    port: 5432
    user: mcp
    database: mcp_migrations_test
EOF

podman cp /tmp/aidb-migrations-config.yaml local-ai-aidb:/app/config/aidb-migrations-config.yaml
podman cp ai-stack/migrations local-ai-aidb:/app/migrations
podman exec -e PYTHONPATH=/app -e AIDB_CONFIG=/app/config/aidb-migrations-config.yaml \
  local-ai-aidb alembic -c /app/migrations/alembic.ini upgrade head
```
