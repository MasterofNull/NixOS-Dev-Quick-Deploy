#!/bin/bash
set -e

echo "Starting NixOS Documentation MCP Server..."

# Wait for Redis to be ready
echo "Waiting for Redis..."
timeout 30 bash -c 'until echo > /dev/tcp/${REDIS_HOST:-localhost}/${REDIS_PORT:-6379}; do sleep 1; done' || echo "Redis not available, using disk cache only"

# Sync repositories on startup (in background)
echo "Syncing documentation repositories..."
python3 -c "
import asyncio
from server import clone_or_update_repo, DOCUMENTATION_SOURCES

async def sync_all():
    for key in DOCUMENTATION_SOURCES:
        if 'repo_url' in DOCUMENTATION_SOURCES[key]:
            print(f'Syncing {key}...')
            await clone_or_update_repo(key)

asyncio.run(sync_all())
" &

# Start the FastAPI server
echo "Starting FastAPI server on port 8094..."
exec uvicorn server:app --host 0.0.0.0 --port 8094 --log-level info
