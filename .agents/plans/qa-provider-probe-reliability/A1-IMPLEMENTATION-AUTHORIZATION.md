# QPPR-A1 host-adoption implementation authorization

**Authorization ID:** `auth-qa-provider-probe-reliability-a1-20260718`
**Idempotency key:** `qa-provider-probe-reliability:a1:host-adoption:v1:20260718`
**Status:** **PREPARED_ONLY / REVISION 3 / BLOCKED ON C1A+C1B / NOT ACTIVATABLE**
**Prepared:** 2026-07-18
**Single use after rebind:** first complete exact eight-file candidate report

## 1. Frozen subjects and prerequisite

| Subject | SHA-256 |
|---|---|
| `.agents/plans/qa-provider-probe-reliability/A1-A2-ADOPTION-DESIGN-PACKET.md` | `44b600bfb3a22e05205c0babb9a72e1ed02c6f84afd71127a5a71afb99c79f18` |
| `.agent/PROJECT-QA-PROVIDER-PROBE-RELIABILITY-PRD.md` | `7f4bf98c4962045c7da863994337cb41cf24798c3ab168ca19169e54f2bebf0d` |
| `.agents/plans/qa-provider-probe-reliability/C1-IMPLEMENTATION-ACCEPTANCE.md` | `3f084c8af9ce53aced4ab40a190688756ed547954262a2277324bdccb541599c` |
| `.agents/plans/qa-provider-probe-reliability/C1A-CONTRACT-AMENDMENT-DESIGN-PACKET.md` | `491c98c56435d88f9f4f784942d28a5c29eeb838ac71b5d80e5657d26ef889de` |
| `.agents/plans/qa-provider-probe-reliability/C1A-IMPLEMENTATION-AUTHORIZATION.md` | `2d4bf8e7efe45a2b85a1f5ad5b2aad3e26791529fa09a465451aa0f0f1759251` |
| `.agents/plans/qa-provider-probe-reliability/C1B-OBSERVER-INTERFACE-DESIGN-PACKET.md` | `d6ff76f71f25e322c7cdd6e70f51afcaedda2b86ab2446c1827075dc6d45d06c` |
| `.agents/plans/qa-provider-probe-reliability/C1B-IMPLEMENTATION-AUTHORIZATION.md` | `96b7d5c646c14e9526fe6f45e513e603788218cab4d76ef46c388365f6ff31d5` |
| accepted C1 process owner | `d458b1044850b336374745c28254a808aba153b16225eedb82396873bc844170` |
| accepted C1 policy | `2cbe6e350f35cd9e0831186df31f9631a10c1e838fb0246fc1f56828abb4a6af` |

This document cannot be independently approved for activation or activated until C1A and C1B are
accepted and committed. A separately reviewed amendment must bind both exact commits, final schema
and process-owner hashes, both final focused-test hashes, and both implementation-acceptance hashes.
Broad preauthorization cannot fill these unknown subjects.

## 2. Exact eight-file ceiling

| # | Operation | Path | Frozen predecessor |
|---:|---|---|---|
| 1 | NEW | `scripts/testing/qa-provider-probe.py` | absent |
| 2 | MODIFY | `scripts/testing/smoke-flagship-cli-surfaces.sh` | `62705e40e0035e1f0c7d050f8e4ccd306a3343e01367468d3166c4a5ab97b261` |
| 3 | MODIFY | `scripts/testing/harness_qa/phases/phase0.py` | `fc43b959e2bbe6eb6753736df4818265616edace598d361fc93a5ddb929bf193` |
| 4 | MODIFY | `scripts/testing/harness_qa/core/result.py` | `d3272af4630a43bb2d0780074411a78339c7ed7cb3fb277892f18fb00c1ff8bd` |
| 5 | MODIFY | `scripts/testing/harness_qa/core/context.py` | `a2cf827b7d25c8ba234d87ae61de631145a67b821c2c086a9725ea0bab92cd80` |
| 6 | MODIFY | `scripts/testing/harness_qa/main.py` | `329627f7e417ddf7ead13a852860d8febeed85c111d1af9d41517b717356db37` |
| 7 | MODIFY | `scripts/testing/harness_qa/reporters/json_out.py` | `8629c57c7a5901871cca135c02f5a04d1a87a8250a9493316c56e6d8e0480fc5` |
| 8 | NEW | `scripts/testing/test-qa-provider-probe-adoption.py` | absent |

## 3. Exact grant after rebind and activation

One bounded implementer may implement only packet sections 3.1–3.4: policy-backed sequential
one-spawn aggregate; stable-inode cross-process lock held through final heartbeat/publication;
strict machine/Phase-0 parity; reserve-before-context invocation flow; the exact four-item
policy-ordered `CheckResult.details` list through one serializer and immutable publication; C1A-
valid atomic heartbeat driven only by C1B events; direct Phase-0 adoption; shell compatibility
delegation; and offline fake-provider adversarial tests including the real two-process contender.
Terminal projection must use the single closed `TerminalProjectionJoin`: one truthful C1B terminal
event plus one validated returned/provisional C1 result, stable-tuple idempotency, one writer/once
guard, bounded signal-publication participation, and cancellation preventing post-redelivery writes.

The implementation candidate may not resolve or execute the real provider profiles. Test PATHs and
resolvers must be deterministic fixtures. The compatibility shell contains no nested timeout,
command interpolation, `nohup`, `disown`, retry, or second lifecycle owner. Dashboard-safe mode
remains explicit host-only `SKIP` and writes no heartbeat.

## 4. Mandatory stops and exclusions

Stop without workaround on C1A or C1B not accepted/committed, missing rebind review, any ninth file,
substitution, predecessor drift, foreign dirty overlap, schema/policy/process-owner change, real
provider resolution/execution, network, retry/fallback, new environment variable/port/dependency,
new store/endpoint/card, dashboard/backend/Nix/systemd/service/broker/cgroup/deploy/traffic action,
pre-lock truncation, lock-inode replace/unlink, blocking lock, synthesized lifecycle state, unbounded
or symlink-following write, a second terminal writer, terminal class before result validation,
post-redelivery join/write, non-four-item details, raw sensitive field, projection-as-authority, shorter deadline,
staging, commit, activation, rollback, or deletion.

The implementer cannot delegate, stage, commit, deploy, or self-accept. It must report all eight
exact hashes, key reasoning/tradeoffs, focused offline evidence, and exclusions. A reviewer edit
recuses that reviewer and creates a new subject.

## 5. Review, adjacency, and activation

After the mandatory C1A+C1B rebind amendment receives independent `PASS`, the owner must explicitly name
the amended authorization SHA-256, one implementer identity, activation and <=24-hour expiry times,
and affirm the eight-file ceiling and stops. A different agent/session must issue exact-subject
implementation acceptance. Only the orchestrator stages and commits.

A1 commit does not activate provider execution or satisfy service coverage. It must be followed
immediately by the independently accepted A2 commit with no unrelated commit between them. Until A2
lands and a separate live-vetting authorization is recorded, A1 remains inactive and no real
provider, API/browser vet, deployment, or traffic is permitted.

`RECORD: PREPARED_ONLY AND NOT ACTIVATABLE. C1A+C1B acceptance plus an exact hash-bound A1 amendment
are mandatory next gates.`
