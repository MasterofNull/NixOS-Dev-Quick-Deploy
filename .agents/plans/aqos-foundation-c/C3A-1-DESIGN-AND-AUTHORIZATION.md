> **SUPERSEDED-BY-ARCHITECTURE 2026-07-30.** The C3a-1 *in-process* write/secret brokers are
> subsumed by the shipped C3b substrate: R1 `execution_grant` already classifies effects
> (`effect_set`/`exec_class`, deny-class network/delegate/secret) and R2 `execution_cell_clone`
> does the TOCTOU-proof `openat2` path mediation INSIDE the bwrap cell. Effect-brokering is now
> realized by routing effect-bearing tools INTO C3b cells (via R5 switchboard adapter) + C4
> network + C3a-2 delegate + C6 scheduler — NOT a standalone in-process broker. This doc is
> retained for its findings/history; do not build it as-is. Active successor: C3A-2 (delegate).

> **DEFERRED 2026-07-29 (owner-ratified resequence).** Effect-brokering now follows C3b
> (execution cells) + C4 (network profiles) — in-process brokering cannot safely precede
> confinement (codex 3-round review). This design is retained with all findings; it resumes
> after C3b+C4 land and an accurate signed per-handler effect inventory replaces the
> `first-party-tools.json` guesses. NEXT ACTIVE SLICE: C3b. See DESIGN-PACKET.md §8 RESEQUENCE.

# Foundation C — C3a-1 Design & Authorization: Write/Secret Brokers + Per-Tool Verified Contexts

**Slice:** C3a-1 (the safe-standalone half of the mandatory C3a split — codex rev2 re-review
`codex-20260729-172222`). **Status:** DESIGN — folds the C3a-1-applicable BLOCKING/SHOULD-FIX
findings; ready for confirmatory review.
**Predecessors (shipped):** C0 lease schema+signer, C1 shadow issuance, **C2 tool-lease
enforcement gate (97131faa, flag DEFAULT-OFF)**.
**Sibling (deferred, own doc, bound to accepted C3a-1 hash):** C3a-2 (delegate / A2A envelope /
quarantine verify / global replay / heartbeat / inbox).
**Successor:** C3b execution cells (bwrap) — required before arbitrary exec/write can run.
**Origin/rationale:** `C3A-DESIGN-AND-AUTHORIZATION.md` (superseded combined rev2).

## 1. Scope (one sentence)
C3a-1 makes the switchboard **classify every admitted tool by its effect from the signed lease
and deny every effect it cannot physically mediate** — permitting only (a) safe reads and (b)
broker-mediated writes/secret-reads through a TOCTOU-proof `openat2` chokepoint — while
denying-closed all exec, network, delegation, and every unclassifiable/uninstrumented tool
until C3b (confinement) and C3a-2 (delegation) land.

## 2. Per-tool VerifiedToolLeaseContext handoff (folds BLOCKING-1, -8; SHOULD-4)
The C2 gate is amended to produce, once per request, a **per-tool** map — not a single shared
context (rev2's singular `verified_payload` + plural `admitted_tools` allowed tool B to be
judged under tool A's broader lease):

```
enforce() -> AuthorityContext
AuthorityContext = VerifiedAuthorityContext | AuthorityUnavailableContext   # closed sum type
VerifiedAuthorityContext = { by_tool: { tool_name -> VerifiedToolLeaseContext } }
VerifiedToolLeaseContext = { tool_name, verified_payload, payload_digest, epoch_verdict,
                             effective_strip, admitting_lease_id, effect_class, effect_scope }
AuthorityUnavailableContext = { safe_read_only: true }   # constructed ONLY inside C2 on
                             # DEV-key/epoch-authority-unavailable; carries NO caller lease,
                             # NO synthesized signature; every privileged broker rejects it.
```

Every broker call **binds `tool_name`** and rejects any context/tool mismatch. BLOCKING-8 fix:
degradation is a distinct variant (not a fake verified lease) built only by C2; it exposes only
the fixed safe-read set and is denied by every privileged broker.

**Flag-composition truth table (SHOULD-4 — closed, unchanged from rev2):**

| C2 `CAPABILITY_LEASE_ENFORCEMENT` | C3a-1 `CAPABILITY_EFFECT_BROKERS` | context | outcome |
|---|---|---|---|
| OFF | any | none | all brokered effects **DENIED** |
| ON | OFF | present | brokers inert (byte-parity with pre-C3a-1) |
| ON | ON | present | brokers evaluate per-tool context |
| ON | ON | absent/malformed | all brokered effects **DENIED** |

## 3. Effect enumeration — every C3a-1-ON tool, classified (folds BLOCKING-3)
Source: `config/first-party-tools.json` (25 tools, already carrying `write_capable`/
`network_capable`/`trust_tier`), classification **read from the signed lease**, config
compare-only (deny on mismatch, never grant). The ceiling freezes this exact table; any
registry handler NOT in it, or classified `unclassifiable`, is **denied before invocation**.

| effect class | tools | C3a-1 outcome |
|---|---|---|
| **read-safe** (tier 3 + screenshot) | git_status, git_diff, search_files, read_file, list_files, check_service, get_system_info, get_hint, query_context, harness_health, get_working_memory, get_prsi_pending, query_aidb, mesh_discovery, recommend_agent_for_task, collective_memory_search, get_screen_size, screenshot, lease_tools | **ALLOW** (no privileged effect) |
| **write** (broker-mediated) | write_file, store_memory | **ALLOW iff** routed through the §4 write/secret broker with proposed-bytes contract; else DENY |
| **exec / subprocess** | run_command, validate_before_commit, prsi_orchestrate | **DENY** `confinement-unavailable` (arbitrary subprocess → deferred to C3b; folds the rev2 NEW FAIL-OPEN — no "unsandboxed-authorized may run" in C3a-1) |
| **network** | delegate_to_remote, run_command | **DENY** deny-all (profiles = C4) |
| **delegate** | delegate_to_remote | **DENY** in C3a-1 (delegation = C3a-2) |

**Consequence stated honestly:** with C3a-1-ON, `run_command` (arbitrary write+net+exec) is
DENIED — so exec-heavy agent workflows do not run under the flag until C3b provides OS-enforced
confinement. This is intentional and is why the flag ships default-OFF and C3b precedes any
realistic flag-ON for those workflows. C3a-1 enforceably covers the write/secret/read surface
now; it does not pretend to safely run arbitrary subprocesses in-process.

## 4. Write / secret brokers — the physical chokepoint (folds BLOCKING-2; SHOULD-1)
Tools return **proposed bytes + relative target**; the broker performs the write. Path safety:
- **Primary:** `openat2(dirfd, rel, RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS)` on a pre-opened
  allowed-root dirfd — the kernel refuses any escape at open time.
- **Fallback when `openat2` is unavailable (BLOCKING-2 fix):** an **fd-only component walk** —
  open each path component with `openat(parent_fd, comp, O_PATH|O_DIRECTORY|O_NOFOLLOW)`, retain
  the fd, open the final component relative to that fd, **never re-resolving a checked pathname**.
  If neither is available → **DENY** (no raceable `realpath`-precheck path exists anywhere).
- **secret broker:** identical dirfd discipline rooted at `/run/secrets/` only; `secret_read_scope`
  is a signed field.
- **Canonical path field (SHOULD-1):** one signed `allowed_output_paths`; comparison is
  **component-aware containment**, never string-prefix. Missing/malformed → deny.

**Acceptance (out-of-scope file must NOT exist or change):** symlink swap, nonexistent
descendants, `..`, abs-vs-rel aliases, component-prefix collisions (`/allowed-evil` vs
`/allowed`), concurrent-create races, and the `openat2`-absent fallback race set.

## 5. Signed classification in issuance (folds BLOCKING-7)
`capability_lease_issuance.py` + the lease schema + first-party manifest projection bind, as
**signed** fields with defined partial orders (child ⊆ parent), added to the ceiling:
- `allowed_output_paths`, `secret_read_scope` — canonical path/scope sets; child is a subset;
  containment is component-aware.
- `exec_class` — total order `none ≤ sandbox-required ≤ unsandboxed-authorized`; attenuation may
  only lower it. (In C3a-1 anything above `none` for a subprocess tool still DENIES —
  classification is bound now so C3b can honor it, but C3a-1 runs no subprocess.)
- missing/malformed field → **deny**. `capability_lease.attenuate` gains the subset/min
  semantics for path-sets and the ordered reduction for `exec_class` (string-equality-only
  constraints are insufficient — BLOCKING-7).
Mutable config may compare-and-deny, never supply a missing permission/path.

## 6. Deny-closed, strip, observability
- Deny-closed everywhere; `enforce()`/brokers never raise (outer fail-closed wrapper, C2
  pattern). `effective_strip` (monotonic `inherited_strip OR signed_strip`, reused from C2)
  drops write/secret permits; safe read survives.
- Each broker allow/deny/degrade emits a schema-conformant decision record (C2 audit pattern:
  stderr JSON behind flag-ON, logging wrapped so it can never change the decision). OTel spans =
  C5.

## 7. Ceiling (frozen exactly at freeze)
- NEW `ai-stack/switchboard/effect_brokers.py` — write + secret + read-classify brokers, one
  module, typed per-broker request objects, shared fail-closed wrapper; exec/network/delegate
  present only as explicit **deny stubs** (`confinement-unavailable` / deny-all).
- EDIT `ai-stack/switchboard/capability_lease_gate.py` — emit the closed-sum per-tool
  `AuthorityContext` (§2).
- EDIT `ai-stack/switchboard/switchboard.py` — store context; route write_file/store_memory
  through the broker; deny every exec/network/delegate/unclassifiable handler before invocation
  (§3).
- EDIT `scripts/ai/lib/capability_lease.py` (attenuate semantics) +
  `scripts/ai/lib/capability_lease_issuance.py` + lease schema + first-party manifest — signed
  classification (§5).
- NEW decision schema; NEW test suite (all §8 acceptance); NEW
  `config/effect-broker-defaults.json` (compare-only DENY tripwire).
Multi-file, security-critical, kernel-syscall-adjacent ⇒ **cheapest-eligible implementer at
activation (Claude fast tier, Rule-17 override recorded), NOT local**; codex + local engaged for
grounding + independent review.

## 8. Acceptance bar (per-slice, offline-first)
- **F3 obligation 4 standalone:** out-of-scope write does not exist/change across the §4
  adversarial set, including the `openat2`-absent fallback.
- per-tool context: tool B cannot be judged under tool A's lease (BLOCKING-1 regression test).
- effect table (§3): each read-safe tool allowed; write tools allowed only via broker; every
  exec/network/delegate/unclassifiable tool denied with the exact reason.
- flag-composition truth table proven; flag-OFF byte-parity; brokers never raise.
- authority-unavailable: only the C2-built `AuthorityUnavailableContext` yields safe-read; every
  other "degraded"/missing/expired → total deny; no unsigned lease synthesized.
- config compare-only: mutating `config/effect-broker-defaults.json` or the manifest can only
  turn allow→deny, never deny→allow, per tool/effect.

## 9. Ceremony + DoD split (folds SHOULD-5)
Enforcement-tier, hash-bound: this design → confirmatory review → **freeze** (subject = this doc,
ceiling §7 incl. the §3 effect table, predecessor hashes incl. capability_lease.py /
capability_lease_issuance.py / capability_lease_gate.py @ 97131faa) → **single-use owner
activation** → build **flag-default-OFF** → independent review → commit. **This authorization
covers ONLY the default-OFF BUILD stage.** C3a-1 is **not "complete"** (packet §9 DoD) until a
later cycle turns the flag ON with a real request allowed/denied live + dashboard surface +
health-spider check + operator intervenability. Standing authorization does NOT activate it.

## 10. What C3a-1 explicitly does NOT do (deferred, own docs)
- **Delegation / A2A / quarantine-verify / global replay reservation / signed heartbeat / inbox
  changes** → **C3a-2** (BLOCKING-4, -5, -6, SHOULD-2), bound to the accepted C3a-1 hash.
- **Arbitrary subprocess / arbitrary-process writes under OS confinement** → **C3b** (bwrap
  cells; the APU perf measurement, packet §9 risk d).
- **Network profiles (the eight)** → **C4** after the threat pass.
- **OTel spans as truth** → **C5**.
