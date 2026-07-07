# Phase-0 Keystone Plan — the per-task `zero_trust` flag

Status: Draft (plan-consensus pending)
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

## Next
Plan-consensus sign-off (per-agent files, as in PRD-consensus) → implement P0.1–P0.5 → then
Slice-2/Slice-3 phases branch off the flag in parallel.
