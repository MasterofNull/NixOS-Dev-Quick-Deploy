# QPPR-C1B Amendment 1 ordering correction — independent authorization review

**Reviewed:** 2026-07-18
**Reviewer:** `codex-subagent-qppr-c1b-acceptance` — independent design/authorization lane
**Verdict:** **PASS / PREPARED_ONLY**

## Exact reviewed subjects

| Subject | Expected SHA-256 | Observed SHA-256 | Result |
|---|---|---|---|
| `C1B-AM1-LIFECYCLE-ORDERING-DESIGN-PACKET.md` | `2aa9093b23df07646122a46a24b3921dbc0d4a6567b5aea9b4c8003d157e00ee` | `2aa9093b23df07646122a46a24b3921dbc0d4a6567b5aea9b4c8003d157e00ee` | exact |
| `C1B-AM1-IMPLEMENTATION-AUTHORIZATION.md` | `748dfffafa3b76371a640f067f356d85b6c2e4faecf7a16647db21a34031c070` | `748dfffafa3b76371a640f067f356d85b6c2e4faecf7a16647db21a34031c070` | exact |

The complete predecessor chain also matched:

| Bound predecessor | SHA-256 | Result |
|---|---|---|
| Original C1B authorization | `96b7d5c646c14e9526fe6f45e513e603788218cab4d76ef46c388365f6ff31d5` | exact |
| Original C1B design packet | `d6ff76f71f25e322c7cdd6e70f51afcaedda2b86ab2446c1827075dc6d45d06c` | exact |
| C1B `REQUEST_REVISION` acceptance | `452b47e2514bb2ec0f85ee712d4630925ae3f2d6e4a801eb246b29f35554d041` | exact |
| Current process-owner candidate | `dbc07131c03a4b98a81364077623dd75fbc07f370e4aca07ea0d5af926e982f1` | exact |
| Current focused observer test | `f5181d9aaecc15c66ddb6b0af3e3f6de0fc666b78ebfa81ae536da3d8267b614` | exact |

The authorization binds the original design transitively through the exact AM1 design hash; the
AM1 design directly records the original design hash. No floating or mutable predecessor reference
is used.

## Architecture and scope review

The proposed correction addresses the reproduced defect without changing cleanup execution. It
freezes one monotonic lifecycle rank:

```text
starting < running < terminating < reaping < terminal
```

Optional states remain optional. A non-increasing attempted state is suppressed without a write,
sequence increment, or elapsed-field update. Consequently, exceptional cleanup entered after
`reaping` cannot publish a backward `terminating` event, while cleanup entered earlier retains the
truthful `terminating` event immediately before its first `SIGCONT`.

The implementation ceiling remains exactly two existing candidate files, both modifications:

1. `scripts/testing/harness_qa/core/process_lifecycle.py`; and
2. `scripts/testing/test-qa-provider-probe-observer.py`.

The process-owner allowance is limited to monotonic state suppression. The test allowance is
limited to the first-`_reap_pid`-after-`reaping` injected-fault regression and its cleanup/order
assertions. The required evidence explicitly preserves the already-passing clean, spawn-failure,
timeout, interruption, residual-child, and pre-`reaping` exceptional paths.

## Preserved contracts

Neither document relaxes caller or duplicate `FD_CLOEXEC`, write-only/nonblocking FIFO validation,
descriptor duplication or closure, the fixed 96-byte descriptor-only record, observer failure
disablement, exact terminal-before-publication ordering, result normalization, cleanup ownership,
signal restoration/redelivery, four/five-second bounds, or default `observer_fd=None` behavior.
Callbacks, observer threads, queues, acknowledgements, retries, blocking I/O, new states, record or
schema expansion, and provider/profile/policy/budget changes remain prohibited.

Provider/network execution, heartbeat/evidence writes, Phase-0, shell, dashboard/backend/API,
Nix/service/broker/cgroup, deployment, traffic, A1/A2, staging, commit, rollback, deletion, and scope
growth are explicit hard stops.

## Authority and next gate

The authorization is single-use and consumed by the first complete exact two-file AM1 candidate
report. It is not activated by the original C1B activation, broad preauthorization, silence, this
review, or this `PASS`. Activation must name:

- authorization SHA-256 `748dfffafa3b76371a640f067f356d85b6c2e4faecf7a16647db21a34031c070`;
- exactly one implementer;
- an explicit activation timestamp and expiry no more than 24 hours later; and
- the unchanged exact two-file ceiling and all stop conditions.

After activation and implementation, a different session must review the revised exact two-file
hashes. Both focused lifecycle suites, Python compilation, lint, diff/security/process-leak checks,
and Tier-0 must pass before the orchestrator may stage or commit. Acceptance or commit cannot
activate QPPR-A1/A2 or a provider path.

`VERDICT: PASS`
