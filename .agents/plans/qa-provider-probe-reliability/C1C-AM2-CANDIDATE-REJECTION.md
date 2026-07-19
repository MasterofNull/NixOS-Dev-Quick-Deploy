# QPPR C1C-AM2 candidate rejection — orchestrator review

**Reviewer:** Fable 5 orchestrator session (orchestrator reject authority; not a formal acceptance grant)
**Reviewed:** 2026-07-19 UTC
**Implementer:** Claude Haiku 4.5 sub-agent, under owner identity-substitution override (PULSE
2026-07-18T20:49:38-0700) for consumed activation
`auth-qa-provider-probe-reliability-c1c-am2-20260719`
**Verdict:** **REQUEST_REVISION** — candidate rejected before any acceptance dispatch

## Rejected candidate identity (preserved as evidence, removed from working tree)

| File | Rejected-candidate SHA-256 | Preserved copy |
|---|---|---|
| `scripts/testing/harness_qa/core/process_lifecycle.py` | `f01a460819a5e1b6deef2688ec1fb5c64aa0b38f6a4f2a1080bdcc5800692716` | `evidence/rejected/c1c-am2-haiku-process_lifecycle.py` |
| `scripts/testing/test-qa-provider-probe-lifecycle.py` | `61b2301e8574c02729d4ed0c13b8dd8be637254e380b7c93afeafe1d8dc8a5fd` | `evidence/rejected/c1c-am2-haiku-test-qa-provider-probe-lifecycle.py` |

Working tree restored to exact predecessors (`ceef8fbe…`, `4dc49ef8…`); frozen observer test
unchanged (`a17d70be…`); baseline re-validated: 29/29 lifecycle + 8/8 observer tests pass.

## Why the candidate fails the amendment

The amendment (`C1C-AM2-OBSERVABLE-FAIL-STOP-AMENDMENT.md`, `02f4c531…`) governs the **synchronous
publication callback** — the `publication` callable invoked at `process_lifecycle.py:1200–1206` after
a first signal, currently a daemon thread with `worker.join(timeout=…)` followed unconditionally by
invocation-lock release and `_restore_and_redeliver(…)`. That cooperative-only join is the exact
defect C1C-AM1/AM2 exist to fix. The candidate never modified that path.

1. **Observer bound to the wrong contract (disqualifying).** `emit_running()` fires before *process
   spawn*; `contract_violation` fires when the overall probe deadline (`deadline_s`) expires — the
   ordinary, expected `deadline_exceeded` failure class; `completed` fires on any process exit,
   including interrupted/nonzero, regardless of publication behavior. The amendment requires the
   sequence-1 record "before invoking the synchronous callback," the deadline bound to the
   publication barrier, and `completed|cancelled` tied to the callback's on-time return.
2. **Fail-stop violates its own boundary (disqualifying).** On the (mis-bound) violation the
   candidate raises `_PublicationContractViolation`, which the dedicated `except` re-raises — but the
   `finally` block still executes `_restore_and_redeliver(…)` and `_INVOCATION_LOCK.release()`.
   Handler/mask restoration, signal redelivery, and lock release after a classified violation are
   exactly what the amendment prohibits ("permanently fail-stops before handler/mask restoration,
   redelivery, invocation-lock release, ordinary return, or later provider start").
3. **Behavior regression on a normal path.** Any caller passing `publication_fd` whose probe
   legitimately exceeds `deadline_s` now gets an exception instead of the structured
   `deadline_exceeded` terminal result, bypassing the in-line cleanup block (tree teardown survives
   only via the exceptional path).
4. **Never-returning callback remains unfixed.** The daemon-thread continuation still outlives
   `join(timeout)` (a prohibited detached continuation), redelivery still proceeds after timeout, and
   no observer record or classifier binding covers it — the core scenario of the amendment.
5. **Record semantics drift.** Sequence-1 carries a relative duration (`deadline_s * 1000`), not the
   required absolute same-host monotonic deadline; `cancelled` is unreachable.
6. **Tests prove the wrong thing.** The four added tests encode the mis-bound semantics, so 33/33
   passing does not evidence the amendment. Deterministic proofs 1–4 of the amendment (event
   barriers, injected classifier time, zero restoration/redelivery/release proof, isolated-fixture
   reap) are absent.

Salvageable pieces for a future revision: `_open_publication_observer` descriptor validation follows
the C1B rules correctly, and `classify_publication_contract` is close to the required pure rule
(needs absolute-monotonic deadline semantics and explicit non-downgrade treatment).

## Consequence

The single-use activation was consumed by the implementer's complete two-file report. A corrected
candidate requires a fresh amendment/authorization cycle (C1C-AM3) with new frozen bytes, new
independent review, and new owner activation. A1-AM3 remains NON-ACTIVATABLE; A2 remains blocked.

`VERDICT: REQUEST_REVISION — candidate bound the observable contract to process runtime instead of the
synchronous publication callback and its fail-stop does not precede restoration/redelivery/lock
release; baseline restored, evidence preserved, C1C-AM3 required.`
