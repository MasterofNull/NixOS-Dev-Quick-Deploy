# Domain Activation Template

**Status:** Accepted — Phase 58A.7 (2026-05-18)
**Upstream authority:** `docs/architecture/canonical-kernel-declaration.md`, `docs/architecture/capability-lifecycle.md`
**Stability:** Frozen for Phase 58A. Changes to the template schema require a named template-revision slice.

---

## Purpose

Future capability-domain expansion should instantiate from a standard pattern rather than inventing bespoke orchestration each time. This template defines the minimum artifacts, wiring, and validation a new domain must provide before it is promoted into active use.

A "domain" is a coherent set of agent capabilities grouped under a shared purpose (e.g., code-generation, memory-crystallization, safety-analysis, trading-analysis). Each domain:
- maps to one or more lifecycle registry entries,
- has a declared routing profile or profile preference,
- has a defined AIDB namespace for its knowledge,
- has a validation hook that confirms the domain is healthy,
- has a rollback procedure.

---

## Template artifacts

To activate a new domain, create the following:

### 1. PRD (required)

Location: `.agent/PROJECT-<DOMAIN-NAME>-PRD.md`

Must contain:
- Domain name and tag (see §Domain tag schema)
- Problem statement and goal
- Kernel objects the domain touches
- Routing profile(s) the domain uses or adds
- AIDB namespace(s) the domain writes to
- Tool preferences (which tool classes agents in this domain may use)
- Acceptance criteria (testable, not aspirational)
- Security and safety considerations
- Rollback procedure

### 2. Lifecycle registry entry (required)

Location: `config/capability-lifecycle-registry.json`

Initial state: `proposed`. Must reach `validated` before routing to the domain is enabled. Must reach `promoted` before the domain is recommended to callers. Schema: see `docs/architecture/capability-lifecycle.md`.

Minimum fields for a new domain entry:
```json
{
  "id": "<domain-tag>",
  "name": "<Human-readable domain name>",
  "domain": "domain-feature",
  "state": "proposed",
  "state_since": "YYYY-MM-DD",
  "description": "What this domain does and which kernel object(s) it serves",
  "kernel_object": "<intent | route-profile | workflow-session | delegation-review | memory-evidence>",
  "evidence": {
    "commit": null,
    "aq_qa_check": null,
    "review_verdict": null,
    "reviewer": null,
    "reviewed_on": null,
    "soak_sessions": 0,
    "rollback_procedure": "<one-liner>"
  },
  "blocked_reason": null,
  "unblock_condition": null,
  "superseded_by": null,
  "replaces": null,
  "related_docs": ["<path/to/domain/PRD.md>"]
}
```

### 3. Instruction payload (required)

Location: `.agent/<DOMAIN-NAME>-INSTRUCTIONS.md` or appended to relevant agent instruction surface.

Must contain:
- Domain tag (for agent identification in session context)
- Eligible task classes within this domain (reference `docs/architecture/qwen-task-eligibility.md` Tier table if Qwen is involved)
- Tool preferences (preferred tools; forbidden tools; fallback order)
- AIDB namespace binding (which namespace agents in this domain read/write)
- Review requirements (which work categories require a gate per `docs/architecture/gemini-review-gate.md`)

### 4. Validation hook (required)

Location: `config/validation-check-registry.json` — add a new check entry.

Minimum check definition:
```json
{
  "id": "<domain-tag>-health",
  "description": "Health check for <domain-name> domain capability",
  "trigger_paths": ["<path/to/domain/code/or/config>"],
  "command": "<command that exits 0 if domain is healthy>",
  "tier": 1,
  "timeout_seconds": 30,
  "enabled": true,
  "require_tool": null
}
```

The check must be runnable by `aq-qa 0` after the domain reaches `validated` state.

### 5. AIDB namespace (if domain writes knowledge)

If the domain writes to AIDB:
- Declare the namespace name in the PRD.
- Add an indexing step to `scripts/automation/aidb-reindex.sh` or equivalent.
- Confirm namespace exists before marking the domain as `validated`.

### 6. Routing preference (if domain adds or prefers a profile)

If the domain prefers a specific routing profile:
- Record it in the PRD.
- If the profile is new, it must go through the capability lifecycle (`proposed → validated`) before the domain can reach `promoted`.
- If the profile already exists, reference it by canonical name from `docs/architecture/routing-profile-inventory.md`.

---

## Domain tag schema

Each domain has a short lowercase kebab-case tag used in registry IDs, AIDB namespaces, instruction headers, and aq-qa check IDs.

Format: `<purpose>[-<qualifier>]`

Examples:
- `code-generation`
- `memory-crystallization`
- `safety-analysis`
- `trading-analysis`
- `domain-activation` (this template's own tag)

Rules:
- Unique across the registry.
- No spaces or underscores.
- ≤ 32 characters.
- Must match the `id` field in the lifecycle registry entry.

---

## Activation sequence

```
1. Author PRD → .agent/PROJECT-<DOMAIN>-PRD.md
2. Add lifecycle registry entry (state: proposed)
3. Implement domain (code/config/instructions) → state: implemented
4. Run validation hook + review gate → state: validated
5. Orchestrator decision: candidate (opt-in routing available)
6. Soak period (≥1 session, no P0/P1) → state: promoted
7. Orchestrator may set as default if it replaces an existing domain
```

At no point may a domain skip from `proposed` to `promoted` without validated evidence.

---

## Rollback

Each domain must declare a rollback procedure in its lifecycle registry entry. Typical rollback:
1. Set registry state to `blocked` or `retired`.
2. Revert routing preference (remove from route-aliases.json or intent-routing-map.json).
3. Remove or disable the aq-qa validation check.
4. Archive AIDB namespace content if needed (do not delete — content is versioned).

---

## Example: hypothetical `safety-analysis` domain

```
Tag: safety-analysis
PRD: .agent/PROJECT-SAFETY-ANALYSIS-PRD.md
Registry ID: safety-analysis
Routing preference: remote-reasoning (architecture/policy queries)
AIDB namespace: safety-patterns
Instruction payload: .agent/SAFETY-ANALYSIS-INSTRUCTIONS.md
Validation hook: safety-analysis-health → checks POST /api/logic/search with safety-patterns namespace
```

---

## Consequences for later phases

Any future capability-expansion phase that adds a new domain must begin by filling in this template. The orchestrator acceptance gate for a new domain is: PRD exists, registry entry exists at `proposed` or better, instruction payload exists, validation hook defined. Without these four artifacts, the domain is not ready to receive work.
