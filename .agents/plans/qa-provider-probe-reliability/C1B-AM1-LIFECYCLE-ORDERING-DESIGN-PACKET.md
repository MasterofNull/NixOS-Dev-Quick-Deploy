# QPPR-C1B Amendment 1 — Lifecycle-event ordering correction

Status: **PREPARED_ONLY / DESIGN_ONLY / UNAUTHORIZED**
Prepared: 2026-07-18
Parent slice: QPPR-C1B lifecycle-observer interface

## 1. Blocking defect and decision

The first C1B candidate passes its focused and parent suites, but independent exact-hash acceptance
reproduced an invalid backward lifecycle transition. The common path emits `reaping` before owned
quiescence/reap work. If the first `_reap_pid` then raises while process identity remains owned, the
exceptional teardown attempts `terminating`; the current emitter deduplicates states but accepts
that lower-order state. The resulting sequence is:

```text
starting -> running -> reaping -> terminating -> terminal
```

This violates the frozen C1B order and would make A1 operator evidence contradictory. Amendment 1
makes the existing emitter monotonic and adds the missing post-`reaping` adversarial regression. It
does not change cleanup execution: exceptional teardown may still signal and reap as required, but
an already-passed lifecycle phase cannot be emitted later.

## 2. Bound reviewed candidate and exact two-file ceiling

| Subject | SHA-256 |
|---|---|
| Original C1B authorization | `96b7d5c646c14e9526fe6f45e513e603788218cab4d76ef46c388365f6ff31d5` |
| C1B design packet | `d6ff76f71f25e322c7cdd6e70f51afcaedda2b86ab2446c1827075dc6d45d06c` |
| C1B `REQUEST_REVISION` acceptance | `47b354f07862514093daa555bb313be30b65e95b898a1d0e8d09afd67211cb05` |
| `scripts/testing/harness_qa/core/process_lifecycle.py` | `dbc07131c03a4b98a81364077623dd75fbc07f370e4aca07ea0d5af926e982f1` |
| `scripts/testing/test-qa-provider-probe-observer.py` | `f5181d9aaecc15c66ddb6b0af3e3f6de0fc666b78ebfa81ae536da3d8267b614` |

The amendment implementation ceiling is exactly the two candidate paths above, both `MODIFY`.
Any hash mismatch, third file, or path substitution is a hard stop.

## 3. Frozen minimal correction

The existing emitter must enforce the frozen lifecycle rank:

```text
starting < running < terminating < reaping < terminal
```

Optional states remain optional. An attempted state whose rank is not greater than the last emitted
state is not written and does not advance sequence or elapsed fields. In particular, exceptional
teardown entered after `reaping` suppresses the late `terminating` record while continuing the
existing cleanup. When termination begins before `reaping`, `terminating` remains emitted
immediately before the first cleanup `SIGCONT`. `terminal` remains attempted exactly once after
cleanup/result normalization and before provisional publication. Observer-only errors retain their
existing disable-without-lifecycle-impact behavior.

The focused test must inject an exception on the first `_reap_pid` call after `reaping` is emitted
and prove the sequence is exactly an allowed ordered sequence ending in one `terminal`, with no
late `terminating`. It must also prove the truthful `cleanup_failed` result, required cleanup,
descriptor closure, absence of leaked fixture processes, and preservation of the pre-`reaping`
exception path where `terminating` precedes cleanup signals.

No callback, thread, queue, acknowledgement, retry, blocking I/O, record/schema expansion, new
state, provider/profile/budget change, or lifecycle-result change is permitted.

## 4. Acceptance and validation

A different agent/session must review the revised exact hashes and may pass only if:

1. the diff is limited to monotonic transition enforcement and the post-`reaping` regression in
   the exact two files;
2. clean, spawn-failure, timeout, interruption, residual-child, pre-`reaping` exception, and
   post-`reaping` exception sequences all satisfy the frozen order and end in exactly one terminal;
3. cleanup, signal restoration/redelivery, descriptor ownership, result normalization, budgets,
   default `observer_fd=None` behavior, and every previously passing C1B contract remain intact;
4. both focused suites, Python compilation, lint/diff/security/process-leak checks, and Tier-0 pass;
   and
5. no provider/network, heartbeat/evidence write, Phase-0/shell/dashboard/backend/API, service,
   deployment, traffic, staging, commit, deletion, rollback, or A1/A2 action occurs.

Any reviewer edit changes the subject and recuses that reviewer. Only the orchestrator may stage
and commit after an independent exact-hash `VERDICT: PASS`.

## 5. Authority and stop boundary

The original C1B authorization was consumed by the reviewed candidate report and does not authorize
this revision. Amendment 1 requires an independently reviewed, hash-bound single-use authorization
and a new explicit owner activation naming one implementer and a window no longer than 24 hours.
Broad preauthorization, the original activation, this design, or a review verdict does not activate
the amendment.

Stop without workaround on scope growth, a predecessor mismatch, foreign overlap, changed passed
C1B behavior, or any action excluded above. Rollback remains unauthorized and, if separately
authorized later, is the atomic final C1B commit rather than an ad hoc amendment reversal.

`RECORD: PREPARED_ONLY. QPPR-C1B Amendment 1 implementation, acceptance, commit, A1/A2 adoption,
and every runtime/live action remain unauthorized.`
