# Container Deployment Hang/Crash Fix - 2025-12-31

## Problem Summary

The nixos-quick-deploy script hangs or crashes during AI stack container deployment at these containers:
- local-ai-open-webui
- local-ai-postgres
- local-ai-redis
- local-ai-mindsdb
- local-ai-health-monitor
- local-ai-nixos-docs
- local-ai-aidb (Exit code 1)
- local-ai-qdrant (Exit code 101)
- local-ai-hybrid-coordinator (Never starts)

## Root Cause Analysis

### 1. Port Conflicts with Host Processes (Critical)

**Issue:** Containers using `network_mode: host` try to bind to ports already in use by previous deployments

**Evidence:**
```bash
$ ss -tlnp | grep 8091
LISTEN 0  2048  0.0.0.0:8091  0.0.0.0:*  users:(("python3",pid=1328823,fd=10))

$ podman exec local-ai-aidb /app/start_with_discovery.sh
ERROR: [Errno 98] error while attempting to bind on address ('0.0.0.0', 8091): address already in use
```

**Affected Containers:**
- `aidb`: Port 8091 conflict
- `hybrid-coordinator`: Port 8092 conflict
- `nixos-docs`: Port 8094 conflict
- `open-webui`: Port 3001 conflict

**Why network_mode: host?**
The docker-compose.yml uses `network_mode: host` for these containers to allow direct localhost access between services. However, this bypasses Docker's port mapping and causes conflicts with existing host processes.

### 2. Qdrant Container Exit Code 101 (Critical)

**Issue:** Qdrant container exits immediately with code 101

**Evidence:**
```bash
$ podman ps -a | grep qdrant
local-ai-qdrant   Exited (101) 3 hours ago (healthy)
```

**Probable Causes:**
- Volume permission mismatch (files owned by root inside container, directory owned by user)
- Corrupted raft_state.json from previous run
- Resource limits preventing startup
- healthcheck configuration issue

### 3. No Pre-Deployment Cleanup (Medium)

**Issue:** Previous deployment processes continue running, causing conflicts

**Impact:**
- Old AIDB servers occupy ports 8091, 8092, 8094
- Resource contention
- Confusing error messages

### 4. Dependency Chain Failures (Medium)

**Issue:** When AIDB and Qdrant fail, dependent containers also fail:
- `hybrid-coordinator` depends on `aidb` (never starts - "Created" status)
- Health checks fail because services aren't running
- Cascade failure of entire stack

## Comprehensive Fix

### Fix 1: Pre-Deployment Cleanup Script

Create a script to stop existing services before deployment:

**File:** `scripts/stop-ai-stack.sh`
```bash
#!/usr/bin/env bash
# Stop all AI stack services (both host and containers)

set -euo pipefail

echo "🛑 Stopping AI Stack services..."

# Stop containers
cd "$(dirname "$0")/../ai-stack/compose"
if podman-compose ps -q >/dev/null 2>&1; then
    echo "  Stopping containers..."
    podman-compose down || true
fi

# Kill host processes on conflicting ports
for port in 8091 8092 8094 3001; do
    if pid=$(lsof -ti:$port 2>/dev/null); then
        echo "  Killing process on port $port (PID: $pid)"
        kill -9 $pid 2>/dev/null || true
    fi
done

# Check for orphaned AIDB/coordinator processes
pkill -9 -f "server.py --config" 2>/dev/null || true
pkill -9 -f "start_with_discovery.sh" 2>/dev/null || true
pkill -9 -f "start_with_learning.sh" 2>/dev/null || true

echo "✅ AI Stack stopped"
```

### Fix 2: Volume Permission Reset Script

**File:** `scripts/reset-ai-volumes.sh`
```bash
#!/usr/bin/env bash
# Reset AI stack volume permissions

set -euo pipefail

AI_STACK_DATA="${HOME}/.local/share/nixos-ai-stack"

echo "🔧 Resetting AI stack volume permissions..."

# Stop containers first
./scripts/stop-ai-stack.sh

# Reset Qdrant volume (most common issue)
if [ -d "$AI_STACK_DATA/qdrant" ]; then
    echo "  Resetting Qdrant volume..."
    chmod -R u+rwX "$AI_STACK_DATA/qdrant"
    # Remove potentially corrupted state
    rm -f "$AI_STACK_DATA/qdrant/raft_state.json"
fi

# Reset other volumes
for vol in aidb hybrid-coordinator nixos-docs health-monitor; do
    if [ -d "$AI_STACK_DATA/$vol" ]; then
        echo "  Resetting $vol volume..."
        chmod -R u+rwX "$AI_STACK_DATA/$vol"
    fi
done

echo "✅ Volumes reset"
```

### Fix 3: Update docker-compose.yml Health Checks

**Issue:** Qdrant healthcheck uses `["CMD", "true"]` which always passes even when container crashes

**Fix:** Update Qdrant healthcheck in [ai-stack/compose/docker-compose.yml](/ai-stack/compose/docker-compose.yml:78-83):

```yaml
# BEFORE
healthcheck:
  test: ["CMD", "true"]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 30s

# AFTER
healthcheck:
  test: ["CMD-SHELL", "curl -f http://localhost:6333/healthz || exit 1"]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 30s
```

### Fix 4: Add Restart Policy to docker-compose.yml

**Issue:** Some containers don't have proper restart policies

**Fix:** Ensure all critical containers have `restart: unless-stopped`

All containers already have this except those in profiles (aider, autogpt, ralph-wiggum).

### Fix 5: Improve Startup Script

**File:** `scripts/start-ai-stack-and-dashboard.sh`

Add pre-flight checks:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 Starting AI Stack..."

# Pre-flight: Stop existing services
echo "  Pre-flight: Stopping existing services..."
"$SCRIPT_DIR/stop-ai-stack.sh"

# Check for port conflicts
echo "  Pre-flight: Checking ports..."
for port in 8091 8092 8094 3001 6333 8080; do
    if lsof -i:$port >/dev/null 2>&1; then
        echo "❌ Port $port is still in use after cleanup!"
        exit 1
    fi
done

# Start containers
cd "$PROJECT_ROOT/ai-stack/compose"
podman-compose up -d

echo "✅ AI Stack started"
```

### Fix 6: Update Phase 09 AI Model Deployment

**File:** `phases/phase-09-ai-model-deployment.sh`

Add cleanup before deployment:

```bash
# Around line 100, before starting AI stack
log_info "Cleaning up previous AI stack deployment..."
if [ -f "${SCRIPT_DIR}/scripts/stop-ai-stack.sh" ]; then
    bash "${SCRIPT_DIR}/scripts/stop-ai-stack.sh" || true
fi
```

## Implementation Steps

### 1. Create Cleanup Scripts

```bash
cd /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy

# Create stop script
cat > scripts/stop-ai-stack.sh << 'EOF'
[Script content from Fix 1]
EOF
chmod +x scripts/stop-ai-stack.sh

# Create volume reset script
cat > scripts/reset-ai-volumes.sh << 'EOF'
[Script content from Fix 2]
EOF
chmod +x scripts/reset-ai-volumes.sh
```

### 2. Fix Qdrant Health Check

Edit `ai-stack/compose/docker-compose.yml` and update the Qdrant healthcheck.

### 3. Update Deployment Scripts

- Modify `scripts/start-ai-stack-and-dashboard.sh` to call cleanup first
- Modify `phases/phase-09-ai-model-deployment.sh` to call cleanup

### 4. Test Deployment

```bash
# Full cleanup
./scripts/stop-ai-stack.sh
./scripts/reset-ai-volumes.sh

# Fresh deployment
./nixos-quick-deploy.sh
```

## Testing Checklist

- [ ] Run `scripts/stop-ai-stack.sh` - should kill all processes
- [ ] Check `lsof -i:8091` - should return nothing
- [ ] Run `scripts/reset-ai-volumes.sh` - should reset permissions
- [ ] Check `ls -la ~/.local/share/nixos-ai-stack/qdrant` - should be writable
- [ ] Start containers with `podman-compose up -d`
- [ ] Check `podman ps` - all containers should be "Up" or "healthy"
- [ ] Check logs: `podman logs local-ai-aidb` - should show "Started server"
- [ ] Check logs: `podman logs local-ai-qdrant` - should show Qdrant started
- [ ] Verify ports: `curl http://localhost:8091/health` - should return success
- [ ] Verify ports: `curl http://localhost:6333/healthz` - should return success

## Alternative: Remove network_mode: host

If port conflicts persist, consider removing `network_mode: host` and using standard Docker networking:

**Pros:**
- No port conflicts
- Better isolation
- Standard Docker networking

**Cons:**
- Need to update all inter-service URLs from `localhost` to container names
- Slightly more complex networking

**Changes Required:**
1. Remove `network_mode: host` from aidb, hybrid-coordinator, nixos-docs, open-webui
2. Add explicit `ports:` mappings
3. Update environment variables to use container names instead of localhost

## Root Cause: Why Does Deployment Hang?

The deployment appears to hang because:

1. **Docker Compose waits for health checks** - When AIDB can't bind to port 8091, it crashes repeatedly
2. **Qdrant crash prevents dependent containers** - hybrid-coordinator waits for AIDB which waits for Qdrant
3. **No timeout on compose up** - podman-compose waits indefinitely for services to become healthy
4. **Silent failures** - Containers crash but compose doesn't report why

## Prevention for Future

1. **Always run cleanup script** before deployment
2. **Add timeout to compose up**: `timeout 300 podman-compose up -d`
3. **Monitor logs during deployment**: `podman-compose logs -f` in separate terminal
4. **Use health check dashboard**: scripts/ai-stack-monitor.sh
5. **Validate ports before start**: Check for conflicts automatically

---

**Date:** 2025-12-31
**Issue:** Container deployment hanging/crashing
**Root Cause:** Port conflicts + Qdrant volume permissions + no cleanup
**Status:** Awaiting implementation
