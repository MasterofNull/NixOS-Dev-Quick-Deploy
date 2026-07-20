# QPPR-C1C — bounded publication acknowledgement interface

**Status:** PREPARED_ONLY / DESIGN_ONLY / IMPLEMENTATION UNAUTHORIZED  
**Prepared:** 2026-07-19  
**Decision basis:** independent A1-AM2 authorization review SHA-256
`6827864ccdcae765b47f0c4daf32416199270a8ef825f1e3efb0e3395ede2d14`

## 1. Defect and decision

Accepted C1 starts the interruption publication callback in a daemon thread, waits only for a local
timeout, then restores and redelivers even if that thread remains alive. A1 is blocked inside
`run_owned_process` and cannot cancel or join its terminal projection before redelivery. Therefore
the three-file A1 amendment cannot deterministically prove zero post-redelivery continuation.

C1C adds a separate opt-in acknowledgement interface. It does not change the existing `publication`
callback or any caller unless the new interface is selected. The new interface is synchronous on
the lifecycle-owning main thread: it receives the provisional closed result and an absolute
monotonic deadline, performs only bounded cooperative work, and returns one closed acknowledgement.
Because no worker or daemon is created, return is the completion/cancellation barrier; restoration
and redelivery cannot race callback continuation.

## 2. Exact two-file prerequisite inventory

| # | Operation | Path | Exact predecessor |
|---:|---|---|---|
| 1 | MODIFY | `scripts/testing/harness_qa/core/process_lifecycle.py` | `ceef8fbe3ba3688ff60525c68167f914500959012e7345692f09f37f6ce0b38e` |
| 2 | MODIFY | `scripts/testing/test-qa-provider-probe-lifecycle.py` | `4dc49ef8133cfa8ab22372ea5a3b402585e1b3a18a9bff75180fe338ae3efac7` |

The accepted C1B observer test remains frozen at
`a17d70be7e9225435ac5cc28a13024d0a6a1885a56e149737775cfeafe1ee63b`.
No third implementation path is required. Any third path or predecessor drift is a hard stop.

Bound evidence includes the QPPR PRD
`7f4bf98c4962045c7da863994337cb41cf24798c3ab168ca19169e54f2bebf0d`, corrected C1B-AM1 commit
`f54cd8c8257a43dd8666209648d4976c323dfbff`, C1B-AM1 acceptance
`1373f508e80311c657e303ea8896616ac3aa943d923e3ccd6d0fd421b270c868`, C1B design
`d6ff76f71f25e322c7cdd6e70f51afcaedda2b86ab2446c1827075dc6d45d06c`, and C1B ordering design
`dfa55f65f6efce20389d6ba0de9313a1bd354c8fb0a31ddfc2f594dd2e050474`.

## 3. Frozen interface

`run_owned_process` gains one optional keyword-only argument conceptually equivalent to:

```python
publication_barrier: Callable[[dict[str, Any], float], Literal["completed", "cancelled"]] | None = None
```

`publication` and `publication_barrier` are mutually exclusive; supplying both returns
`contract_invalid` before spawn. The barrier is invoked only after cleanup, result normalization,
and the C1B terminal-event attempt, and only on an outer-signal path where publication is currently
permitted. Its second argument is the absolute monotonic end of the existing publication remainder,
never a fresh or extendable timeout. The callback must inspect that deadline before each bounded
operation and return `cancelled` when insufficient budget remains.

The lifecycle owner invokes the barrier synchronously on its main thread. It creates no thread,
task, queue, retry, continuation, or executor. Only exact returns `completed` or `cancelled` are
accepted; exception, unknown return, return after the supplied deadline, or callback contract
violation is typed as publication cancellation and cannot change the already normalized provider
result. After the callback returns there is no callback execution to outlive restoration/redelivery.
The existing handler, mask, subreaper, lock-release, and one-redelivery order remains unchanged.

This is a cooperative bounded interface: the only authorized adopter is independently reviewed code
whose deadline compliance is proven with deterministic barriers. Arbitrary or untrusted callbacks
are prohibited. The legacy callback remains solely for compatibility and cannot be used by A1.

## 4. Deterministic acceptance evidence

The existing lifecycle test gains fixture-only cases proving:

1. barrier invocation follows terminal observer emission and result normalization;
2. `completed` and `cancelled` acknowledgements return before restoration/redelivery, on the same
   lifecycle-owning thread, with no live worker/thread/task afterward;
3. a deadline-already-expired callback performs zero publication action and returns `cancelled`;
4. default, returning-custom, ignored, SIGTERM, and SIGINT paths observe acknowledgement before
   redelivery/handler return;
5. a deterministic post-redelivery canary observes zero callback steps;
6. both-interface admission fails before spawn; invalid acknowledgement and callback exception fail
   closed without retry or result/schema mutation;
7. legacy publication behavior and all accepted C1/C1B observer behavior remain unchanged; and
8. the four/five-second cleanup/restoration/redelivery budgets are not relaxed.

Tests must use events/barriers and injected monotonic clocks for ordering assertions rather than
sleep-based proof. They invoke no provider, network, heartbeat, evidence store, Phase 0, API,
browser, service, or deployment action.

## 5. Stops and dependency gate

Stop on a third file, hash drift, existing-interface removal or semantic change, callback thread or
background continuation, deadline extension, unbounded wait, retry, result/schema/policy/budget
change, provider/network/heartbeat/evidence/Phase-0/A1/A2 action, new dependency/env/port/store,
Nix/service/deploy action, staging, commit, deletion, delegation, or self-acceptance.

Exactly one bounded implementer owns both files. A separate flagship reviewer must accept the exact
two-file candidate before the orchestrator may commit. C1C acceptance and commit are prerequisites,
not transitive A1 authority. A1 requires a new exact post-C1C rebind. A2 remains blocked.

`RECORD: PREPARED_ONLY. C1C, A1/A2, providers, network, Phase 0, heartbeat/evidence, API/browser,
deployment, traffic, rollback, staging, and commit remain unauthorized.`
