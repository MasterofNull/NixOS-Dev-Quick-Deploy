# QPPR-C1C Amendment 3 — synchronous publication with code-anchored fail-stop

**Status:** PREPARED_ONLY / NON-ACTIVATABLE
**Prepared:** 2026-07-19 UTC, Fable 5 orchestrator session
**Supersedes for implementation:** consumed C1C-AM2 activation; rejected candidate
`C1C-AM2-CANDIDATE-REJECTION.md` SHA-256 `544b84dd5a01c7b57e9ebcf27b7a0849a3eb395b1642b52f9ac7fce039a1a9b6`
**Inherits unchanged:** C1C-AM2 observable contract (`02f4c5317faa80aac7d2872d04eafa8cf5337c9297f1a335fe737160d06e8dfc`),
C1C-AM1 safety-first SRE policy (`bced486ad8af5ced589b71a853ccdffe2927dd5288b650e0c2b48c7eaa924f3c`),
owner SRE ratification recorded at PULSE 2026-07-18T20:39:01-0700

## Why AM3 exists

The AM2 candidate was rejected because it bound the observable contract to overall process runtime
instead of the synchronous publication callback, and its violation path still flowed through
handler/mask restoration, signal redelivery, and invocation-lock release. AM3 changes no requirement
of AM2 — it anchors every requirement to the exact code so the binding cannot be misread again, and
it resolves the one real contradiction the rejected attempt exposed: the predecessor's daemon-thread
publication is itself a prohibited worker.

## Exact ceiling (unchanged, restored predecessors)

| Path | Exact predecessor SHA-256 |
|---|---|
| `scripts/testing/harness_qa/core/process_lifecycle.py` | `ceef8fbe3ba3688ff60525c68167f914500959012e7345692f09f37f6ce0b38e` |
| `scripts/testing/test-qa-provider-probe-lifecycle.py` | `4dc49ef8133cfa8ab22372ea5a3b402585e1b3a18a9bff75180fe338ae3efac7` |

Observer regression frozen at `a17d70be7e9225435ac5cc28a13024d0a6a1885a56e149737775cfeafe1ee63b`.

## Code-anchored requirements

All line numbers refer to the predecessor bytes above.

**R1 — The governed contract is the `publication` callback, nothing else.** The subject is the
invocation currently at `process_lifecycle.py:1051-1057`: after a first signal, `publication` is run
on a `threading.Thread(daemon=True)` and joined with a timeout, after which lines 1061 (`_INVOCATION_
LOCK.release()`) and 1065 (`_restore_and_redeliver(…)`) execute unconditionally. The publication
observer must attach to THIS invocation. It must not attach to process spawn, the probe deadline
(`deadline_s`), process exit, or any other event. Binding the observer to `deadline_exceeded` or any
ordinary failure class is the rejected-candidate defect and an automatic acceptance failure.

**R2 — Remove the worker; invoke synchronously.** When the new publication-status barrier is
supplied (`publication_fd` plus `publication`), the callback runs synchronously in the owner thread.
No `threading.Thread`, worker, daemon, task, queue, retry, or second writer may be created for it
(AM2: "The lifecycle owner never creates a publication worker"). The legacy path — `publication`
without `publication_fd` — keeps the existing lines 1051-1057 byte-for-byte semantics; the new
behavior is strictly opt-in.

**R3 — Sequence-1 record immediately before the synchronous call.** Emit exactly
`qa.provider-publication.v1|1|running|<absolute_deadline_monotonic_ms>\n` where the deadline is the
absolute same-host monotonic time of the publication barrier: `first_signal_at + margin`, the same
≤5-second restoration/redelivery budget already computed at line 1053 — not a relative duration, and
not derived from `deadline_s`. Record ≤ `PIPE_BUF`, ASCII, no provider identity/PID/argv/path/
output/environment/credential/verdict. Descriptor validation follows the accepted C1B rules
(write-only, nonblocking, FIFO, `FD_CLOEXEC`, validated then duplicated); the rejected candidate's
`_open_publication_observer` validation logic satisfied this and may be reused.

**R4 — On-time return.** If the callback returns and observer monotonic now ≤ the bound deadline:
emit sequence-2 `completed` (or `cancelled` if the lifecycle skipped invocation because the
remaining budget was already zero), then proceed normally — lock release, restoration, redelivery
within the existing ≤5-second SLO. Existing SLO evidence must remain untouched.

**R5 — Late return: fail-stop that structurally precedes BOTH restoration paths.** If the callback
returns with observer monotonic now > deadline: emit sequence-2 `contract_violation`, then
permanently fail-stop. "Permanently fail-stop" is defined mechanically, because the rejected
candidate proved prose is not enough. The predecessor has TWO code paths that restore/redeliver/
release, and the violation path must be unreachable by both:

- the `except Exception:` handler at predecessor line 1083, whose recovery branch releases the
  invocation lock at line 1118 and reaches `_restore_and_redeliver(…)` at line 1142; and
- the `finally:` block at line 1160, which releases the lock at line 1179 and calls
  `_restore_and_redeliver(…)` at line 1184 whenever `lock_held`/`controller` still carry live state.

Before raising, the implementation must therefore neutralize the shared restoration state that both
paths consume: the invocation lock is NOT released (`lock_held` set false while the lock object
stays held, so every later `run_owned_process` in the process returns `probe_busy` — the enforced
"no later provider start"), and the signal controller must NOT reach `_restore_and_redeliver`
(set `controller = None` without transferring it to a redelivery variable). The violation exception
must not be classifiable as the generic `except Exception:` recovery case — a dedicated exception
type re-raised before that handler's recovery logic is the expected shape. Child-process teardown
via `_exceptional_teardown` remains permitted and required — the prohibition covers handler/mask
restoration, redelivery, lock release, and ordinary return, not child cleanup. A violation path
that reaches line 1118, 1142, 1179, or 1184 with live state is an automatic acceptance failure.

**R6 — Never-returning callback: blocked owner, authoritative external classifier.** Because R2
makes the call synchronous, a callback that never returns blocks the owner thread before lock
release, restoration, redelivery, and ordinary return — safety holds structurally, with no code
after the call needed to enforce it. The blocked owner cannot emit sequence-2; the authoritative
state is the exported pure classifier (AM2 rule verbatim): last valid record `running` AND observer
monotonic now > bound deadline AND no valid sequence-2 ⇒ `CONTRACT_VIOLATION`. The classifier
depends only on the validated record, the bound deadline, injected observer monotonic time, and
sequence-2 presence — no callback state, thread inspection, wall time, PID, or stuck-owner marker.
Missing/invalid record ⇒ `unavailable`, never healthy. Once violated, later data cannot downgrade
the classification; the classifier must treat a sequence-2 arriving after a violation-classified
point as invalid post-terminal input, and tests must prove it. The rejected candidate's
`classify_publication_contract` skeleton is close and may be corrected rather than rewritten.

**R7 — Record validation fails closed.** Invalid, missing, duplicate, backward, or post-terminal
records classify as `unavailable` or retain the violated state; they never produce
`completed`/`cancelled`. Status backpressure (full pipe, closed reader) disables emission without
altering cleanup, redelivery, or creating a fallback writer.

## Deterministic proof (isolated fixtures, no sleep-only assertions)

1. On-time `completed` and the zero-budget `cancelled` path emit exact sequence 1/2; existing
   ≤5-second redelivery evidence unchanged.
2. Never-return: an event-blocked callback in a subprocess fixture emits `running`; injected
   classifier time one millisecond past the bound yields `CONTRACT_VIOLATION`; the fixture proves no
   restoration, no redelivery, no lock release, no ordinary return, no later provider, no second
   writer, no publication thread; the parent then terminates and reaps only its exact isolated
   fixture.
3. Late-return: an event-delayed callback past the deadline emits `contract_violation`; the same
   fixture-process proof of permanent fail-stop, including a follow-up `run_owned_process` in the
   fixture returning `probe_busy`.
4. Strict rejection of invalid/duplicate/backward/post-terminal records, including sequence-2 after
   a classified violation.
5. Legacy publication without `publication_fd` (daemon thread, join, restore) byte-frozen semantics;
   C1B observer tests and the frozen observer file unchanged.
6. `rg -n "threading.Thread" scripts/testing/harness_qa/core/process_lifecycle.py` shows no new
   thread creation attributable to the barrier path.

No finite redelivery SLO is claimed for either violation path — the owner's recorded SRE
ratification covers exactly this exception and carries forward to AM3 unchanged; activation must
restate it.

## Stops

Stop on: a third file; hash drift; observer bound to any event other than the `publication` callback
invocation; any new thread/worker/task/retry/second writer on the barrier path; a violation path
that reaches restoration/redelivery/lock release/ordinary return; finite violation-path redelivery
claim; classifier dependence on callback-owned state or wall time; legacy-path semantic change;
unbounded/high-cardinality records; provider/network/heartbeat/evidence/Phase-0/A1/A2/API/browser/
Nix/service/deployment action; staging; commit; deletion; delegation; self-acceptance.

A1-AM3 four-file recovery remains NON-ACTIVATABLE until C1C-AM3 is reviewed, activated,
independently accepted, committed, and finally rebound. A2 remains blocked.

`RECORD: PREPARED_ONLY. No implementation or live action is authorized.`
