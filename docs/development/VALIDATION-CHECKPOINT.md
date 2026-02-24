# Validation Checkpoint - Day 2 Infrastructure
## Step-by-Step Validation Before Proceeding

**Date:** January 23, 2026
**Status:** 🛑 CHECKPOINT - Validate Before Continuing

---

## What We've Built So Far

✅ **Completed:**
1. Podman API setup script
2. Secure API client library with allowlists and audit logging
3. Infrastructure test suite
4. Documentation

⏸️ **Paused Before:**
- Updating service code (health-monitor, ralph-wiggum, container-engine)
- Updating Kubernetes manifests
- Final deployment

---

## Why Validate Now?

As you correctly identified, it's critical to validate each step before moving forward. Remote AI agents lose context, making it difficult to go back and fix earlier steps.

**This checkpoint ensures:**
- Podman API is working correctly
- API client library functions properly
- Infrastructure is ready for service updates
- We catch issues early, not after 8 hours of work

---

## Validation Steps (Run These In Order)

### Step 1: Run Podman API Setup Script

```bash
cd ~/Documents/try/NixOS-Dev-Quick-Deploy

# Run the setup script
./scripts/setup-podman-api.sh
```

**What it does:**
- Enables Podman API socket
- Configures networking
- Updates .env file with API configuration
- Tests API connectivity

**Expected output:**
```
[SUCCESS] Podman API socket enabled and running
[SUCCESS] Podman API is responding
[SUCCESS] Updated .env file with Podman API configuration
```

**If it fails:**
- Check if Podman is installed: `podman --version`
- Check if you have systemd: `systemctl --version`
- Review error messages for specific issues

---

### Step 2: Run Infrastructure Validation Tests

```bash
cd ~/Documents/try/NixOS-Dev-Quick-Deploy

# Run the test suite
./scripts/test-podman-api.sh
```

**What it tests:**
1. ✓ Podman installation
2. ✓ Podman API socket enabled
3. ✓ HTTP connectivity to API
4. ✓ List containers operation
5. ✓ Get container details operation
6. ✓ Python API client library
7. ✓ Container network access (host.containers.internal)
8. ✓ .env file configuration

**Expected output:**
```
╔════════════════════════════════════════════════════════════╗
║       Podman API Infrastructure Validation Tests          ║
╚════════════════════════════════════════════════════════════╝

Test 1: Check Podman Installation
[✓] Podman is installed: podman version 4.x.x

Test 2: Check Podman API Socket
[✓] Podman API socket is active (user mode)

Test 3: Test Podman API HTTP Connectivity
[✓] Podman API responding on http://localhost:2375

Test 4: Test API - List Containers
[✓] API can list containers: X containers found

Test 5: Test API - Get Container Details
[✓] API can get container details: container-name

Test 6: Test Python API Client Library
[✓] Python API client library works correctly

Test 7: Test API Access from Container
[✓] Container can reach Podman API via host.containers.internal

Test 8: Check .env File Configuration
[✓] .env file has PODMAN_API_URL: http://host.containers.internal:2375

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TEST SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total Tests: 8
Passed: 8
Failed: 0

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ ALL TESTS PASSED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Infrastructure is ready for service updates!
```

**If tests fail:**
- Review the specific test that failed
- Most common fix: Run `./scripts/setup-podman-api.sh`
- Check logs: `journalctl --user -u podman.socket` (user mode)
- Check logs: `journalctl -u podman-api.service` (system mode)

---

### Step 3: Manual API Test (Optional)

If you want to manually verify the API works:

```bash
# Test 1: Get API version info
curl http://localhost:2375/v4.0.0/libpod/info | jq .

# Test 2: List containers
curl http://localhost:2375/v4.0.0/libpod/containers/json | jq .

# Test 3: Get specific container (replace CONTAINER_NAME)
curl http://localhost:2375/v4.0.0/libpod/containers/CONTAINER_NAME/json | jq .
```

**Expected:** JSON responses with container/system info

---

### Step 4: Verify .env Configuration

```bash
cd ~/Documents/try/NixOS-Dev-Quick-Deploy

# Check that Podman API configuration was added
grep -A 20 "Secure Container Management" ~/.config/nixos-ai-stack/.env
```

**Expected output:**
```bash
# ============================================================================
# Secure Container Management (Day 2 - Week 1)
# ============================================================================
# Podman REST API - replaces privileged containers and socket mounts
PODMAN_API_URL=http://host.containers.internal:2375
PODMAN_API_VERSION=v4.0.0

# Container operation audit logging
CONTAINER_AUDIT_ENABLED=true
CONTAINER_AUDIT_LOG_PATH=/data/telemetry/container-audit.jsonl

# Operation allowlists (comma-separated)
HEALTH_MONITOR_ALLOWED_OPS=list,inspect,restart
RALPH_WIGGUM_ALLOWED_OPS=list,inspect,create,start,stop,logs
CONTAINER_ENGINE_ALLOWED_OPS=list,inspect,logs
```

---

## Validation Checklist

Before proceeding to service updates, verify:

- [ ] Setup script ran successfully
- [ ] All 8 validation tests passed
- [ ] Manual API test works (optional)
- [ ] .env file has Podman API configuration
- [ ] No error messages in logs

---

## If All Tests Pass ✅

**You're ready to proceed!** The infrastructure is solid and we can now:

1. Update health-monitor to use HTTP API
2. Update ralph-wiggum to use HTTP API
3. Update container-engine to use HTTP API
4. Update Kubernetes manifests to remove privileged/socket mounts
5. Test the integrated system

---

## If Tests Fail ❌

**Common Issues & Fixes:**

### Issue 1: Podman API socket not enabled
```bash
# Fix: Run setup script
./scripts/setup-podman-api.sh
```

### Issue 2: Cannot reach API on port 2375
```bash
# Check if socket is running
systemctl --user status podman.socket

# Check if service is running
systemctl --user status podman.service

# Check logs
journalctl --user -u podman.socket -n 50
```

### Issue 3: Python packages missing
```bash
# Install required packages
pip install httpx structlog
```

### Issue 4: Cannot reach host.containers.internal from container
```bash
# This is expected if no containers are running
# Will be fixed when we update Kubernetes manifests with proper networking
```

---

## Next Steps After Validation

Once validation passes, I will:

1. **Update health-monitor** (45 minutes)
   - Replace subprocess calls with API client
   - Test restart functionality

2. **Update ralph-wiggum** (1 hour)
   - Replace docker library with API client
   - Test container orchestration

3. **Update container-engine** (30 minutes)
   - Replace socket-based API with HTTP API
   - Add operation allowlist

4. **Update Kubernetes manifests** (30 minutes)
   - Remove `privileged: true`
   - Remove socket mounts
   - Add `extra_hosts` configuration

5. **Integration testing** (1 hour)
   - Deploy updated stack
   - Verify all services work
   - Run security validation

**Total estimated time:** 3-4 hours

---

## Commands to Run Now

```bash
# 1. Run setup script
cd ~/Documents/try/NixOS-Dev-Quick-Deploy
./scripts/setup-podman-api.sh

# 2. Run validation tests
./scripts/test-podman-api.sh

# 3. If all pass, report back to continue
```

---

## Reporting Results

After running the tests, please share:

1. **Did setup script succeed?** (Yes/No + any errors)
2. **How many tests passed?** (X/8)
3. **Any warnings or errors?** (Copy-paste relevant output)

Based on your results, I'll either:
- **If all pass:** Continue with service updates immediately
- **If some fail:** Help troubleshoot the specific issues first

---

**Status:** 🛑 WAITING FOR VALIDATION
**Next:** Report test results to continue
