---
doc_type: design-review
id: codex-return-catchup-audit-20260814
title: Codex Return Catch-up Audit — Rule 18 Confirmatory Review
status: draft
reviewer: codex
verdict: "Part A: 2x DEFECT[MEDIUM] — drain generation/completion-type + frontmatter looseness (both fixed this commit); metric-sync + finding-freshness CONFIRMED. Part B: friction consensus."
date: 2026-08-14
head: 4baf65fd3803f4362fc7e02fa440c47024a08b45
---

# Codex Return Catch-up Audit — 2026-08-14

Scope: independent, advisory review of Claude-authored commits `ebfef8a7`, `041878bd`,
`4baf65fd`, `615b4086`, and `91094566`, verified against live code at HEAD
`4baf65fd3803f4362fc7e02fa440c47024a08b45`. I did not author these commits and changed no
reviewed surface.

## Part A — Confirmatory audit

### `ebfef8a7` + `041878bd` — Antigravity drain verification

**Strongest issue pressed:** whether receipt history from an earlier generation of a reused task ID
can make the current task appear drained or undrained, and whether the health snapshot can retrigger
the watched inbox.

**Code read:** `scripts/ai/aq-antigravity-inbox:116-117,129-135,163-195,225-232,297-328,332-384`;
`nix/modules/services/antigravity-auto-wake.nix:31-64,83-104,121-147`.

**Verdict: DEFECT[MEDIUM].** `_drain_status(tid)` is generation-blind. It considers all receipt
records for a task ID, checks for a record type named `complete`, and ages the newest successful
nudge without filtering either record by the current task generation
(`aq-antigravity-inbox:165-174`). The actual completion writer records type `completion`, not
`complete` (`:297-298,327-328`). `_undrained()` derives only the task ID from the current pending or
claimed member and never supplies its content-hash generation (`:176-187`).

The failing input is operationally reachable: complete task generation A under task ID `same-id`,
then enqueue generation B under the same filename without nudging B. A receipt containing A's
one-hour-old `cli-nudge-ok` plus A's normal `completion` made HEAD return
`("undrained-stale", ~3600)` for B and list B as undrained. This is a harmful false-positive: the
timer fails and emits an alert for a task that has never received a nudge. Conversely, any legacy or
manually migrated record named `complete` would make every later generation of the same task ID look
drained, because `_load()` permits that record type and the check is also generation-blind. The
official writer does not currently emit `complete`, so that false-negative is latent rather than
produced by the normal CLI.

Bounded follow-up: compute the current member's generation and filter both successful nudge and
completion evidence to it; use the canonical `completion` record type; add regressions for task-ID
reuse across generations and for the post-completion receipt shape.

The snapshot's default location is outside the watched inbox
(`antigravity-auto-wake.nix:97-103` versus the watched path at `:121-127`), so the deployed default
does not form a wake feedback loop. The temp-and-rename write is same-directory (`:53-58`). Residual
hardening: the independently configurable path is not asserted to remain outside `inboxDir`, and
write failure is swallowed by `|| true`, so persistence is best-effort. This does not invalidate the
default-path safety conclusion, but the documentation should not imply guaranteed persistence.

The 300-second threshold itself is internally consistent: `_drain_status` uses `age >= 300`, and the
timer defaults to 300 seconds. Live evidence showed the timer repeatedly alerting on a genuinely
stale task and later returning success after the inbox cleared. The current live CLI returned
`undrained_count: 0`, exit 0.

### `4baf65fd` — autonomous-improvement metric sync

**Strongest issue pressed:** whether the schema guard masks non-drift failures, whether another
collector repeats the timestamp/column mismatch, and whether the private deviation directory meets
the exact `_open_locked` ownership/mode contract.

**Code read:** `ai-stack/autonomous-improvement/trend_database.py:105-254`;
`ai-stack/autoresearch/autoresearch.py:98-145`;
`ai-stack/mcp-servers/hybrid-coordinator/knowledge/llm_router.py:121-149`;
`nix/modules/services/autonomous-improvement.nix:96-105,122-164`;
`scripts/ai/lib/workflow_deviation_io.py:48-75`.

**Verdict: CONFIRM.** The experiments producer defines `created_at` and `accepted`; the collector
checks precisely those two columns and returns an empty source contribution only when the table or a
queried column is absent (`trend_database.py:225-239`). Parse/type failures in present data are not
silently classified as schema drift. The routing collectors use `timestamp`, and both the live
`routing_decisions` schema and its producer define `timestamp`; no second timestamp-versus-actual-
column mismatch was found in the autonomous-improvement collectors.

The deployed directory is `hyperd:users 0750`, matching the service's `User=hyperd` and satisfying
`_open_locked`'s exact-owner and no-group/other-write checks (`workflow_deviation_io.py:48-69`). The
deployed service environment points at that directory, and recent live runs completed metric sync
successfully. No deviation file exists currently, which is consistent with no failure needing a
receipt rather than evidence of a bad directory.

### `615b4086` — frontmatter schema registration

**Strongest issue pressed:** whether registration lets a document claim a governance-bearing type
while omitting the metadata that gives that type meaning.

**Code read:** `config/doc-frontmatter-schema.yaml:97-168` and
`scripts/governance/check-doc-frontmatter.py:66-142`.

**Verdict: DEFECT[MEDIUM].** The newly registered types make their semantic identity fields optional.
A synthetic document containing only `doc_type: design-review`, `id`, `title`, and
`status: complete` validates without a reviewer, date, verdict, subject, or subject hash. Likewise,
an `active` integration contract validates without parties or either authority field, and an
`active` collaboration brief validates with only `id` and `status`. Before registration these inputs
failed as unknown types; they now pass because the validator checks only unconditional field
presence and the global status allowlist (`check-doc-frontmatter.py:122-140`). This is not merely an
old weakness exposed unchanged: these four new allowlist entries create the newly accepted cases.

Drafts may legitimately lack a final verdict, so the bounded follow-up should be status-aware rather
than making every field unconditional: at minimum, require reviewer/date for every design review and
reviewer/verdict/subject binding for a completed one; define equivalent minimum identity/authority
requirements for active or complete contracts and briefs. Add negative fixtures for semantically
empty `active`/`complete` documents. The repository-wide frontmatter scan currently passes, so this
is a validation-strength defect, not a report that current documents fail the gate.

### `91094566` — finding freshness and registration guidance

**Strongest issue pressed:** whether the skill allows action on stale evidence or grants authority,
and whether unknown-type guidance recommends another route-around.

**Code read:** `.agent/skills/finding-freshness/SKILL.md:15-51`, `.agent/SKILL_INDEX.md:27`, and
`scripts/governance/check-doc-frontmatter.py:107-120`.

**Verdict: CONFIRM (sanity).** The skill requires a current-HEAD producer check and reproduction
before logging, dispatching, or requesting a grant, and it treats a changed producer as a reason to
reverify rather than as proof either way. It grants no implementation or activation authority. The
validator still rejects unknown types and now points maintainers toward explicit schema registration
instead of type-flipping. The skill itself passes the frontmatter validator and is registered in the
skill index. The schema-quality defect above remains a separate review requirement for any proposed
registration; it does not make this diagnostic guidance unsound.

## Part A rollup

**ROLLUP: BOUNDED FOLLOW-UP REQUIRED.** This is not an advisory PASS because two real defects were
reproduced at HEAD:

1. Make Antigravity drain evidence generation-bound and use canonical `completion` records.
2. Strengthen the four new doc-type schemas with status-aware semantic requirements and negative
   fixtures.

No history rewrite is warranted. `4baf65fd` and `91094566` are confirmed; the default Antigravity
snapshot placement and the 300-second grace/timer pairing are also confirmed.

Validation evidence:

- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/testing/test-antigravity-inbox.py` — PASS.
- Current `aq-antigravity-inbox verify --json` — exit 0, zero undrained tasks.
- Generation-reuse reproduction against imported HEAD module — generation B incorrectly returned
  `undrained-stale` from generation A's nudge.
- Live `routing_decisions` and `experiments` SQLite schema inspection — queried columns match.
- `TrendDatabase.collect_all_metrics()` against live sources — completed without schema error.
- `python3 scripts/governance/check-doc-frontmatter.py --all` — PASS.
- Synthetic minimal completed review / active contract / active brief — all incorrectly returned
  `True` from `validate_frontmatter()`.

## Part B — Flat-org friction consensus

Claude's five items are directionally right, but they understate the failure mode I experienced. A
multi-day lane outage is not merely a "single implementer bottleneck." It creates a review-debt queue
whose cost compounds while HEAD, subject status, and prior substitute reviews continue moving.
`.agent/collaboration/AGENT-CATCHUP-QUEUE.md` mixes tables and chronological prose, contains entries
from multiple outages and agents, and relies on a returning reviewer to manually determine what is
still live, superseded, blocking, or already closed. The queue has no machine-enforced catch-up SLO,
bounded batch size, dependency order, risk score, or durable per-entry state transition.

The missed frictions are:

1. **Availability and return are not first-class measured states.** The queue records prose such as
   "Codex DOWN until Aug 15," but admission, substitution, and recovery workload are not driven by a
   shared capacity signal. The system can keep accruing named-lane debt without a budget or alert.
2. **Catch-up debt has no backpressure or reconciliation primitive.** Every substitute-reviewed
   commit can create another advisory return audit. On return, freshness checking each item is
   necessary but serial, and already-superseded work consumes the same initial attention as an
   activation blocker.
3. **Confirmatory-review latency weakens review value.** A late advisory can find a real defect only
   after integration and sometimes after deployment. That is useful, but categorically weaker than a
   pre-integration independent gate; the dashboard should distinguish substitute acceptance,
   confirmatory debt, and finally reconciled assurance.
4. **Large catch-up bundles pressure review depth.** Combining unrelated commits to drain the queue
   efficiently creates an incentive to skim. Independence is not enough if the review unit exceeds a
   defensible evidence budget.

I would reprioritize the list as follows: first, transactional/pathspec-scoped staging and commit
ownership, because it prevents evidence corruption; second, lane-availability plus catch-up-debt
control, elevating Claude's "single implementer" item from low-medium throughput to medium-high
resilience; third, the unified in-flight/debt projection, because it is the measurement substrate for
the first two; fourth, finding freshness; fifth, doc-type vocabulary lag. The last item is real but
cheaper and less systemic than unbounded review debt.

**One concrete self-improvement mechanism:** build `aq-catchup reconcile --lane <lane>` backed by
structured per-entry records. Each entry should carry the exact subject hash, file set, enqueue time,
risk/activation class, substitute reviewer, dependency/supersession links, current status, and
freshness-check timestamp. Reconciliation should compare the subject with HEAD, automatically close
exactly superseded or already-confirmed entries, rank the rest by activation risk × age, emit bounded
review packets, and project debt count/oldest age/SLO breach to the dashboard. This turns return from
a prose archaeology exercise into a measurable queue with backpressure while preserving the rule
that a real late defect opens a bounded follow-up rather than rewriting history.
