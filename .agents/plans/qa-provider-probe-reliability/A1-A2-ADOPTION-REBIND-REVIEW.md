# QPPR-A1/A2 adoption rebind — independent review

**Reviewed:** 2026-07-19
**Reviewer identity:** `codex-subagent-qppr-a1-a2-rebind-review`
**Reviewer role:** independent architecture, security, SRE, QA, and dashboard-contract reviewer
**Implementation authority:** none
**Overall verdict:** **PASS**

## Exact reviewed subjects

| Subject | Expected SHA-256 | Observed SHA-256 | Verdict |
|---|---|---|---|
| `A1-A2-ADOPTION-REBIND-AMENDMENT.md` | `51200b64ff2f859e1ba225fc238ede8fd81aa403c9ac2a9efc97000bb51477dc` | `51200b64ff2f859e1ba225fc238ede8fd81aa403c9ac2a9efc97000bb51477dc` | **PASS** |
| `A1-AM1-IMPLEMENTATION-AUTHORIZATION.md` | `7fdedc347ce536a27b340ca609140db6fc63d55b13d4662bafe03526147a6e9e` | `7fdedc347ce536a27b340ca609140db6fc63d55b13d4662bafe03526147a6e9e` | **PASS / PREPARED_ONLY** |
| `A2-AM1-IMPLEMENTATION-AUTHORIZATION.md` | `15194e07296b068d99ecc3838a929432d671d46d01c45d0800cdffb0cd261c17` | `15194e07296b068d99ecc3838a929432d671d46d01c45d0800cdffb0cd261c17` | **PASS / NOT ACTIVATABLE** |

No reviewed subject was edited by this reviewer.

## Prerequisite and lineage verification

The rebound package closes the original C1A/C1B placeholders without changing the accepted A1/A2
design or either inventory ceiling:

- Commit `52b0a0716ea2e008c2ca1b137c689482e2995543` exists, is an ancestor of the current branch, and
  contains the exact C1A acceptance, final heartbeat schema, and focused lifecycle test bytes bound
  by the amendment: `73808146d65e877a15e0396f8e8adb5b726b986f7a01baccf5a5aa14b21d1987`,
  `1acaa61d4b3fe2737a513112c49578bf5b596c04f4916f4e4647e8e7516b7ac4`, and
  `4dc49ef8133cfa8ab22372ea5a3b402585e1b3a18a9bff75180fe338ae3efac7`.
- Commit `f54cd8c8257a43dd8666209648d4976c323dfbff` exists, is an ancestor of the current branch, and
  contains the exact corrected C1B-AM1 acceptance, process owner, and focused observer test bytes:
  `1373f508e80311c657e303ea8896616ac3aa943d923e3ccd6d0fd421b270c868`,
  `ceef8fbe3ba3688ff60525c68167f914500959012e7345692f09f37f6ce0b38e`, and
  `a17d70be7e9225435ac5cc28a13024d0a6a1885a56e149737775cfeafe1ee63b`.
- Both implementation acceptances end in independent `PASS` verdicts. The amendment truthfully
  treats the original C1B acceptance as historical `REQUEST_REVISION` and credits only the final
  C1B-AM1 acceptance.
- The accepted policy remains exact at
  `2cbe6e350f35cd9e0831186df31f9631a10c1e838fb0246fc1f56828abb4a6af`.
- The accepted adoption design and original A1/A2 authorization bytes remain exact at
  `44b600bfb3a22e05205c0babb9a72e1ed02c6f84afd71127a5a71afb99c79f18`,
  `336f454aa0e9c5e31f7fc7f10c5fee6a41d10d4e54588d8572a6c1ed9ec738e9`, and
  `7a4a2cf4f66aac0898d4c7cde003fa81cd8773b4e1b508ad5bcc18eb74f1d68e`.

The rebind therefore satisfies the original design's exact prerequisite edge. No missing,
superseded, unavailable, recused, or self-reviewing lane is presented as active acceptance.

## A1 authorization adjudication

**Verdict: PASS / eligible for exact owner activation.**

All eight target conditions were independently reproduced against the current worktree. The six
modified predecessors match the authorization exactly:

| Path | Verified predecessor SHA-256 |
|---|---|
| `scripts/testing/smoke-flagship-cli-surfaces.sh` | `62705e40e0035e1f0c7d050f8e4ccd306a3343e01367468d3166c4a5ab97b261` |
| `scripts/testing/harness_qa/phases/phase0.py` | `fc43b959e2bbe6eb6753736df4818265616edace598d361fc93a5ddb929bf193` |
| `scripts/testing/harness_qa/core/result.py` | `d3272af4630a43bb2d0780074411a78339c7ed7cb3fb277892f18fb00c1ff8bd` |
| `scripts/testing/harness_qa/core/context.py` | `a2cf827b7d25c8ba234d87ae61de631145a67b821c2c086a9725ea0bab92cd80` |
| `scripts/testing/harness_qa/main.py` | `329627f7e417ddf7ead13a852860d8febeed85c111d1af9d41517b717356db37` |
| `scripts/testing/harness_qa/reporters/json_out.py` | `8629c57c7a5901871cca135c02f5a04d1a87a8250a9493316c56e6d8e0480fc5` |

`scripts/testing/qa-provider-probe.py` and
`scripts/testing/test-qa-provider-probe-adoption.py` are absent and are not symlinks. All eight
paths are clean. There is no inventory substitution or ninth path.

The authorization preserves the accepted architecture and security boundary: one policy-ordered
sequential aggregate, one stable-inode nonblocking admission owner, one pre-reserved immutable QA
invocation, one closed four-result evidence shape and serializer, and one C1A-valid atomic
projection writer driven only by validated monotonic C1B events plus the terminal result join. It
retains bounded cleanup, no retry/fallback, no synthesized or backward lifecycle state, no second
terminal writer, no post-redelivery write, and no sensitive projection fields.

Phase-0 check `0.6.1`, compatibility-shell delegation, immutable evidence parity, and offline
fake-provider adversarial coverage remain one atomic maximum-eight implementation slice. This
satisfies the service-coverage requirement without admitting real providers: dashboard-safe
execution stays a host-only `SKIP`, writes no heartbeat, and is not acceptance authority. Real
provider resolution, network, live QA, dashboard/API/browser work, dependencies, environment,
ports, Nix/service/deployment, staging, commit, and self-acceptance remain excluded.

The activation gate is exact and sufficient: the owner must name authorization SHA-256
`7fdedc347ce536a27b340ca609140db6fc63d55b13d4662bafe03526147a6e9e`, exactly one implementer,
an explicit activation time and expiry no more than 24 hours later, and affirm the eight-file
ceiling and stop conditions. Prerequisite acceptance or broad preauthorization does not activate
the slice.

## A2 checkpoint adjudication

**Verdict: PASS as a non-activatable checkpoint only.**

The four observed predecessor hashes reproduce exactly, all five target paths are clean, and
`scripts/testing/test-dashboard-qa-provider-probe.py` is absent and not a symlink. These values are
correctly labeled observations rather than activation bindings.

The frozen future grant preserves passive, non-authoritative dashboard parity: one bounded
symlink-safe projection reader; an early-return `projection_only=true` branch on the existing
Phase-0 route before cache, tasks, evidence, or execution; a fixed low-cardinality object; exactly
six accessible text-only rows in the existing card; and one visibility-aware, cancellable,
single-flight one/two-second poller. It prohibits a new route, card, store, cache authority,
provider execution, unsafe HTML, sensitive fields, projection-as-acceptance, and live API/browser
work.

The authorization does not combine A1 and A2 authority and cannot be activated now. It explicitly
requires all of the following after A1: the exact A1 authorization and candidate, an independent
final A1 acceptance, the accepted A1 commit, current branch `HEAD`, proof that no unrelated commit
intervened, and recomputation of all five predecessor/absence conditions. That final amendment must
receive its own exact-hash independent review and distinct owner activation. This correctly
protects the consecutive atomic-commit and service-coverage boundary.

## Validation and exclusions

- Requested subject hashes: **PASS, 3/3 exact**.
- Accepted prerequisite commit/object bindings: **PASS, 2/2 commits and 6/6 committed byte subjects exact**.
- Policy, design, and original-authorization lineage: **PASS, all declared hashes exact**.
- A1 predecessor/absence/cleanliness conditions: **PASS, 8/8**.
- A2 checkpoint predecessor/absence/cleanliness conditions: **PASS, 5/5**.
- A1/A2 authority separation and consecutive-commit gate: **PASS**.
- Passive projection, service coverage, privacy, locking, lifecycle, evidence, and monitoring
  contracts: **PASS, retained without broadening**.

This was a static contract review. It executed no provider, network, QA phase, API, browser,
heartbeat/evidence writer, deployment, traffic, rollback, or destructive operation. It authorizes
no implementation by itself. Any reviewed-subject or target-byte change requires a new independent
review.

VERDICT: PASS — exact QPPR rebind package resolves C1A/C1B prerequisites, makes only A1 eligible for exact owner activation, and correctly keeps A2 non-activatable pending accepted adjacent A1 and a final post-A1 rebind
