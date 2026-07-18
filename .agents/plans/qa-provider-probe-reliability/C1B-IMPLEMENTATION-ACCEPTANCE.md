# QPPR-C1B lifecycle-observer implementation — independent acceptance

**Reviewed:** 2026-07-18
**Reviewer:** `codex-subagent-qppr-c1b-acceptance` — independent acceptance lane
**Verdict:** **REQUEST_REVISION**

## Exact reviewed subject

The activated authorization and both implementation subjects matched the hashes supplied to this
review exactly:

| Subject | SHA-256 | Result |
|---|---|---|
| `C1B-IMPLEMENTATION-AUTHORIZATION.md` | `96b7d5c646c14e9526fe6f45e513e603788218cab4d76ef46c388365f6ff31d5` | exact |
| `scripts/testing/harness_qa/core/process_lifecycle.py` | `dbc07131c03a4b98a81364077623dd75fbc07f370e4aca07ea0d5af926e982f1` | exact |
| `scripts/testing/test-qa-provider-probe-observer.py` | `f5181d9aaecc15c66ddb6b0af3e3f6de0fc666b78ebfa81ae536da3d8267b614` | exact |

The implementation inventory is exactly the authorized two files: one modification and one new
focused test. No third candidate path or path substitution was observed.

## Passing evidence

- `python3 scripts/testing/test-qa-provider-probe-observer.py`: **PASS, 7/7 in 6.253 s**.
- `python3 scripts/testing/test-qa-provider-probe-lifecycle.py`: **PASS, 29/29 in 51.321 s**.
- `python3 -m py_compile scripts/testing/harness_qa/core/process_lifecycle.py scripts/testing/test-qa-provider-probe-observer.py`: **PASS**.
- `ruff check scripts/testing/harness_qa/core/process_lifecycle.py scripts/testing/test-qa-provider-probe-observer.py`: **PASS**.
- `git diff --check -- scripts/testing/harness_qa/core/process_lifecycle.py scripts/testing/test-qa-provider-probe-observer.py`: **PASS**.
- Post-test process scan found no remaining observer/lifecycle fixture process.
- `scripts/governance/tier0-validation-gate.sh --pre-commit`: **PASS, 23/23** (including QA Phase 0, 172 checks).

These checks confirm the optional keyword-only API, caller and duplicate `FD_CLOEXEC` validation,
write-only/nonblocking FIFO checks, close-on-exec duplication, bounded descriptor-only records,
ordinary clean/spawn-failure/timeout/interruption/residual-child sequences, terminal-before-
publication behavior, disable-on-write-fault behavior, duplicate closure, default-path
compatibility, and the accepted C1/C1A lifecycle regression behavior for the paths exercised by the
candidate suite. No provider resolution, network call, heartbeat/evidence write, Phase-0 adoption,
dashboard/API change, service action, or live traffic action is present in the candidate diff.

## Blocking defect — exceptional transition reversal after `reaping`

The emitter deduplicates states but does not enforce the frozen lifecycle order. In the normal
owner path, `reaping` is emitted before descendant/quiescence and leader-reap work. If one of those
operations raises while `identity` is still owned, the outer exception handler invokes
`_exceptional_teardown`, which unconditionally attempts `terminating` before its cleanup signals.
Because `terminating` has not previously been seen, the emitter accepts it even though `reaping`
was already emitted.

A review-only injection that raises on the first `_reap_pid` call reproduced this exact record
sequence:

```text
qa.provider-probe-state.v1|1|starting|53
qa.provider-probe-state.v1|2|running|54
qa.provider-probe-state.v1|3|reaping|227
qa.provider-probe-state.v1|4|terminating|348
qa.provider-probe-state.v1|5|terminal|632
```

The returned result was truthfully `cleanup_failed`, but the event order violates the frozen C1B
partial order:

```text
starting -> running? -> terminating? -> reaping -> terminal
```

This is not merely a missing assertion. A1 is explicitly designed to consume sequence-valid C1B
events without fabricating lifecycle state; accepting a backward transition would make its
operator evidence internally contradictory. The existing exceptional-teardown test injects a
fault before `reaping`, so it does not cover this post-`reaping` branch.

## Required revision and re-review

1. Make lifecycle transition emission monotonic so no exceptional path can emit `terminating` after
   `reaping`, while retaining the required pre-signal `terminating` event when cleanup first begins
   before the reaping phase.
2. Add a focused adversarial test that injects an exception after `reaping` has been emitted and
   proves the resulting sequence remains an allowed prefix/order ending in exactly one `terminal`.
3. Re-run the focused observer and lifecycle suites, compilation, lint/diff/security/leak checks,
   and Tier-0 against the revised exact hashes.

Any candidate edit changes the reviewed subject hashes and requires a new independent acceptance.
This review does not authorize staging, commit, QPPR-A1/A2 adoption, heartbeat/evidence writes,
providers, network, dashboard/API work, deployment, or traffic.

`VERDICT: REQUEST_REVISION`
