# Local Delegation Reliability Implementation Plan

Status: **R0 COMPLETE / ACCEPTED — R0M PLANNING ACTIVE; R1–R4 UNAUTHORIZED**
Parent: `.agent/PROJECT-LOCAL-DELEGATION-RELIABILITY-PRD.md`

## 1. Authorization boundary

This plan requests authorization for **R0 only**: seven new contract/fixture assets and executable
reproductions. R0 must not import from, alter, register, or project into the live delegation,
Phase-0, validation-registry, or dashboard paths. R1–R4 remain unauthorized until R0 is independently
accepted.

The staged L2B-A 14-file candidate remains a separate change set. R0 has zero inventory overlap and
must fail its adoption guard if any live path consumes it before later authorization.

## 2. Exact R0 inventory

1. `.agent/PROJECT-LOCAL-DELEGATION-RELIABILITY-PRD.md`
2. `.agent/PROJECT-LOCAL-DELEGATION-RELIABILITY-PLAN.md`
3. `config/schemas/local-delegation-runtime-policy.schema.json`
4. `config/local-delegation-runtime-policy.json`
5. `scripts/ai/lib/local_delegation_reliability.py`
6. `scripts/testing/fixtures/local-delegation-reliability-golden.json`
7. `scripts/testing/test-local-delegation-reliability.py`

Operational collaboration projections may change but are not implementation inventory.

## 3. R0 pure contract module

`local_delegation_reliability.py` must be pure and dependency-light. It may:

- validate the committed policy;
- allocate deterministic test IDs through an injected entropy/time source;
- resolve an effective budget/liveness plan from explicit task facts and policy;
- model the state machine and renewals without sleeping or spawning processes;
- normalize evidence fingerprints;
- model cancellation transitions from injected process observations;
- model fair admission, execution-epoch exhaustion, checkpoint/yield/requeue, fenced lease CAS,
  registry CAS, immutable context/RSS admission, and sequence-bound progress validation;
- run committed golden fixtures and return sanitized contract health.

It must not import `dispatch.py`, `aq-agent-loop`, `agent_executor.py`, task registry, switchboard,
live callers, process APIs, network clients, environment state, or telemetry writers.

## 4. Required R0 fixtures

- same-second allocation with 100 injected entropy values and a 10,000-ID deterministic set;
- collision rejection for repeated entropy;
- wrapper-to-result identity propagation model;
- budgets for code, structured, research, tool-call, repair, and synthesis turns;
- characterization of imported 256/800 constants plus literal 512/256 retry/synthesis overrides;
- explicit override provenance and invalid/undersized implementation budget rejection;
- queue wait followed by cold prefill and long active generation without false timeout;
- optional operator wall-clock expiry versus continuing trusted progress, plus cumulative capability
  exhaustion that checkpoints/yields instead of self-renewing;
- FIFO/weighted arbitration, priority aging, maximum slot residency, bounded queue age, epoch/quantum
  exhaustion, checkpoint/yield/requeue, and a starvation adversary;
- typed queue, prefill, generation-silence, tool, orphan, and operator-cap failures;
- >12 distinct read fingerprints accepted with checkpoints;
- >10 distinct observation fingerprints accepted with checkpoints;
- repeated identical read and missing-file fingerprints nudged then stopped;
- SIGTERM success, grace expiry/SIGKILL success, cancel-failed, repeated-cancel, PID-reuse, and
  cancel-vs-complete state traces with exactly one terminal publication;
- descriptor-bound canonical worktree/path leases, symlink/overlap rejection, fencing tokens,
  acquire-before-inference, death-before-release, and stale-owner recovery;
- concurrent registry mutations, stale-generation rejection, and lost-update detection;
- old-inode/new-inode replacement interleavings proving a dedicated stable lock spans generation
  CAS, atomic replace, file fsync, and parent-directory fsync;
- context pre-admission, compaction integrity, RSS/OOM cleanup, and zero leaked authority;
- trusted producer/causal-operation/sequence progress plus truncation, replay, reorder,
  stale-producer, forged-producer, and volatile-only tamper cases;
- correlated authoritative `QUEUED -> PREFILL -> GENERATING` transitions, unavailable-evidence
  fail-closed behavior, and calibration provenance/freshness/cold-warm uncertainty;
- switchboard-only admission, direct `/slots` poll TOCTOU contention, and rejection of a competing
  slot authority or any inference-capable direct llama bypass;
- declared environment override acceptance and undeclared-live-alias drift rejection;
- a live-source manifest with normalized hashes and static/subprocess D1–D11 characterizations;
- a bidirectional adoption guard proving R0 neither imports live runtime surfaces nor is imported or
  consumed by them.

## 5. Evidence boundary

R0 contract health is test output only. Phase-0 registration, Bash fallback, validation-registry
entries, dashboard backend/UI, and live telemetry are explicitly deferred to R4. The golden fixture
records, and the focused test verifies:

- normalized source paths and content hashes for each D1–D11 reproducer;
- the defect predicate and expected current result;
- the proposed fixed-contract result generated only by the pure model;
- stable fixture/vector digests and sanitized reason codes.

The test may read the named live sources and launch bounded fixture subprocesses, but the pure module
may not import them. Every subprocess uses an isolated temporary working directory, HOME, and state
root; a minimal allowlisted environment; no network, socket, model-service, live-agent, or delegation
calls; no canonical registry, sidecar, telemetry, or repository writes; and read-only source or a
synthetic copied fixture only. Process count, wall time, CPU, address space/RSS, and output bytes are
bounded. The test compares before/after hashes for every frozen live source and relevant canonical
state directory. Source drift or any mutation produces an explicit characterization failure, never
an implicit claim that the defect remains reproduced.

## 6. Validation

```bash
python3 scripts/testing/test-local-delegation-reliability.py
python3 scripts/testing/test-local-inference-budget.py
python3 scripts/testing/test-analysis-only-stagnation-mode.py
python3 scripts/testing/test-exploration-stagnation-guard.py
python3 scripts/testing/test-local-agent-first-token-timeout.py
scripts/governance/tier0-validation-gate.sh --pre-commit
```

R0 passes only when an independent flagship reviewer confirms the fixtures characterize D1–D11,
cover starvation, epoch, PID, CAS, fencing, terminal-race, OOM, and telemetry-integrity cases, and
the proposed R1–R4 contracts cannot authorize live changes. Tier0 is a regression gate only; R0
adds no Phase-0 check until R4.

After R0 acceptance, a separately planned and reviewed **R0M monitored-work slice** must close the
current visibility gap before R1. Its acceptance requires task-level projection for internal Codex
collaboration, local/Claude registry delegations, and Antigravity inbox work; PID/cgroup correlation;
wrapper/child deduplication; executable-aware daemon classification; stale-process expiry; and an
Agentic Ops fixture proving active, idle, completed, and uncorrelated states. R0M must not change
inference routing or consume the R0 runtime policy.

## 7. Proposed later implementation inventory

R1–R4 will be split after R0 evidence. Expected live-path candidates, not yet authorized:

- `scripts/ai/delegate-to-local`
- `scripts/ai/aq-agent-loop`
- `scripts/ai/lib/dispatch.py`
- `scripts/ai/lib/task_config.py`
- `scripts/ai/lib/task_registry.py`
- `ai-stack/local-agents/agent_executor.py`
- `ai-stack/mcp-servers/shared/llm_config.py`
- `ai-stack/switchboard/switchboard.py`
- `config/env-contract.yaml`
- focused tests, Phase-0, registry, dashboard backend/UI

Expected R0M candidates, also not yet authorized, include `scripts/ai/aq-tui-dashboard`, the existing
collaboration/delegation event projection surfaces, focused process-classification/correlation tests,
and documentation. R0M requires its own exact inventory and cannot be silently absorbed into R1.

Any Nix/service activation is a distinct deployment slice after repo-only live-path tests pass.

## 8. Stop conditions

Stop and request revision if R0 imports live code, changes a live caller, introduces a new state
store, treats heartbeat as progress, removes all silence bounds, permits concurrent unleased writers,
changes the L2B-A staged inventory, or adds dashboard/Phase-0/registry wiring. Dashboard and Phase-0
coverage are mandatory R4 promotion gates, not R0 assets.
