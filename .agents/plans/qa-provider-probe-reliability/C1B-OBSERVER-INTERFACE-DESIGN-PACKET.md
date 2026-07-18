# QPPR-C1B — Nonblocking lifecycle-observer interface

Status: **PREPARED_ONLY / DESIGN_ONLY / REVISION 2 / UNAUTHORIZED**
Prepared: 2026-07-18
Predecessor commit: `19c78faaf5ab6d3635ac05a80fd5ba3c63cb1aae`
Revision basis: independent reviews SHA-256
`dc1f2a3835291c7a587e33c5a3096b09a5f4610d816cd1d9a51dd1abda651b92` and
`26e74adc45dd69b8ef88b95109c21d69cb07adb33c5cebeb51952affdf6c9fa4`.

Revision 2 retains the accepted descriptor-only observation architecture while freezing terminal
event ordering relative to provisional publication and replacing an unobservable descriptor-
provenance claim with an explicit `FD_CLOEXEC` preflight contract.

## 1. Defect and decision

Accepted C1 owns the true `starting|running|terminating|reaping|terminal` transitions but exposes
only a terminal result. A1 cannot truthfully publish internal cleanup states, and a callback or
worker-thread workaround could block cleanup, outlive terminal return, or fabricate state.

C1B adds one optional descriptor-only observation interface to `run_owned_process`. The observer is
a caller-created nonblocking pipe. The lifecycle owner duplicates and validates its write end, emits
only fixed bounded records with nonblocking `os.write`, ignores observer backpressure/failure, and
closes its duplicate immediately after exactly one terminal event. A1 may consume these truthful
events; it never synthesizes terminating or reaping.

## 2. Bound predecessor and exact two-file ceiling

| # | Operation | Path | Frozen predecessor |
|---:|---|---|---|
| 1 | MODIFY | `scripts/testing/harness_qa/core/process_lifecycle.py` | `d458b1044850b336374745c28254a808aba153b16225eedb82396873bc844170` |
| 2 | NEW | `scripts/testing/test-qa-provider-probe-observer.py` | must be absent |

Bound design chain:

| Subject | SHA-256 |
|---|---|
| QPPR PRD | `7f4bf98c4962045c7da863994337cb41cf24798c3ab168ca19169e54f2bebf0d` |
| C1 implementation acceptance | `3f084c8af9ce53aced4ab40a190688756ed547954262a2277324bdccb541599c` |
| C1 process owner | `d458b1044850b336374745c28254a808aba153b16225eedb82396873bc844170` |

No third implementation file or path substitution is permitted. C1A is orthogonal: it changes the
schema and original lifecycle test, not either C1B path.

## 3. Frozen interface

`run_owned_process` gains exactly one optional keyword-only parameter:

```python
observer_fd: int | None = None
```

If non-null, the helper must use `fcntl(F_GETFD)` to require `FD_CLOEXEC` on the caller descriptor,
then `dup` it with close-on-exec semantics and require an open write-only nonblocking FIFO/pipe
(`O_NONBLOCK`, `S_ISFIFO`). It never clears nonblocking or close-on-exec mode. A descriptor missing
`FD_CLOEXEC`, or otherwise invalid, returns `contract_invalid` before spawn and does not close or
mutate the caller's original. The duplicated descriptor is also verified `FD_CLOEXEC`; provider
spawn retains `close_fds=True`. The contract makes no claim about unobservable descriptor
provenance—only these verifiable flags, type, mode, and closure properties.

Each event is one ASCII line no larger than 96 bytes and no larger than `PIPE_BUF`:

```text
qa.provider-probe-state.v1|<sequence>|<state>|<elapsed_ms>\n
```

- `sequence` is a decimal integer beginning at 1 and increasing exactly by one.
- `state` is the closed lifecycle enum.
- `elapsed_ms` is a monotonic nonnegative integer capped at 300000.
- The record carries no invocation, provider, PID, argv, path, output, environment, prompt,
  credential, error text, result, or acceptance verdict.

`os.write` occurs only on the lifecycle-owning main thread. `BlockingIOError`, `BrokenPipeError`,
short write, `EPIPE`, `EBADF`, and any observer-only error disable further observer writes and never
change process cleanup, terminal result, signal restoration, redelivery, or budgets. No callback,
queue worker, observer thread, retry, wait, flush, fsync, or acknowledgement is allowed inside C1B.

## 4. Exact state semantics

The helper emits at most one event for each state and preserves this partial order:

```text
starting -> running? -> terminating? -> reaping -> terminal
```

- `starting`: after contract/preflight and signal-controller ownership, immediately before spawn.
- `running`: only after process PID/pidfd/PGID/SID/start-time identity is bound.
- `terminating`: immediately before the first cleanup `SIGCONT`; absent when termination is not
  needed and never inferred by A1.
- `reaping`: immediately before the common quiescence/owned-descendant/leader-reap phase, including
  clean exit and exceptional teardown.
- `terminal`: exactly once after descriptor-bound cleanup and result normalization are complete,
  before the provisional-publication callback is started and before handler/mask restoration plus
  redelivery. This ordering is the synchronization edge used by A1's separately frozen terminal
  join; C1B does not write a heartbeat or add failure data to the observer record.

Preflight or observer-contract rejection that occurs before observation ownership emits nothing.
Spawn failure emits `starting -> reaping -> terminal`. A direct clean exit emits
`starting -> running -> reaping -> terminal`. Timeout/interruption/residual cleanup emits all five.
Exceptional teardown uses the same ordered emitter. Once terminal is attempted, the duplicate fd is
closed in the same `finally` boundary and no later branch may emit. Failure to deliver an observer
record is not permission to fabricate it elsewhere.

Observer work must consume no measurable lifecycle budget: adversarial acceptance requires the
four-second child-cleanup and five-second cleanup/restoration/redelivery SLOs to remain within the
accepted tolerances with a full pipe, closed reader, and injected write failures.

## 5. Required offline acceptance evidence

The new focused test uses local fixture subprocesses and real `os.pipe2(O_NONBLOCK|O_CLOEXEC)` pairs.
It must prove:

1. exact clean, spawn-failure, timeout, interruption, residual-child, and exceptional-teardown
   sequences and monotonic sequence/elapsed fields;
2. `terminating` precedes the first cleanup signal, `reaping` precedes reap, and `terminal` follows
   cleanup/result normalization;
3. a closed reader, full pipe, short write, injected `EPIPE|EAGAIN|EBADF`, and observer parse failure
   cannot alter the lifecycle result, cleanup order, descendant quiescence, or redelivery;
4. invalid blocking, read-only, regular-file, closed, negative, and `missing_cloexec` descriptors
   fail closed before spawn without closing or mutating the caller descriptor;
5. `FD_CLOEXEC` is verified on caller and duplicate, `close_fds=True` remains effective, and a local
   fixture provider cannot observe the duplicated descriptor;
6. no event occurs after terminal, no callback/thread is created, no retry occurs, and every helper
   duplicate is closed on normal, exception, and signal paths; and
7. the existing C1 lifecycle suite remains 27/27 offline with unchanged result/policy behavior.

Required validation: both focused lifecycle suites, Python compilation, changed-file security scan,
post-test process scan, and `scripts/governance/tier0-validation-gate.sh --pre-commit`.

## 6. Stop, rollback, and authority

Stop on a third file, predecessor drift, shared-file conflict, callback/thread/queue observer,
blocking descriptor operation, record expansion, provider/network/heartbeat/evidence/dashboard/API
action, schema/policy/budget/profile change, A1/A2 edit, service/Nix/deploy/traffic action, staging,
commit, rollback, deletion, or any provenance assertion not reducible to the frozen flag/type/mode
checks. Do not work around a stop.

Rollback is the atomic C1B commit, restoring the accepted helper hash and removing the new test only
after the archive/reference SOP is satisfied. It preserves C1A and all accepted C1 behavior; A1
remains blocked without C1B.

Exactly one bounded implementer owns both files and cannot delegate, stage, commit, deploy, or
self-accept. A different session reviews the exact candidate hashes. Only the orchestrator may
commit after final `PASS`. A separately reviewed authorization and explicit owner activation are
mandatory.

`RECORD: PREPARED_ONLY. C1B implementation, A1/A2 adoption, heartbeat/evidence writes, providers,
network, dashboard, deployment, and rollback remain unauthorized.`
