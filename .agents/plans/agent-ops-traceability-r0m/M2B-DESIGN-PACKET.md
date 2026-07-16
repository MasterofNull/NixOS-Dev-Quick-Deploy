# Agent Ops Traceability M2B — Atomic Dispatch Adoption Design Packet

Status: **PAUSED/SUPERSEDED BY AGENT CONNECTION RELIABILITY — NO IMPLEMENTATION AUTHORITY**
Parent design: `M2-DESIGN-PACKET.md` Revision 3
Base: `57b87e2d` (M2A accepted, committed, and dormant)
Prepared: 2026-07-16 by Codex orchestrator

> Runtime evidence after Revision 4 review proved that a caller-owned in-process supervisor remains
> inside the managed agent's parent-death sandbox/cgroup and cannot survive tool/session teardown.
> A sandboxed `systemd-run --user` escape probe was also denied. Receipt and activation-lock
> invariants remain inputs, but the launch boundary moves to the pre-existing host-side `aq-dispatchd`
> service in `.agent/PROJECT-AGENT-CONNECTION-RELIABILITY-PRD.md`. No M2B1 authorization may be
> prepared from this packet.

## 1. Outcome and activation boundary

M2B installs a single-process dispatch supervisor and dormant wrapper adapters, then activates them
through one separately authorized, lock-protected mode switch after legacy work drains. After
activation, a wrapper may launch provider work only after a durable queued record is projected, the
supervisor identity is attached with mandatory compare-and-swap (CAS), and an in-process
receipt-bound exec barrier is released. The Agent Ops TUI and Phase-0 checks expose the same contract
health before the switch can be activated.

This packet is a design and review artifact only. It does not authorize edits, dispatch cutover,
deployment, process termination, a new lifecycle store, M3, local-reliability R1–R4, inference
R1–R4, or owner-Q8 authority changes.

## 2. Preconditions and adoption guard

M2B cannot be activated unless all of these remain true at the candidate base:

1. M2A commit `57b87e2d` is reachable and its accepted files match their committed hashes.
2. No supported wrapper imports or invokes the M2A writer or barrier before the atomic candidate.
3. The three pre-adoption hardening defects in Section 4 are closed and covered by focused tests.
4. Both monitored flagship design lanes review this exact packet or the owner explicitly records a
   lane-specific waiver; implementation and acceptance are always separate decisions.
5. A fresh authorization binds the base, exact file inventory, packet hash, reviewer evidence,
   allowed implementer role, stop conditions, and single-use idempotency key.

Any partial wrapper adoption is a hard failure. Git staging or commit is not an activation boundary
because repository wrappers are executed directly. M2B therefore has two separately reviewed grants:
M2B1 installs dormant enforcement code while the activation manifest remains `legacy`; M2B2 drains
legacy work and flips that single manifest to `enforced` under the shared admission lock. Unknown,
missing, malformed, or version-mismatched manifest states fail closed.

## 3. Exact maximum implementation inventory

The M2B1 candidate may change only these twenty-two files:

1. `.agent/PROJECT-AGENT-OPS-TRACEABILITY-PRD.md`
2. `.agent/PROJECT-AGENT-OPS-TRACEABILITY-PLAN.md`
3. `config/schemas/agent-ops-projection.schema.json`
4. `scripts/ai/lib/agent_ops_projection.py`
5. `scripts/testing/test-agent-ops-projection.py`
6. `scripts/ai/aq-delegation-registry`
7. `scripts/ai/lib/task_registry.py`
8. `scripts/ai/aq-dispatch-supervisor` (new single-process launch broker and activator)
9. `config/schemas/agent-ops-dispatch-adoption.schema.json` (new closed activation contract)
10. `config/agent-ops-dispatch-adoption.json` (new atomic activation manifest; initially `legacy`)
11. `scripts/ai/aq-tui-dashboard`
12. `scripts/ai/delegate-to-local`
13. `scripts/ai/delegate-to-claude`
14. `scripts/ai/delegate-to-codex`
15. `scripts/ai/delegate-to-antigravity`
16. `scripts/ai/delegate-to-gemini`
17. `scripts/testing/harness_qa/phases/phase0.py`
18. `scripts/ai/_aq-qa-bash`
19. `config/validation-check-registry.json`
20. `docs/architecture/role-matrix.md`
21. `docs/operations/agent-ops-window.md`
22. `scripts/testing/fixtures/local-delegation-reliability-golden.json`

The M2A input schema is consumed but should not require modification. If implementation proves that
`config/schemas/delegation-task-record.schema.json`, another helper, Nix wiring, the web dashboard,
or any twenty-third file must change, stop and revise/re-review the inventory before editing it.

M2B2 changes only `config/agent-ops-dispatch-adoption.json` from the exact reviewed `legacy` document
to the exact reviewed `enforced` document through the supervisor's activation operation. Any other
M2B2 file mutation is a stop condition. Status documentation follows only after acceptance and does
not share the runtime activation transaction.

## 4. Mandatory pre-adoption hardening

These are acceptance blockers, not optional cleanup.

### 4.1 Mandatory CAS on every mutation

`attach-process` and `transition` require a non-negative `expected_revision`; omission is a closed,
typed CLI/library error. `begin` returns revision 1. Every successful mutation increments the record
revision exactly once and returns the new revision. A stale revision performs no write. Terminal
idempotent replay is allowed only when the caller supplies the current revision and requests the same
terminal state and reason; it returns the unchanged record without fabricating a new revision.

Wrappers must carry the returned revision in memory across each transition. They may recover an
unknown revision only through bounded `show` plus explicit reconciliation rules; they may not retry a
mutation blindly or derive authority from a cached/pre-lock record.

### 4.2 Receipt-bound barrier release

The new Python supervisor owns registry admission, fork, barrier descriptors, attachment, release,
wait, and terminal convergence in one process. `attach-process` returns an opaque Python receipt
object bound to task ID, committed record revision, PID, PID start time, barrier nonce, creator PID,
and monotonic expiry. `ExecBarrier.release()` accepts only that object and verifies the full binding
before writing the release byte. Caller-supplied PID/start time or machine JSON cannot release it.
Receipts are single-use, never cross the CLI/stdout boundary, never persist to registry/logs/metrics,
reject pickling/serialization, and are invalid after fork or expiry.

The supervisor closes unused descriptors immediately. EOF, timeout, duplicate release, malformed or
mismatched receipt, parent death, attachment failure, or PID/start-time drift exits without provider
exec. Tests must observe zero fake-provider bytes for every denied path.

### 4.3 Symlink-safe durable replacement

Registry rewrites create a unique same-directory temporary regular file with exclusive creation,
no symlink following, restrictive mode, and bounded retry. Writes loop until the complete bounded
payload is written and treat zero/short/error writes as failure. The writer fsyncs the temporary file,
atomically replaces the registry while holding the stable sibling lock, fsyncs the parent directory,
and cleans up only the exact temporary inode it created. The registry and stable lock are revalidated
as non-symlink regular files at the descriptor boundary. No fixed `.tmp` path or pre-lock truncation
is permitted.

Crash/fault tests cover short writes, ENOSPC, fsync failure, rename failure, malicious pre-created
symlinks, concurrent writers, and cleanup; the last durable registry must remain valid JSONL.

## 5. Atomic wrapper protocol

All supported wrappers—local, Claude, Codex, and Antigravity—delegate launch ownership to
`aq-dispatch-supervisor`, which uses one shared protocol:

1. Complete existing policy, secret, model-tier, and budget checks without starting provider work.
2. Normalize bounded lane/role/access/task-class/output-expectation fields; never store prompt text,
   prompt-derived hashes, argv, environment values, output, headers, credentials, or provider errors.
3. Call `begin`; require a closed revision-1 queued record.
4. Run the pure projection preflight and require the exact fresh `degraded/queued` admission verdict.
5. Create the receipt-bound barrier and fork a child that cannot provider-exec before release.
6. Read the child PID start time, call CAS `attach-process` in the same supervisor process, verify the
   returned running record, and release only with the in-memory matching receipt.
7. CAS-transition every exit path—success, provider error, timeout, cancellation, signal, launch
   error, zero output, and shell `set -e`/pipeline failure—to a typed terminal state.
8. Emit machine-clean status/list/check output and reconcile stale active rows only through the
   shared writer. Human diagnostics go to stderr and never trail machine JSON.

Wrapper adapters may differ only in provider argv construction and existing provider-specific policy.
They pass an argv vector without shell evaluation plus bounded metadata to the supervisor; they never
transport a receipt or construct a shell command string. The supervisor preserves stdin/stdout/stderr,
wait/background behavior, exit status, signal forwarding, timeouts, and cancellation, and may signal
only the child/process group it created. A static gate rejects direct registry mutation patterns in
all five wrapper files after activation.

During M2B1, every wrapper reads the closed activation manifest under the stable admission lock. In
`legacy` it follows its existing path; in `enforced` it invokes only the supervisor; any other state
fails closed before provider launch. The activator takes the exclusive admission lock, rejects the
switch unless no supported legacy row/process is active, atomically and durably replaces the manifest,
and releases the lock. Legacy admission holds the shared lock through its active-row creation, so a
new legacy launch cannot race the drain check and switch.

`delegate-to-gemini` becomes a fail-closed compatibility surface: it launches no process, performs
no registry mutation, returns a stable machine-readable retirement reason and nonzero exit, and
points operators to `delegate-to-antigravity`. It is not a silent alias or authority transfer.

Direct platform subagents, `aq-antigravity-agent`, and unrelated IDE processes remain
`UNTRACKED/BLOCKED`; M2B does not hide or grandfather them.

## 6. Monitoring-first contract

The same atomic candidate must make adoption observable before acceptance:

- TUI and `--json` show queued/degraded, attached/tracked, terminal/stale, contract version, writer
  health, preflight rejection, attachment timeout, CAS conflict, integrity failure, and reconciliation.
- Metrics use bounded lane/reason/status labels only. Task IDs, PIDs, paths, model names, prompts,
  responses, argv, and raw provider errors are forbidden labels.
- Phase-0, Bash fallback, and validation registry fail closed if any supported wrapper bypasses the
  writer, if Gemini can launch, or if TUI/schema/registry contract versions disagree.
- Dashboard counts must converge within the accepted cache TTL: queued within one refresh, exactly
  one running card after attachment, and no active card after terminal/stale convergence.

No live traffic cutover is accepted on unit evidence alone. M2B acceptance requires a bounded live
smoke using a fake/local harmless provider path plus sanitized TUI and machine output; real remote
model traffic is not required to prove the enforcement boundary.

## 7. Required evidence

Focused evidence must prove at least:

1. omitted/stale/future CAS revisions fail without mutation; concurrent mutations have one winner;
2. terminal idempotence is revision-bound and illegal transitions remain closed;
3. no provider byte precedes a valid receipt-bound release, including parent death and PID reuse;
4. durable replacement survives short write, full disk, fsync/rename faults, symlinks, and contention;
5. all four supported wrappers create queued-before-launch, attach identity, and converge every exit;
6. removing/unavailable writer or projector prevents all four provider launches;
7. no supported wrapper contains or exercises a second registry writer;
8. retired Gemini launches nothing and returns the stable typed redirect;
9. prompt/secret/path/argv canaries are absent from registry, cards, JSON, and metric labels;
10. Agent Ops TUI/JSON parity and active-count convergence hold under the cache TTL;
11. `test-agent-ops-projection.py`, `test-local-delegation-reliability.py`, L2A, and L2B-A regressions
    pass, followed by `aq-qa 0 --machine` and Tier0 pre-commit;
12. the final staged file list is a subset of Section 3 and every changed file is independently
    hash-bound for flagship acceptance.

## 8. Implementation and acceptance sequence

1. Codex, monitored Fable/Claude when available, and monitored Antigravity review Revision 4.
2. Codex reconciles blocking findings and repeats changed-scope review until the design passes.
3. Codex prepares a single-use hash-bound M2B1 authorization in `PREPARED_ONLY` state; only the owner
   may activate it.
4. One implementor model installs the dormant broker, manifest, wrapper adapters, monitoring, and
   gates without staging, committing, deploying, stashing, activating, or broadening scope.
5. Codex validates the exact M2B1 candidate; independent flagship acceptance reviews hashes/evidence.
6. Only accepted M2B1 may commit with manifest mode `legacy`.
7. Codex prepares a separate single-use M2B2 authorization binding exact pre/post manifest bytes,
   zero-active-work evidence, activation command, rollback-to-fail-closed plan, and live smoke.
8. Only the owner may activate M2B2. The activator performs the exclusive-lock drain check and single
   durable manifest switch; independent flagship acceptance then reviews live evidence.

## 9. Stop conditions and residual threat

Stop for a new database/event log, new inference/network route, credential change, process discovery
by raw substring, prompt retention, unbounded repair, unrelated-process termination, web-dashboard
redesign, internal-platform routing, Q8 authority selection, or any out-of-inventory edit.

M2B makes supported wrappers observable and fail-closed; it does not authenticate hostile peers that
share the same Unix account and repository write authority. A schema-valid same-user forgery remains
a documented residual threat until a separately authorized state-spine/service boundary owns writes.

`RECORD: M2B is PREPARED_ONLY. M2A remains dormant. No wrapper adoption or implementation is authorized.`
