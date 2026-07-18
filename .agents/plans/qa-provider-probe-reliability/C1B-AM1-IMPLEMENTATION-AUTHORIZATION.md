# QPPR-C1B Amendment 1 lifecycle-ordering authorization

**Authorization ID:** `auth-qa-provider-probe-reliability-c1b-am1-20260718`
**Idempotency key:** `qa-provider-probe-reliability:c1b:observer-ordering:am1:20260718`
**Status:** **PREPARED_ONLY — IMPLEMENTATION NOT AUTHORIZED**
**Prepared:** 2026-07-18
**Single use:** consumed by the first complete exact two-file Amendment 1 candidate report

## 1. Exact bound subjects

| Subject | SHA-256 |
|---|---|
| `C1B-AM1-LIFECYCLE-ORDERING-DESIGN-PACKET.md` | `dfa55f65f6efce20389d6ba0de9313a1bd354c8fb0a31ddfc2f594dd2e050474` |
| Original C1B authorization | `96b7d5c646c14e9526fe6f45e513e603788218cab4d76ef46c388365f6ff31d5` |
| C1B `REQUEST_REVISION` acceptance | `47b354f07862514093daa555bb313be30b65e95b898a1d0e8d09afd67211cb05` |
| `scripts/testing/harness_qa/core/process_lifecycle.py` | `dbc07131c03a4b98a81364077623dd75fbc07f370e4aca07ea0d5af926e982f1` |
| `scripts/testing/test-qa-provider-probe-observer.py` | `f5181d9aaecc15c66ddb6b0af3e3f6de0fc666b78ebfa81ae536da3d8267b614` |

Any mismatch is a hard stop. This authorization amends the reviewed uncommitted C1B candidate; it
does not replace, reopen, or broaden the consumed original authorization.

## 2. Exact grant

One bounded implementer may modify exactly:

1. `scripts/testing/harness_qa/core/process_lifecycle.py`; and
2. `scripts/testing/test-qa-provider-probe-observer.py`.

The process owner may change only enough to prevent non-increasing lifecycle-event emission while
preserving the frozen optional-state order, and the focused test may change only enough to add the
first-`_reap_pid`-after-`reaping` adversarial regression and associated cleanup/order assertions.
The post-`reaping` exceptional path must not emit late `terminating`; a cleanup path that begins
before `reaping` must retain `terminating` immediately before its first cleanup signal.

All previously passing C1B descriptor validation, bounded record, nonblocking failure, lifecycle
result, cleanup, redelivery, publication-order, budget, and default-path contracts remain mandatory.

## 3. Mandatory stop conditions

Stop without workaround on a third file, path substitution, bound-hash drift, foreign overlap,
record/schema/state expansion, callback/thread/queue/acknowledgement, retry or blocking I/O, changed
cleanup/result/signal/publication behavior, relaxed four/five-second bounds, new provider/profile/
budget/policy, real provider or network, heartbeat/evidence write, Phase-0/shell/dashboard/backend/
API/Nix/service/broker/cgroup/deploy/traffic action, A1/A2 edit, staging, commit, rollback, deletion,
or any change beyond the bound ordering defect and regression.

The implementer cannot delegate, stage, commit, deploy, or self-accept. Its complete report must
name both exact final hashes, the reproduced root cause, transition-order reasoning, exact offline
test measurements, descriptor/process-leak evidence, and explicit exclusions. A reviewer edit
changes the subject and recuses that reviewer.

## 4. Review, activation, and acceptance

Independent design/authorization review of this exact document is required before activation. The
owner must then explicitly name this authorization's exact SHA-256, exactly one implementer, an
activation timestamp and expiry no more than 24 hours later, and affirm that the exact two-file
ceiling and every stop condition remain unchanged. The original C1B activation, broad
preauthorization, silence, or a review `PASS` does not activate Amendment 1.

A different agent/session must review the revised exact two-file hashes and issue
`VERDICT: PASS|FAIL|REQUEST_REVISION`. Required evidence is both focused lifecycle suites, Python
compilation, lint/diff/security/process-leak checks, and Tier-0. Only the orchestrator may stage and
commit after exact-subject `PASS`. Acceptance or commit does not activate QPPR-A1/A2 or any provider
path.

`RECORD: PREPARED_ONLY. QPPR-C1B Amendment 1 implementation, acceptance, commit, A1/A2 adoption,
provider execution, runtime/live actions, deployment, and rollback remain unauthorized.`
