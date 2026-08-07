---
title: "Foundation C — C2 scheduler-context issuer FREEZE (Q-C6-1)"
slice: "C2-SCI"
kind: "FREEZE (hash-bound; build gated on owner activation)"
date: "2026-08-07"
frozen_design_sha256: "c934db23474cb6a42a0b32eae9b1c29a510965f2c4b140672c71bc422e35e242"
build_head: "411ddd92b8fce229293e098f849f21240e729f63"
---

# C2 scheduler-context issuer — FREEZE

Frozen at design **rev4** (SHA-256 `c934db23…242`), binding review PASS. Build gated on a single-use OWNER
build-activation grant (below). Drift of the frozen design bytes or the anchored baseline ⇒ re-freeze.

## Review chain (independent; Rule 18)
- rev1 REQUEST_REVISION → rev2 (FAIL — assumed asymmetric lease that didn't exist) → rev3 (ALA built) →
  **rev4** (ALA ACTIVATED + baseline re-anchored).
- **rev4 binding review = PASS** (fresh Claude flagship, Codex-substitute; `…/c2-scheduler-context-issuer-rev4-review/fresh-flagship.md`):
  all 4 re-anchored hashes match byte-for-byte, all NEW files absent by design, all 7 points SOUND, no
  fail-open/oracle/fail-closed-breakage. Two LOW notes folded (line ref → :552; slot_queue single-use
  forward-looking → issuer-side `{lease_id, grant_digest}` ledger is the authoritative 1:1).
- Advisory (non-gating, fold on return): local Qwen + Antigravity.

## Anchored baseline (verify at build; drift ⇒ re-freeze)
| Op | Path | Pre-build SHA-256 |
|---|---|---|
| EDIT | `ai-stack/switchboard/capability_lease_gate.py` | `0686c6faa5a33306e0037f7f32a1b317ec76e2a2fcd33a6ada03d5ee85ed8cc8` |
| EDIT | `scripts/ai/lib/dispatch.py` | `1b083b1025877385cb4e295234edd23a61a85aae554393fb87792c732e01dd92` |
| EDIT | `nix/modules/services/default.nix` | `c3b6d18e26f303b4f58aabc3869ed30bb95a20c274d9badb1b4813bccdec7ce4` |
| NO EDIT | `nix/modules/services/switchboard.nix` | `9b090af1c662cc9aa1e52b5d9a270e197461140b8c7c8e0ff9cec5627c93dfba` (post-ALA-flip; NOT edited by this slice) |
| NEW | `scripts/ai/lib/scheduler_context_issuer.py` · `scripts/ai/lib/scheduler_context_transport.py` · `nix/modules/services/c2-scheduler-context-issuer.nix` · `config/aqos/c6-scheduler-signer-keys.json` · `config/schemas/scheduler-lease-gate-decision.schema.json` · `scripts/testing/test-scheduler-context-issuer.py` · `scripts/testing/test-c2-sci-service-coverage.py` | absent (design §1) |
| EDIT | `scripts/testing/harness_qa/phases/phase0.py` · `dashboard/backend/api/routes/aistack.py` · `assets/dashboard.js` | (hashes at build) |

SOPS: add `c6-scheduler-context-signing-key` (Ed25519 private) → `/run/secrets/…` owned by the issuer
principal `0400`; **pattern (HARD): adding a key to secrets.nix MUST be followed by `sops <file>`** or the
stack cascades.

## Build note — SIZE + decomposition
This is a LARGE slice (a NEW confined service + UDS transport + signer authority + two gate/dispatch edits
+ 2 new config files + tests + dashboard). Larger than the enforce-verify envelope. Recommended
decomposition for the implementer (all default-OFF, each orchestrator-verified):
- **B1**: `scheduler_context_issuer.py` (mint + sign + `verify_authoritative`-verify the presented lease +
  OBLIG-1 expiry/epoch + single-use ledger) + `scheduler_context_transport.py` + `test-scheduler-context-issuer.py`.
- **B2**: `c2-scheduler-context-issuer.nix` (confined default-OFF service, SOPS key, UDS) + `default.nix`
  import + `c6-scheduler-signer-keys.json` + schema.
- **B3**: `capability_lease_gate.py` outbound client (on ALLOW) + `dispatch.py` authenticated ingress —
  both flag-gated `CAPABILITY_SCHEDULER_CONTEXT_ISSUER=0`, byte-parity flag-OFF.
- **B4**: Service Coverage — `test-c2-sci-service-coverage.py` + phase0 registration + dashboard card.

## Owner build-activation grant (single-use; OWNER emits — orchestrator MUST NOT self-emit)
```
scripts/ai/aq-event emit --agent owner --type activation.grant \
  --subject c2-scheduler-context-issuer-build \
  --payload '{"idempotency_key":"c2-scheduler-context-issuer-build-20260807","subject_design_sha256":"c934db23474cb6a42a0b32eae9b1c29a510965f2c4b140672c71bc422e35e242","build_head":"411ddd92b8fce229293e098f849f21240e729f63","predecessors":["enforce-asymmetric-verify-build","ala-rev4-minter-activated"],"implementer":"sonnet","window_hours":48}'
```
`implementer: sonnet` per-sub-slice (Rule 17); the confined-service + crypto-transport subslices may
warrant a stronger tier if a subslice proves complex — record any deviation. Hash-bound single-use owner
act, NOT standing authority.

`RECORD: FROZEN. No implementation, service enablement, key material, flag flip, or activation until the owner grant is emitted.`
