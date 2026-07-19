# QPPR-A1 Amendment 1 host-adoption implementation authorization

**Authorization ID:** `auth-qa-provider-probe-reliability-a1-am1-20260719`
**Idempotency key:** `qa-provider-probe-reliability:a1:host-adoption:am1:20260719`
**Status:** **PREPARED_ONLY — IMPLEMENTATION NOT AUTHORIZED**
**Prepared:** 2026-07-19
**Single use:** consumed by the first complete exact eight-file candidate report

## 1. Exact bound subjects

| Subject | SHA-256 or Git object |
|---|---|
| `A1-A2-ADOPTION-REBIND-AMENDMENT.md` | `51200b64ff2f859e1ba225fc238ede8fd81aa403c9ac2a9efc97000bb51477dc` |
| `A1-A2-ADOPTION-DESIGN-PACKET.md` | `44b600bfb3a22e05205c0babb9a72e1ed02c6f84afd71127a5a71afb99c79f18` |
| original `A1-IMPLEMENTATION-AUTHORIZATION.md` | `336f454aa0e9c5e31f7fc7f10c5fee6a41d10d4e54588d8572a6c1ed9ec738e9` |
| C1A commit | `52b0a0716ea2e008c2ca1b137c689482e2995543` |
| `C1A-IMPLEMENTATION-ACCEPTANCE.md` | `73808146d65e877a15e0396f8e8adb5b726b986f7a01baccf5a5aa14b21d1987` |
| final heartbeat schema | `1acaa61d4b3fe2737a513112c49578bf5b596c04f4916f4e4647e8e7516b7ac4` |
| final C1A focused test | `4dc49ef8133cfa8ab22372ea5a3b402585e1b3a18a9bff75180fe338ae3efac7` |
| corrected C1B-AM1 commit | `f54cd8c8257a43dd8666209648d4976c323dfbff` |
| `C1B-AM1-IMPLEMENTATION-ACCEPTANCE.md` | `1373f508e80311c657e303ea8896616ac3aa943d923e3ccd6d0fd421b270c868` |
| final process owner | `ceef8fbe3ba3688ff60525c68167f914500959012e7345692f09f37f6ce0b38e` |
| final C1B focused test | `a17d70be7e9225435ac5cc28a13024d0a6a1885a56e149737775cfeafe1ee63b` |
| accepted policy | `2cbe6e350f35cd9e0831186df31f9631a10c1e838fb0246fc1f56828abb4a6af` |

Any mismatch is a hard stop. This single-use amendment supersedes the original A1 authorization's
unresolved prerequisite placeholders; it does not broaden the accepted adoption design.

## 2. Exact maximum-eight ceiling

| # | Operation | Path | Exact predecessor |
|---:|---|---|---|
| 1 | NEW | `scripts/testing/qa-provider-probe.py` | absent, including no symlink |
| 2 | MODIFY | `scripts/testing/smoke-flagship-cli-surfaces.sh` | `62705e40e0035e1f0c7d050f8e4ccd306a3343e01367468d3166c4a5ab97b261` |
| 3 | MODIFY | `scripts/testing/harness_qa/phases/phase0.py` | `fc43b959e2bbe6eb6753736df4818265616edace598d361fc93a5ddb929bf193` |
| 4 | MODIFY | `scripts/testing/harness_qa/core/result.py` | `d3272af4630a43bb2d0780074411a78339c7ed7cb3fb277892f18fb00c1ff8bd` |
| 5 | MODIFY | `scripts/testing/harness_qa/core/context.py` | `a2cf827b7d25c8ba234d87ae61de631145a67b821c2c086a9725ea0bab92cd80` |
| 6 | MODIFY | `scripts/testing/harness_qa/main.py` | `329627f7e417ddf7ead13a852860d8febeed85c111d1af9d41517b717356db37` |
| 7 | MODIFY | `scripts/testing/harness_qa/reporters/json_out.py` | `8629c57c7a5901871cca135c02f5a04d1a87a8250a9493316c56e6d8e0480fc5` |
| 8 | NEW | `scripts/testing/test-qa-provider-probe-adoption.py` | absent, including no symlink |

## 3. Exact grant after owner activation

One named bounded implementer may implement only adoption-design sections 3.1-3.4: the
policy-ordered sequential aggregate; stable-inode admission lock; reserved immutable invocation;
closed four-item result evidence through one serializer; C1A-valid atomic heartbeat driven only by
validated, monotonic C1B events and the one terminal join; direct Phase-0 check `0.6.1` adoption;
compatibility-shell delegation; and offline fake-provider adversarial tests. The exact Phase-0
integration evidence and lifecycle contract ship in this same atomic commit.

Tests use fixtures only. No real provider executable, credential, network, live QA run, dashboard,
API, deployment, or traffic action is permitted. Dashboard-safe execution remains an explicit
host-only `SKIP`, writes no heartbeat, and cannot become acceptance authority.

## 4. Stops, review, activation, and adjacency

All stops and exclusions in the original authorization and rebind amendment remain mandatory.
Additionally stop on any ninth file, target drift, foreign overlap, schema/policy/process-owner
change, synthesized or backward lifecycle state, second heartbeat/terminal writer, post-redelivery
write, non-four-item evidence, real provider resolution, shorter deadline, retry/fallback, new env/
port/dependency/store/route/card, Nix/service/deploy action, staging, commit, or deletion.

The implementer cannot delegate, stage, commit, deploy, or self-accept. It reports all eight final
hashes, root-cause/objective reasoning, important tradeoffs, exact focused offline evidence, and
explicit exclusions. An independent exact-hash reviewer must issue a final `PASS`; only the
orchestrator may then commit.

Before implementation, an independent flagship review must pass this exact authorization and its
bound amendment. The owner must then explicitly name this authorization's exact SHA-256, exactly
one implementer, an activation timestamp and expiry no more than 24 hours later, and affirm the
eight-file ceiling and stops. Broad preauthorization or the prerequisite acceptances do not
activate A1.

The accepted A1 commit must be followed immediately by separately rebound, activated, implemented,
accepted, and committed A2 with no unrelated intervening commit. Neither commit activates live
provider, API/browser, deployment, or traffic behavior.

`RECORD: PREPARED_ONLY. QPPR-A1/A2 implementation and every runtime/live action remain unauthorized.`
