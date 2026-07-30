---
title: "Foundation C C3b R5: Default-OFF Switchboard Adapter + Grant Signing — Design Packet"
slice: "C3b / R5"
status: "R5_DESIGN_REVIEWED_PASS — build blocked on single-use owner activation + R4 PASS (enforcement-tier)"
review: "antigravity/gemini (independent, codex-substitution) PASS — 7/7 obligations CLOSED, Q-R5-1..3 endorsed (distinct CAPABILITY_CELL_ADAPTER flag; key rotation tied to revocation_epoch; minimal noop/single-file-write/read-validate vocab). NOTE: light-model PASS on a HIGH-STAKES grant-signing/key-provisioning slice — codex confirmatory (Aug-4) is a required depth gate before activation."
revision: 1
kind: "design-only"
implementation_authorization: "NONE — enforcement-tier: requires single-use owner activation before build"
activation_authorization: "NONE"
author: "Opus (codex-substitution — codex usage-limited to 2026-08-04; catch-up audit queued)"
predecessors:
  - "C3b R3 runner built (ccbc0718), flag+enable OFF, Nix module live-validated (dormant)"
  - "R1 grant (f3a39f52), R2 clone (582113af); C2 tool-lease gate (97131faa)"
  - "R4 performance gate (must be PASS before R5 activation)"
successors:
  - "C3b R6 separate live-canary activation"
---

# Foundation C — C3b R5: Default-OFF Switchboard Adapter + Grant Signing

## 0. Provenance & authority
Authored by Opus (codex-substitution). Independent review → antigravity/gemini + codex-on-return.
**DESIGN-ONLY.** **R5 is ENFORCEMENT-TIER** — it is where the switchboard first MINTS a signed
execution grant and calls the runner, and where the Ed25519 **private** signing key is provisioned.
Per Rule 15 + the R0–R6 discipline, R5 IMPLEMENTATION requires a **single-use owner activation**
before any build, AND R4's performance gate must be PASS. Even after the build, the adapter ships
**DEFAULT-OFF** (byte-parity with pre-R5) — actually routing live effects is R6 (separate canary).
No deployment cutover here.

## 1. Scope (R0 §5 R5 row — bounded)
Deliver, all **default-OFF**: (a) a **guarded switchboard adapter** that, for a C2-admitted
cell-required effect, mints an R1 grant, submits it to the R3 runner UDS, and consumes the typed
result; (b) **grant signing + key provisioning** (Ed25519 private key via SOPS — no key in tracked
files); (c) **receipt projection** (runner typed receipts → PULSE/audit/dashboard, span-shaped,
low-cardinality); (d) **AQ-QA Service-Coverage integration**; (e) the **dashboard Service-Coverage
surface**. **Out of scope:** turning the feature on / routing real traffic (R6), network (C4),
auto-merge, any change to the R3 runner's enforcement code, any change to the C2 gate's admission
semantics (R5 consumes C2's verdict; it does not alter it).

## 2. The adapter seam (guarded, default-OFF)
- A NEW flag gates the whole adapter (reuse `CAPABILITY_EXECUTION_CELLS` OR a distinct
  `CAPABILITY_CELL_ADAPTER` — reviewer to choose; default **"0"**). Flag OFF ⇒ the switchboard path
  is **byte-for-byte identical to pre-R5** (parity-tested), the adapter is never imported/called.
- The adapter attaches AFTER C2 admission (`_admit_tool_call`) and R3's classification: only an
  effect classified (R1) as cell-required and admitted by C2 reaches the adapter. Everything C2
  denies is already denied; R5 never widens C2.
- On a cell-required admitted effect (flag ON): mint grant (§3) → connect the runner UDS (client
  group member) → send the signed grant → receive the typed result (GREEN diff-retained / RED /
  QUARANTINED / typed denial) → project the receipt (§4). **The switchboard never itself constructs
  a cell, runs bwrap, or creates a namespace** (that is the runner's sole job; the switchboard stays
  hardened, `RestrictNamespaces=true`, byte-parity anchor 4811326e unchanged). Any adapter/runner
  error → deny-closed (the effect does not happen), never a bypass.

## 3. Grant signing + key provisioning (the sharp edge)
R1 fixed SF-1: grants are **Ed25519 asymmetric** — the signer (gate/switchboard) holds the
**private** key, the runner holds only the **public** key. R5 provisions this keypair:
- **NO key in tracked files** (HARD security rule — Nix store is public). The **private** signing
  key is a **SOPS secret** decrypted to `/run/secrets/…` and read by the switchboard via systemd
  `LoadCredential=`/`/run/secrets` (the existing secrets pattern); it is NEVER in a tracked `.nix`,
  env literal, or repo path. The **public** key MAY be a tracked config value (it is non-secret) and
  is what the R3 runner already loads.
- Key generation/rotation is an **operator step** (documented), producing `{private→SOPS,
  public→tracked config}`; the switchboard signs with the private key at grant-mint time; the runner
  verifies with the public key. A DEV key (no production secret) → the switchboard mints DEV-signed
  grants that the production runner's public key REJECTS (mirrors C2's DEV-key degrade; proven by test).
- Signing is deny-closed on key-unavailable: if the private key is absent/unreadable, the adapter
  mints **no grant** → the effect is denied (never an unsigned or fallback grant). This is the
  authority-degrade posture (deny privileged, the effect simply does not run).
- The grant binds (R1 §2): base_revision (current trusted OID), effect_set + scopes (from the C2/R1
  classification), exec_class, logical_paths, resource_limits, a fresh unique grant_id, revocation_epoch
  (current), a bounded expiry. The switchboard is the sole minter; the UDS/runner never mint.

## 4. Receipt projection + observability
Runner typed receipts (admit/deny/GREEN/RED/QUARANTINED/rollback, low-cardinality — no grants,
paths, prompts, or high-card IDs) are projected to: PULSE (`aq-event` projection, consistent with
B3), the a2a/activation audit surface, and a **dashboard Service-Coverage card** exposing runner/
receipt state + denial/revocation counts. No secret or high-cardinality datum crosses to the
dashboard. This satisfies the "observable" DoD leg without waiting for C5 (OTel is still C5; R5
uses the existing projection surface).

## 5. AQ-QA Service-Coverage integration (R0 §8 requirement)
A NEW AQ-QA phase-0 check exercises the **full default-OFF adapter path**: grant mint → signature
→ UDS admission (SO_PEERCRED) → runner typed result → receipt projection → a typed denial fixture
AND a typed success fixture. A `/health` probe alone does NOT count (R0 §8). The adapter code, the
AQ-QA check, and the dashboard projection must be committed together (or in immediately consecutive
commits on the same branch); the sequence may not be released with any one absent.

## 6. Ceiling (frozen at R5 freeze; enforcement-tier)
- EDIT `ai-stack/switchboard/switchboard.py` — the guarded adapter (flag-gated; mint→submit→project),
  attached after C2 admission; flag-OFF byte-parity. (This changes the L2B-pinned switchboard.py →
  the `local-inference-l2b` golden manifest must be re-pinned in the same reviewed commit, as in C2.)
- NEW `ai-stack/switchboard/execution_cell_adapter.py` — grant minting (Ed25519 sign via the SOPS
  private key), UDS client, typed-result handling, deny-closed wrapper.
- EDIT Nix: the SOPS secret declaration for the private signing key (`secrets.nix` + `sops` re-encrypt
  — operator step) + the switchboard unit's `LoadCredential`/secret access for it; a tracked public-key
  config value; the runner's client-group membership for the switchboard identity (if not already).
  **`RestrictNamespaces=true` + the switchboard hardening stay unchanged** (only credential access added).
- NEW receipt/projection schema; EDIT the dashboard backend + a Service-Coverage card; NEW AQ-QA
  phase-0 check (registered in BOTH phase0.py `results.extend` AND `_aq-qa-bash`, per the dual-harness rule).
- NEW `scripts/testing/test-execution-cell-adapter.py` — offline: flag-OFF byte-parity; mint→sign→verify
  round-trip; DEV-key-rejected-by-prod-runner; key-unavailable → deny (no grant); deny-closed on runner
  error; receipt projection shape; the AQ-QA fixture path.
- **MUST NOT:** alter C2 admission semantics, the R3 runner enforcement code, R1/R2 frozen files, or
  weaken switchboard hardening; MUST NOT route real traffic or flip any flag/enable (R6).

## 7. Acceptance bar
- Flag OFF → switchboard byte-for-byte identical to pre-R5 (parity test); adapter never called.
- Flag ON (test harness): a C2-admitted cell-required effect → grant minted + Ed25519-signed →
  runner admits (public-key verify) → typed result → receipt projected. A DEV-signed grant →
  runner REJECTS. Key-unavailable → deny, no grant, effect does not run.
- The adapter never constructs a cell / runs bwrap / creates a namespace itself; any runner/adapter
  error → deny-closed (effect not performed), never a bypass; forced-remote invariant preserved
  (never a silent OpenRouter reroute).
- No secret / no key in any tracked file; the private key path is SOPS `/run/secrets` only.
- AQ-QA Service-Coverage check passes (typed denial + success fixtures, not just /health); dashboard
  card renders runner/receipt/denial/revocation without secrets or high-card IDs.
- switchboard.nix hardening (RestrictNamespaces/NoNewPrivileges/caps) unchanged except added
  credential access; R4 gate is PASS before activation.

## 8. Review obligations
1. flag-OFF byte-parity (adapter fully inert; switchboard path unchanged).
2. R5 never widens C2 admission; consumes C2's verdict; deny-closed on any adapter/runner error.
3. grant signing: Ed25519 private key from SOPS `/run/secrets` ONLY — no key in tracked files;
   key-unavailable → deny (no unsigned/fallback grant); DEV-key rejected by the prod runner.
4. the switchboard never constructs a cell / bwrap / namespace; runner stays the sole confiner;
   switchboard hardening unchanged (credential access only).
5. receipt projection is low-cardinality, secret-free; AQ-QA Service-Coverage exercises the full
   default-OFF path (not /health); dual-harness registration.
6. L2B golden re-pin for switchboard.py in the same reviewed commit (drift discipline, as C2).
7. no live traffic / no flag-or-enable flip / no deployment cutover (R6); R4 PASS is a precondition.

## 9. Ceremony (enforcement-tier)
design → independent review → freeze (subject = this doc; predecessor hashes R1/R2/R3 code + C2
gate + switchboard.py @ its commit; the SOPS secret name (not the key); the adapter protocol; the
AQ-QA check; the L2B re-pin plan) → **single-use owner activation** (hash-bound) → build
**flag-default-OFF** → independent review → commit (with L2B re-pin). Turning the adapter ON +
`enable=true` runner + `nixos-rebuild` is the FURTHER, separate R6 owner act. Standing authorization
does NOT activate R5. **R4 performance gate must be PASS before R5 activation.**

## 10. Open questions for review
- Q-R5-1: one adapter flag reused (`CAPABILITY_EXECUTION_CELLS`) vs a distinct
  `CAPABILITY_CELL_ADAPTER` — recommend distinct, so the runner-present and switchboard-routes-to-it
  states are independently controllable (defense in depth). Reviewer to confirm.
- Q-R5-2: key rotation/epoch — should the grant-signing keypair rotation be tied to the
  `revocation_epoch` counter, so a key roll also bumps the epoch (revoking in-flight grants)?
  Recommend yes; specify at R5 (design-level) even though rotation is an operator step.
- Q-R5-3: exactly which C2-admitted effects become cell-required in R5's first cut — recommend the
  minimal R1/R3 vocabulary only (single-file-write / read-validate), everything else stays denied /
  non-cell, deferring richer routing to a later reviewed slice.

**Requested reviewer result:** `PASS` / `FAIL` / `REQUEST_REVISION` against R5 scope + §8. No review
outcome authorizes build or activation; R5 build additionally requires single-use owner activation +
an R4 PASS.
