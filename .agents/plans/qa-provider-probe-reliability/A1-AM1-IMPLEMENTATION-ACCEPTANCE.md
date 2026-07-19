# QPPR-A1 Amendment 1 host adoption — independent implementation acceptance

**Reviewed:** 2026-07-19
**Reviewer:** `codex-subagent-qppr-a1-am1-acceptance` — independent architecture, security, SRE, QA, and dashboard-contract lane
**Verdict:** **REQUEST_REVISION**

## Authority and exact candidate

The owner activated authorization
`5f992de921103870572cd765178e1a358e308a4ed7061efbb471fbfe499ad322` for
`codex-subagent-qppr-a1-am1-implementer` from 2026-07-18T17:23:48Z through
2026-07-19T17:23:48Z. The authorization, rebind, design, predecessor commits, and accepted C1A/C1B
evidence remain exact. The candidate contains exactly the authorized eight paths:

| Path | Observed SHA-256 |
|---|---|
| `scripts/testing/qa-provider-probe.py` | `755b730d6d7446d76f21933d2e273ca4ed7f8f65a808672e532caab007b5d0ab` |
| `scripts/testing/smoke-flagship-cli-surfaces.sh` | `98a1c8f2a9b67895f7e42d9ae176d65b706128d92b93033c1094c2b6d23bcdfb` |
| `scripts/testing/harness_qa/phases/phase0.py` | `b01edf1308c6433c6fae1316a75b7d4251b77df9afa5d8e4fb41b99c5ca63999` |
| `scripts/testing/harness_qa/core/result.py` | `4c72e8aa658a67a5168fb9817a21a247c596ac29aa55b7fd776d5f18f0320776` |
| `scripts/testing/harness_qa/core/context.py` | `ef2993079c1ffed301e9b9cc41014944706f37ca4e3879fb7605223af314e6ea` |
| `scripts/testing/harness_qa/main.py` | `2137974e61f991cf363ae0dbca1511f3d801728d01f43b5af974050e4df9f4c0` |
| `scripts/testing/harness_qa/reporters/json_out.py` | `7d62ff15da20e969384a858c67d8e0dea1b34423e941f205f780d66d65a11f29` |
| `scripts/testing/test-qa-provider-probe-adoption.py` | `f7e286dfa23ef3b22eea713e1ec4b9b350c3e5e4b29ba4a0098d9d4f0eb7123c` |

The two new paths were absent and the six modified-path predecessors match the authorization. No
ninth path, target substitution, staging, commit, deployment, provider call, network call, API call,
browser action, or A2 action was attributed to this review.

## Passing evidence

- Offline A1 adoption suite: **PASS, 12/12**.
- Accepted parent lifecycle suite: **PASS, 29/29**.
- Corrected lifecycle observer suite: **PASS, 8/8**.
- Existing dashboard QA single-flight structural test: **PASS**.
- Python compilation of all seven Python subjects, `bash -n`, `shellcheck`, and path-scoped
  `git diff --check`: **PASS**.
- `ruff check` on the two new Python subjects: **PASS**. A broad legacy-file Ruff run reports only
  pre-existing findings outside the changed lines and is not attributed to this slice.
- Changed-line credential, network, shell-injection, and HTML-injection scan: **PASS, no matches**.
- Tier-0 pre-commit gate: **PASS, exit 0**.

These successes confirm the eight-file boundary, basic fake-provider normalization, policy order,
direct Phase-0 call site, compatibility-shell delegation, dashboard-safe structural skip, immutable
invocation reservation order, serializer plumbing, stable lock inode across ordinary contention,
and offline-only test execution. They do not close the contract defects below.

## Blocking findings

1. **Terminal publication is asynchronous across signal redelivery.** At
   `scripts/testing/qa-provider-probe.py:340`, C1 receives `consumer.submit_result` as its bounded
   publication callback. That callback only stores a result and sets an event; it does not wait for
   the validated terminal event, acquire a one-shot `COMMITTING` state, write the terminal heartbeat,
   or cancel the join before returning. The daemon reader performs the write later. C1 can therefore
   restore/redeliver a signal before the heartbeat write, and the reader can write after redelivery.
   This violates the frozen one-terminal-event/result join, callback participation, and no-write-
   after-redelivery contracts. The focused suite contains no default/custom/ignored signal fixture
   proving terminal projection before redelivery and zero writes afterward.

2. **The terminal result is neither closed-schema validated nor fully identity-bound.** The checks
   at `scripts/testing/qa-provider-probe.py:262-277` accept only matching invocation/provider and a
   literal terminal state. They do not require the expected profile, validate the closed C1 result
   schema, validate result/failure-class values, or bind the expected terminal sequence. A diagnostic
   supplied a wrong profile and unknown failure class; `invalid` remained false and `result_ready`
   became true. Such a value can become terminal projection input, contrary to the design.

3. **Canonical execution can fabricate its immutable invocation identity.** At
   `scripts/testing/qa-provider-probe.py:302`, a missing `qa_invocation_id` generates a UUID even when
   `canonical=True`. A no-spawn lock-contention diagnostic confirmed that canonical mode returned four
   records under a newly fabricated UUID. Canonical Phase-0 publication must reject a missing reserved
   invocation; only standalone compatibility mode may mint its non-authoritative identity.

4. **Unsafe existing lock permissions are normalized before admission instead of rejected.** At
   `scripts/testing/qa-provider-probe.py:88`, `fchmod(0600)` occurs before the first safety validation.
   A diagnostic created an effective-user-owned mode-0666 persistent lock; `acquire()` returned true
   after silently changing it to 0600. The frozen stable-inode contract requires proving the named
   inode is not group/world writable before admission and failing closed on a violation.

5. **The evidence serializer is open rather than the frozen four-record contract.** At
   `scripts/testing/harness_qa/core/result.py:35-36`, any non-`None` list is emitted unchanged. A
   diagnostic assigned `[{"secret": "accepted"}]`, and `to_dict()` published it. Neither the Phase-0
   assignment at `phase0.py:487` nor the serializer independently validates exactly four items,
   policy order, reserved invocation identity, and the closed result schema. This permits sensitive
   or malformed details to cross the JSON and immutable-evidence boundary.

## Required revision boundary

Retain the exact eight-file ceiling. Implement the frozen `TerminalProjectionJoin` as the sole
terminal writer with compare-and-set inputs, full result/schema/profile/sequence validation,
callback-bounded commit, cancellation, and adversarial ordinary plus default/custom/ignored signal
tests proving no post-redelivery write. Require an existing reserved invocation for canonical mode.
Validate the persistent lock before any chmod/mutation. Make the single serializer enforce the exact
four-item closed, ordered, invocation-bound evidence contract and add negative tests for extra,
missing, reordered, malformed, sensitive, and cross-wired records. Any revised byte requires a new
hash-bound independent review; this reviewer made no candidate edit.

QPPR-A1 is not accepted or committable. QPPR-A2 remains blocked and non-activatable. No live provider,
heartbeat/evidence activation, API/browser vet, deployment, traffic, rollback, or unrelated action is
authorized by this record.

VERDICT: REQUEST_REVISION — terminal projection can race or follow signal redelivery, terminal inputs and four-item evidence are not closed-schema validated, canonical mode can fabricate invocation identity, and unsafe lock permissions are normalized before validation
