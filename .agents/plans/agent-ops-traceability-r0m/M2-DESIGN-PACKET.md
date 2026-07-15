# Agent Ops Traceability M2 — Dispatch Enforcement Design Packet

Status: **REVISION 3 PREPARED_ONLY — FLAGSHIP RE-REVIEW REQUIRED; NO IMPLEMENTATION AUTHORITY**
Parent: `.agent/PROJECT-AGENT-OPS-TRACEABILITY-PRD.md`
Base: `760b50d3` with M0/M1 accepted and committed

## 1. Outcome

Every supported remote or local dispatch route must create a visible, contract-valid queued record
before it may invoke a model or IDE worker. A route that cannot create and re-project that record fails
closed without launching provider work. M2 reuses the existing delegation registry; it creates no
new lifecycle store, inference route, network authority, or process-killing authority.

## 2. Exact proposed implementation inventory

1. `.agent/PROJECT-AGENT-OPS-TRACEABILITY-PRD.md`
2. `.agent/PROJECT-AGENT-OPS-TRACEABILITY-PLAN.md`
3. `config/schemas/delegation-task-record.schema.json` (new strict input contract)
4. `config/schemas/agent-ops-projection.schema.json`
5. `scripts/ai/lib/agent_ops_projection.py`
6. `scripts/testing/test-agent-ops-projection.py` (projection plus writer/CLI concurrency and
   descriptor-barrier primitive coverage)
7. `scripts/ai/aq-delegation-registry`
8. `scripts/ai/lib/task_registry.py`
9. `scripts/ai/aq-tui-dashboard`
10. `scripts/ai/delegate-to-local`
11. `scripts/ai/delegate-to-claude`
12. `scripts/ai/delegate-to-codex`
13. `scripts/ai/delegate-to-antigravity`
14. `scripts/ai/delegate-to-gemini`
15. `scripts/testing/harness_qa/phases/phase0.py`
16. `scripts/ai/_aq-qa-bash`
17. `config/validation-check-registry.json`
18. `docs/architecture/role-matrix.md`
19. `docs/operations/agent-ops-window.md`

This explicitly revises the parent R0M inventory to include the already-existing shared registry CLI
and library, a real closed input schema, and the TUI that must render the new contract health. That
expansion is required to avoid five duplicated, race-prone registry writers and prose-only closure.
Any twentieth implementation file is a stop-and-review condition.

## 3. Current defects M2 must close

- Claude, Codex, Gemini, and Antigravity maintain separate inline append/rewrite implementations;
  several rewrite the JSONL file after an unlocked read and can lose concurrent updates.
- `TaskRegistry._locked_rewrite()` opens the registry with `"w"` before taking its lock, allowing
  truncation before exclusion, and its read and rewrite locks do not form one transaction.
- wrappers commonly write `running` before a durable child PID exists, omit PID start time, retain
  raw prompt descriptions, and leave dead rows `running` after early exits.
- the accepted M1 projector treats an active record without PID identity as stale, so the required
  create-before-launch sequence needs an explicit short-lived queued admission state.
- `delegate-to-gemini` remains an exposed retired route and can bypass the current Antigravity
  routing declaration unless it fails closed or becomes a monitored compatibility redirect.

## 4. Trust boundary and non-claim

M2 is supported-route enforcement and observability, not hostile-writer authentication. The current
repository registry is writable by peer agents running as the same account. A string such as
`admission_producer=dispatcher`, an unkeyed digest, or a returned CAS token cannot prove which peer
wrote a row. M2 must not describe those fields as authentication or as a zero-trust capability.

Until Q8 selects an authority and a separately reviewed descriptor/service boundary owns writes:

- a fresh PID-less queued row may be visible as `degraded/queued`, never authoritative `tracked`;
- only PID + start-time + bounded process correlation may promote live work to `tracked/running`;
- direct or forged repository writes remain detectable contract violations where malformed, but a
  schema-valid same-user forgery cannot be cryptographically distinguished and is an explicit
  residual threat;
- full hostile-agent write integrity belongs to the future state-spine/authority slice, not M2.

## 5. Shared writer and contract

`scripts/ai/aq-delegation-registry` becomes the only supported wrapper-facing registry mutation
surface, backed by `TaskRegistry`. Existing `registry.jsonl` remains the sole lifecycle authority.

`config/schemas/delegation-task-record.schema.json` is the Draft 2020-12, closed, versioned SSOT for
new records and transition requests. The writer must:

- use a stable sibling lock inode, bounded exclusive-lock acquisition, bounded file/record sizes,
  strict JSON-object parsing, `fsync`, atomic replacement, and parent-directory durability;
- perform read/validate/mutate/write under one lock; never truncate before lock acquisition;
- reject duplicate task IDs, malformed registries, unknown fields for new records, stale record
  revisions, illegal transitions, non-regular files, and symlinked registry/lock paths;
- expose machine-only `begin`, `attach-process`, `transition`, `show`, and `reconcile` operations;
- keep reconciliation explicit and evidence-based; PID alone never proves identity or death.

Every new record is closed and bounded. It stores a safe operator task class/summary, not raw prompt
text or a prompt-derived hash that permits dictionary inference, headers, environment values, output,
secrets, or argv. Historical legacy rows remain readable but cannot be templates for new writes.

## 6. Dispatch state machine

Legal transitions:

```text
begin -> queued
queued -> running | failed | cancelled
running -> waiting | cancelling | done | failed | cancelled | stale
waiting -> running | cancelling | done | failed | cancelled | stale
cancelling -> cancelled | failed | stale
terminal -> same terminal state only (idempotent replay)
```

`begin` writes `queued` before provider/model work. Required new-record fields include record version,
task ID, lane, normalized role/access, safe task class, output-artifact expectation,
created epoch, record revision, and `admission_producer=dispatcher`. No PID is permitted yet.

The pure projector shows a closed, fresh, PID-less queued record as `degraded/queued`: visible and
eligible for supported-wrapper preflight, but not authenticated. The grace window is fixed at 30
seconds from the writer-supplied integer epoch; future timestamps, clock skew beyond 5 seconds,
expired rows, malformed rows, and legacy queued claims are `blocked/stale`. `attach-process` must
observe PID plus `/proc` start time and advance the revision before work is `tracked/running`.

## 7. Wrapper sequence and fail-closed behavior

Each supported wrapper performs exactly:

1. normalize lane, role, access class, safe task class, and output expectation; neither the request
   nor the strict input schema contains raw prompt text or a prompt-derived digest;
2. call shared `begin`; receive a machine record, record revision, and non-authoritative CAS token;
3. feed that record through the pure projector admission check and require the exact
   non-authoritative `degraded/queued` verdict;
4. create an anonymous pipe barrier and fork a supervisor child whose read end blocks before provider
   exec while the dispatch parent retains the write end;
5. the parent observes and attaches the child PID plus `/proc` start time, then writes one bounded
   release byte; the child closes both barrier descriptors and `exec`s the provider, preserving the
   attached PID identity. EOF, timeout, malformed release, or attachment failure exits without exec;
6. transition every exit path, including launch error, provider error, timeout, cancellation,
   `set -e`, pipeline failure, signal, and zero-output early exit, to a typed terminal state;
7. make `--status`, `--check`, and `--list` machine-clean and reconcile dead active rows through the
   same shared writer rather than appending prose to JSON output.

If `begin`, projection preflight, or process attachment fails, provider work is never exec'd. The
wrapper may close its own not-yet-released supervisor descriptor/process under existing authority.
M2 does not acquire authority to kill unrelated or pre-existing processes.

Supported lanes are `delegate-to-local`, `delegate-to-claude`, `delegate-to-codex`, and
`delegate-to-antigravity`. The retired `delegate-to-gemini` route must fail closed with a stable
redirect reason and must not launch Gemini or silently alias authority. Direct internal platform
subagents and `aq-antigravity-agent` remain `UNTRACKED/BLOCKED` for implementation until a separately
reviewed lifecycle bridge exists.

## 8. Observability and gates

M2 extends the accepted projection with bounded metrics/reasons for dispatch admission success,
preflight rejection, attachment timeout, illegal transition, registry-integrity failure, and stale
reconciliation. No task ID, PID, path, provider error text, model response, or other request-derived
value becomes a metric label.

The Agent Ops TUI/JSON remains the operator surface and is in the exact inventory so new states and
contract health cannot land dark. Tests must prove that a new queued record appears as degraded within
one refresh, an attached process becomes exactly one tracked running card, every exit
becomes terminal/stale within the cache TTL, and no wrapper can launch when the shared preflight is
unavailable. Phase-0, Bash fallback, and the validation registry ship in the same M2 commit.

## 9. Required tests

- concurrent `begin`/transition stress with no lost rows, duplicates, truncation, or malformed JSON;
- stable-lock inode and atomic-replacement behavior; lock timeout; symlink/non-regular rejection;
- duplicate ID, stale revision, unknown field, invalid role/lane, oversized registry/record/prompt,
  malformed legacy line, and illegal transition failures;
- queued grace success and expiry; forged producer; PID reuse; PID disappears before attachment;
- a schema-valid same-user forged row remains an explicitly documented residual threat and cannot be
  mislabeled authenticated solely because it claims the shared producer;
- supervisor exec barrier proves no provider/fake-provider byte is emitted before process attachment;
- launch failure and zero-output exit converge to typed terminal records for every supported wrapper;
- `--status`/`--check` emit one machine document without trailing diagnostic prose;
- raw prompt/secret/path/argv canaries absent from new registry rows and projection/card output;
- new registry rows, strict-schema properties, and projections contain no prompt-derived digest field;
- retired Gemini route launches nothing and returns the stable redirect reason;
- parent M1, local reliability R0, L2A, and L2B-A regression suites remain green.

## 10. Slice split, stop conditions, and non-goals

M2 is split to keep the authority change reviewable:

- **M2A — contract foundation, no wrapper adoption:** items 1–8 and 19 only. Land the strict schema,
   transactional writer/CLI, degraded queued projection, contract health, and hermetic concurrency/
   barrier primitives. Item 6 owns writer/CLI concurrency stress and the fake-provider pipe-barrier
   proof as well as projection coverage. Existing wrappers remain unchanged; no live route consumes
   M2A. Its commit must carry a written, dated activation deferral stating that activation is M2B
   wrapper adoption and remains unauthorized.
- **M2B — atomic supported-route adoption and gates:** items 1–2, 5–19 as needed by the exact
  candidate. Cut all supported wrappers to the shared writer, fail Gemini closed, expose TUI health,
  and land Phase-0/Bash/registry/role/docs together. No wrapper may be partially activated.

M2A and M2B require separate hash-bound authorizations and independent acceptance. M2B cannot be
authorized until M2A is committed and its adoption guard proves no wrapper imports or invokes it.

Stop for a new database/event log, inference or network routing change, live L2B-B/R1–R4 adoption,
writer lease expansion, process discovery by raw substring, prompt retention, unbounded registry
repair, unrelated process termination, web-dashboard redesign, or any out-of-inventory edit.

M2 does not authorize M3 live verification, local reliability R1–R4, inference R1–R4, a new
lifecycle store, internal-platform implementation routing, or owner Q8 authority decisions.

## 11. Authorization sequence

1. Codex architecture/security consistency review of this packet.
2. Independent Claude architecture contribution if the monitored lane is available.
3. Independent Antigravity flagship design and threat-model review.
4. Revise this packet until the flagship verdict is `PASS`.
5. Prepare a hash-bound, single-use M2A authorization; owner/orchestrator activates it.
6. Assign M2A to an implementor model; require independent flagship acceptance before commit.
7. Only after M2A acceptance, prepare and review a separate atomic M2B adoption authorization.

`RECORD: M2 design is PREPARED_ONLY. No wrapper, registry, QA, role, or runtime implementation is authorized.`
