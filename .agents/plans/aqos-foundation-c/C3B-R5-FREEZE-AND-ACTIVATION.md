# Foundation C — C3b R5 Freeze & Owner Activation

> **ACTIVATED + CONSUMED 2026-07-30** — owner activation.grant event `ffd469a6` (agent=owner, owner-directed orchestrator-executed). Drift check CLEAN (subject 10494dca + all 7 predecessors + R4 gate PASS). Single-use key `…:v1:20260730` CONSUMED — R5 build in progress (Claude-fast). Orchestrator provisions the Ed25519 grant keypair (private→SOPS, public→tracked) + L2B re-pin at commit.


**Enforcement-tier + HIGH-STAKES.** R5 is the switchboard adapter that first MINTS a signed
execution grant and calls the runner — and where the **Ed25519 grant-signing private key** is
provisioned. Design is independently reviewed PASS (`c3b-r5-review/antigravity.md`,
`R5_DESIGN_REVIEWED_PASS`, light-model) + the **R4 performance gate is PASS** (APU acceptance
`de0ea80e`). This packet FREEZES the subject and defines the single-use owner activation for the R5
**build** (flag-default-OFF). Per owner directive 2026-07-30 (authorize→enforce→activate→validate→
dogfood; codex verifies all slices on Aug-4 return), R5 proceeds now with codex auditing on return.

## Frozen subject
- **Idempotency key:** `aqos-foundation-c:c3b:r5-switchboard-adapter:v1:20260730`
- **Subject:** `C3B-R5-DESIGN-AND-AUTHORIZATION.md` SHA-256
  `10494dcafefeea0a562add71186b5f3f7fa85a6a7f4ab5819338ce3ef9e53cd8`
- **Build-base HEAD:** `6b61c662d7b4292fa9e1dea2d510e13d8207b20e` (verify unchanged before build).
- **R4 gate:** PASS (C3B-R4-ACCEPTANCE-REPORT-20260730.md; clone p95 0.098s / spawn 0.9ms / RSS
  0.2MiB / teardown 1.68-2.4ms — all under budget). REQUIRED precondition, satisfied.
- **Predecessor hashes (unchanged at build time):**
  - `scripts/ai/lib/execution_grant.py` → `29e9c1d6d2fa5cc7…` (R1; the sign/verify surface)
  - `scripts/ai/lib/execution_cell_clone.py` → `a706f1270dbfce37…` (R2)
  - `ai-stack/switchboard/execution_cell_runner.py` → `a01aa7e81b29c063…` (R3)
  - `ai-stack/switchboard/capability_lease_gate.py` → `3e92d2fe97a1ea8b…`
  - `ai-stack/switchboard/switchboard.py` → `98823202d4ffd38a…` (R5 EDITS it → L2B re-pin)
  - `scripts/ai/lib/capability_lease.py` → `a6f923924071618b…`
  - `config/first-party-tools.json` → `a17650f228b4ff17…`

## What activation authorizes (the R5 ceiling — flag DEFAULT-OFF)
Per design §6:
- NEW `ai-stack/switchboard/execution_cell_adapter.py` — grant minting (Ed25519 sign via the SOPS
  **private** key), UDS client to the R3 runner, typed-result handling, deny-closed wrapper.
- EDIT `ai-stack/switchboard/switchboard.py` — the guarded adapter after C2 admission
  (mint→submit→project), flag-gated (NEW `CAPABILITY_CELL_ADAPTER` default "0"), flag-OFF byte-parity.
  **L2B golden re-pin for switchboard.py in the same commit.**
- **Ed25519 grant keypair provisioning:** generate the keypair; **private → SOPS `/run/secrets/
  aq-grant-signing-key`** (declared in secrets.nix, root:ai-stack 0440 — mirrors aq-lease-signing-key);
  **public → tracked config** (`config/grant-signing-public-key`, non-secret) that the R3 runner loads.
  Key-unavailable ⇒ no grant minted ⇒ deny (authority-degrade). DEV key rejected by the prod runner.
- EDIT Nix: switchboard credential access to the private key (LoadCredential/group) — **hardening
  unchanged** (RestrictNamespaces/NoNewPrivileges/caps intact); runner client-group membership.
- NEW receipt/projection schema + dashboard Service-Coverage card + NEW AQ-QA phase-0 check
  (dual-harness registered: phase0.py results.extend AND _aq-qa-bash).
- EDIT `config/env-contract.yaml` — `CAPABILITY_CELL_ADAPTER` (default "0").
- NEW `scripts/testing/test-execution-cell-adapter.py`.
- **MUST NOT:** alter C2 admission semantics; weaken switchboard/runner hardening; handle/forward an
  API key; route to a non-intended provider; touch R1/R2/R3 frozen enforcement code (consume only);
  turn the flag ON or route real traffic (that is a further owner act = R6 canary).
- **Implementer:** cheapest-eligible (Claude-fast, Rule-17 — high-stakes crypto/UDS/adapter above
  local's envelope); Opus independent review; codex confirmatory audit on Aug-4.

## Owner activation (single-use — the step only you can take)
```
scripts/ai/aq-event emit --agent owner --type activation.grant \
  --subject aqos-foundation-c-c3b-r5-switchboard-adapter \
  --payload '{"idempotency_key":"aqos-foundation-c:c3b:r5-switchboard-adapter:v1:20260730","subject_design_sha256":"10494dcafefeea0a562add71186b5f3f7fa85a6a7f4ab5819338ce3ef9e53cd8","build_head":"6b61c662d7b4292fa9e1dea2d510e13d8207b20e","r4_gate":"PASS","predecessors":{"execution_grant":"29e9c1d6d2fa5cc7","execution_cell_clone":"a706f1270dbfce37","execution_cell_runner":"a01aa7e81b29c063","capability_lease_gate":"3e92d2fe97a1ea8b","switchboard":"98823202d4ffd38a","capability_lease":"a6f923924071618b","first_party_tools":"a17650f228b4ff17"},"implementer":"claude-fast","window_hours":24,"note":"R5 switchboard adapter + Ed25519 grant signing, flag CAPABILITY_CELL_ADAPTER default-OFF; L2B re-pin; codex audits on return"}'
```
After you emit it, the orchestrator verifies the drift check (subject + predecessors + HEAD unchanged
+ R4 PASS), routes the cheapest-eligible implementer to build EXACTLY the ceiling flag-default-OFF,
independently reviews, re-verifies switchboard hardening unchanged, re-pins L2B, runs tier0, commits.
Turning `CAPABILITY_CELL_ADAPTER` ON + routing real cell effects is a FURTHER owner act (R6 canary).

## Note on the enforcement ladder after R5
R5 (flag-OFF build) wires the runner into a guarded, still-off path. Turning it ON (R6) makes the
switchboard actually route admitted cell-effects through the R3 bwrap runner — the point where the
whole C3b confinement spine starts doing real work. That step gets its own validation + dogfood cycle.
