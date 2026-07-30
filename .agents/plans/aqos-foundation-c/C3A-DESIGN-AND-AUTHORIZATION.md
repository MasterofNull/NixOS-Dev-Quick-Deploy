> **SUPERSEDED 2026-07-29 by the mandatory C3a-1 / C3a-2 split** (codex rev2 re-review
> `codex-20260729-172222`, slice-size judgment: split is mandatory). This combined doc is
> retained as the origin/rationale record. Active designs: `C3A-1-DESIGN-AND-AUTHORIZATION.md`
> (write/secret brokers + per-tool verified contexts + deny-all exec/network/unclassified —
> safe-standalone) and `C3A-2-DESIGN-AND-AUTHORIZATION.md` (delegate/A2A/quarantine/replay/
> heartbeat — bound to the accepted C3a-1 hash). Findings B1–B8 are folded into those docs.

# Foundation C — C3a Design & Authorization: Policy Effect Brokers (rev2)

**Slice:** C3a (Foundation C §8). **Status:** DESIGN rev2 — codex binding review REVISE (8
BLOCKING + 5 SHOULD-FIX) folded; ready for confirmatory re-review.
**Predecessors (shipped):** C0 lease schema+signer, C1 shadow issuance, **C2 tool-lease
enforcement gate (committed 97131faa, flag DEFAULT-OFF)**. **Successor:** C3b execution cells.
**SSOT:** `.agents/plans/aqos-foundation-c/DESIGN-PACKET.md` §3,§4,§6,§8,§9.
**Review:** `codex-20260729-171430` (REVISE) — this rev folds all 8 BLOCKING + 5 SHOULD-FIX.

> **rev2 delta (why this changed):** rev1 assumed (a) C2 hands brokers the verified lease — it
> does not; (b) a single pre-`execute_tool_call` decision can mediate all effects — it cannot;
> (c) `a2a_guard` has a local signer — it does not (the signer is `capability_lease`); (d) a
> pure "reject-on-return" write broker satisfies F3-4 without C3b — it does not (the bytes are
> already on disk). rev2 makes brokers the **physical** effect chokepoints, adds the C2
> `VerifiedLeaseContext` handoff, and moves remote output through a quarantine→verify→commit
> path. C3a is now safe **fail-closed standalone** (no dependency on C3b rollback).

## 1. What C3a is (one sentence)
Every side-effect an admitted tool would perform (write / secret-read / delegate / exec /
network) is performed **through** a deny-closed broker that is the *physical* boundary for
that effect and consumes C2's request-scoped verified-lease verdict — so an unauthorized
effect never reaches the filesystem/network/subprocess at all, rather than being reported and
regretted afterward.

## 2. Composition with C2 — the `VerifiedLeaseContext` handoff (folds BLOCKING-1, -8; SHOULD-4)
rev1 error: C2's `_admit_tool_call` (switchboard.py:1195) returns only `(admitted, decision)`;
`enforce()` never surfaces the verified lease; `_route_target` (2495) runs *before* per-tool
admission. Brokers cannot "reuse the same verified lease" without re-verifying or trusting raw
request data.

**Fix — C2 build-surface amendment (added to the C3a ceiling):** `capability_lease_gate.enforce()`
additionally produces, once per request, an **immutable `VerifiedLeaseContext`**:
`{verified_payload, payload_digest, epoch_verdict, effective_strip (=inherited_strip OR
signed_strip), authority_degrade_state, admitting_capability, admitted_tools}`. It is stored on
the request scope by the switchboard and is the **only** input a broker will accept.

**Flag-composition truth table (SHOULD-4 — "independent flag" ≠ "independent authority"):**

| `CAPABILITY_LEASE_ENFORCEMENT` (C2) | `CAPABILITY_EFFECT_BROKERS` (C3a) | verified context | broker outcome |
|---|---|---|---|
| OFF | any | none | **all brokered effects DENIED** (no authority to permit) |
| ON | OFF | present | brokers inert (pre-C3a behavior; parity-tested) |
| ON | ON | present | brokers evaluate against the context |
| ON | ON | absent/malformed | **all brokered effects DENIED** |

C3a-ON can never *widen* authority beyond a C2-produced context; with no context, everything
brokered denies closed.

## 3. Effect boundaries — brokers at the *last responsible boundary* (folds BLOCKING-3)
rev1 error: a decision immediately before `registry.execute_tool_call()` cannot see effects a
generic tool performs internally. **Fix:** brokers sit at the effect-bearing primitives, and
any tool whose effects are *not* routed through a broker is **unclassifiable → DENIED** under
C3a-ON. Enumerated boundaries (the build pins the exact call sites; these are the classes):
- **filesystem write** → `effect_brokers.write_open()` (the only sanctioned write path, §3.1).
- **secret read** → `effect_brokers.secret_open()` — opens only under `/run/secrets/`.
- **subprocess spawn / exec** → `effect_brokers.exec_spawn()` (§3.4).
- **delegation dispatch + inbound acceptance** → `effect_brokers.delegate()` (§4), inbound via
  the **`aq-antigravity-inbox` completion/receipt path** (NOT `a2a_guard.scan_secrets`, which is
  outbound text scanning).
- **outbound socket / HTTP** → `effect_brokers.network()` — **deny-all** in C3a (§3.5).
An admitted tool that reaches any effect not via its broker, or a multi-effect/uninstrumented
tool, is denied with `unclassifiable-effect`. `effective_strip` drops every **privileged**
broker permit-path for the request (write/secret/delegate/unsandboxed-exec/network); safe read
survives — reusing C2's monotonic posture, not a weaker re-derivation.

### 3.1 write broker — the physical chokepoint (folds BLOCKING-2; SHOULD-1)
rev1 error: a "reject the returned result" broker leaves the out-of-scope bytes already
written; `realpath()` precheck is TOCTOU-vulnerable (target creation / symlink swap). **Fix:**
the write broker **performs the write itself**: tools return *proposed bytes + relative target*,
never write directly. The broker opens via a pre-opened **allowed-root dirfd** using
`openat2(RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS)` (fallback: `O_NOFOLLOW` + dirfd-relative
component checks) so the kernel refuses any escape at open time — no TOCTOU window. Any
**write-capable tool not converted to broker-mediated I/O is DENIED under C3a** (deny-before-
write); arbitrary-process writes are deferred to C3b cells. This makes C3a satisfy **F3
obligation 4 standalone** (no reliance on C3b rollback).
**Acceptance (must prove the out-of-scope file does NOT exist or change):** symlink swap,
nonexistent descendants, `..`, absolute vs relative aliases, component-prefix collisions
(`/allowed-evil` vs `/allowed`), and concurrent create races.
**Canonical field (SHOULD-1):** one signed `allowed_output_paths` (a.k.a. write scope);
`allowed_write_paths` in §4 is the delegate-scoped subset of the same field — unknown aliases
DENY, never fall back to config.

### 3.2 secret_read broker
Opens only under `/run/secrets/` (SOPS runtime); tracked Nix / repo paths / env scraping →
DENY. Scope is a signed field (`secret_read_scope`), not read from config.

### 3.3 delegate broker → see §4 (signed-A2A verify-before-write).

### 3.4 exec broker (folds BLOCKING-6; Q-C3a-2)
Classification lives in C3a, but the C3a/C3b gap must never run a sandbox-required command
unsandboxed: **explicitly authorized `unsandboxed-exec` may run; sandbox-required exec DENIES
with `confinement-unavailable` until C3b provides bwrap; unclassifiable exec DENIES.**

### 3.5 network broker
**Deny-all** (fail-closed keystone). Profile-scoped egress (the ratified eight) is **C4**, after
the threat pass. No profile may fail open. **Forced-remote invariant (SHOULD-3):** an explicit/
forced-remote request whose intended OAuth lane is unavailable returns **denial**, never a
fall-through to another provider (esp. OpenRouter) — explicit acceptance test required.

## 4. Delegate broker — signed-A2A verify-before-write (folds BLOCKING-4, -5; SHOULD-2)
rev1 errors: named a nonexistent `a2a_guard` signer; allowed remote to write the authoritative
path before verification; non-atomic idempotency.

**Signer (real):** `capability_lease.canonical_payload`/`sign` (HMAC-SHA256) + `resolve_key`
(the same local, **no-remote-key** infrastructure C0–C2 use). "No keys" = **no remote/API
keys**; the local HMAC key material is still protected (SOPS `/run/secrets/`, DEV-key degrade
applies exactly as C2). A **new canonical A2A envelope schema** (added to the ceiling) whose
signature covers ALL authority-bearing fields: `output_digest`, `expected_output_path`,
`allowed_write_paths`, `schema_id` + `schema_version`, `child_lease_id`, `deadline`,
`heartbeat_seq`, `idempotency_token`.

**Quarantine→verify→commit (BLOCKING-5):** the remote lane writes ONLY to an untrusted
quarantine blob (never the authoritative path). The broker then, in order: (1) safely reads the
blob; (2) verifies signature + `output_digest` + `deadline` + `child_lease_id` (⊆ parent, via
`attenuate`) + path ⊆ `allowed_write_paths` + schema; (3) **atomically reserves** the
`idempotency_token` via the `aq-antigravity-inbox` receipt lock (`_task_lock`/`_receipt_path`);
(4) commits through the **write broker (§3.1)** to the final path. No remote principal writes
the authoritative path directly.

**Heartbeat (SHOULD-2, deterministic):** signed **monotonic `heartbeat_seq`** + trusted receipt
time; a state machine `live → pending-late (seq gap within `deadline`) → dead (deadline blown
OR gap > allowed_gap)`; transitions are irreversible and append-only; replayed/duplicate seq
rejected. `dead` → acceptance denied (and feeds C3b rollback later). The `aq-antigravity-inbox`
receipt protocol is **extended** for atomic idempotency reservation + signed heartbeat records —
`aq-antigravity-inbox` + its receipt schema + tests are **in the ceiling**.

## 5. Signed effect classification in issuance (folds BLOCKING-7)
Current `capability_lease_issuance.py` binds only coarse `network`/`writes` constraints. C3a
requires the issuer to bind canonical **signed** classification: `allowed_output_paths`,
`secret_read_scope`, `delegate_scope`, `exec_class ∈ {none, unsandboxed-authorized,
sandbox-required}`, with a defined **attenuation order** (child ⊆ parent for every field).
`capability_lease_issuance.py` + the lease schema + the first-party manifest projection are
**in the ceiling**. Mutable config may compare against signed values and DENY on mismatch, but
may **never supply** a missing permission/path (generalizes C2 codex-3; NICE-TO-HAVE property
test: config can only turn allow→deny, never deny→allow, per broker).

## 6. Authority-unavailable posture (folds BLOCKING-8)
Only a **trusted C2-produced `authority_degrade_state`** inside `VerifiedLeaseContext` enables a
**narrowly enumerated safe-read** capability (deny privileged/write/network/delegate) + a LOUD
alert. Missing / malformed / expired / caller-supplied "degraded" leases → **total denial**.
Never synthesize or accept an unsigned lease. Zero fail-open; not fail-closed-to-total-DoS
(reconciles with keystone boot-safety) — but the *only* path to safe-read is C2's signed degrade
verdict.

## 7. Observability
Each broker allow/deny/degrade emits a schema-conformant decision record (C2 audit pattern:
stderr JSON behind flag-ON, logging wrapped so it can never affect the decision):
`broker, effect, decision, reason, lease_id, parent_lease_id, revocation_epoch, scope`. These
become OTel spans in **C5** (not C3a).

## 8. Ceiling (expanded by the review; pinned exactly at freeze)
- NEW `ai-stack/switchboard/effect_brokers.py` — the five brokers, one module, **typed
  per-broker request objects**, shared fail-closed wrapper (Q-C3a-1 APPROVED conditionally).
- EDIT `ai-stack/switchboard/capability_lease_gate.py` — produce `VerifiedLeaseContext` (§2).
- EDIT `ai-stack/switchboard/switchboard.py` — store the context; route write/secret/exec/
  delegate/network through brokers at the enumerated boundaries; forced-remote deny (§3.5).
- EDIT `scripts/ai/lib/capability_lease_issuance.py` (+ lease schema + manifest projection) —
  signed classification fields (§5).
- NEW A2A envelope schema + EDIT `scripts/ai/aq-antigravity-inbox` (+ receipt schema) — atomic
  idempotency reservation + signed heartbeat (§4).
- NEW decision schema; NEW test suite (all §9 acceptance).
- NEW `config/effect-broker-defaults.json` — compare-only DENY tripwire, never a grant source.
Multi-file, security-critical, kernel-syscall-adjacent ⇒ **cheapest-eligible implementer at
activation (Claude fast tier, Rule-17 override recorded), NOT local**; codex + local engaged for
grounding + independent review (never-skip-local; all-agents-engaged). This is a **larger slice
than rev1 implied** — if review judges it too large, the natural sub-split is C3a-1 {write +
secret + exec + network deny-all + VerifiedLeaseContext} and C3a-2 {delegate + A2A envelope +
inbox}. Recommendation deferred to re-review.

## 9. Acceptance bar (per-slice, offline-first)
- **F3 obligation 4** standalone (no C3b): out-of-scope write **does not exist/change** across
  the §3.1 adversarial set.
- each broker: in-scope allow, out-of-scope deny, deny-closed on missing/expired/unverifiable
  lease and on `unclassifiable-effect`, dropped under `effective_strip`.
- delegate: bad signature / past deadline / replayed idempotency / path outside
  `allowed_write_paths` / schema-invalid / `dead` heartbeat → NOT accepted, **no write to the
  authoritative path**; a fully valid envelope → committed via the write broker.
- exec: unsandboxed-authorized runs; sandbox-required → `confinement-unavailable`;
  unclassifiable → deny.
- network: deny-all; forced-remote → deny, never reroute (SHOULD-3 test).
- authority-unavailable: only C2-signed degrade → safe-read; every other "degraded" → total deny.
- flag-composition truth table (§2) proven; flag-OFF byte-parity; brokers never raise
  (fail-closed wrapper).
- bound-classification: mutable config can only deny, never grant, per broker (NICE-TO-HAVE).

## 10. Ceremony + DoD split (folds SHOULD-5)
Enforcement-tier, hash-bound — same as C2: design → confirmatory re-review → freeze (subject =
this doc [+ any amendment], ceiling §8, predecessor hashes incl. capability_lease.py,
capability_lease_issuance.py, capability_lease_gate.py @ 97131faa) → **single-use owner
activation** → build **flag-default-OFF** → independent review → commit.
**This authorization covers ONLY the default-OFF BUILD stage.** C3a is **not "complete"** (packet
§9 DoD) until a *later, separate* cycle turns the flag ON and supplies: a real request
allowed/denied live, dashboard surface + health-spider check, and operator intervenability
(revoke/epoch-bump). OTel spans land in C5. Standing authorization does NOT activate C3a.

## 11. C3b forward-scope (separate slice, own doc)
C3b — execution cells: isolated git-worktree (or `git stash -u` fallback) under **bubblewrap**
whose allowed set == the lease's allowed set; `workspace.snapshot` before first write; GREEN →
merge+retain, RED/timeout/heartbeat-miss/revocation → drop worktree + `workspace.rollback`. C3b
turns C3a's "deny arbitrary-process writes" into "run them safely in a cell," and carries the
**APU bwrap perf measurement** (packet §9 risk d). Own design→review→freeze→activation doc once
C3a lands; C3a is safe fail-closed without it.

## 12. Open-question verdicts (codex-confirmed)
- **Q-C3a-1** one `effect_brokers.py` + typed broker requests + immutable context — ADOPTED.
- **Q-C3a-2** classification in C3a, deny sandbox-required exec until C3b — ADOPTED (§3.4).
- **Q-C3a-3** reuse `aq-antigravity-inbox` receipts ONLY with atomic replay reservation + signed
  heartbeat + inbox implementation in scope — ADOPTED (§4, §8).
