# AI Stack End-to-End Testing Plan

**Version:** 1.0.0
**Status:** Active
**Objective:** Validate security, functionality, and reliability of the locally hosted AI stack.

---

## Phase 1: Security & Infrastructure Verification

**Goal:** Ensure the foundation is secure and properly configured.

- [ ] **TLS Certificates**: Verify `generate-nginx-certs.sh` creates valid keys/certs with correct permissions (0600/0644).
- [ ] **File Permissions**: Check that sensitive config files are not world-readable.
- [ ] **Environment Variables**: Verify `.env` exists and contains required keys (without logging values).

## Phase 2: Component Logic Tests (Unit/Local)

**Goal:** Verify individual scripts and modules work in isolation.

- [ ] **Garbage Collection**:
  - Simulate old telemetry files.
  - Run `garbage_collection.py`.
  - Verify old files are deleted/compressed and new ones remain.
- [ ] **Ralph Orchestrator**:
  - Instantiate `RalphOrchestrator`.
  - Mock dependencies (Hybrid/AIDB).
  - Verify task execution flow (Context -> Route -> Execute -> Learn).

## Phase 3: Service Integration (Health Checks)

**Goal:** Ensure services are up and communicating.

- [ ] **Service Health**: Query `/health` endpoints for:
  - Ralph Wiggum (Port 8098)
  - Hybrid Coordinator (Port 8092)
  - AIDB (Port 8091)
  - Qdrant (Port 6333)
- [ ] **Dashboard API**: Verify aggregation of metrics at Port 8889.

## Phase 4: End-to-End Workflow

**Goal:** Validate the full "Task -> Learn" loop.

1. **Submission**: Submit a task to Ralph Wiggum.
2. **Routing**: Verify Hybrid Coordinator receives routing request.
3. **Execution**: Verify Ralph attempts iterations.
4. **Learning**: Verify telemetry is written to `hybrid-events.jsonl`.
5. **Optimization**: Verify Garbage Collector can parse/clean the resulting logs.

---

## Execution Strategy

Run the master test suite:

```bash
python3 scripts/test_e2e.py
```

### Failure Handling Protocol

1. **Identify**: Log the specific failure (e.g., "GC script failed to delete file").
2. **Fix**: Apply code patch to the failing component.
3. **Retest**: Re-run the specific test case.
4. **Proceed**: Move to next phase only after pass.
