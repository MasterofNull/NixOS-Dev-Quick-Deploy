# Deployed-payload audit vs shared-engine contract (resuming Codex's Run-3 audit)

Auditor: Claude Opus 4.8 (integrator, resuming the Codex slice during its session
limit). Scope: read-only audit of the deployed template payload against the owner's
architecture contract — install portable project-scoped contracts/commands/seeds +
gate bundle + capability manifest; CONNECT to the versioned shared factory engine;
DECLARE unavailable/unauthorized capabilities instead of copying host-specific
credentials, ports, hardware, histories, or mutable runtime state.

## What the payload does correctly
- Gate-bundle MANIFEST (1.0.0-ft1, 36 files): project-scoped agent contracts
  (AGENTS/CLAUDE/CODEX/LOCAL/GEMINI/WORKFLOW-CANON/SHARED-RULES as .tmpl), gate
  bundle, checks.d, hooks, pm-tracker, stack-adapters. No host runtime state.
- Commands + workflow seeds present in the agentic-workflow payload
  (.claude/commands/*.tmpl, .agent/workflows/*.tmpl, start-workflow.sh.tmpl).
- Collaboration state (PULSE/RESUME/issues-backlog/archive) is SEEDED FRESH by
  factory_gate_install.COLLABORATION_STATE — NOT copied from host spools. Good:
  mutable runtime state is not replicated (matches the contract).

## Findings (likely Run-3 "incomplete / stale" root causes)

### F1 (HIGH) — no capability manifest in the payload
The contract requires installing a "capability manifest" and "explicitly declaring
unavailable or unauthorized capabilities." No such artifact exists in either payload
(only the gate-bundle file MANIFEST and unrelated vscode manifests). A deployed
project has nothing that declares which shared-engine capabilities (coordinator,
models, tools, skills, telemetry, secrets) are available/authorized vs
unavailable/unauthorized. This is the missing "declare, don't assume" surface.

### F2 (HIGH) — host-specific engine URLs hardcoded, not declared
`templates/agentic-workflow/.claude/settings.json.tmpl` hardcodes the host shared
engine:
  - HYBRID_URL = http://127.0.0.1:8003
  - AIDB_URL   = http://127.0.0.1:8002
  - permitted Bash curl to http://127.0.0.1:800*, hints endpoint 127.0.0.1:8003/hints
These are baked into every deployed project with no {{PLACEHOLDER}} and no declared
fallback. Connecting to the shared engine is INTENDED, but per the contract it must
be DECLARED (capability manifest / resolved endpoint), not copied as a raw same-host
port. Consequence: a project whose engine is unreachable, on another host, or
unauthorized gets a dead hardcoded URL instead of a typed "capability unavailable."
(prime.md.tmpl's discovery curl is less severe — it degrades to "Harness offline".)

### F3 (MED) — agent-contract templates may be stale vs canonical host rules
The AGENTS.md/CLAUDE.md/WORKFLOW-CANON .tmpl payloads should be re-diffed against the
current canonical host rule set (Rules 1-21, DoD/activation, trunk-protection,
cheapest-eligible, etc.). If the templates predate recent canon, deployed projects
onboard with a stale contract. (Not yet line-diffed here — flagged for the owner of
the slice.)

## Recommended slice (for Codex on return, or delegable)
1. Add a capability-manifest artifact to the payload that DECLARES the shared-engine
   endpoints + per-capability available/unavailable/unauthorized state, resolved at
   install/preflight from the target's environment (reuse the FT-5 readiness lane
   model: TRANSPORT_UNAVAILABLE is informational, not a hardcoded live URL).
2. Replace the hardcoded settings.json.tmpl URLs with resolved placeholders bound to
   that manifest; a missing/unauthorized engine yields a typed declared-unavailable
   state, never a dead URL.
3. Re-diff the agent-contract templates against current canon; refresh if stale.

## Lossless-upgrade thread (Codex's other interrupted validation)
The Run-3 lossless-upgrade CORRECTIVE landed (9cbd0a8c) and is covered by
test-factory-gate-retrofit.py 14/14 (upgrade_idempotent_preserves_user_files,
upgrade_succeeds_with_ordinary_receipt, upgrade_refuses_unsafe_receipt) — an
idempotent re-apply refreshes factory tooling while preserving all user files +
collaboration state, and refuses unsafe receipt destinations. The interrupted
symlink harness (ln failed on .agents/improvement/candidates.json — a nonexistent
parent) was validating that host mutable spools are not copied; the audit confirms
they are fresh-seeded, not replicated. Remaining: a live end-to-end lossless upgrade
across an actual bundle-version bump (only 1.0.0-ft1 exists today, so only idempotent
re-apply is currently testable).
