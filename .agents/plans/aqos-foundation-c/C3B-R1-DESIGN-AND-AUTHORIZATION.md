---
title: "Foundation C C3b R1: Pure Grant Schema + Classification — Design Packet"
slice: "C3b / R1"
status: "R1_REVIEWED_PASS"
review: "antigravity/gemini (independent, codex-substitution) PASS — 9/9 obligations CLOSED, SF-1/2/3 resolved; 1 SHOULD-FIX + 2 NICE-TO-HAVE folded. Opus-verified the load-bearing claims (ed25519 import, epoch anchors, is_normalized). codex confirmatory audit queued for Aug-4 return."
revision: 1
kind: "design-only"
implementation_authorization: "NONE"
activation_authorization: "NONE"
author: "Opus (codex-substitution — codex usage-limited to 2026-08-04; catch-up audit queued)"
predecessors:
  - "C3b R0 design PASS (C3B-R0-REVIEW-OPUS.md)"
  - "C2 tool-lease gate, flag OFF (97131faa)"
successors:
  - "C3b R2 self-contained clone primitive"
---

# Foundation C — C3b R1: Pure Grant Schema + Classification

## 0. Provenance & authority
Authored by Opus as a **codex-substitution** (codex usage-limited until 2026-08-04; recorded in
`AGENT-CATCHUP-QUEUE.md`). Independent binding review routed to the Antigravity/Gemini lane
(codex's usual seat); codex confirmatory audit is queued for its return (advisory unless it
surfaces a real defect → bounded follow-up, never rewrite). **This packet is DESIGN-ONLY.** It
authorizes no code, sockets, clones, bwrap, Nix, runtime, activation, or commit. It folds R0
review findings SF-1 and SF-3; SF-2 (global userns) is out of R1 scope and recorded as a pre-R3
grounding task.

## 1. Scope (R0 §5 R1 row — bounded)
Define, as **closed schemas + pure functions with golden vectors**: (1) the execution-grant
schema, (2) grant verification pure functions, (3) multi-effect + trusted-path classification
pure functions. **Out of scope (belongs to later R-stages):** UDS/sockets, git clone/worktree,
bwrap, Nix/service changes, any filesystem access, any live traffic. R1 code (when later
authorized) is pure/offline and side-effect-free.

## 2. The execution grant (closed schema)
The grant is a **new artifact distinct from the CapabilityLease**. It is a signed *projection of
a verified lease* plus execution-cell-specific fields, minted by C2's gate at admission time. It
is NOT the lease and is NOT rehydrated from mutable lease state later.

Current lease signed fields (verified in `capability_lease_issuance.py`): `issued_to, issued_at,
expires_at, permissions, input_schema, output_schema, trust_tier, zero_trust_behavior,
cost_class, parent_lease_id, revocation_epoch, signature`. The grant references the lease and
adds execution scope:

| Field | Type / invariant |
|---|---|
| `grant_schema_version` | int; unknown version → deny (no forward-compat guessing) |
| `grant_id` | unique, collision-resistant (≥128-bit); the replay-reservation key |
| `lease_id`, `task_id`, `request_id` | bound identities copied from the verified lease/request |
| `issued_at`, `expires_at` | RFC3339 UTC; `now ∉ [issued_at, expires_at)` → deny |
| `revocation_epoch` | int; compared to the authoritative source (§5) |
| `base_revision` | full 40/64-hex Git OID (never a symbolic ref); syntactic-validated in R1 |
| `effect_set` | closed signed set of `{effect, scope}` (see §4) |
| `exec_class` | enum `none < sandbox-required`; `unsandboxed-authorized` NOT accepted in C3b |
| `trusted_repo_id` | opaque id of the trusted clone source (resolved in R2, not R1). R1 MUST validate it is a non-empty, syntactically-valid string (bounded charset + min length); a blank/whitespace id → `grant-malformed` deny, so it can never be passed as a bypass target into R2 (antigravity SHOULD-FIX 2026-07-29) |
| `logical_paths` | signed allowlist of cell-relative logical paths (classified in §4; resolved R2) |
| `resource_limits` | `{timeout_s, max_output_bytes, cell_class}` bounded ints |
| `grant_digest` | canonical digest over all fields except `signature` (see §3) |
| `signature` | detached signature over the canonical serialization (see §3) |

Any missing / malformed / unknown-typed field → typed `grant-malformed` deny. No defaulting.

## 3. Signing model — SF-1 decision: **asymmetric Ed25519** (justified)
**Decision: the execution grant is signed with Ed25519 (asymmetric), NOT the symmetric HMAC used
for C0–C2 leases.** Rationale (folds R0 review SF-1): the cell runner is a *new privileged
boundary* — it alone is granted userns to construct cells. With symmetric HMAC the runner must
hold the signing key to verify, so a compromised runner could **mint its own grants**. With
Ed25519 the **gate/issuer holds the private key** (SOPS `/run/secrets/`, same secret-handling as
today; still "no remote/API keys" — this is a local key) and the **runner holds only the public
verify key** (non-secret). A compromised runner can verify but cannot forge. Feasibility verified:
`cryptography`'s `ed25519` is importable in the pinned env (`from
cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey` → present); PyNaCl is
NOT (do not depend on it).
- **Canonical serialization:** reuse `capability_lease.canonical_payload`'s discipline (recursive
  sorted keys, every field except `signature`, stable UTF-8/JSON) so the signed bytes are
  deterministic; `grant_digest` = SHA-256 of that canonical form.
- **Key separation:** the grant-signing keypair is distinct from the lease HMAC key. Loss of the
  lease key cannot mint grants; loss of the grant *public* key discloses nothing.
- **Degrade (consistency with C2 §S4):** if the grant private key/authority is unavailable at
  admission, the gate issues **no grant** → the runner receives nothing → cell denied. There is
  no unsigned or symmetric fallback grant. (A dev/test key, if used, is a distinct public key the
  production runner does NOT trust — mirrors C2's DEV-key degrade; proven by a golden vector.)

## 4. Classification (pure) — SF-3 folded
### 4.1 Multi-effect classification
`effect_set` is a **closed signed set**; a grant is classifiable iff every element is a known
`{effect, scope}` from the closed vocabulary and mutually consistent. Vocabulary for C3b:

| effect | R1 pure-classification result |
|---|---|
| `read` / `deterministic-validate` | allowed-class (scope = declared read paths) |
| `write` | allowed-class (scope = declared logical output paths) |
| `subprocess` | allowed-class ONLY as a bounded command descriptor (scope = the descriptor) |
| `network`, `delegate` | **deny-class** — no C3b grant may carry them (require C4) |
| `secret`, `device`, `mount`, `privilege`, `host-process`, `arbitrary-env` | **deny-class** |

Unknown / omitted / duplicated / contradictory (e.g. `write` on a `read`-only scope) /
unrepresentable effect → typed `classification-ambiguous` deny (conservative). The classifier is
a **pure function**: `classify(effect_set) -> Classification | Denial`; it reads no filesystem
and no config at decision time.

### 4.2 Trusted-path classification (pure, no FS access in R1)
`classify_paths(logical_paths, declared_scopes) -> PathPlan | Denial`. Pure syntactic checks only
(real resolution is R2/R3): reject absolute host paths, `..` traversal, any symlink-escape marker,
NUL/control bytes, and Unicode forms that are not NFC-normalized (use stdlib
`unicodedata.is_normalized("NFC", s)` — verified available — NOT a custom regex, which invites
edge-case escapes; antigravity NICE-TO-HAVE) or that collide under
casefold/normalization; every path must fall under a signed logical allowlist prefix by
**component-aware containment** (never string-prefix — `/a/bc` is not under `/a/b`). Missing/empty
allowlist → deny.

### 4.3 SF-3 initial tool classification (conservative; manifest is NOT authoritative)
The R0-review SF-3 crux: `config/first-party-tools.json` effect flags are **known inaccurate** vs
real handlers (issues-backlog 2026-07-29: tier-3 tools do network/subprocess; `store_memory` is an
HTTP POST; `computer_use` writes at import). R1 therefore classifies **conservatively from a
handler audit, not the manifest**, and treats any tool lacking an accurate signed classification as
deny. Initial C3b-eligible mapping (to be confirmed by the R2/R5 handler audit before any tool is
actually routed):

| tool | real effect (audited) | C3b R1 class |
|---|---|---|
| `write_file` | filesystem write | `write` → proposed-bytes descriptor (cell-relative) |
| `run_command` | subprocess (+ net + write) | `subprocess` bounded descriptor, **network stripped** → the command may run in a cell but any net egress is denied (C4); if the command intrinsically needs net → deny |
| `read_file`, `list_files`, `search_files` | read (search_files/git via subprocess) | read-validate IF proven pure-read; `search_files`/`git_*` that shell out → `subprocess` descriptor |
| `store_memory`, `get_hint`, `query_context`, `query_aidb`, coordinator-query tools | HTTP to coordinator (network) | **deny in C3b** (network → C4) |
| `delegate_to_remote` | network + delegate | **deny in C3b** (C3a-2 + C4) |
| `screenshot`, `get_screen_size` | subprocess + write (+ import-time mkdir) | **deny in C3b** until the import-time write bug is fixed and effects audited |
| `prsi_orchestrate`, `validate_before_commit` | orchestration/subprocess | **deny in C3b** (multi-effect/unaudited) |

**No tool is trusted from the manifest's `write:False/net:False`.** An accurate signed
per-handler effect inventory is a stated R2/R5 prerequisite (backlog item); until then the runner
denies any tool not in a conservatively-audited allow set.

## 5. Verification pure functions (deny-closed, never raise)
All return a typed result; any exception is caught → total deny (C2 fail-closed pattern).
- `verify_signature(grant, public_key) -> ok | bad-signature` — Ed25519 verify over the canonical
  serialization; `grant_digest` recomputed and compared.
- `verify_freshness(grant, now) -> ok | expired | not-yet-valid` — half-open `[issued_at, expires_at)`.
- `verify_schema_version(grant) -> ok | unknown-version` — closed known set.
- `verify_epoch(grant, current_epoch) -> ok | stale-epoch` — authoritative source is
  `capability_lease_gate.resolve_current_epoch` reading `config/capability-lease-epoch` (verified:
  gate lines 172 / 84). `current_epoch is None` (unreadable/absent) → **stale/deny**, never skip.
  R1 freezes this epoch-source API+hash as its dependency; a change requires a reviewed epoch-source
  contract. **Observability (antigravity NICE-TO-HAVE):** when the epoch read swallows a
  file/parse/permission exception to return `None`, it MUST emit a diagnostic warning to logs/
  telemetry — a silent `None`-deny hides an operational fault ("can't manage what you can't measure").
- `reserve_replay(grant_id) -> reserved | replayed` — **uniqueness domain = `grant_id`** (globally
  unique; NOT task-scoped — folds R0 §7 replay finding). R1 defines the pure reservation *contract*
  and its `reserved → committed | failed` state semantics; the durable store is R3 (the pure
  function takes a reservation-set interface).
- `verify_grant(grant, public_key, now, current_epoch, reservation) -> VerifiedGrant | Denial` —
  composes the above in a fixed order; **any** failure → typed denial; only an all-pass yields an
  immutable `VerifiedGrant` (the sole object later stages accept, mirroring C3a's per-tool context).

## 6. Golden vectors (R1 acceptance evidence)
A frozen vector file maps each input to its exact typed outcome. Minimum set:
- one fully-valid grant → `VerifiedGrant`.
- per-field single-mutation tamper (each of §2's fields) → `bad-signature` or `grant-malformed`.
- expired, not-yet-valid, unknown `grant_schema_version`, stale/absent epoch, replayed `grant_id`.
- each deny-class effect (network/delegate/secret/device/mount/privilege/host-process/arbitrary-env)
  → `classification-ambiguous`/deny; each contradictory/duplicated effect → deny.
- each path-escape class (abs host, `..`, symlink-escape, NUL, non-NFC, casefold-collision,
  component-prefix-not-containment) → path deny.
- DEV/test signing key verified against the production public key → deny (degrade proof).
Every vector is deterministic and offline. No vector is skipped or averaged.

## 7. R1 → R2 handoff
R2 (self-contained clone primitive) consumes: the immutable `VerifiedGrant`, its `base_revision`
(to clone at the verified OID), the `PathPlan` (to rebase logical→cell paths against the fixed
cell root), and `resource_limits`. R2 performs the first filesystem/git actions; R1 hands only
pure, verified data. R1 introduces **no** socket, clone, bwrap, or Nix surface.

## 8. Review obligations (independent reviewer must test, not just approve)
1. grant schema is closed; every missing/unknown/malformed field denies.
2. **SF-1**: Ed25519 asymmetric signing is correctly specified so a key-less/compromised runner
   cannot forge a grant; key separation from the lease HMAC; no symmetric/unsigned fallback;
   degrade issues no grant.
3. replay uniqueness domain is `grant_id`, globally unique, with `reserved→committed|failed`.
4. epoch source is the real `resolve_current_epoch`/`config/capability-lease-epoch`; `None`→deny.
5. **SF-3**: classification is conservative, manifest-distrusting; every network/subprocess/
   multi-effect/unaudited tool denies; no tool trusted from `write:False/net:False`.
6. path classification is pure + component-aware; every escape class denies.
7. all verify functions are pure, deny-closed, never-raise; only all-pass yields `VerifiedGrant`.
8. golden vectors cover every deny path with exact typed outcomes.
9. R1 introduces no socket/clone/bwrap/Nix/FS surface (scope containment).

## 9. Freeze criteria
Freeze pins: this document; the grant JSON schema + canonical-serialization rule; the Ed25519
verify contract + key-separation statement; the pure-function signatures + typed denial set; the
golden-vector file; the frozen `resolve_current_epoch`/epoch-path dependency hash; and the SF-3
audited-tool classification table. Any changed reviewed byte → re-review. **R1 PASS is not
implementation authorization**; R1 pure-function *code* (when later built) is a cheapest-eligible
implementer slice, and R2+ each need their own hash-bound design and (for enforcement) single-use
owner activation.

## 10. Deferred (recorded, not in R1)
- **SF-2 global userns** (`security.unprivilegedUsernsClone`) — pre-R3 host grounding + owner
  ratification; Nix/host, not R1.
- Durable replay store, clone/rebase, bwrap, runner service — R2/R3.
- Accurate signed per-handler effect inventory to replace the manifest — R2/R5 prerequisite
  (backlog 2026-07-29).

**Requested reviewer result:** `PASS` / `FAIL` / `REQUEST_REVISION` against this R1 scope and the
§8 obligations. No review outcome authorizes build or activation.
