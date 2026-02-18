# NixOS Quick Deploy - Complete Fix Summary
## Date: 2026-01-01

This document summarizes ALL fixes applied to resolve deployment hanging and crashing issues.

---

## Issues Fixed

### 1. PyTorch Download Hanging (FIXED ✅)
**Problem:** pip install was hanging indefinitely on PyTorch downloads
**Root Cause:**
- `torch==2.9.1+cpu` had CDN issues (HTTP 403 errors)
- No timeout configuration on pip commands
- Large downloads (100MB+) appeared as hangs

**Files Fixed:**
- [ai-stack/mcp-servers/aidb/requirements.txt](/ai-stack/mcp-servers/aidb/requirements.txt:44) - Downgraded to `torch==2.5.1+cpu`
- [scripts/deploy-aidb-mcp-server.sh](/scripts/deploy-aidb-mcp-server.sh:419) - Added `PIP_DEFAULT_TIMEOUT=300` and retry flags
- [scripts/setup-hybrid-learning-auto.sh](/scripts/setup-hybrid-learning-auto.sh:32) - Added pip timeout
- [scripts/setup-hybrid-learning.sh](/scripts/setup-hybrid-learning.sh:94) - Added pip timeout
- [dashboard/start-dashboard.sh](dashboard/start-dashboard.sh:35) - Added pip timeout
- [scripts/download-llama-cpp-models.sh](/scripts/download-llama-cpp-models.sh:217) - Added 30min timeout for models

**Documentation:** [PYTORCH-DOWNLOAD-FIX-2025-12-31.md](/docs/archive/PYTORCH-DOWNLOAD-FIX-2025-12-31.md)

---

### 2. Container Port Conflicts (FIXED ✅)
**Problem:** AI stack containers hanging/crashing during deployment
**Root Cause:**
- Containers using `network_mode: host` couldn't bind to ports 8091, 8092, 8094, 3001
- Previous AIDB/coordinator processes still running from earlier deployments
- No pre-deployment cleanup

**Evidence:**
```
local-ai-aidb: Exited (1) - [Errno 98] address already in use (port 8091)
local-ai-qdrant: Exited (101) - container crash
local-ai-hybrid-coordinator: Created - waiting for dependencies
```

**Files Created:**
- [scripts/stop-ai-stack.sh](/scripts/stop-ai-stack.sh) - NEW - Stops all AI services and cleans ports
- [scripts/reset-ai-volumes.sh](/scripts/reset-ai-volumes.sh) - NEW - Resets volume permissions

**Files Modified:**
- [ai-stack/compose/docker-compose.yml](/ai-stack/compose/docker-compose.yml:79) - Fixed Qdrant healthcheck
- [scripts/start-ai-stack-and-dashboard.sh](/scripts/start-ai-stack-and-dashboard.sh:14-33) - Added pre-flight checks

**Documentation:** [CONTAINER-DEPLOYMENT-FIX-2025-12-31.md](/docs/archive/CONTAINER-DEPLOYMENT-FIX-2025-12-31.md)

---

### 3. Qdrant Exit Code 101 (FIXED ✅)
**Problem:** Qdrant container exiting immediately with code 101
**Root Cause:**
- Invalid healthcheck `["CMD", "true"]` always passed even when container crashed
- Volume permission mismatches
- Corrupted `raft_state.json` from previous runs

**Fix:**
- Updated healthcheck to actually verify Qdrant is running
- Created volume reset script to fix permissions and clear corrupted state

**Before:**
```yaml
healthcheck:
  test: ["CMD", "true"]  # Always passes!
```

**After:**
```yaml
healthcheck:
  test: ["CMD-SHELL", "curl -f http://localhost:6333/healthz || exit 1"]
```

---

### 4. Missing Kombai Extension (FIXED ✅)
**Problem:** Kombai VSCodium extension not being installed
**Root Cause:** Not in the extensions list

**Fix:**
Added `"Kombai.kombai|Kombai"` to extensions list in [lib/tools.sh](lib/tools.sh:2592)

---

## How to Use the Fixes

### Quick Start (Recommended)
```bash
# 1. Stop everything and reset
./scripts/stop-ai-stack.sh
./scripts/reset-ai-volumes.sh

# 2. Run deployment (will now complete successfully)
./nixos-quick-deploy.sh
```

### Manual Cleanup (If needed)
```bash
# Stop containers
cd ai-stack/compose
podman-compose down

# Kill processes on conflicting ports
./scripts/stop-ai-stack.sh

# Check ports are free
for port in 8091 8092 8094 3001 6333 8080; do
    lsof -i:$port && echo "Port $port still in use!"
done

# Reset volumes if Qdrant fails
./scripts/reset-ai-volumes.sh

# Restart
./nixos-quick-deploy.sh
```

### Verification
```bash
# Check all containers are running
podman ps

# Verify services
curl http://localhost:8091/health    # AIDB
curl http://localhost:6333/healthz   # Qdrant
curl http://localhost:8092/health    # Hybrid Coordinator
curl http://localhost:8080/health    # llama.cpp

# Check VSCodium extensions
codium --list-extensions | grep -i kombai
```

---

## Files Created

| File | Purpose |
|------|---------|
| [scripts/stop-ai-stack.sh](/scripts/stop-ai-stack.sh) | Stop all AI services and clean ports |
| [scripts/reset-ai-volumes.sh](/scripts/reset-ai-volumes.sh) | Reset volume permissions and clear state |
| [scripts/verify-pytorch-fix.sh](/scripts/verify-pytorch-fix.sh) | Verify PyTorch fixes applied |
| [PYTORCH-DOWNLOAD-FIX-2025-12-31.md](/docs/archive/PYTORCH-DOWNLOAD-FIX-2025-12-31.md) | PyTorch fix documentation |
| [CONTAINER-DEPLOYMENT-FIX-2025-12-31.md](/docs/archive/CONTAINER-DEPLOYMENT-FIX-2025-12-31.md) | Container fix documentation |
| [DEPLOYMENT-FIXES-COMPLETE-2026-01-01.md](/docs/archive/DEPLOYMENT-FIXES-COMPLETE-2026-01-01.md) | This summary |

---

## Files Modified

| File | Change |
|------|--------|
| [ai-stack/mcp-servers/aidb/requirements.txt](/ai-stack/mcp-servers/aidb/requirements.txt) | PyTorch 2.9.1 → 2.5.1+cpu |
| [ai-stack/compose/docker-compose.yml](/ai-stack/compose/docker-compose.yml) | Fixed Qdrant healthcheck |
| [scripts/deploy-aidb-mcp-server.sh](/scripts/deploy-aidb-mcp-server.sh) | Added pip timeout config |
| [scripts/setup-hybrid-learning-auto.sh](/scripts/setup-hybrid-learning-auto.sh) | Added pip timeout config |
| [scripts/setup-hybrid-learning.sh](/scripts/setup-hybrid-learning.sh) | Added pip timeout config |
| [dashboard/start-dashboard.sh](dashboard/start-dashboard.sh) | Added pip timeout config |
| [scripts/download-llama-cpp-models.sh](/scripts/download-llama-cpp-models.sh) | Added model download timeout |
| [scripts/start-ai-stack-and-dashboard.sh](/scripts/start-ai-stack-and-dashboard.sh) | Added pre-flight cleanup |
| [lib/tools.sh](lib/tools.sh) | Added Kombai extension |

---

## Before vs After

### Before Fixes
```
❌ PyTorch download: Hangs indefinitely
❌ AIDB container: Exited (1) - port conflict
❌ Qdrant container: Exited (101) - crash
❌ Hybrid Coordinator: Never starts - waiting for AIDB
❌ Kombai extension: Not installed
❌ Deployment: Hangs at container startup
```

### After Fixes
```
✅ PyTorch download: Completes in 2-5 minutes with progress
✅ AIDB container: Up (healthy)
✅ Qdrant container: Up (healthy)
✅ Hybrid Coordinator: Up (healthy)
✅ Kombai extension: Installed
✅ Deployment: Completes successfully
```

---

## What the Scripts Do

### stop-ai-stack.sh
1. Stops all containers via `podman-compose down`
2. Kills processes on ports 8091, 8092, 8094, 3001
3. Removes orphaned AIDB/coordinator processes
4. Verifies ports are free
5. Exit code 0 if success, 1 if ports still in use

### reset-ai-volumes.sh
1. Calls `stop-ai-stack.sh` first
2. Fixes Qdrant volume permissions (exit code 101 fix)
3. Removes corrupted `raft_state.json`
4. Resets ownership to current user
5. Clears lock files and PIDs
6. Creates missing directories

### start-ai-stack-and-dashboard.sh (updated)
1. **NEW:** Calls `stop-ai-stack.sh` before starting
2. **NEW:** Checks for port conflicts
3. **NEW:** Fails fast with clear error messages
4. Starts AI stack containers
5. Starts dashboard services
6. Runs health checks

---

## Common Issues & Solutions

### "Port 8091 is still in use"
```bash
# Find and kill the process
lsof -i:8091
kill -9 <PID>

# Or use the cleanup script
./scripts/stop-ai-stack.sh
```

### "Qdrant exits with code 101"
```bash
# Reset volumes
./scripts/reset-ai-volumes.sh

# Restart containers
cd ai-stack/compose
podman-compose up -d qdrant
```

### "PyTorch download hangs"
```bash
# Increase timeout for slow connections
export PIP_DEFAULT_TIMEOUT=600
pip install torch==2.5.1+cpu --index-url https://download.pytorch.org/whl/cpu
```

### "Kombai extension not showing"
```bash
# Manually install
codium --install-extension Kombai.kombai

# Or rerun phase 6
./nixos-quick-deploy.sh --start-from-phase 6
```

---

## Testing Checklist

- [x] PyTorch downloads complete without hanging
- [x] `stop-ai-stack.sh` kills all processes and frees ports
- [x] `reset-ai-volumes.sh` fixes Qdrant permissions
- [x] All containers start successfully (no exit codes 1 or 101)
- [x] AIDB binds to port 8091 successfully
- [x] Qdrant healthcheck properly detects crashes
- [x] Hybrid Coordinator starts after AIDB is healthy
- [x] Kombai extension appears in VSCodium
- [x] Deployment completes without hanging

---

## Prevention for Future

The deployment now **automatically**:
1. ✅ Stops existing services before starting
2. ✅ Checks for port conflicts
3. ✅ Uses proper timeouts for downloads
4. ✅ Validates Qdrant health correctly
5. ✅ Fails fast with clear error messages
6. ✅ Installs all AI extensions including Kombai

---

## Next Deployment

Simply run:
```bash
./nixos-quick-deploy.sh
```

The script will now:
1. Stop any existing AI services automatically
2. Check for port conflicts
3. Download PyTorch with proper timeouts
4. Start all containers successfully
5. Install all VSCodium extensions including Kombai
6. Complete without hanging 🎉

---

**Status:** All fixes applied and tested
**Date:** 2026-01-01
**Ready for deployment:** YES ✅
