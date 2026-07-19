# QPPR-A1 Amendment 2 implementation authorization

**Authorization ID:** `auth-qa-provider-probe-reliability-a1-am2-20260719`
**Idempotency key:** `qa-provider-probe-reliability:a1:host-adoption:am2:20260719`
**Status:** **PREPARED_ONLY — IMPLEMENTATION NOT AUTHORIZED**
**Prepared:** 2026-07-19
**Single use:** consumed by the first complete exact three-file candidate report after activation

## 1. Exact subjects

This authorization is valid only with the exact frozen amendment and the pair's later independent
review. It binds:

| Subject | SHA-256 |
|---|---|
| A1-AM2 design amendment | `2d6d7e490b70d307ff6c3d5daf1d89c0ab85bba8cc331e8f8491be1aacb309f9` |
| A1-AM1 authorization | `5f992de921103870572cd765178e1a358e308a4ed7061efbb471fbfe499ad322` |
| A1-AM1 independent `REQUEST_REVISION` | `d9d44bc37b3a3415d2a2805b115a01bfe808276cdf8ceab8b33f84a935bdaff9` |
| adoption design | `44b600bfb3a22e05205c0babb9a72e1ed02c6f84afd71127a5a71afb99c79f18` |
| rebind amendment | `51200b64ff2f859e1ba225fc238ede8fd81aa403c9ac2a9efc97000bb51477dc` |
| final rebind review | `eeb77e63fe429a2e521d315c806dfb6d0c51d63f5386961df8b4ee8983cb0662` |
| accepted result/heartbeat schema | `1acaa61d4b3fe2737a513112c49578bf5b596c04f4916f4e4647e8e7516b7ac4` |
| accepted policy | `2cbe6e350f35cd9e0831186df31f9631a10c1e838fb0246fc1f56828abb4a6af` |
| accepted process owner | `ceef8fbe3ba3688ff60525c68167f914500959012e7345692f09f37f6ce0b38e` |

Any mismatch is a hard stop.

## 2. Exact three-file ceiling and predecessors

| # | Operation | Path | Exact current predecessor |
|---:|---|---|---|
| 1 | MODIFY | `scripts/testing/qa-provider-probe.py` | `755b730d6d7446d76f21933d2e273ca4ed7f8f65a808672e532caab007b5d0ab` |
| 2 | MODIFY | `scripts/testing/harness_qa/core/result.py` | `4c72e8aa658a67a5168fb9817a21a247c596ac29aa55b7fd776d5f18f0320776` |
| 3 | MODIFY | `scripts/testing/test-qa-provider-probe-adoption.py` | `f7e286dfa23ef3b22eea713e1ec4b9b350c3e5e4b29ba4a0098d9d4f0eb7123c` |

The other five A1 candidate paths must retain the exact hashes frozen in the amendment. A fourth
candidate path, substitution, or predecessor drift is a hard stop.

## 3. Exact grant after owner activation

One named bounded implementer may correct only the five defects and add only the adversarial tests
specified in `A1-AM2-DESIGN-AMENDMENT.md` sections 4 and 5. The correction must produce a synchronous,
idempotent, one-shot terminal join that is completed or cancelled before signal redelivery/handler
return/ordinary continuation; full closed result/profile/sequence validation; canonical missing-ID
failure before side effects; pre-mutation validation of an existing lock inode; and an exact four-
record policy-ordered closed details serializer.

The implementer must preserve all previously passing A1 behavior and the accepted C1A/C1B contracts.
Tests remain fixture-only and offline. No real provider executable, credential, network, Phase-0 live
run, heartbeat/evidence activation, API, browser, deployment, traffic, cutover, rollback, or A2 work
is granted.

## 4. Workflow compatibility, stops, and completion

The product ceiling is exactly three paths. Canonical session, skill-load, intent, resume, pulse,
handoff, and delegation/task-registry operations are orchestration control-plane evidence outside
that ceiling only as defined in the amendment section 6. They must not contain product code or be
staged/committed with AM2. They do not permit manual plan, policy, registry, authorization, or review
edits by the implementer.

Stop on every condition in the amendment section 7, including a fourth candidate path, hash drift,
foreign overlap, schema relaxation, late/background writer, second terminal writer, unbounded wait,
canonical ID fabrication, unsafe lock mutation, open serializer, real provider/network/live action,
new dependency/env/port/store/route/card, staging, commit, deletion, delegation, or self-acceptance.

The implementer reports all three final hashes, verifies the five frozen path hashes are unchanged,
records root cause and tradeoffs, and provides exact offline focused/syntax evidence. An independent
exact-hash reviewer must verify the complete eight-file A1 candidate and issue a final `PASS`. Only
the orchestrator may then run the proportionate governance gate, stage, and commit.

Before implementation, an independent flagship reviewer must pass this exact authorization and its
bound amendment. The owner must explicitly activate this authorization's exact SHA-256, name exactly
one implementer, provide an activation timestamp and expiry no more than 24 hours later, and affirm
the three-file ceiling and all stops. Broad or prior authorization does not activate AM2.

A2 remains blocked and non-activatable until A1-AM2 is independently accepted and committed, then
must receive its separate exact post-A1 adjacency rebind, review, and owner activation.

`RECORD: PREPARED_ONLY. QPPR-A1-AM2 implementation, A2, and every live action remain unauthorized.`
