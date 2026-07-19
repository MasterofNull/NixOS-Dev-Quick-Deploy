# QPPR-A1/A2 adoption rebind amendment

Status: **PREPARED_ONLY / REVISION 1 / IMPLEMENTATION UNAUTHORIZED**
Prepared: 2026-07-19
Parent design: `A1-A2-ADOPTION-DESIGN-PACKET.md`

## 1. Purpose and decision

This amendment closes the prerequisite placeholders in the accepted adoption design after the
separate QPPR-C1A heartbeat-contract and corrected QPPR-C1B lifecycle-observer commits. It changes
no adoption semantics or file ceiling.

QPPR-A1 may now receive one exact, independently reviewed, owner-activated implementation
authorization. QPPR-A2 remains a separate consecutive slice. Its current target predecessors are
recorded below, but its authorization remains non-activatable until the accepted A1 commit and
acceptance record exist and a final post-A1 rebind proves adjacency and unchanged target bytes.
Combining the two grants would bypass that frozen gate and is prohibited.

## 2. Exact accepted prerequisite evidence

| Subject | SHA-256 or Git object |
|---|---|
| C1A commit | `52b0a0716ea2e008c2ca1b137c689482e2995543` |
| `C1A-IMPLEMENTATION-ACCEPTANCE.md` | `73808146d65e877a15e0396f8e8adb5b726b986f7a01baccf5a5aa14b21d1987` |
| final `config/qa-provider-probe-contract.schema.json` | `1acaa61d4b3fe2737a513112c49578bf5b596c04f4916f4e4647e8e7516b7ac4` |
| final `scripts/testing/test-qa-provider-probe-lifecycle.py` | `4dc49ef8133cfa8ab22372ea5a3b402585e1b3a18a9bff75180fe338ae3efac7` |
| corrected C1B-AM1 commit | `f54cd8c8257a43dd8666209648d4976c323dfbff` |
| `C1B-AM1-IMPLEMENTATION-ACCEPTANCE.md` | `1373f508e80311c657e303ea8896616ac3aa943d923e3ccd6d0fd421b270c868` |
| final `scripts/testing/harness_qa/core/process_lifecycle.py` | `ceef8fbe3ba3688ff60525c68167f914500959012e7345692f09f37f6ce0b38e` |
| final `scripts/testing/test-qa-provider-probe-observer.py` | `a17d70be7e9225435ac5cc28a13024d0a6a1885a56e149737775cfeafe1ee63b` |
| accepted C1 policy | `2cbe6e350f35cd9e0831186df31f9631a10c1e838fb0246fc1f56828abb4a6af` |
| adoption design | `44b600bfb3a22e05205c0babb9a72e1ed02c6f84afd71127a5a71afb99c79f18` |
| original A1 authorization | `336f454aa0e9c5e31f7fc7f10c5fee6a41d10d4e54588d8572a6c1ed9ec738e9` |
| original A2 authorization | `7a4a2cf4f66aac0898d4c7cde003fa81cd8773b4e1b508ad5bcc18eb74f1d68e` |

The C1A acceptance is a final independent `PASS`. The initial C1B acceptance is historical
`REQUEST_REVISION`; the C1B-AM1 acceptance is the final independent `PASS` for the corrected exact
subjects. No unavailable or recused lane is credited as a reviewer.

## 3. A1 exact maximum-eight inventory rebound at C1B-AM1 HEAD

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

The target paths are clean. A1 retains the exact design grant: one policy-backed sequential
aggregate, one stable-inode admission owner, one immutable invocation identity, one closed
four-result evidence shape, one C1A projection writer driven only by validated C1B events, direct
Phase-0 adoption, shell compatibility delegation, and offline fake-provider tests. Phase-0 service
coverage is mandatory in the same atomic A1 commit. A1 remains inactive until A2 follows and the
separate live-vetting grant is accepted.

## 4. A2 exact maximum-five checkpoint

| # | Operation | Path | Current observed predecessor |
|---:|---|---|---|
| 1 | MODIFY | `dashboard/backend/api/services/qa_runner.py` | `abc105fc8caa7cc72fcc02df75e28ed930173741081cb88cdffb0769a26ec0e0` |
| 2 | MODIFY | `dashboard/backend/api/routes/aistack.py` | `8ae69185c83c4a55e8d41060078ea7575387cd0edd873988fdd9261f505b48db` |
| 3 | MODIFY | `dashboard.html` | `801a50b24c09879471771bac53ea31f34ee22ba5236cf96033dcaaa88cd93323` |
| 4 | MODIFY | `assets/dashboard.js` | `4e3b44cb0caa8a86988b1b2de68091df90ef4f51d09caccfc65cd9c05990c8b6` |
| 5 | NEW | `scripts/testing/test-dashboard-qa-provider-probe.py` | absent, including no symlink |

The target paths are clean. These values are a checkpoint, not a final A2 activation binding.
After exact A1 acceptance and commit, the final A2 rebind must name that commit and acceptance,
recompute all five predecessor conditions, and prove no unrelated commit intervened. A2 retains
the exact design grant: one bounded passive projection reader, the existing Phase-0 route's
`projection_only=true` early-return branch, the existing QA Phase 0 Status card's six accessible
rows, safe text-only rendering, bounded single-flight polling, and focused offline API/browser DOM
tests. It may add no route, card, store, provider execution, or acceptance authority.

## 5. Shared stops, review, and activation

Both slices remain separate atomic commits on the same branch. Stop without workaround on any
inventory growth or substitution, predecessor/absence drift, foreign overlap, real provider or
network use, live API/browser execution, heartbeat or evidence mutation outside the frozen A1
contract, a new route/card/store/cache authority, projection-as-acceptance, new dependency/env/port,
Nix/systemd/service/broker/cgroup change, deployment, traffic, cutover, rollback, deletion, staging,
commit, delegation by an implementer, or self-acceptance.

An independent flagship architecture/security/SRE/QA reviewer must verify the exact amendment and
authorization hashes. A1 then requires explicit owner activation naming its exact rebound
authorization hash, one implementer, and a window no longer than 24 hours. A2 requires a distinct
post-A1 exact rebind, independent review, and distinct owner activation. A reviewer edit creates a
new subject and requires a different independent review.

`RECORD: PREPARED_ONLY. A1/A2 implementation, provider/API/browser execution, deployment, traffic,
and all live actions remain unauthorized.`
