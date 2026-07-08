# F3 (CapabilityLease + OTel + Signed A2A Envelope) — Aggregate (4/4 landed — RATIFIED)

Last Updated: 2026-07-07

## Contributors
- **claude** ✅ (full design) · **codex/gpt-5.5** ✅ (deepest — 200+L, epoch revocation + bwrap agreement)
  · **local[Qwen]** ✅ (real CapabilityLease schema, self-truncated at ~995 tok, 0 tool calls — salvaged;
  never skipped) · **antigravity[Gemini]** ✅ (83L, via IDE OAuth inbox).

## Unanimous verdict — the SAME four-part design, independently
All four teams converged on ONE architecture (no dissent):
1. **CapabilityLease** as the single authority primitive subsuming all 5 ad-hoc auto-selection layers.
2. **OTel spans** (turn/tool/lease/validation) as the operational truth; audit/PULSE/matrix become views.
3. **Signed A2A task envelope + liveness heartbeat** for the antigravity node (local signing, NO keys).
4. **Automatic git-worktree rollback** before any write-capable execution.

## 1. CapabilityLease — the one abstraction (claude + codex + antigravity + local all agree)
Every capability (tool, skill, plugin, MCP, RAG source, DB, cache, model, remote lane) is a signed,
short-lived, attenuable lease. Consensus fields: `id/lease_id/version/source/owner/issued_to/issued_at/
expires_at/permissions{actions,resources,constraints}/input_schema/output_schema/trust_tier/
zero_trust_behavior/cost_class/observability_hooks/revocation_rule/signature`.
- **Deny-by-default admission**: nothing usable until capability-intake admits it + policy issues a lease.
- **The 5 layers become lease EVALUATORS** (attenuate or deny), not parallel policy hints. `a2a_guard`,
  action-policy, dispatch-budget, capability-intake, auto-selection/routing each only shrink a lease.
- **Phase-0 `zero_trust` collapses into ONE lease behavior** (`zero_trust_behavior: strip` — write/
  network/secret_read/delegate/unsandboxed-exec stripped irreversibly for that request). No separate flag.
- **Monotonic least-privilege**: within a request permissions only shrink; elevation = new parent policy
  decision + new lease_id + span event + stricter revocation epoch.
- **codex's decisive additions**: `parent_lease_id` (attenuation chain), **epoch-based revocation**
  (`revocation_epoch` checked by every executor — a stale cached lease can't revive after policy/session
  epoch increments), `allowed_output_paths` enforced even when the tool SUCCEEDS, and **bwrap ⇄ lease
  agreement** (the lease defines the allowed set; Slice-2 bwrap is the kernel-level enforcement of that
  same set).
- Property tests (all three name them): stripped-can't-reacquire · caller-`zero_trust=false`-can't-
  downgrade-inherited-stricter · stale-lease-can't-revive-after-epoch · output-outside-allowed-paths-
  rejected-even-on-success.

## 2. OTel span model (claude + codex + antigravity)
W3C trace context across coordinator/switchboard/local-executor/antigravity. Spans: `agent.turn` (root),
`agent.selection`, `capability.lease.issue`, `tool.call`, `model.call`, `a2a.task`, `validation.gate`,
`workspace.snapshot`/`workspace.rollback`. Stable `harness.*` attributes (round_id, task_id, agent.role/
name, lane, model+version, tokens_in/out, latency_ms, lease.bundle_ids, lease.zero_trust, lease.trust_tier,
capability.id/source, tool.name, output.path, validation.result, rollback.snapshot_id).
- **Emit**: switchboard (turn/selection/model.call), coordinator (lease issue/deny/attenuate/revoke),
  agent_executor (tool.call/validation.gate/workspace.snapshot), antigravity path (a2a.task + heartbeat +
  envelope/output verification), capability-intake (admission/rejection).
- **Read**: the live matrix "Selections" panel reads the span stream (the PAUSED observability, now
  OTel-native → also Jaeger/Grafana). Selections (bundle/hot-swap/injectHints/zero_trust) become span
  ATTRIBUTES — one schema, inspectable everywhere. **PULSE/audit become projections of traces, not
  independent partial ledgers** (codex). Local OTLP collector OR a JSONL span log first (no external dep),
  but OTLP-compatible from day one.

## 3. Signed A2A envelope + heartbeat (all — the antigravity node hardening)
The watched folder becomes **transport only**; the **signed envelope is the authority**. Fields:
`{schema_version, round_id, task_id, idempotency_key, issuer, assignee, created_at, deadline,
expected_output_path, allowed_write_paths, lease_bundle, task, heartbeat{path,interval,stale_after},
signature{alg:ed25519, key_id, value}}`.
- **NO API keys, signing ≠ auth** (unanimous): the harness signs LOCALLY with an Ed25519 key stored
  outside tracked files (age/sops or host-local key path). **The IDE OAuth identity is NOT a signing
  root** — it authenticates the IDE to its own service; harness task authority = local signature + admitted
  lease bundle.
- **Heartbeat**: IDE agent touches a liveness file every ~20-30s; round marks antigravity `pending-late`
  vs `dead` on stale (feeds F1 quorum). antigravity's own spec: miss 60s → `pending-late`/`failed`.
- **Output contract**: verify signature + deadline + idempotency + lease bundle + allowed write path +
  output schema BEFORE writing; coordinator rejects unsigned/stale/path-escaping/schema-invalid outputs.
  → This directly hardens the exact inbox lane that carried these three contributions (a bare watched
  folder is fragile; this round proved it — the IDE went idle ~6h before processing f1/f2/f3).

## 4. Automatic worktree-scoped rollback (all — enforced in the executor, not agent habit)
Before the first write of any write-capable lease: `workspace.snapshot` via **isolated git worktree**
(preferred) or a scoped `git stash -u` fallback. Agent writes ONLY in the worktree under Slice-2 bwrap
(only allowed paths mounted writable) → validation under the same trace (schema/path/py_compile/bash -n/
tier0) → on GREEN merge + retain until orchestrator review; on RED/timeout/heartbeat-miss/revocation drop
the worktree (instant revert) + emit `workspace.rollback`. Safety: rollback never crosses the allowed
write-path set; if stash fallback sees unrelated dirty files outside lease scope, **deny the write lease**
rather than snapshot the whole workspace; validation failure revokes the write lease for that task_id
(retry needs a fresh lease + snapshot). Ties Slice-2 sandbox + F3 rollback + the gates into ONE safe path.

## local[Qwen] note
Dispatch `e1k8vc` (595s, 0 tool calls) emitted a genuine `CapabilityLease` JSON schema (id/version/source/
owner/permissions/SPIFFE-owner…) as TEXT and self-truncated at ~995 tokens mid-`"network`. Its design
CONCURS with the consensus (CapabilityLease + deny-by-default + zero_trust as a lease mode). Salvaged to
local.md. This is itself F2/F3 evidence: a fast-lane + GBNF (F2) would make local's structured emission
reliable, and F1's typed sidecar + collect-time extraction captures even a truncated local answer.

## Acceptance criteria (merged, becomes the F3 implementation bar)
- ONE schema represents tools/skills/plugins/MCP/RAG/DB/cache/models/remote lanes.
- A zero_trust request cannot perform irreversible ops even if downstream code asks.
- The live matrix answers: what was selected, why, under which lease, what was denied, what ran, what
  validation proved — all from spans.
- Antigravity output accepted only when signed + fresh + schema-valid + written to the expected path.
- Every write-capable execution has a recoverable snapshot before the first mutation.

## Reading list (named by the teams)
object-capability model · macaroons · SPIFFE/SPIRE · TUF/Sigstore · Zanzibar · OpenTelemetry semantic
conventions · W3C Trace Context · git worktree isolation · bubblewrap (bwrap).

## Status
**4/4 landed — RATIFIED.** Unanimous four-part design (CapabilityLease + OTel spans + signed A2A envelope
+ worktree rollback). codex is the implementation baseline (epoch revocation, allowed_output_paths, bwrap⇄
lease agreement, PULSE-as-trace-projection); claude/antigravity/local concur and add the OTel read-panel,
VRAM/heartbeat specifics, and schema confirmation. The Phase-0 Slice-2/Slice-3 zero-trust work folds in
here: **zero_trust = one CapabilityLease behavior**. F3 closes the foundation-critique roadmap (F1+F2+F3
all now 4/4 RATIFIED).
