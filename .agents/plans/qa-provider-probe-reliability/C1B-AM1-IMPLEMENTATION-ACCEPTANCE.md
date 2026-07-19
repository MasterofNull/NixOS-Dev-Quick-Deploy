# QPPR-C1B Amendment 1 lifecycle ordering — independent implementation acceptance

**Reviewed:** 2026-07-19
**Reviewer:** `codex-subagent-qppr-c1b-am1-acceptance` — independent acceptance lane
**Verdict:** **PASS**

## Authority and exact subjects

The owner activated the independently reviewed single-use authorization for
`codex-subagent-qppr-c1b-am1-implementer` from `2026-07-18T18:08:30Z` through
`2026-07-19T18:08:30Z`. The authorization and final implementation subjects match the hashes
assigned to this review exactly:

| Subject | Expected SHA-256 | Observed SHA-256 | Result |
|---|---|---|---|
| `C1B-AM1-IMPLEMENTATION-AUTHORIZATION.md` | `9cfcf7f633f8cebc1a8ed67cb6f5f258daab450d9b7756106041f21660b0a4c6` | `9cfcf7f633f8cebc1a8ed67cb6f5f258daab450d9b7756106041f21660b0a4c6` | exact |
| `scripts/testing/harness_qa/core/process_lifecycle.py` | `ceef8fbe3ba3688ff60525c68167f914500959012e7345692f09f37f6ce0b38e` | `ceef8fbe3ba3688ff60525c68167f914500959012e7345692f09f37f6ce0b38e` | exact |
| `scripts/testing/test-qa-provider-probe-observer.py` | `a17d70be7e9225435ac5cc28a13024d0a6a1885a56e149737775cfeafe1ee63b` | `a17d70be7e9225435ac5cc28a13024d0a6a1885a56e149737775cfeafe1ee63b` | exact |

The bound design packet is exact at
`dfa55f65f6efce20389d6ba0de9313a1bd354c8fb0a31ddfc2f594dd2e050474`; the normalized prior
`REQUEST_REVISION` acceptance is exact at
`47b354f07862514093daa555bb313be30b65e95b898a1d0e8d09afd67211cb05`; and the original C1B
authorization and design remain exact at `96b7d5c646c14e9526fe6f45e513e603788218cab4d76ef46c388365f6ff31d5`
and `d6ff76f71f25e322c7cdd6e70f51afcaedda2b86ab2446c1827075dc6d45d06c`.

The implementation inventory is exactly the authorized two paths: the existing process owner is
modified and the focused observer test is new. No third implementation path or path substitution
is part of this candidate. Foreign worktree changes were not attributed to this slice.

## Defect correction and adversarial proof

The emitter now binds every lifecycle state to the frozen rank
`starting < running < terminating < reaping < terminal`. It returns before mutating rank, sequence,
or elapsed-record construction when an attempted transition is non-increasing. Consequently, the
exceptional teardown reached after `reaping` continues its existing cleanup but suppresses the
contradictory late `terminating` event. Cleanup that starts before `reaping` still emits
`terminating` immediately before its first `SIGCONT`.

The new injected-fault regression raises on the first `_reap_pid` call observed after `reaping` and
proves all of the following:

- the exact event sequence is `starting, running, reaping, terminal` with monotonic sequence and
  elapsed fields;
- `terminal` occurs exactly once and no late `terminating` is emitted;
- the result remains truthfully `cleanup_failed`;
- required `sigcont` and reap cleanup actions still occur;
- the fixture child set returns to its baseline; and
- the one owned observer duplicate is closed.

The existing pre-`reaping` injected exception continues to produce the ordered
`starting, running, terminating, reaping, terminal` sequence. Clean, spawn-failure, timeout,
interruption, and residual-child paths likewise retain their frozen optional-state order and end in
one terminal event.

## Validation evidence

- `python3 scripts/testing/test-qa-provider-probe-observer.py`: **PASS, 8/8 in 7.738 s**.
- `python3 scripts/testing/test-qa-provider-probe-lifecycle.py`: **PASS, 29/29 in 51.174 s**.
- `python3 -m py_compile` on both candidate paths: **PASS**.
- `ruff check` on both candidate paths: **PASS**.
- `git diff --check` on both candidate paths: **PASS**.
- Diff-only security scan: **PASS**. Matches were limited to the accepted credential-redaction
  expressions; no hardcoded credential, network client, shell execution, or unsafe dynamic
  execution was introduced.
- Post-test `python3` process scan for observer/lifecycle fixtures: **PASS, zero remaining fixture
  processes**.
- `scripts/governance/tier0-validation-gate.sh --pre-commit`: **PASS, 23/23**, including QA Phase 0
  at 172 checks and roadmap verification at 609 checks.

The focused and parent suites preserve caller/duplicate `FD_CLOEXEC`, write-only nonblocking FIFO
validation, 96-byte bounded records, observer-fault disablement, descriptor closure, cleanup and
result normalization, signal restoration and exactly-once redelivery, terminal-before-publication,
the four/five-second SLOs, and default `observer_fd=None` behavior. No callback, observer thread,
queue, acknowledgement, retry, blocking observer I/O, schema/state expansion, or provider/profile/
budget change was observed.

## Exclusions and next authority gate

No provider or network execution, heartbeat/evidence write, Phase-0, shell, dashboard/backend/API,
Nix/service/broker/cgroup, deployment, traffic, A1/A2, staging, commit, rollback, or deletion action
was performed by this reviewer. Only the orchestrator may stage and commit these exact accepted
subjects. This PASS does not activate QPPR-A1/A2 or any runtime/live path.

VERDICT: PASS — exact QPPR-C1B-AM1 subjects satisfy the ordering correction and all retained C1B acceptance contracts
