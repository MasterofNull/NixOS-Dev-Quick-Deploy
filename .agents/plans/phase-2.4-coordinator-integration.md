# Slice 2.4: Coordinator Integration - Implementation Plan

**Status:** Ready to Start
**Owner:** qwen (implementation) + codex (review)
**Effort:** 2-3 days
**Priority:** P0 (BLOCKS 2.5, 2.6, 2.7)
**Created:** 2026-04-14

---

## Objective

Integrate the Phase 2 workflow engine (parser, validator, executor) with the existing hybrid coordinator, enabling YAML workflow execution through HTTP API and local agent orchestration.

---

## Current State

### Completed Components ✅
- `yaml_workflow_handlers.py` - HTTP handlers implemented
- `workflow_executor.py` - Local execution capability
- `llm_client.py` - Switchboard integration
- Parser, validator, graph modules - All tested

### Missing Integration ❌
- HTTP handlers not registered in coordinator main app
- No end-to-end integration tests
- `trio` dependency missing (causing test failures)
- Memory system integration not validated
- Agent routing integration not tested

---

## Implementation Tasks

### Task 1: Find Coordinator Main App Entry Point
**Effort:** 30 minutes

Find where the coordinator HTTP server is initialized and routes are registered.

**Files to check:**
- `ai-stack/mcp-servers/hybrid-coordinator/server.py`
- `ai-stack/mcp-servers/hybrid-coordinator/main.py`
- `ai-stack/mcp-servers/hybrid-coordinator/__init__.py`
- `ai-stack/mcp-servers/hybrid-coordinator/app.py`

**Success criteria:**
- Located main aiohttp Application setup
- Found route registration pattern
- Identified startup/initialization sequence

---

### Task 2: Integrate YAML Workflow Handlers
**Effort:** 2-3 hours

Register the YAML workflow routes in the coordinator's main application.

**Steps:**
1. Import `yaml_workflow_handlers` in main app
2. Call `yaml_workflow_handlers.init()` during startup
3. Call `yaml_workflow_handlers.register_routes(app)` to register routes
4. Add error handling for import failures
5. Add logging for successful initialization

**Example integration:**
```python
# In coordinator main app
try:
    from . import yaml_workflow_handlers
    YAML_WORKFLOWS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"YAML workflows not available: {e}")
    YAML_WORKFLOWS_AVAILABLE = False

# In startup function
if YAML_WORKFLOWS_AVAILABLE:
    yaml_workflow_handlers.init(workflows_dir="ai-stack/workflows/examples")
    yaml_workflow_handlers.register_routes(app)
```

**Validation:**
```bash
# Start coordinator
systemctl restart ai-hybrid-coordinator

# Check routes registered
curl http://127.0.0.1:8003/yaml-workflow/executions

# Should return JSON (empty array or error, not 404)
```

**Success criteria:**
- Routes registered successfully
- Coordinator starts without errors
- HTTP endpoints respond (even if empty)

---

### Task 3: Fix Dependencies and Test Infrastructure
**Effort:** 1-2 hours

Fix the `trio` dependency issue causing test failures.

**Steps:**
1. Add `trio` to Python dependencies
   - Check if it's in `requirements.txt`, `pyproject.toml`, or Nix expression
   - Add if missing: `trio>=0.22.0`
2. Add `pytest-trio` for async test support
3. Verify test configuration in `pytest.ini`
4. Re-run coordinator tests

**Files to update:**
- `requirements.txt` or `pyproject.toml`
- Possibly `nix/modules/ai-stack/python-packages.nix`

**Validation:**
```bash
python3 -m pytest ai-stack/workflows/tests/test_coordinator.py -v
```

**Success criteria:**
- No import errors for `trio`
- Coordinator tests run (may still fail, but should execute)

---

### Task 4: Add End-to-End Integration Test
**Effort:** 3-4 hours

Create a test that validates the full workflow execution path through the HTTP API.

**Test file:** `ai-stack/workflows/tests/test_e2e_integration.py`

**Test scenarios:**
1. Execute simple-sequential workflow via HTTP API
2. Check execution status
3. Verify workflow completes successfully
4. Validate results in session state
5. Test error handling (invalid workflow)
6. Test cancellation

**Example test:**
```python
import httpx
import pytest


@pytest.mark.asyncio
async def test_workflow_execution_via_http():
    """Test workflow execution through coordinator HTTP API."""
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8003") as client:
        # Execute workflow
        response = await client.post(
            "/yaml-workflow/execute",
            json={
                "workflow_file": "ai-stack/workflows/examples/simple-sequential.yaml",
                "inputs": {"task": "test task"},
                "async_mode": False,
            }
        )
        assert response.status_code == 200
        result = response.json()
        assert "execution_id" in result

        # Check status
        execution_id = result["execution_id"]
        response = await client.get(f"/yaml-workflow/{execution_id}/status")
        assert response.status_code == 200
        status = response.json()
        assert status["status"] in ["completed", "in_progress"]
```

**Success criteria:**
- Test passes with coordinator running
- Workflow executes end-to-end
- Status tracking works
- Results are retrievable

---

### Task 5: Validate Memory System Integration
**Effort:** 2-3 hours

Ensure workflow nodes can load memory context (L0-L3) as specified in YAML.

**Steps:**
1. Review memory integration in `workflow_executor.py`
2. Add memory loading in phase execution
3. Test with workflow that uses memory layers
4. Validate memory context is passed to LLM

**Test workflow:** `test-memory-integration.yaml`
```yaml
name: memory-integration-test
version: 1.0
nodes:
  - id: test-node
    agent: local
    prompt: "Test memory integration"
    memory:
      layers: [L0, L1]
      topics: [architecture]
    outputs:
      - result
```

**Validation:**
- Create test workflow with memory config
- Execute and verify memory is loaded
- Check logs for memory loading activity

**Success criteria:**
- Memory layers load successfully
- Context passed to executor
- No errors in memory integration

---

### Task 6: Validate Agent Routing Integration
**Effort:** 2-3 hours

Ensure workflows can route to different agents (local, qwen, codex, claude).

**Steps:**
1. Review agent routing in `yaml_workflow_handlers.py`
2. Test workflow with different agent assignments
3. Validate local agent routing works
4. Document remote agent routing (blocked by rate limits)

**Test workflow:** `test-agent-routing.yaml`
```yaml
name: agent-routing-test
version: 1.0
agents:
  implementer: local
nodes:
  - id: test-node
    agent: ${agents.implementer}
    prompt: "Test agent routing"
    outputs:
      - result
```

**Validation:**
- Execute workflow with `agent: local`
- Verify execution routes to local LLM
- Document expected behavior for other agents

**Success criteria:**
- Local agent routing works
- Agent assignment from YAML respected
- Error handling for unavailable agents

---

### Task 7: Create Integration Documentation
**Effort:** 1-2 hours

Document the integration for future reference.

**File:** `docs/workflows/INTEGRATION.md`

**Content:**
- Architecture overview (how components connect)
- API endpoints and usage
- Memory integration details
- Agent routing configuration
- Troubleshooting common issues
- Example HTTP requests

**Success criteria:**
- Documentation complete and clear
- Examples tested and working
- Troubleshooting guide useful

---

## Validation Checklist

Before marking Slice 2.4 complete:

- [ ] HTTP routes registered in coordinator main app
- [ ] Coordinator starts without errors
- [ ] `/yaml-workflow/execute` endpoint responds
- [ ] `/yaml-workflow/{id}/status` endpoint works
- [ ] End-to-end integration test passes
- [ ] Dependencies fixed (`trio` installed)
- [ ] Coordinator tests execute (may have some failures)
- [ ] Memory integration validated
- [ ] Agent routing validated (local only)
- [ ] Integration documentation complete
- [ ] All changes committed to git

---

## Test Execution Plan

### Unit Tests
```bash
# Parser and validator
python3 -m pytest ai-stack/workflows/tests/test_parser.py -v
python3 -m pytest ai-stack/workflows/tests/test_validator.py -v
python3 -m pytest ai-stack/workflows/tests/test_graph.py -v
```

### Integration Tests
```bash
# Workflow integration
python3 -m pytest ai-stack/workflows/tests/test_integration.py -v

# Coordinator integration
python3 -m pytest ai-stack/workflows/tests/test_coordinator.py -v

# End-to-end
python3 -m pytest ai-stack/workflows/tests/test_e2e_integration.py -v
```

### Manual Testing
```bash
# Start coordinator
systemctl restart ai-hybrid-coordinator

# Execute workflow via curl
curl -X POST http://127.0.0.1:8003/yaml-workflow/execute \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_file": "ai-stack/workflows/examples/simple-sequential.yaml",
    "inputs": {"task": "test"},
    "async_mode": false
  }'

# Check status
curl http://127.0.0.1:8003/yaml-workflow/executions

# Get stats
curl http://127.0.0.1:8003/yaml-workflow/stats
```

---

## Success Criteria

**Technical:**
- All HTTP endpoints operational
- End-to-end workflow execution works
- Integration tests passing (90%+)
- Local agent routing functional
- Memory integration validated

**Documentation:**
- Integration guide complete
- API reference documented
- Examples tested

**Git:**
- Changes committed with conventional format
- Tests passing in CI (if applicable)

---

## Estimated Timeline

**Day 1:**
- Tasks 1-2: Find and integrate handlers (3-4 hours)
- Task 3: Fix dependencies (1-2 hours)
- Start Task 4: Integration tests (2 hours)

**Day 2:**
- Complete Task 4: Integration tests (2 hours)
- Task 5: Memory integration (2-3 hours)
- Task 6: Agent routing (2-3 hours)

**Day 3:**
- Task 7: Documentation (1-2 hours)
- Validation and testing (2-3 hours)
- Git commit and review (1 hour)

**Total:** 2-3 days

---

## Delegation Strategy

**Primary implementer:** qwen
- Tasks 1-6: Implementation work
- Integration testing
- Bug fixes

**Reviewer:** codex
- Code review
- Integration validation
- Acceptance testing

**Orchestrator (claude):**
- Monitor progress
- Unblock issues
- Final acceptance

---

## Risk Mitigation

**Risk:** Coordinator app structure unclear
- **Mitigation:** Start with Task 1 (discovery), document findings

**Risk:** Integration breaks existing functionality
- **Mitigation:** Test existing endpoints after integration, add regression tests

**Risk:** Memory/agent routing complex
- **Mitigation:** Start with simple tests, iterate, document limitations

**Risk:** Remote agent routing unavailable
- **Mitigation:** Accept local-only for now, document future work

---

## Next Steps After Completion

Once Slice 2.4 is complete:
1. **Parallel start:** Slices 2.5 (Templates) and 2.6 (CLI)
2. **Update:** Phase 2 plan with completion evidence
3. **Commit:** All changes with validation evidence

---

**Ready to delegate to qwen for implementation.**
