# QPPR-C1B Amendment 1 ordering correction — independent authorization review R2

**Reviewed:** 2026-07-18
**Reviewer:** `codex-subagent-qppr-c1b-acceptance` — independent design/authorization lane
**Verdict:** **PASS / PREPARED_ONLY**

This is a fresh exact-subject review after acceptance-record whitespace normalization and authority
rebind. `C1B-AM1-AUTHORIZATION-REVIEW.md` is stale history and grants no authority.

## Exact reviewed subjects

| Subject | Expected SHA-256 | Observed SHA-256 | Result |
|---|---|---|---|
| `C1B-AM1-LIFECYCLE-ORDERING-DESIGN-PACKET.md` | `dfa55f65f6efce20389d6ba0de9313a1bd354c8fb0a31ddfc2f594dd2e050474` | `dfa55f65f6efce20389d6ba0de9313a1bd354c8fb0a31ddfc2f594dd2e050474` | exact |
| `C1B-AM1-IMPLEMENTATION-AUTHORIZATION.md` | `9cfcf7f633f8cebc1a8ed67cb6f5f258daab450d9b7756106041f21660b0a4c6` | `9cfcf7f633f8cebc1a8ed67cb6f5f258daab450d9b7756106041f21660b0a4c6` | exact |
| Normalized C1B `REQUEST_REVISION` acceptance | `47b354f07862514093daa555bb313be30b65e95b898a1d0e8d09afd67211cb05` | `47b354f07862514093daa555bb313be30b65e95b898a1d0e8d09afd67211cb05` | exact |
| Current process-owner candidate | `dbc07131c03a4b98a81364077623dd75fbc07f370e4aca07ea0d5af926e982f1` | `dbc07131c03a4b98a81364077623dd75fbc07f370e4aca07ea0d5af926e982f1` | exact |
| Current observer-test candidate | `f5181d9aaecc15c66ddb6b0af3e3f6de0fc666b78ebfa81ae536da3d8267b614` | `f5181d9aaecc15c66ddb6b0af3e3f6de0fc666b78ebfa81ae536da3d8267b614` | exact |

The bound original C1B authorization remains
`96b7d5c646c14e9526fe6f45e513e603788218cab4d76ef46c388365f6ff31d5`, and the bound original C1B
design remains `d6ff76f71f25e322c7cdd6e70f51afcaedda2b86ab2446c1827075dc6d45d06c`.

## Rebind reconstruction proof

The revised subjects are semantically identical to the previously reviewed AM1 documents:

- replacing normalized acceptance hash `47b354f0...` with stale hash `452b47e2...` in the current
  design reconstructs design SHA-256
  `2aa9093b23df07646122a46a24b3921dbc0d4a6567b5aea9b4c8003d157e00ee` exactly; and
- making that same acceptance substitution plus replacing the rebound design hash `dfa55f65...`
  with `2aa9093b...` in the current authorization reconstructs authorization SHA-256
  `748dfffafa3b76371a640f067f356d85b6c2e4faecf7a16647db21a34031c070` exactly.

No correction semantics, inventory, stop condition, evidence requirement, or activation rule
changed during normalization and rebind.

## Scope and contract verdict

The amendment remains limited to two modifications:

1. monotonic lifecycle-event suppression in
   `scripts/testing/harness_qa/core/process_lifecycle.py`; and
2. the first-`_reap_pid`-after-`reaping` injected-fault regression in
   `scripts/testing/test-qa-provider-probe-observer.py`.

The frozen order remains `starting < running < terminating < reaping < terminal`. Optional states
remain optional. Non-increasing attempts cannot write or advance sequence/elapsed fields. Cleanup
entered before `reaping` retains truthful `terminating` before its first `SIGCONT`; cleanup entered
after `reaping` suppresses only the contradictory late event and continues cleanup unchanged.

All previously passing caller/duplicate `FD_CLOEXEC`, write-only/nonblocking FIFO validation,
descriptor closure, fixed 96-byte record, disable-on-observer-fault, terminal-before-publication,
result normalization, process cleanup, signal restoration/redelivery, four/five-second bounds, and
default `observer_fd=None` contracts remain mandatory. Callback/thread/queue/acknowledgement,
retry, blocking I/O, record/schema/state expansion, and provider/profile/policy/budget changes
remain prohibited.

The exact two-file ceiling and hard stops continue to exclude provider/network execution,
heartbeat/evidence writes, Phase-0, shell, dashboard/backend/API, Nix/service/broker/cgroup,
deployment, traffic, A1/A2, staging, commit, rollback, deletion, and scope growth.

## Authority and next gate

This authorization is single-use. Neither this review, the stale review, the original C1B
activation, broad preauthorization, nor silence activates it. Owner activation must name exact
authorization SHA-256 `9cfcf7f633f8cebc1a8ed67cb6f5f258daab450d9b7756106041f21660b0a4c6`, exactly one implementer,
an explicit activation and expiry no more than 24 hours apart, and the unchanged two-file ceiling
and stop conditions.

A different session must independently accept the revised implementation hashes. Both focused
lifecycle suites, compilation, lint, diff/security/process-leak checks, and Tier-0 must pass before
the orchestrator may stage or commit. Acceptance or commit cannot activate QPPR-A1/A2 or a provider
path.

`VERDICT: PASS`
