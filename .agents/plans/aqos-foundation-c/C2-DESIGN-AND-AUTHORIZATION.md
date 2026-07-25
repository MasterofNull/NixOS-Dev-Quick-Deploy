# Foundation C — C2 Tool-Lease Enforcement (Design + Authorization)

**Status: PREPARED_ONLY — IMPLEMENTATION NOT AUTHORIZED.** This record remains
PREPARED_ONLY after an independent review PASS. Implementation requires a **later,
explicit, single-use OWNER activation** naming this record's frozen SHA-256, the exact
implementer, the exact HEAD, and a ≤24h window. **A broad/standing authorization ("proceed
with all slices") does NOT activate this slice** — C2 turns ENFORCEMENT on in the live
switchboard, the first Foundation C slice that changes running behavior, so it is
hash-bound by the owner's own governance.

**Idempotency key:** `aqos-foundation-c:c2:tool-lease-enforcement-flag-gated:v1:20260724`.
**Track:** AQ-OS Unified Program — Foundation C, design §8 C2. **Builds on:** C0 `0319488b`
(lease primitive), C1 `f121c713` (shadow issuance policy). **Author:** fable-5.

## Why hash-bound (vs C0/C1 standing-auth)
C0/C1 added only NEW files and enforced nothing (report-only/shadow). C2 **edits the live
switchboard tool-resolution path** (`_resolve_tool_lease`, `ai-stack/switchboard/switchboard.py:1132`)
and, when its flag is ON, **DENIES tools** that lack a valid lease. That is a running-behavior
change on the request hot path ⇒ single-use owner activation required.

## Design

### The gate (flag-gated, DEFAULT-OFF)
A new env flag `CAPABILITY_LEASE_ENFORCEMENT` (default `"0"`). When **off**, the tool-calling
loop behaves EXACTLY as today (byte-for-byte — verified by a parity test); C2 shipped with the
flag off changes nothing in the running system (the *activation* is flipping the flag, a
separate owner act).

**Hook point (REVISED per C2 review B1 — gate the TRUE execution chokepoint, not the virtual
lease tool).** The set that actually gates execution is `allowed_names`, seeded by
`_normalize_local_tools` (`switchboard.py:1552`) and checked per-call at
`switchboard.py:1673` (`if tool_name not in allowed_names:` → reject) immediately before the
tool executes in the `else` branch at `:1706`. `_resolve_tool_lease` (`:1690`) only fires when
the model voluntarily calls the virtual `lease_tools` tool, and the intent bundles
(`_TOOL_BUNDLES`) inject executable privileged tools (e.g. `run_command`) DIRECTLY into the
initial `allowed_names` — so gating only `_resolve_tool_lease` is a fail-open. **C2 gates the
per-call admission at `:1673`:** when the flag is ON, a tool is admitted for execution iff it
is in `allowed_names` **AND** the lease gate admits it. A rejected tool returns the existing
`unsupported/denied` tool-result shape (no execution). This is the executor chokepoint every
real tool call passes through. (The `_resolve_tool_lease` working-set path is ALSO passed
through the same gate so a leased-in tool still needs lease admission — but the load-bearing
gate is the per-call `:1673` check.)

When **on**, for each tool call:
- Admitted iff a valid CapabilityLease admits the tool (reusing `capability_lease_issuance` +
  `capability_lease.verify`): lease present, signature-valid, non-expired, and **not
  epoch-stale** (`current_epoch` ALWAYS resolved and passed — never `None` in enforcement;
  the executor epoch check ships HERE per design S1).
- `zero_trust_behavior: strip` on the request's derived lease drops write/network/delegate/
  unsandboxed-exec-capable tools (collapses keystone `zero_trust` into the lease behavior —
  task-scoped monotonic, design S3; a caller cannot pass `zero_trust=false` to keep them).
- **Deny-closed:** missing/expired/unverifiable/epoch-stale lease → tool DROPPED, never
  executed. No fail-open path.

**Fail-open closures the review required (BLOCKING B1/B2 + S-a/S-b/S-c):**
- **(B2) DEV-key = authority-unavailable.** `resolve_key()` returns `(key, is_dev)`; `is_dev`
  means no production signing secret is present. In enforcement mode **`is_dev=True` triggers
  the S4 authority-unavailable degrade** — the gate NEVER verifies/admits under the public DEV
  key. Degrade = minimal least-privilege: admit only a fixed **safe-read allowlist** (non-
  write, non-network, non-exec tools), drop all privileged tools, LOUD log. NOT total denial,
  NOT fail-open.
- **(S-a) Epoch source + unresolvable posture.** `current_epoch` is read from a policy-epoch
  source (a single-int file `config/capability-lease-epoch` / env `AQ_LEASE_POLICY_EPOCH`,
  default 0; the bump *control surface* is C6, C2 only READS it). If the epoch source is
  present-but-unparseable → treat as authority-unavailable → S4 degrade (NEVER skip the stale
  check by passing `current_epoch=None`).
- **(S-b) Tool→lease admission mapping.** A tool is admitted iff SOME admitted candidate's
  shadow lease (from `shadow_issue`, `would_issue=True`, verifying) lists the tool in
  `permissions.actions` AND that lease passes `verify` (+ epoch + not stripped). `enforce()`
  builds the tool→admitting-lease map by iterating candidate leases once per request.
- **(S-c) Guarded, fail-closed gate call.** The gate import is lazy inside the enforcement
  branch (N1: `scripts/ai/lib` is already on `sys.path`, so the import is safe) and the whole
  `enforce()` call is wrapped so ANY internal exception FAILS CLOSED (the tool is dropped),
  never crashes tool resolution and never leaks out of the loop.
- Every admit/drop/strip/degrade emits an audit line (span-shaped; OTel spans are C5).

### File ceiling (exactly 4)
1. **EDIT** `ai-stack/switchboard/switchboard.py` — add the flag read + the per-call lease
   admission at the `:1673` chokepoint (and route the `_resolve_tool_lease` result through the
   same gate). The entire new path is behind `if CAPABILITY_LEASE_ENFORCEMENT`; guarded lazy
   import; fail-closed wrapper. Minimize the edit to the tool-call admission region.
2. **NEW** `ai-stack/switchboard/capability_lease_gate.py` — the pure gate:
   `enforce(tool_names:set, candidates_ctx, epoch_source, key_resolver) -> (admitted:set,
   decisions:list)`. Imports C0/C1 libs; deny-closed; is_dev→S4 degrade; unresolvable-epoch→S4
   degrade; tool→lease mapping. Unit-testable without the server.
3. **NEW** `scripts/testing/test-capability-lease-gate.py` — acceptance (below).
4. **NEW** `config/schemas/capability-lease-gate-decision.schema.json` — the audit-decision
   contract (observability).

**(S-d) Remote-tool path — written deferral.** `_filter_remote_tools_for_working_set`
(`switchboard.py:2955`) governs the working set for REMOTE (non-local-tool-calling) requests;
it is NOT the local execution chokepoint that runs `run_command`. C2 gates the local
tool-calling execution path (the privileged-execution priority). Remote-tool-working-set
gating is **explicitly deferred to a named follow-up (C2-remote)**; until then remote-tool
selection is out of C2's enforcement scope — acceptable because it does not execute local
privileged tools. Recorded so it is a deliberate deferral, not an unnoticed gap.

The `CAPABILITY_LEASE_ENFORCEMENT` **NixOS option** (declarative, profile-driven per the
architecture constraint) is a bounded sub-item: ship the env read now (default off, works
without Nix), declare the `nix/modules/.../options.nix` + `profiles/ai-dev.nix` flag in the
SAME activation cycle when the owner turns it on (Rule 13 — no runtime-only enablement).

### Acceptance (per-slice, F3 proof obligations)
- **Flag OFF = zero behavior change:** a parity test proves the tool-call admission at the
  `:1673` chokepoint is byte-for-byte identical with the flag off vs the pre-C2 code (the C2
  commit is inert until flipped).
- **(B1) Per-call chokepoint is gated:** with the flag ON and no valid lease admitting it, a
  privileged tool that is in the initial `allowed_names` bundle (e.g. `run_command`) is
  DROPPED at `:1673` and never executed — the test drives the actual tool-call path, not just
  `_resolve_tool_lease`. This is the load-bearing anti-fail-open test.
- **Deny-closed:** tool with no/expired/tampered/epoch-stale lease → DROPPED. → F3 (1)
  stripped-can't-reacquire, (3) stale-lease-can't-revive-after-epoch.
- **(B2) DEV-key never admits:** with `is_dev=True` (no production secret), enforcement does
  NOT verify under the DEV key — it degrades to the safe-read allowlist; a privileged tool is
  dropped even if a DEV-key-signed lease "admits" it.
- **Strip:** `zero_trust_behavior: strip` drops write/network/delegate/exec tools; a caller
  cannot pass `zero_trust=false` to keep them → F3 (2) can't-downgrade-inherited-stricter.
- **(S-a) Unresolvable epoch → degrade:** an unparseable epoch source → S4 degrade (privileged
  dropped), never `current_epoch=None` skip.
- **Authority-unavailable** → least-privilege degrade (safe reads kept, privileged dropped),
  never total-deny, never fail-open.
- **(S-c) Gate exception fails closed:** an injected exception inside `enforce()` → the tool
  is DROPPED and resolution does not crash.
- **Revocation:** bumping the policy epoch drops an in-flight lease's tools on the next call
  (intervenability, design S1).
- Offline; the gate is a pure function tested directly + a targeted test of the `:1673`
  admission branch (mock the tool-call loop inputs; no live server needed).

### Out of scope (deferred)
No network profiles (C4), no cells/bwrap (C3b), no OTel span backend (C5), no epoch-bump
control surface (C6 — C2 only READS the epoch + enforces the check). No new tools.

## Activation protocol (what the owner does)
1. Independent review of THIS record → PASS (no fail-open, ceiling, off=inert).
2. Freeze: record this file's SHA-256 + the C0/C1 predecessor hashes; verify HEAD.
3. **Owner single-use activation** (`aq-event pulse`, `agent:owner`) naming this SHA-256 +
   implementer + HEAD + ≤24h window. THEN the cheapest-eligible implementer builds the
   4-file ceiling; independent review; commit with the flag DEFAULT-OFF.
4. Turning the flag ON in the running system is a **further** owner act (+ the Nix option in
   the same cycle) — enforcement does not go live merely by committing C2.

## Reviewer / next
Independent design review (not the author) of this record for fail-open, ceiling,
off-is-inert, and F3 faithfulness. On PASS → freeze + present the exact owner activation
line. codex confirmatory audit queued.

**Review status (2026-07-25): rev2 — REVISE folded, RE-REVIEW required before freeze.**
Independent flagship review (Opus, `C2-REVIEW-OPUS.md`) returned **REVISE** with 2 BLOCKING
fail-opens + 4 SHOULD-FIX. Both BLOCKING were real and material — they falsified C2's core
claim:
- **B1** — the design gated only the virtual `_resolve_tool_lease` path, but the true
  execution chokepoint is the per-call `allowed_names` check at `switchboard.py:1673`, and the
  intent bundles inject `run_command` directly ⇒ flag-ON would execute privileged tools
  ungated. **Folded:** the gate is re-anchored at `:1673` (§The gate, revised).
- **B2** — `resolve_key()` silently returns a public DEV key when the production secret is
  absent ⇒ flag-ON would admit under a publicly-known key. **Folded:** `is_dev=True` now
  triggers the S4 authority-unavailable degrade; the gate never verifies under the DEV key.
- S-a (epoch source + unresolvable→degrade), S-b (tool→lease mapping), S-c (guarded import +
  fail-closed wrapper), S-d (remote-tool path written-deferred) — all folded.

Because the fix was **material (corrected chokepoint + trust-root)**, this revised record
requires a fresh independent flagship RE-REVIEW confirming B1/B2 are closed and no new
fail-open was introduced, BEFORE the hash is frozen. **Stays PREPARED_ONLY; NOT eligible for
owner activation until the re-review PASSES + hash frozen.** No enforcement work proceeds
meanwhile. codex confirmatory audit still queued.
