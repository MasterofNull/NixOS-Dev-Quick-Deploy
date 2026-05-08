# Phase 28 — Guarded Execution & Runtime Safety Gating

## Objective

Close the P0 parity gap: "Guarded tool execution — runtime enforcement layer" and
"Planner/executor separation with explicit safety modes."

Turn the UAG lifecycle FSM's `ABORTED` state into a live, enforced safety boundary.
Every delegation through the DELEGATE phase must pass a blast-radius gate before
execution proceeds. High-blast-radius operations either require approval (PRSI queue)
or are blocked outright, depending on session safety mode.

## Context References

- `ai-stack/mcp-servers/hybrid-coordinator/lifecycle_fsm.py` — UAG FSM (DELEGATE → VALIDATE transition)
- `ai-stack/mcp-servers/hybrid-coordinator/intake_gateway.py` — UAG HTTP handlers
- `ai-stack/mcp-servers/hybrid-coordinator/evidence_safety_handlers.py` — existing safety hooks
- `ai-stack/mcp-servers/hybrid-coordinator/http_server.py` — wiring point
- `config/runtime-prsi-policy.json` — approval/rejection policy reference
- `docs/AGENT-PARITY-MATRIX.md` — gap classification context

## Scope Lock

In scope:
- Blast-radius classifier for tool calls and action strings
- Safety mode per UAG lifecycle session (`strict | review | open`)
- DELEGATE phase gate that blocks or queues high-blast-radius actions
- New HTTP endpoints: `POST /control/safety/gate` (configure session mode) + `GET /control/safety/gate/{session_id}`
- aq-qa check `0.9.1` for safety gate health
- Tests and documentation

Out of scope:
- Replacing PRSI queue implementation
- Sandboxing subprocess execution (separate from gate logic)
- Changing existing `/control/safety/check` or hook behavior
- Remote trust rotation (separate P0 gap)

Constraints:
- Never hardcode ports/URLs — read from env vars
- No bare pip install — pure Python stdlib + existing deps
- Safety gate must be additive: existing sessions without a mode default to `open` (no regression)
- gate logic must be stateless where possible (Redis for session state)

## Sub-phases

### 28.1 — Blast Radius Classifier + Session Safety Mode

**New file**: `ai-stack/mcp-servers/hybrid-coordinator/blast_radius_classifier.py`

```python
# Classify a string action/tool call into: "low" | "medium" | "high" | "critical"
# Pattern-based, no ML:
#   critical: rm -rf, DROP TABLE, force-push, --force, nixos-rebuild switch (production)
#   high:     git push, git reset, DELETE /api/*, nixos-rebuild, systemctl stop/restart
#   medium:   git commit, file writes outside /tmp, POST to internal APIs
#   low:      read-only tool calls, GET requests, aq-qa, syntax checks
def classify(action: str) -> str: ...
def batch_classify(actions: list[str]) -> dict[str, str]: ...
```

**Extend `LifecycleSession`** in `lifecycle_fsm.py`:
- Add `safety_mode: str = "open"` field (default `"open"` for backward compat)
- Add `safety_gate_log: List[Dict[str, Any]]` — record of gate evaluations per session

**Deliverables**:
- `blast_radius_classifier.py` — pattern list + classify() + batch_classify()
- `lifecycle_fsm.py` updated — `safety_mode` field + `safety_gate_log`
- `scripts/testing/test-blast-radius-classifier.py` — unit tests (20+ patterns)

**Validation**:
- `python3 -m py_compile blast_radius_classifier.py lifecycle_fsm.py`
- `python3 scripts/testing/test-blast-radius-classifier.py`

### 28.2 — DELEGATE Phase Gate

**New file**: `ai-stack/mcp-servers/hybrid-coordinator/safety_gate.py`

Gate logic:
1. On DELEGATE phase entry, extract action strings from session context
2. Run `blast_radius_classifier.classify()` on each
3. Apply gate policy based on session `safety_mode`:
   - `open`: allow all (no-op gate)
   - `review`: `high` → queue to PRSI; `critical` → block (set ABORTED)
   - `strict`: `medium+` → block (set ABORTED with reason)
4. Return `GateResult(allowed: bool, blocked_actions: list, queued_actions: list, reason: str)`

**HTTP endpoints** (add to `evidence_safety_handlers.py` register_routes):
- `POST /control/safety/gate` — `{session_id, safety_mode: "open"|"review"|"strict"}` → set mode in Redis
- `GET /control/safety/gate/{session_id}` → `{safety_mode, gate_log}`

**Wire into UAG** (`intake_gateway.py`):
- Before advancing DELEGATE → VALIDATE: call `safety_gate.evaluate(session)` 
- If `!result.allowed`: advance session to ABORTED with gate reason
- Gate log appended to `session.safety_gate_log`

**Deliverables**:
- `safety_gate.py` — `evaluate()` + `GateResult` dataclass
- `evidence_safety_handlers.py` — 2 new routes + `register_routes` additions
- `intake_gateway.py` — gate call in DELEGATE → VALIDATE transition
- `http_server.py` — no changes needed (routes via evidence_safety_handlers)
- `scripts/testing/test-safety-gate.py` — gate policy tests per safety_mode

**Validation**:
- `python3 -m py_compile safety_gate.py evidence_safety_handlers.py intake_gateway.py`
- `python3 scripts/testing/test-safety-gate.py`

### 28.3 — aq-qa Check + Documentation + Closeout

**aq-qa check `0.9.1`**:
```bash
# Check: safety gate endpoint responds and returns valid schema
curl -sf $HYBRID_COORDINATOR_URL/control/safety/gate \
  -X POST -H "Content-Type: application/json" \
  -d '{"session_id":"healthcheck","safety_mode":"open"}'
# Expects 200 + {"ok": true}
```
Add to `scripts/ai/aq-qa` in the `_phase_0_checks` section.

**Documentation**:
- Add `docs/operations/SAFETY-GATE-GUIDE.md` — blast radius classification table, safety mode guide, operator configuration, gate log reading

**Phase 28 closeout**:
- Mark Phase 28 complete in `docs/SYSTEM-IMPROVEMENT-PLAN-2026-03.md`
- Update `docs/AGENT-PARITY-MATRIX.md` — mark "Guarded tool execution" and "Planner/executor separation" as `Near parity`
- `scripts/governance/tier0-validation-gate.sh --pre-commit` — must be 8/8
- Commit: `feat(phase-28): guarded execution and runtime safety gating complete`

## Validation

Per sub-phase:
- `python3 -m py_compile` all new/changed modules
- `bash -n` any new shell scripts
- `python3 <test-script>` for each test file
- `aq-qa 0` after each sub-phase: ≥ 40 passed / 0 failed

Final gate:
- `scripts/governance/tier0-validation-gate.sh --pre-commit` — 8/8

## Evidence

Files to produce:
- `ai-stack/mcp-servers/hybrid-coordinator/blast_radius_classifier.py`
- `ai-stack/mcp-servers/hybrid-coordinator/safety_gate.py`
- `ai-stack/mcp-servers/hybrid-coordinator/lifecycle_fsm.py` (extended)
- `ai-stack/mcp-servers/hybrid-coordinator/evidence_safety_handlers.py` (2 routes added)
- `ai-stack/mcp-servers/hybrid-coordinator/intake_gateway.py` (gate wired)
- `scripts/testing/test-blast-radius-classifier.py`
- `scripts/testing/test-safety-gate.py`
- `scripts/ai/aq-qa` (check 0.9.1 added)
- `docs/operations/SAFETY-GATE-GUIDE.md`

## Rollback

- Revert `lifecycle_fsm.py` — `safety_mode` field is additive, sessions without it default to `open`
- Remove new routes from `evidence_safety_handlers.py` register_routes
- Remove gate call from `intake_gateway.py` — sessions proceed unconditionally
- No database migration needed (Redis TTL handles session state cleanup automatically)
