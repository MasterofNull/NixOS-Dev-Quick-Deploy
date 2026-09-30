---
doc_type: prd
id: agentic-os-cohort-parity-20260925
title: Agentic OS Cohort and Configuration Parity
status: active
owner: codex-orchestrator
created: 2026-09-25
runtime_authority: false
---

# Agentic OS Cohort and Configuration Parity

## Objective

## Resume reconciliation — 2026-09-26

Main is now `4fa4e0f3`: Claude's C6a v2 (`e645dadf`, PR #346) and model freshness
(`aa0a38a4`) are merged. Earlier unmerged/rejected statements below describe the original
`1160f18f` subject, not current integration state. Fresh cohort review of C6a v2 remains due.
The old worktree's monotonic-time changes remain a separate unpublished candidate.
Antigravity's PR #349 restored hosted workflow success, but independent audits found an
empty skill-bundle smoke job, artifact-only upstream SARIF, broad secret-scan exclusions,
and weakened dependency locking. Immediate bounded repairs restore the smoke assertion
and SARIF reporting; subsequent slices reconcile exclusions and locks. No prior alert
dismissal is counted as vulnerability remediation without evidence.
Antigravity's agentic-workspace PRD is concurrent work; preserve it and coordinate ownership.

### Original objective

Make flat multi-model collaboration an enforced, observable execution contract rather than a prompt
convention. Claude, Codex, local Qwen, and Antigravity/Gemini must receive one hash-bound baseline,
retain their own identity and evidence, and never be converted from unavailable, truncated, or parked
into acceptance. Provider configuration, context tooling, memory, and model routing must be generated
from declared sources and validated against the running system.

## Trigger evidence

- C6a commit `1160f18f1da74a0ab474b4cb0dc7cf1844cf574e` was implemented by Claude Sonnet;
  Claude Opus review then hit a provider 429 before a cross-model review existed.
- The replacement flat round completed isolated Codex and local dispatches, but the shared round
  remained `0/4`: Codex's valid report stayed in its worktree, while local's completed output was
  truncated before any terminal disposition. Antigravity's inbox item remained unclaimed.
- Independent Codex review and fresh deterministic repros found two HIGH fail-open token-consumption
  defects and one MEDIUM observability defect. C6a therefore remains rejected and unmerged.
- `aq-ctx-freshness --check` reports the knowledge graph 16 days behind HEAD.
- Agent-context tooling and Codex sub-agent checks pass, but the local-agent config test contains a
  stale exact-source assertion, and the collaboration test imports a removed/relocated `agents`
  package without a valid harness entrypoint.
- Claude's live settings contain a redacted plaintext credential embedded in historical permission
  text and a broad permission sediment. The declarative producer seeds MCP configuration but does not
  enforce a bounded permission schema or secret-pattern hygiene.
- `aq-collab-round` archives stale Antigravity inbox entries without the mandatory pre-archive scan.
- Official provider documentation confirms the declared September 2026 model IDs are current; the
  lower compatibility model table and some profile/tool suggestions remain candidates for SSOT drift.

## Frozen invariants

1. The coordinator is flat: no provider becomes the implicit manager of the other lanes.
2. Every binding round records exact subject hash, common baseline, role, lane/model, disposition,
   validation evidence, and availability state. Only a complete independent `PASS` earns review
   credit; missing, truncated, stale, or unavailable output is non-accepting.
3. Isolated worktree reports are imported through a receipt-backed collector and verified against
   the expected owned path. Collection never executes or blindly applies implementation patches.
4. Local output must contain the round's terminal disposition and exact subject before it is landed.
5. Antigravity/Gemini inbox state must distinguish pending, claimed, completed, parked, and unavailable;
   stale files may be archived only through the repository archive-reference SOP.
6. lean-ctx registration, hooks, and freshness are tested for Claude, Codex, Gemini/Antigravity, and
   local/tooling consumers. Documentation alone is not evidence of runtime availability.
7. Rendered agent settings contain no plaintext credential material and no undeclared wildcard
   authority. Secret rotation remains an explicit external-account owner action.
8. Provider model IDs and capability flags are validated from official provider sources or live model
   discovery, then represented once in the canonical registry. Profiles reference that registry.
9. Hot memory stays an index. Session and review state remain in warm memory/collaboration records.
10. Every new enforcement path ships with focused QA and a visible dashboard/Agent Ops status; unknown
    evidence renders unknown or unhealthy, never `ok`.

## Slices

### P0 — C6a containment and revision

- Keep `1160f18f` unmerged.
- Complete or honestly park all cohort lanes; preserve the valid Codex and local receipts.
- Repair persisted-record schema validation, temporal consistency, and dashboard truthfulness in the
  isolated C6a branch; add adversarial tests for all reproduced cases.
- Re-run one common hash-bound cohort review. Activation remains excluded.

### P1 — Collaboration result integrity

- Teach `aq-collab-round` to collect owned review artifacts from isolated Codex/local worktrees or
  their patch receipts, validate exact round path/subject/disposition, and reject incomplete output.
- Stop generating premature abstention artifacts. Represent provider limits as parked/unavailable.
- Route Antigravity archival through `pre-archive-scan.sh`; retain an auditable move receipt.
- Add hermetic tests for isolated-result import, truncation rejection, stale-subject rejection,
  terminal-disposition validation, and archive blocking.

### P2 — Configuration, context, and credential hygiene

- Add a declarative bounded permission contract for Claude rather than preserving accumulated runtime
  permission strings. Detect secret-shaped permission entries without printing their values.
- Verify lean-ctx MCP and hook parity across live Claude, Codex, Gemini/Antigravity, and harness
  configs; refresh the graph through the supported freshness command and expose age/status.
- Replace brittle source-string assertions with behavioral payload/config tests.
- Repair the collaboration test's canonical package/entrypoint or retire it through the archive SOP.

### P3 — Routing/model SSOT and observability

- Reconcile `model-coordinator.json`, switchboard profiles, lane eligibility, role matrix, and runtime
  config against official provider IDs and live availability.
- Remove compatibility tables, hardcoded ports/URLs, and privileged tool suggestions that bypass the
  port/env/tool contracts; reference declared services and policy-bound wrappers.
- Add `aq-qa` integration checks and dashboard/Agent Ops indicators for cohort completeness, adapter
  health, context freshness, config drift, and secret-hygiene status.

### P4 — Historical review coverage

- Process `.agent/collaboration/AGENT-CATCHUP-QUEUE.md` in risk-ranked, hash-bound rounds.
- Reconcile existing review evidence before dispatch. Do not spend a full cohort on already accepted
  hashes; do not grandfather missing evidence.
- Any material finding against a merged hash creates a current-HEAD remediation slice and regression,
  not a rewrite of history.

## Validation

- Focused hermetic tests for each changed contract.
- Live harmless dispatch canaries for Codex, local, Antigravity, and Claude when quota permits.
- `aq-ctx-freshness --check`, agent-context tooling, routing/profile/eligibility checks, memory budget,
  credential-hygiene scan, round collector tests, and service parity smoke.
- Relevant `aq-qa --machine` phases and `scripts/governance/tier0-validation-gate.sh --pre-commit`.
- Independent hash-bound review by models other than the implementer before integration.

## Exclusions and authority

No C6 activation, deployment, service restart, destructive git action, credential rotation, external
account mutation, or silent model/provider fallback is authorized by this PRD. Live settings cleanup
outside the repository requires an explicit scoped approval and a recoverable backup. Runtime adoption
of revised routing remains a separate deployment/activation act after review.
