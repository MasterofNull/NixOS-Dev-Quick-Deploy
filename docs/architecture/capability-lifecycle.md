# Capability Lifecycle Schema

**Status:** Accepted — Phase 58A.6 (2026-05-18)
**Upstream authority:** `docs/architecture/canonical-kernel-declaration.md`, `docs/architecture/gemini-review-gate.md`
**Stability:** Frozen for Phase 58A. New states require a named lifecycle-revision slice.

---

## Purpose

Define the canonical state machine and evidence requirements for harness capabilities — routing profiles, model backends, tool allowances, domain features, and agent capabilities. This schema answers "is this capability ready for production use, and what is the evidence?"

This document complements `config/capability-gap-catalog.json` (binary/package dependencies) and `config/hardware-capability-matrix.json` (hardware-specific promotion pipeline). It focuses on **agent-facing runtime capabilities**: things an orchestrator decides whether to route to, enable, or promote.

---

## State machine

```
             ┌─────────┐
             │ proposed │   ← idea, PRD, or slice plan exists
             └────┬─────┘
                  │ slice plan accepted by orchestrator
                  ▼
           ┌─────────────┐
           │ implemented  │   ← code/config change committed
           └──────┬───────┘
                  │ validation gates pass; review gate PASS
                  ▼
           ┌─────────────┐
           │  validated   │   ← aq-qa check added and passing; no regressions
           └──────┬───────┘
                  │ orchestrator promotes to candidate for broader use
                  ▼
           ┌─────────────┐
           │  candidate   │   ← available but not default; opt-in routing
           └──────┬───────┘
                  │ soak period passed; no P0/P1 failures; orchestrator promotes
                  ▼
           ┌─────────────┐
           │  promoted    │   ← active, recommended, but not yet the system default
           └──────┬───────┘
                  │ orchestrator sets as default (replaces prior default)
                  ▼
           ┌─────────────┐
           │   default    │   ← system default; all new work uses this capability
           └──────┬───────┘
                  │ superseded by newer promoted capability
                  ▼
          ┌──────────────┐
          │  superseded  │   ← no longer default; still available for compatibility
          └──────┬───────┘
                 │ formally retired; removed from routing/profile tables
                 ▼
           ┌──────────┐
           │  retired  │   ← removed; no new work should reference this capability
           └──────────┘

Special state (can enter from any non-retired state):
           ┌──────────┐
           │  blocked  │   ← cannot be promoted due to hardware, policy, or safety constraint
           └──────────┘
```

### Allowed transitions

| From | To | Trigger | Who may trigger |
|---|---|---|---|
| proposed | implemented | slice committed with evidence | implementer |
| implemented | validated | aq-qa gate passes; review gate PASS | reviewer |
| validated | candidate | orchestrator decision | orchestrator |
| candidate | promoted | soak + no P0/P1 failures | orchestrator |
| promoted | default | orchestrator replaces prior default | orchestrator |
| default | superseded | new capability promoted to default | orchestrator |
| superseded | retired | explicit retirement slice | orchestrator |
| any → blocked | — | hardware/policy/safety constraint detected | orchestrator or architect |
| blocked → validated | unblock condition met | orchestrator |

### Prohibited transitions

- `proposed → default` (skipping validation)
- `implemented → promoted` (skipping validation gate)
- `candidate → default` (skipping promoted state)
- Any state → superseded/retired without orchestrator decision
- Self-transition without new evidence

---

## Evidence requirements per state

| State | Required evidence |
|---|---|
| **proposed** | PRD or slice plan in `.agent/` or `.agents/plans/`; problem statement; acceptance criteria |
| **implemented** | Commit SHA; list of changed files; syntax validation passed (py_compile / bash -n / nix-instantiate) |
| **validated** | aq-qa check present and passing for this capability; tier0 gate passing; review gate PASS verdict |
| **candidate** | Orchestrator decision recorded in HANDOFF.md; no aq-qa regressions; rollback procedure documented |
| **promoted** | Soak log (≥1 session with no P0/P1 failures); orchestrator PASS in HANDOFF.md |
| **default** | Routing/profile update committed; old default demoted to superseded in registry |
| **superseded** | Registry updated; compatibility note added; replacement capability is `default` |
| **retired** | Retirement slice committed; references removed or redirected; aq-qa checks removed or updated |
| **blocked** | Block reason documented in registry entry; hardware class or policy constraint named; unblock condition stated |

---

## Registry shape

Capabilities are registered in `config/capability-lifecycle-registry.json`. Each entry:

```json
{
  "id": "capability-id",
  "name": "Human-readable name",
  "domain": "routing | inference | memory | delegation | tool | domain-feature",
  "state": "proposed | implemented | validated | candidate | promoted | default | superseded | retired | blocked",
  "state_since": "YYYY-MM-DD",
  "description": "What this capability does and which kernel object it serves",
  "kernel_object": "intent | route-profile | workflow-session | delegation-review | memory-evidence",
  "evidence": {
    "commit": "SHA or null",
    "aq_qa_check": "check-id or null",
    "review_verdict": "PASS | FAIL | PENDING_REVIEW | null",
    "reviewer": "Claude | Gemini | Codex | human | null",
    "reviewed_on": "YYYY-MM-DD or null",
    "soak_sessions": 0,
    "rollback_procedure": "one-liner or doc reference"
  },
  "blocked_reason": "null or reason string",
  "unblock_condition": "null or condition string",
  "superseded_by": "capability-id or null",
  "replaces": "capability-id or null",
  "related_docs": ["path/to/doc.md"]
}
```

---

## Runtime surfaces

| Surface | Role |
|---|---|
| `config/capability-lifecycle-registry.json` | Registry SSOT — machine-readable state for all capabilities |
| `docs/architecture/capability-lifecycle.md` | State machine definition and evidence requirements |
| `aq-qa 0` checks | Validate that `default` and `promoted` capabilities are healthy |
| `.agent/collaboration/HANDOFF.md` | Records transition decisions (candidate, promoted, blocked) |
| `docs/architecture/gemini-review-gate.md` | Defines the review gate that gates `implemented → validated` |

---

## Operator workflow

### Promoting a capability

```bash
# 1. Confirm aq-qa passes for the capability
aq-qa 0

# 2. Update registry state
# Edit config/capability-lifecycle-registry.json: state, state_since, evidence

# 3. Record decision in HANDOFF.md
# Include: capability-id, new state, evidence summary, rollback procedure

# 4. Commit
git add config/capability-lifecycle-registry.json .agent/collaboration/HANDOFF.md
scripts/governance/tier0-validation-gate.sh --pre-commit
git commit -m "feat(lifecycle): promote <id> to <state>"
```

### Blocking a capability

```bash
# 1. Edit registry: state=blocked, blocked_reason, unblock_condition
# 2. Remove from active routing if applicable
# 3. Commit with evidence of constraint
```

### Retiring a capability

```bash
# 1. Verify a replacement is in default or promoted state
# 2. Remove routing/profile references in a retirement slice
# 3. Update registry: state=retired, state_since
# 4. Update or remove aq-qa checks for the retired capability
```

---

## Consequences for 58A.7

The domain activation template should produce entries in this lifecycle registry. A new domain activation artifact starts as `proposed` and must reach at least `validated` before it is referenced from canonical routing surfaces.
