# QPPR-C1C Amendment 2 — observable fail-stop classification

**Status:** PREPARED_ONLY / OWNER SRE RATIFICATION REQUIRED / NON-ACTIVATABLE  
**Prepared:** 2026-07-19  
**Revision basis:** `520fdcaccf7b19ded8ab061a4f0f6bfdf6ac3d2772c425ccfcc2487e5aa3c19d`

## Decision and exact boundary

C1C-AM1 correctly chooses safety over liveness for a non-returning synchronous publication callback,
but its blocked owner cannot mark the deadline transition. C1C-AM2 makes an external monotonic
classifier authoritative without adding a worker or weakening fail-stop behavior.

The exact implementation ceiling remains two MODIFY paths:

| Path | Exact predecessor |
|---|---|
| `scripts/testing/harness_qa/core/process_lifecycle.py` | `ceef8fbe3ba3688ff60525c68167f914500959012e7345692f09f37f6ce0b38e` |
| `scripts/testing/test-qa-provider-probe-lifecycle.py` | `4dc49ef8133cfa8ab22372ea5a3b402585e1b3a18a9bff75180fe338ae3efac7` |

The observer regression remains frozen at
`a17d70be7e9225435ac5cc28a13024d0a6a1885a56e149737775cfeafe1ee63b`.

## Authoritative observable contract

The opt-in barrier gains a caller-owned, validated, nonblocking close-on-exec pipe dedicated to
publication status. Before invoking the synchronous callback, the lifecycle owner emits one bounded
ASCII record no larger than `PIPE_BUF`:

```text
qa.provider-publication.v1|1|running|<absolute_deadline_monotonic_ms>\n
```

On an on-time return it emits sequence 2 with `completed` or `cancelled`. On a return observed after
the deadline it emits sequence 2 with `contract_violation`, then permanently fail-stops before
handler/mask restoration, redelivery, invocation-lock release, ordinary return, or later provider
start. No record contains provider identity, PID, argv, path, output, environment, credential, or
verdict. Pipe validation and observer-error isolation follow the accepted C1B descriptor rules;
status backpressure cannot alter cleanup or create a fallback writer.

For a callback that never returns, the authoritative classification is the pure rule:

```text
last valid record = running
AND observer monotonic_now_ms > bound absolute_deadline_monotonic_ms
AND no valid sequence-2 acknowledgement
=> CONTRACT_VIOLATION
```

The lifecycle module exposes this closed pure classifier so the caller and tests do not reimplement
inference. Classification depends only on the validated record and the same-host monotonic clock,
not on callback progress, thread scheduling, wall time, PID inspection, or a stuck owner marker.
Once classified, later data cannot downgrade it. A missing/invalid status record is `unavailable`,
never healthy or completed.

The status descriptor is mandatory when the new barrier is supplied; either alone, a blocking/read-
only/regular descriptor, missing `FD_CLOEXEC`, or legacy `publication` plus barrier fails before
spawn. The lifecycle owner never creates a publication worker, daemon, task, retry, or second writer.

## Deterministic proof

The isolated fixture tests must prove with event barriers and injected classifier time:

1. on-time `completed|cancelled` emits exact sequence 1/2 before <=5-second redelivery;
2. never-return emits `running`; advancing injected observer time one millisecond beyond the bound
   produces authoritative `CONTRACT_VIOLATION` while the fixture shows no restoration, redelivery,
   lock release, ordinary return, later provider, or second writer;
3. late-return-after-deadline emits `contract_violation`, then remains permanently fail-stopped with
   the same zero restoration/redelivery/release/return/second-writer proof;
4. the parent terminates and reaps only its exact isolated fixture after observing the bound state;
5. invalid, missing, duplicate, backward, or post-terminal status records fail closed; and
6. legacy publication, C1B observer, cleanup ordering, and normal SLO evidence remain unchanged.

No sleep-only assertion is sufficient. No finite redelivery SLO is claimed for either violation
path. Owner SRE ratification of that explicit exception remains mandatory.

## Stops and downstream gate

Stop on a third file, hash drift, unbounded/high-cardinality record, publication worker, detached
continuation, finite violation-path redelivery claim, classifier dependence on callback-owned state,
legacy semantic change, provider/network/heartbeat/evidence/Phase-0/A1/A2/API/browser/Nix/service/
deployment action, staging, commit, deletion, delegation, or self-acceptance.

A1-AM3's exact four-file roadmap recovery remains design-resolved but NON-ACTIVATABLE until owner
ratification plus C1C-AM2 review, activation, acceptance, commit, and final byte rebind. A2 remains
blocked.

`RECORD: PREPARED_ONLY. No implementation or live action is authorized.`
