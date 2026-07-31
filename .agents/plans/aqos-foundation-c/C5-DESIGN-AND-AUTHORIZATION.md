---
title: "Foundation C C5: OTel Spans as Source of Truth (audit/PULSE/matrix as projections) — Design Packet"
slice: "C5"
status: "C5_DESIGN_REVIEWED_PASS (non-enforcement; standing-auth to build) — light-model review, codex confirmatory queued"
revision: 1
kind: "design-only"
implementation_authorization: "NONE (non-enforcement observability — standing-auth class)"
activation_authorization: "NONE"
author: "Opus (codex-substitution — codex usage-limited to 2026-08-04; catch-up audit queued)"
predecessors:
  - "C2 gate (97131faa); C3b R1-R4 (grant/clone/runner/perf); C4 network design"
  - "B3 aq-event projection (PULSE/RESUME already event-sourced)"
successors:
  - "C6 epoch-revocation <-> scheduler seam"
---

# Foundation C — C5: OTel Spans as Source of Truth

## 0. Provenance & authority
Authored by Opus (codex-substitution). Independent review → antigravity/gemini + codex-on-return.
**DESIGN-ONLY.** C5 is **NON-ENFORCEMENT observability** — it makes the *already-decided* C2/C3b/C4
enforcement events emit canonical spans and makes audit/PULSE/matrix *projections* of those spans.
It gates nothing and changes no admission/confinement/egress decision, so it is **standing-auth
class** (like C0/C1) — no single-use owner activation to build. It ships behind an observability
flag default-OFF only to preserve byte-parity while shadow-validated.

## 1. Scope (DESIGN-PACKET §7, §8)
Make **OTel spans the operational source of truth**: (a) a canonical span taxonomy over the C2/C3b/
C4 decision points (turn / tool / lease / validation / workspace / broker); (b) every lease
issue/attenuate/deny/revoke and every broker allow/deny/degrade emits a span carrying
`lease_id/parent_lease_id/revocation_epoch/decision`; (c) **PULSE, a2a-audit, ACTIVATION-AUDIT, and
the parity matrix become PROJECTIONS of spans** (generalizing B3's aq-event PULSE/RESUME projector);
(d) **W3C Trace Context** propagated across A2A hops. **Out of scope:** any enforcement change,
C6's scheduler seam, turning spans into a gate (they observe, never decide).

## 2. Build on what exists (grounded 2026-07-30 — no new SDK required)
- `scripts/ai/lib/trace.py` — the local span API (`_tracing.span(name, agent, attrs)`; W3C trace
  context; used by `dispatch.py::_maybe_span` around model generation). C5 reuses this `span()` — no
  external OpenTelemetry SDK dependency.
- `ai-stack/mcp-servers/hybrid-coordinator/trace_collector.py` — already records a full span per
  `/query` to the PostgreSQL `query_traces` table with `gen_ai.*` attributes and **optionally pushes
  OTLP when `OTEL_EXPORTER_OTLP_ENDPOINT` is set (gracefully skips otherwise)**. C5 reuses this
  emit-and-optional-export pattern; no hard OTLP dependency (works fully offline).
- `scripts/ai/aq-event` (B3) — `event_log.emit` + `resume_projector` already PROJECT PULSE/RESUME
  from events. C5 EXTENDS this projector so audit/matrix are span-derived too. Spans are the new
  event source; the projection machinery already exists.
- `.agents/events/*.jsonl`, `.agents/telemetry`, `/var/lib/ai-stack/hybrid/telemetry` — the local
  span/event sinks (no network; C5 adds no egress — telemetry stays local, consistent with C4).

## 3. Canonical span taxonomy (the source of truth)
Closed set of span kinds, each with required attributes (superset; deny-closed on a malformed span
= it is dropped from projections + flagged, never silently trusted):

| span kind | opened at | required attrs |
|---|---|---|
| `turn` | a request/session turn | `turn_id`, `agent`, W3C `traceparent` |
| `tool` | C2 `_admit_tool_call` | `tool`, `decision(admit/deny/strip)`, `reason`, `lease_id` |
| `lease` | C1/C2 issue/attenuate/deny/revoke | `lease_id`, `parent_lease_id`, `revocation_epoch`, `op`, `decision` |
| `validation` | tier0 / out-of-cell validator | `verdict(GREEN/RED)`, `declared_paths_ok`, `grant_digest` |
| `workspace` | C3b snapshot/rollback | `event(snapshot/rollback/quarantine)`, `cell_id`, `base_oid`, `grant_digest` |
| `broker` | C3a/C4 effect/egress allow/deny | `broker`, `effect`, `decision`, `reason`, `profile_id?`, `lease_id` |

All attrs are **low-cardinality + secret-free** (no payloads, prompts, keys, full paths — path is a
declared-scope id, not the bytes). W3C `traceparent` links child spans to the turn and across A2A hops.

## 4. Projections (audit/PULSE/matrix become span-derived)
Extend the B3 projector: each projection is a **pure fold over the span stream**, reproducible +
idempotent (re-running the projector on the same spans yields byte-identical output — the B3 property).
- **PULSE** ← project `pulse.append`-shaped lines from `tool`/`lease`/`workspace`/`broker` spans.
- **a2a-audit** ← project from A2A `broker`/`delegate` spans (the outbound/inbound records).
- **ACTIVATION-AUDIT** ← project from `activation.grant` events + the `lease`/`workspace` spans they
  authorize (so the activation ledger is span-backed, not hand-edited — consistent with the
  existing "never hand-edit PULSE/RESUME" rule).
- **parity matrix** ← project agent/lane coverage from `tool`/`lease` spans.
A projection NEVER decides anything; it reads spans and writes a derived view. Hand-editing a
projected surface is a drift the projector's `--check` catches (as PULSE/RESUME already do).

## 5. Shadow-first + flag
- NEW observability flag `CAPABILITY_SPAN_TRUTH` (default **"0"**). OFF ⇒ the current audit/PULSE
  surfaces are authoritative and byte-identical to today (parity-tested); the span emitters run in
  **shadow** (emit spans, but the old surfaces stay authoritative), exactly like C1's shadow issuance.
  Flip-to-ON (a later, low-risk step — it's observability, not enforcement) makes the projections
  authoritative. No enforcement decision ever depends on a span.
- Spans emit through `trace.py`; export is the existing optional OTLP (offline-safe). No new egress.

## 6. Ceiling (frozen at C5 freeze; non-enforcement)
- NEW `scripts/ai/lib/span_taxonomy.py` — the closed span-kind schema + attr validators (low-card,
  secret-free; malformed span → dropped+flagged).
- EDIT the C2 gate / C3b runner / C4 broker decision points to emit the §3 spans via `trace.py`
  (additive, shadow, flag-gated; flag-OFF byte-parity).
- EXTEND `scripts/ai/aq-event` + `resume_projector` (or a new `span_projector.py`) so audit/PULSE/
  ACTIVATION-AUDIT/matrix are span-derived, with a `--check` drift gate.
- NEW decision/span schema + NEW `scripts/testing/test-span-truth.py` (offline: taxonomy validation,
  secret-free/low-card assertions, projection idempotency/reproducibility, flag-OFF byte-parity,
  malformed-span-dropped, W3C traceparent propagation, hand-edit drift caught).
- **MUST NOT:** make any enforcement decision depend on a span; emit any secret/high-card datum;
  add network egress; change C2/C3b/C4 admission/confinement/egress behavior (emit-only).

## 7. Acceptance bar
- every C2/C3b/C4 decision emits its §3 span with the required low-card, secret-free attrs.
- projections are pure/idempotent/reproducible folds; hand-edit → drift caught by `--check`.
- flag-OFF → old surfaces authoritative + byte-identical (parity); spans shadow-emit.
- no span carries a secret/prompt/key/raw-path; malformed span dropped+flagged, never trusted.
- W3C traceparent links child spans + crosses A2A hops; OTLP export offline-safe (skips w/o endpoint).
- no enforcement decision reads a span (spans observe, never gate).

## 8. Review obligations
1. spans are emit-only observability — nothing enforces on a span; C2/C3b/C4 behavior unchanged.
2. attrs are low-cardinality + secret-free (no payloads/keys/prompts/raw-paths); malformed → dropped.
3. projections are pure/idempotent/reproducible; drift caught; no hand-edit authority.
4. flag-OFF byte-parity; shadow-first (old surfaces authoritative until a later low-risk flip).
5. no new network egress (telemetry stays local, consistent with C4); OTLP optional/offline-safe.
6. reuses trace.py/trace_collector/aq-event — no fabricated SDK dependency (verify the anchors exist).

## 9. Freeze criteria + ceremony
Non-enforcement ⇒ standing-auth: design → independent review → freeze → build (flag-default-OFF) →
review → commit. No single-use owner activation needed (it gates nothing). Flipping
`CAPABILITY_SPAN_TRUTH` to ON later is a low-risk observability step, not an enforcement act.
Predecessor hashes: trace.py, aq-event/resume_projector, the C2/C3b/C4 decision surfaces (emit
points added additively).

## 10. Open questions for review
- Q-C5-1: one `span_projector.py` vs extending the existing B3 projector in place — recommend extend
  in place (spans are just a richer event source; reuse the proven projection machinery).
- Q-C5-2: should ACTIVATION-AUDIT become fully span-derived now, or stay hand-appended with a span
  cross-check first? Recommend span-derived with a one-cycle shadow cross-check (catch discrepancies
  before making spans authoritative).
- Q-C5-3: OTLP export — keep it strictly optional/offline-safe (no endpoint configured by default),
  confirming C5 adds zero network egress (recommend yes; a remote OTLP sink would be a NEW C4 profile).

**Requested reviewer result:** `PASS` / `FAIL` / `REQUEST_REVISION` against C5 scope + §8. C5 is
non-enforcement; no review outcome authorizes an enforcement change (there is none to authorize).
