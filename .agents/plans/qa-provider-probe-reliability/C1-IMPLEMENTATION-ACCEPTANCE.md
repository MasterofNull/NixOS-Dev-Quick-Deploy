# QA Provider Probe Reliability C1 Amendment 3 — Independent Implementation Acceptance

**Verdict:** **PASS**  
**Reviewed:** 2026-07-18  
**Review role:** independent acceptance, process-lifecycle, security, and SRE reviewer  
**Candidate authority:** `d4c574ddecd21c5f88e501806cde7593bb3fb1b4c59c003d3479d1527b035743`  
**Authorization review:** `eccd72ab06cec92a0be6759484ce2541198a28cc0eea929bcdb58b5a1c4c0fd4`  
**Implementation authority:** none

## Exact candidate-local PASS subject

All five paths remain untracked NEW files and absent from `HEAD`.

| Path | Verified SHA-256 |
|---|---|
| `scripts/testing/harness_qa/core/process_lifecycle.py` | `d458b1044850b336374745c28254a808aba153b16225eedb82396873bc844170` |
| `config/qa-provider-probe-contract.schema.json` | `afe2a2aa5c6de4fed87a224d8aa845317d5e734d9403e68ff164a98ca6544756` |
| `config/qa-provider-probe-policy.json` | `2cbe6e350f35cd9e0831186df31f9631a10c1e838fb0246fc1f56828abb4a6af` |
| `scripts/testing/fixtures/qa-provider-probe-vectors.json` | `92c21f55f07b4c5c751c545f1f5c633159b4329c7c514b77b17f6c18769b8c62` |
| `scripts/testing/test-qa-provider-probe-lifecycle.py` | `e15143277baa39b83c644227ce600768bac65e574d14bc5ddc71a00132673767` |

The bound design and authorization subjects retain their declared hashes. The five-file ceiling and
all static exclusions pass: no live provider execution/resolution, network, shell, Phase-0/runtime
adoption, A1–A3, service, Nix, environment-variable, port, store, broker, cgroup, dashboard,
deployment, traffic, cutover, cleanup of unrelated state, or rollback.

## Accumulated contract adjudication

- Draft-2020-12 objects are closed. The policy schema and runtime require the exact ordered four
  profile tuples and exact immutable 45/2/1/200, one-attempt, 4,096/65,536 budgets. Duplicate,
  reordered, omitted, cross-bound, raised-budget, and caller-override cases fail before spawn.
- The helper owns one argv-only `DEVNULL`/new-session process, continuously drains bounded streams,
  uses monotonic deadlines, pidfd plus start-time/PGID/SID identity, WNOWAIT leader anchoring,
  subreaper restoration, two-pass quiescence, and terminal reap. ESRCH and externally reaped direct-
  child races never authorize stale numeric group signalling.
- Frozen cleanup order and residual-member handling pass for deadline, self-stop, fork, leader-zero,
  cleanup-phase interruption, escaped session, and exceptional primary-cleanup failure.
- The exceptional finalizer now performs descriptor-bound best-effort teardown, quiescence, adopted-
  child/leader reap, and pidfd closure before restoring the subreaper, releasing the invocation lock,
  consuming controller ownership, restoring handlers/mask, and attempting one redelivery.
- Default, ignored, returning, non-returning, terminating-observer, raising, second-signal, and
  blocked-publication cases preserve Revision-3 semantics and the four/five-second bounds. A raising
  custom handler is invoked once and is not replayed by the finalizer.
- Both streams remain drained after caps. Stderr control characters, paths, generic credentials,
  `Authorization: Bearer`, and standalone `Bearer` values are sanitized; raw stdout is validation-
  only and absent from results. Overflow cannot pass.
- Golden `exit_only` and `machine_json_v1` normalization is one-spawn and covers the complete closed
  failure enum with lifecycle-first precedence and no retry.

## Exceptional-finalizer reproduction

A standalone real-SIGTERM fixture injected one primary `_send_group(SIGTERM)` fault. The returned
typed result was `fail/cleanup_failed` and recorded terminal `quiescence=complete` then
`reap=complete`. Independent observations at/after redelivery were:

```text
handler_calls=1
handler_lock_released=true
handler_restored=true
handler_subreaper=prior_subreaper=0
pidfds_closed=true
owned_children_after=[]
redelivered=true
signal_to_redelivery_elapsed=0.282 s
```

No reviewer cleanup was required and no unrelated process was waited or signalled.

## Validation evidence

- Python compilation — PASS.
- JSON parsing — PASS (3/3).
- Draft-2020-12 schema check and current policy/vector instance validation — PASS.
- Focused lifecycle suite — PASS (27/27 in 44.562 s).
- Standalone real-SIGTERM exceptional-finalizer reproduction — PASS, exit 0, empty stderr.
- Static forbidden-surface scan — PASS; only schema identifiers matched `http` text.
- Post-test fixture/process scan — PASS; no owned fixture or sleep child remained.
- Shared Tier-0 — PASS (orchestrator-serialized combined-candidate gate, 23 passed, 0 failed,
  exit 0). The five QPPR candidate hashes were reverified unchanged after the gate.

## Gate decision

The exact candidate is **PASS at every candidate-local and shared acceptance gate**. The
orchestrator-serialized `scripts/governance/tier0-validation-gate.sh --pre-commit` completed with
23 passed, 0 failed, exit 0, and all five reviewed candidate hashes remain exact. The orchestrator
may stage and commit this bounded C1 subject under the activated authorization. Any candidate hash
change requires fresh independent review.

This PASS does not authorize QPPR-A1, A2, A3, live providers, deployment, traffic, cutover,
rollback, or unrelated cleanup.
