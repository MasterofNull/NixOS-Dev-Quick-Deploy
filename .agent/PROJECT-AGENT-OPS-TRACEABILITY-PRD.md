# Agent Ops Traceability R0M PRD

Status: **M0 ACCEPTED — M1 CANDIDATE AWAITING INDEPENDENT ACCEPTANCE; M2–M3 BLOCKED**
Parent: `.agent/PROJECT-LOCAL-DELEGATION-RELIABILITY-PRD.md`
Trigger: R0 acceptance directive that monitored work must precede live R1

Transition evidence: L2B-A accepted independently and committed as `fbeffbab`; Antigravity M0 and
L2B-A acceptance and the independent M1 design review permit the active single-use M1 grant. This
does not authorize M2–M3 or R1–R4.

## 1. Outcome

Every agent work route is either correlated to an authoritative task record and visible in Agentic
Ops, or explicitly shown as `UNTRACKED/BLOCKED`. A process name, heartbeat, PULSE entry, model claim,
or stale registry row cannot independently assert that work is active or complete.

R0M is a read-only projection and enforcement boundary. It creates no lifecycle store, changes no
inference request, adopts none of the R0 runtime policy, and authorizes no R1–R4 behavior.

## 2. Current defects

1. `aq-tui-dashboard` scans raw `pgrep -af` strings; incidental bootstrap `exec` text can classify
   Codex/bwrap wrappers as active work.
2. Parent/wrapper/child processes are not ancestry/cgroup deduplicated.
3. Internal platform collaboration tasks have no repository task record and appear as green
   `process, no task log` cards.
4. Antigravity inbox pending/completed/archive state is absent from Agentic Ops.
5. Registry rows, progress sidecars, processes, and inbox items use different identities without a
   typed correlation verdict.
6. An uncorrelated process is presented as nominal instead of a monitoring-policy violation.

## 3. Authority and trust contract

| Fact | Authority | Non-authoritative evidence |
|---|---|---|
| delegated task lifecycle | existing delegation registry plus terminal/process evidence | prompt/output text |
| local phase/progress | trusted progress sidecar under its current producer contract | generic heartbeat |
| process liveness | `/proc` PID + start time + ancestry/PGID/session/cgroup snapshot | PID alone or raw `pgrep` line |
| Antigravity work | inbox pending file, lane state, requested output, archive transition | IDE/process-name guess |
| collaboration work | supported lifecycle event or harness-managed delegation record | PULSE, prose, model claim |
| completion | authoritative terminal record plus required artifact/process evidence | file existence alone |

No R0M component writes these authorities. The projection recomputes from bounded snapshots and
emits provenance, freshness, and uncertainty. Conflicts fail closed.

## 4. Canonical projection

Define closed `aq.agent-ops-projection.v1` records with:

- stable `work_id`, lane, role, model/profile class, and source authority;
- state: `queued|running|waiting|cancelling|terminal|idle|untracked|conflict|stale`;
- phase/progress age and bounded evidence timestamps;
- PID identity tuple, parent/cgroup correlation, and deduplication group where applicable;
- writer/read-only authority classification without prompt or secret content;
- terminal reason and artifact expectation/result;
- visibility verdict: `tracked|degraded|blocked`, reason code, and source freshness.

Cardinality is bounded: no prompt, output, path content, raw command, run ID, PID, or model response
becomes a metric label. Machine JSON may include sanitized instance identifiers for operator drill-in.

## 5. Process classification

Read `/proc/<pid>/{cmdline,stat,status,cgroup}` with PID start-time confirmation. Parse executable and
argv positions, never arbitrary substring presence. Collapse bwrap/sandbox/child chains into one
work unit using ancestry and cgroup evidence. Recognize idle app/MCP servers separately from active
harness dispatch processes. A process lacking a correlated authority is red `UNTRACKED`, never a
green task and never silently killed by the projector.

## 6. Route policy

- `delegate-to-local|claude|codex`: allowed only when registry creation and initial progress evidence
  succeed before model work.
- Antigravity inbox: allowed as traceable asynchronous review/research; pending and archived states
  are visible even without an IDE PID.
- Internal platform collaboration/subagent APIs: review/read-only use is blocked from implementation
  unless a supported lifecycle event bridge provides stable identity, start, progress, and terminal
  evidence. PULSE is audit context, not that bridge.
- Main interactive operator session and persistent app servers are labeled session/daemon, not
  delegated work.

## 7. Monitoring and enforcement

Agentic Ops TUI and machine JSON expose tracked work, untracked processes, stale/conflicting records,
inbox work, correlation health, and last refresh. A dispatch preflight denies implementation when its
lane cannot become tracked. R0M itself does not terminate processes; intervention remains explicit.

Phase-0 and Bash fallback must exercise projection fixtures and fail if the monitoring contract is
absent or invalid. The feature is incomplete unless the TUI/machine surface shows every fixture state.

## 8. Success metrics

- 100% of harness-managed fixture tasks correlate to exactly one work unit.
- 0 duplicate cards for wrapper/child chains.
- 100% of uncorrelated active processes display `blocked`, never nominal.
- stale/reused PID, replaced registry row, forged heartbeat, and conflicting terminal fixtures fail
  closed with typed reasons.
- Antigravity pending → completed/archive transition appears within one refresh interval.
- completed processes disappear from active count within cache TTL and remain available as recent
  terminal history.
- no prompt/secret/raw command content appears in projection metrics or default cards.
- metrics include `inbox_pending_count`, `inbox_processing_duration_seconds`, and
  `cgroup_correlation_failures_total` with bounded lane/reason labels only.

## 9. Non-goals

No new database/event log, process killing, inference routing, token/timeout changes, provider
credentials, live R1 adoption, Nix deployment, or replacement of the existing lifecycle authorities.

## 10. Exit gate

Independent flagship review must approve the PRD, exact implementation inventory, schemas, fixtures,
and enforcement boundary. R0M must then pass repository tests, Phase-0, Tier 0, and a live TUI/machine
smoke before R1 planning may be authorized.
