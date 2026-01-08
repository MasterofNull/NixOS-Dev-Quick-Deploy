# Testing Guide - AI Stack Health Checks

## Overview

This repository includes comprehensive health check and test scripts for the AI stack.

## Health Check Scripts

### Quick Health Check (Recommended)

```bash
# Simple, dependency-free health check
python3 scripts/check-ai-stack-health-v2.py
```

Features:
- No external dependencies (uses only stdlib + requests)
- Smart container detection
- Checks Qdrant, llama.cpp, Open WebUI
- Handles optional services (PostgreSQL, Redis, Ollama)
- Clear status indicators

### Verbose Mode

```bash
python3 scripts/check-ai-stack-health-v2.py -v
```

Shows:
- Running containers list
- Detailed service information
- Collection counts for Qdrant
- Model loading status

### JSON Output

```bash
python3 scripts/check-ai-stack-health-v2.py -j > health-check.json
```

Useful for automation and monitoring.

## Advanced Test Suites

### RAG Workflow Tests

Tests the complete RAG (Retrieval Augmented Generation) workflow:

```bash
# Install dependencies (NixOS specific)
# Note: Due to NixOS immutable /nix/store, use containers for full testing

# Quick test inside Qdrant container
podman exec -it local-ai-qdrant /bin/sh -c "
  curl http://localhost:6333/healthz &&
  curl http://localhost:6333/collections | jq
"
```

Tests covered:
- Ollama embedding generation (384 dimensions)
- Qdrant connectivity
- Collection existence check
- Store and retrieve workflow
- Semantic search functionality
- Complete RAG workflow with context augmentation

### Continuous Learning Tests

Tests the continuous learning system components:

```bash
# Tests value scoring algorithm
# Tests interaction storage with metadata
# Tests error solution storage
# Tests high-value pattern detection
```

Tests covered:
- 5-factor value scoring (complexity, reusability, novelty, confirmation, impact)
- Interaction storage with automatic value scoring
- Error and solution storage
- High-value pattern storage in skills-patterns collection
- Error retrieval by semantic similarity

## NixOS-Specific Testing Notes

### Virtual Environment Issues

On NixOS, Python virtual environments can have issues with system libraries (libstdc++.so.6, etc). This is documented in our continuous learning guides.

**Solution 1**: Use containerized testing
```bash
# Run tests inside AI stack containers
podman exec -it local-ai-qdrant python3 /path/to/test.py
```

**Solution 2**: Use the hybrid-ai-stack.sh helper
```bash
# The helper script handles environment properly
./scripts/hybrid-ai-stack.sh status
```

**Solution 3**: Install packages system-wide (not recommended for NixOS)

## Automated Health Monitoring

### Cron Job Setup

Add to your crontab:
```bash
# Check AI stack health every hour
0 * * * * /path/to/nixos-quick-deploy/scripts/check-ai-stack-health-v2.py -j >> /var/log/ai-stack-health.log 2>&1
```

### Systemd Timer (Recommended for NixOS)

Create `/etc/systemd/system/ai-stack-health.service`:
```ini
[Unit]
Description=AI Stack Health Check
After=network.target

[Service]
Type=oneshot
ExecStart=/path/to/scripts/check-ai-stack-health-v2.py -j
StandardOutput=journal
StandardError=journal
```

Create `/etc/systemd/system/ai-stack-health.timer`:
```ini
[Unit]
Description=AI Stack Health Check Timer

[Timer]
OnCalendar=hourly
Persistent=true

[Install]
WantedBy=timers.target
```

Enable:
```bash
sudo systemctl enable --now ai-stack-health.timer
```

## Interpreting Results

### Status Indicators

- ✓ **OK**: Service is healthy and responding correctly
- ⚠ **Warning**: Service running but with issues (missing collections, no models loaded)
- ✗ **Error**: Service not reachable or failing health checks
- ○ **Not Running**: Optional service not currently running

### Common Warnings and Fixes

#### Qdrant: Missing Collections

**Warning**: "Qdrant is healthy (missing 5 collections)"

**Fix**:
```bash
./scripts/setup-hybrid-learning-auto.sh
```

#### llama.cpp: No Models Loaded

**Warning**: "llama.cpp is healthy (no models loaded - may be downloading)"

**Check Progress**:
```bash
podman logs -f local-ai-llama-cpp
```

First-time model download takes 10-45 minutes depending on connection speed.

#### PostgreSQL/Redis Not Running

**Status**: "Container not running (optional service)"

These are optional services. To start:
```bash
./scripts/hybrid-ai-stack.sh up
```

## Integration with Deployment

### Phase 9 Testing

The health check integrates with `nixos-quick-deploy.sh` Phase 9:

```bash
#In Phase 9, after AI stack deployment:
python3 scripts/check-ai-stack-health-v2.py -v
```

Shows deployment status and verifies all services started correctly.

## Continuous Integration

### Pre-Commit Hook

Create `.git/hooks/pre-push`:
```bash
#!/bin/bash
echo "Running AI stack health check..."
python3 scripts/check-ai-stack-health-v2.py
exit $?
```

Ensures AI stack is healthy before pushing changes.

## Troubleshooting

### Import Errors on NixOS

**Error**: `libstdc++.so.6: cannot open shared object file`

**Cause**: Virtual environment missing system libraries

**Solution**: Use system Python or run tests in containers
```bash
# Option 1: Remove venv, use system Python
rm -rf venv

# Option 2: Run in container
podman exec -it local-ai-qdrant python3 script.py
```

### Connection Refused Errors

**Error**: "Service is not reachable (connection refused)"

**Cause**: Container not running

**Fix**:
```bash
# Check containers
podman ps --filter "label=nixos.quick-deploy.ai-stack=true"

# Start stack
./scripts/hybrid-ai-stack.sh up
```

### Timeout Errors

**Error**: "Service timed out after 5s"

**Cause**: Service starting up or under heavy load

**Fix**:
```bash
# Increase timeout
python3 scripts/check-ai-stack-health-v2.py --timeout 30

# Check service logs
podman logs SERVICE_NAME
```

## Documentation References

- [System Overview](/docs/agent-guides/00-SYSTEM-OVERVIEW.md)
- [Service Status Checking](/docs/agent-guides/02-SERVICE-STATUS.md)
- [RAG Context Guide](/docs/agent-guides/21-RAG-CONTEXT.md)
- [Continuous Learning](/docs/agent-guides/22-CONTINUOUS-LEARNING.md)
- [Qdrant Operations](/docs/agent-guides/30-QDRANT-OPERATIONS.md)

## Contributing

When adding new tests:

1. Follow patterns in existing test scripts
2. Include cleanup code to remove test data
3. Document expected behavior and error conditions
4. Test on clean NixOS installation
5. Update this TESTING.md with new test procedures

---

**Last Updated**: 2025-12-20
**Tested On**: NixOS 24.11
**Python Version**: 3.13
