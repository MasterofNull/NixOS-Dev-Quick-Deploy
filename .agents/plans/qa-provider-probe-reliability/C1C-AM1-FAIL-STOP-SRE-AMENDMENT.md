# QPPR-C1C Amendment 1 — fail-stop publication safety boundary

**Status:** PREPARED_ONLY / OWNER SRE RATIFICATION REQUIRED / NON-ACTIVATABLE  
**Prepared:** 2026-07-19  
**Revision basis:** independent review
`15a1b110e2483d6be46aa8f46faf56fd27288ce4fbfc611fbea944dcb0c81e38`

## 1. Decision requiring owner ratification

An in-process callback cannot be both forcibly cancelled and guaranteed to preserve the accepted
five-second signal-redelivery SLO when it never returns. Python cannot safely terminate a thread;
redelivering while it remains alive violates no-post-redelivery continuation, while waiting forever
violates the liveness SLO. A killable child boundary is not a minimal safe prerequisite here because
A1 terminal publication joins parent-owned observer state, file descriptors, locks, and threads;
forking that multi-threaded state is unsafe and a spawnable publication protocol would require a
new service/protocol/store architecture beyond this bounded slice.

C1C-AM1 therefore chooses the smallest sound safety-first contract and makes its liveness tradeoff
explicit. For the exact independently reviewed A1 callback, a returning `completed|cancelled`
acknowledgement must preserve the existing five-second restoration/redelivery SLO. A callback that
does not return by its absolute deadline is a contract violation and the lifecycle owner **fail-
stops before signal restoration/redelivery**. It must not claim completion, release execution
authority, start another provider, or permit post-redelivery continuation. This exceptional path has
no finite redelivery SLO; operator intervention terminates the containing QA invocation. It is a
safety invariant, not a healthy or accepted result.

This is a deliberate revision of the C1 liveness contract for the opt-in C1C interface only. Legacy
`publication` behavior is unchanged. The owner must explicitly ratify this safety-over-liveness
tradeoff before C1C-AM1 can be activated. Without that ratification, implementation remains blocked.

## 2. Exact two-file inventory

| # | Operation | Path | Exact predecessor |
|---:|---|---|---|
| 1 | MODIFY | `scripts/testing/harness_qa/core/process_lifecycle.py` | `ceef8fbe3ba3688ff60525c68167f914500959012e7345692f09f37f6ce0b38e` |
| 2 | MODIFY | `scripts/testing/test-qa-provider-probe-lifecycle.py` | `4dc49ef8133cfa8ab22372ea5a3b402585e1b3a18a9bff75180fe338ae3efac7` |

The observer test remains frozen at
`a17d70be7e9225435ac5cc28a13024d0a6a1885a56e149737775cfeafe1ee63b`.
Any third implementation path, substitution, or predecessor drift is a hard stop.

## 3. Enforceable interface and state

The opt-in synchronous `publication_barrier(provisional_result, absolute_deadline)` remains mutually
exclusive with legacy `publication`. The lifecycle owner invokes it only after cleanup,
normalization, and C1B terminal-event attempt. The callback returns exactly `completed` or
`cancelled`; returning ends all callback execution on the owning main thread before restoration.

The owner tracks a closed publication state:

```text
NOT_REQUESTED -> RUNNING -> COMPLETED|CANCELLED
RUNNING -> CONTRACT_VIOLATION_FAIL_STOP
```

- `COMPLETED`: callback returned `completed` no later than the supplied deadline.
- `CANCELLED`: callback returned `cancelled` no later than the supplied deadline or raised before it.
- `CONTRACT_VIOLATION_FAIL_STOP`: the callback remains in progress beyond the deadline. Restoration,
  redelivery, invocation-lock release, ordinary return, and later provider start are prohibited.

Because the callback is synchronous, a non-returning callback already holds the lifecycle-owning
thread at the fail-stop boundary. No background worker is created and no redelivery can occur. The
contract does not claim that the owner can regain control from arbitrary native code. Monitoring
must classify an externally observed overrun as `publication_contract_violation`; a later recovery
slice may move publication to a broker-owned killable execution boundary.

## 4. Deterministic evidence

Offline tests must prove with events/barriers and an isolated fixture process:

1. returning `completed` and `cancelled` callbacks finish before restoration/redelivery and preserve
   the accepted <=5-second signal-to-redelivery SLO;
2. a deliberately non-returning callback reaches the fail-stop marker, then the parent fixture
   observes no redelivery, no callback continuation *after redelivery* (because redelivery never
   occurs), no invocation return, no second provider, and no lock-authority release;
3. the parent test terminates and reaps that isolated fixture using its exact child identity, proving
   the suite itself leaves no process behind without weakening the production fail-stop rule;
4. deadline-expired and exception callbacks return/cancel deterministically without retries;
5. dual-interface admission fails before spawn; legacy publication and observer regressions remain
   unchanged; and
6. no sleep-only assertion serves as the ordering proof.

## 5. Stops and authority

Stop on an attempt to claim finite redelivery for a non-returning callback, detach/daemonize callback
work, force-kill a Python thread, add a publication subprocess/protocol, relax legacy SLOs, change
result/schema/policy/budgets, expand inventory, or perform provider/network/heartbeat/evidence/
Phase-0/A1/A2/API/browser/Nix/service/deploy/traffic action. No staging, commit, deletion,
delegation, or self-acceptance.

Independent flagship review, explicit owner SRE ratification, exact authorization activation,
independent candidate acceptance, and orchestrator-only commit remain mandatory. C1C-AM1 completion
does not activate A1. A1-AM3 remains non-activatable until final exact post-C1C rebind. A2 remains
blocked.

`RECORD: PREPARED_ONLY / OWNER SRE RATIFICATION REQUIRED. C1C-AM1, A1/A2, providers, network, live
Phase 0, deployment, and every live action remain unauthorized.`
