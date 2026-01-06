# Fixes Applied - December 31, 2025

## Summary
Fixed critical issues preventing the AI stack and NixOS MCP server from deploying correctly.

---

## Issues Found & Fixed

### 1. ✅ **Podman-Compose Pod Conflict**
**Problem:** `network_mode: host` is incompatible with podman-compose's automatic pod creation
**Symptom:** Containers stuck in "Created" state, unable to start
**Fix Applied:**
```yaml
# Added to docker-compose.yml (line 52-55)
x-podman:
  userns: "keep-id"
  pod: false
```
**Impact:** Disables automatic pod creation, allowing `network_mode: host` to work correctly

---

### 2. ✅ **Stuck Podman-Compose Process**
**Problem:** `podman create` for `local-ai-open-webui` hung for over 1 hour
**Symptom:** `podman-compose up` blocked, unable to proceed
**Fix Applied:**
```bash
kill -9 3754959 3680827  # Killed stuck processes
podman pod rm -f pod_compose  # Removed stuck pod
```
**Impact:** Unblocked deployment pipeline

---

### 3. ✅ **NixOS MCP Server Script Permissions**
**Problem:** `start_server.sh` was not executable
**Symptom:** Would fail when Docker tries to execute CMD
**Fix Applied:**
```bash
chmod +x ai-stack/mcp-servers/nixos-docs/start_server.sh
```
**Impact:** Script can now be executed by the container

---

## Files Modified

### [docker-compose.yml](compose/docker-compose.yml)
- Added `x-podman` configuration to disable pod creation
- Resolves network_mode: host compatibility issue

### [start_server.sh](../mcp-servers/nixos-docs/start_server.sh)
- Made executable (chmod +x)
- Ensures Docker can run the startup script

---

## Current Status

### ✅ Completed
- [x] Fixed docker-compose.yml pod conflict
- [x] Killed stuck processes
- [x] Made startup scripts executable
- [x] Removed stuck pods

### 🔄 In Progress
- [ ] NixOS docs container build (downloading PyTorch ~900MB)
  - Status: Running normally, not stuck
  - ETA: 5-15 minutes (network dependent)

---

## Next Steps

### 1. Wait for Build Completion
```bash
# Monitor build progress
watch -n 5 'podman ps -a --format "table {{.ID}}\t{{.Names}}\t{{.Status}}"'
```

### 2. Test Deployment
Once the build completes, deploy and test:
```bash
cd ai-stack/compose
podman-compose up -d nixos-docs
podman logs -f local-ai-nixos-docs
curl http://localhost:8094/health
```

### 3. Verify All Services
```bash
# Check all containers
podman-compose ps

# Check logs for errors
podman-compose logs | grep -i error

# Test NixOS docs API
curl -X POST http://localhost:8094/packages/search \
  -H "Content-Type: application/json" \
  -d '{"name": "git"}'
```

---

## Technical Details

### Why `network_mode: host` Was Causing Issues

Podman-compose automatically creates a pod for all services by default. Pods use a shared network namespace, which conflicts with `network_mode: host` (which requires the host's network namespace).

The fix (`x-podman: pod: false`) tells podman-compose to NOT create a pod, allowing each container to use its own network configuration.

### Alternative Solutions (Not Chosen)

1. **Remove `network_mode: host`** - Would require port mapping for all services
2. **Use podman directly** - Would lose docker-compose orchestration
3. **Separate compose files** - Would fragment the stack

---

## Verification Checklist

After build completion, verify:

- [ ] All containers start successfully
- [ ] No containers in "Created" state
- [ ] Health checks pass for all services
- [ ] NixOS docs API responds on port 8094
- [ ] No pod conflicts in logs
- [ ] Services can communicate via localhost

---

## Files Created

1. `ai-stack/mcp-servers/nixos-docs/server.py` - FastAPI server
2. `ai-stack/mcp-servers/nixos-docs/Dockerfile` - Container definition
3. `ai-stack/mcp-servers/nixos-docs/requirements.txt` - Python deps
4. `ai-stack/mcp-servers/nixos-docs/start_server.sh` - Startup script
5. `ai-stack/mcp-servers/nixos-docs/README.md` - Documentation

---

**Date:** December 31, 2025
**Status:** Fixes applied, awaiting build completion
**Estimated Completion:** 5-15 minutes
