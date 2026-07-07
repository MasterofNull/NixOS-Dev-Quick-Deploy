# Phase-0 Keystone Plan — the per-task `zero_trust` flag

Status: Ratified v2 — plan-consensus 3/3 APPROVE-WITH-CHANGES (claude + codex + local[Qwen]; antigravity to append)
Owner: AI Stack Maintainers
Last Updated: 2026-07-07

Implements the ratified keystone from `.agent/PRD-slice2-slice3-zero-trust-inference.md` — the
single primitive both Slice 2 (tool-catalog lock) and Slice 3 (remote-routing block) consume.
Build this FIRST; both slices depend on it. Flag-gated, default-off behavior preserved until
consumers are wired + tested.

## Grounding (verified anchors)
- Switchboard has NO `a2a_guard`/`secret_findings` reference today → it must SCAN on ingest.
- Tool leasing/filter: `switchboard.py:_resolve_tool_lease` (~1100) + the tool-catalog builder.
- Routing decision: `switchboard.py:_route_target(request, payload, profile)` (~2367);
  route header `x-ai-route` (line 53).
- Secret scanner: `scripts/ai/lib/a2a_guard.py::scan_secrets` (already used by delegate-to-*).
- Audit trail: `.agent/collaboration/a2a-audit.log` (a2a_guard.audit; viewer `aq-a2a-audit`).

## Design
`zero_trust` is DERIVED per request at the switchboard, not passed by the caller (callers are
untrusted). One boolean, two consumers.

```
request ingest ──► derive_zero_trust(messages)  # scan via a2a_guard; FAIL-CLOSED
                          │  (re-evaluated every request — never latched)
              ┌───────────┴────────────┐
   Consumer A: tool-catalog filter   Consumer B: route_target
   (strip privileged tools)          (block/downgrade remote)
                          └──► audit zero_trust decision → a2a-audit.log
```

## Phases (each independently testable; flag-gated by `SWB_ZERO_TRUST_ENFORCE`, default off→on)
### P0.1 — Derivation (fail-closed, per-request)
- Add `derive_zero_trust(messages) -> (bool, list[kinds])` to switchboard: load `a2a_guard`
  (SourceFileLoader, like the delegate scripts); scan the request's message contents.
  `zero_trust = bool(findings)`. **FAIL-CLOSED**: any exception loading/scanning → `True`.
- Compute it on every request ingest (per-request re-eval); attach to the request context.
- Declare `zero_trust: bool = false` conceptually in the request model (internal field; not
  caller-settable — if a caller sets it true we honor it, false is ignored in favor of the scan).

### P0.2 — Consumer A: tool-catalog lock
- In the tool-catalog builder + `_resolve_tool_lease`: when `zero_trust`, remove the privileged
  set (`reload-model`, `proposals/apply`, shell-like, endpoint-mutation, remote-escalation,
  `lease_tools`-to-privileged) from the allowed/leased names. Immutable for that request.
- Runtime already rejects out-of-catalog calls (defense-in-depth) — no change needed there.

### P0.3 — Consumer B: remote-routing block
- In `_route_target`: when `zero_trust`, never return a remote target. Deterministic fallback
  (PRD V9): if the request is large-context, route to local chunking or return an explicit
  refusal payload — NOT a silent drop.

### P0.4 — Audit + observability
- On every `zero_trust=true` decision, `a2a_guard.audit(direction="zero_trust", ...)` with the
  finding kinds (redacted) → `a2a-audit.log`; surfaced by `aq-a2a-audit` + the ops dashboard.

### P0.5 — Tests (the keystone acceptance)
- `test-switchboard-zero-trust.py`:
  - secret-bearing request → `zero_trust=true`, privileged tools ABSENT from the catalog AND
    remote route blocked (ONE test proves both Slice-2 and Slice-3 enforcement).
  - clean request → `zero_trust=false`, full catalog, normal routing (default path unaffected).
  - FAIL-CLOSED: `a2a_guard` unavailable/raises → `zero_trust=true` (privileged stripped).
  - mid-conversation secret (appears in a later message) → flips true on that request.

## Flag / rollout
- `SWB_ZERO_TRUST_ENFORCE` (env): off = derive + audit only (observe); on = enforce (strip +
  block). Ship off, validate the audit signal on real traffic, then flip on. Mirrors the
  established flag-gated pattern (Phase A/B routing).

## Acceptance criteria
- Keystone test passes (secret → tools stripped + remote blocked; clean → unaffected; fail-closed).
- No latency regression on the clean path (scan is a regex pass over message text — cheap).
- `zero_trust` decisions visible in `aq-a2a-audit --blocks`.

## Non-goals (Phase 0)
- The bwrap sandbox (Slice 2.1+), GBNF (Slice 3.2+) — those CONSUME the flag; not built here.
- The signed network token (PRD V5) — Phase-0 blocks net via the sandbox default; the lease is
  a Slice-2 item.

## Validation + gates
py_compile + `test-switchboard-zero-trust.py`; tier0 + focused-CI; live: POST a secret-bearing
request to the switchboard, confirm audit shows `zero_trust` + tools stripped. Switchboard change
runs from the store snapshot → needs a rebuild to activate in the service (repo run for tests).

## v2 — Ratified consensus changes (BINDING; fold into P0.1–P0.5 before/while coding)
Plan-consensus 3/3 APPROVE-WITH-CHANGES. Aggregate: `.agents/plans/plan-consensus/AGGREGATE.md`.

**Derivation (P0.1):**
- Canonical context `zero_trust: bool` + `zero_trust_kinds: list`.
- **Task-scoped MONOTONIC (raise-only)**: `zt = task_sticky OR scan(current_messages); task_sticky |= zt`.
  Re-derived per request from CURRENT messages; never a cross-session latch; resolves prune-downgrade.
- **Fail-closed via ONE unit-tested helper** collapsing ALL failure cases (exception / malformed /
  missing import / stale-unparseable) → `true`. Ignore caller `false`; honor caller `true` (raise only).
- **Boot-safety (qwen):** a STARTUP `a2a_guard` health-check — log a loud warning but do NOT block
  service boot (a broken guard must degrade + alert, not fail boot).
- **Scan scope:** ALL message content incl. TOOL RESULTS; bound the scanned text (no unbounded traversal).

**Consumer A — tool-catalog (P0.2):** strip the privileged set at THREE sites — base catalog BEFORE
`_normalize_local_tools`, explicit requested `tools`, AND `_resolve_tool_lease`; `lease_tools` must
not reacquire stripped tools. **Enumerate the privileged tool NAMES explicitly (qwen)** in config so
the filter is unambiguous + testable.

**Consumer B — routing (P0.3):** check `zero_trust` before EVERY remote-return in `_route_target`:
`forceProvider=remote`, `ROUTING_MODE=remote_only`, `x-ai-route: remote`, provider hints, remote
model prefixes, intent routing, `DEFAULT_PROVIDER=remote`. Deterministic fallback (PRD V9), not silent drop.

**Flag + audit (P0.4):** `SWB_ZERO_TRUST_ENFORCE` off = derive+audit only, on = enforce; **document
it in the switchboard env schema (qwen)**. Audit redacted payload + failure-reason labeling; LOUD
alert on guard-load failure (fleet-wide capability impact).

**Tests (P0.5) — 14:** keystone(secret→stripped+blocked) · fail-closed · mid-conversation ·
tool-result-secret · sticky-after-prune · observe-vs-enforce · caller-false-no-downgrade ·
caller-true-honored · lease-cant-reacquire · forced-remote(profile/header/model/default-provider)-
downgraded · streaming-follows-block · scanner-exception→audit · clean-large-latency-budget ·
**concurrency-isolation (qwen: clean + secret dispatched in parallel → per-request, no latch under load)**.

## Next
RATIFIED (3/3; antigravity appends via the IDE lane when integrated). → implement P0.1–P0.5 with the
v2 changes → then Slice-2/Slice-3 phases branch off the flag in parallel.
