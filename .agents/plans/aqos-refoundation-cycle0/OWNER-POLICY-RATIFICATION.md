# Owner Policy Ratification — AQ-OS Refoundation Cycle 0 Governance

**Decision type:** governance-policy ratification (NOT plan ratification, NOT implementation authorization)
**Owner:** hyperd
**Provenance:** explicit owner directive issued in the operator session on 2026-07-10
("answer the owner governance questions so we can ratify"); drafted and recorded by the fable-5
orchestrator on the owner's instruction.
**Attribution assurance:** `ORCHESTRATOR_ATTESTED`
**Date:** 2026-07-10
**Grounding:** every answer below adopts, or explicitly decides between, options already reviewed and
concurred by two independent model families (Anthropic REVIEW-FABLE5.md, Gemini
antigravity-findings-review.md) plus the Codex-family package defaults in STATE-CONTRACT.md.

## Scope declaration — what this record does and does not do

This record ratifies the **governance policy** (authorization, quorum, waiver, proxy, identity,
privacy/retention, and measurement protocol). Under the package's own state machine it does **not**:

- ratify the plan (`plan_ratified` still requires fresh eligible `APPROVE` reviews of the final
  tool-frozen package root from two independent model families);
- issue `implementation_authorized` (a separate, later, attributed owner action);
- convert any failed or unavailable lane into a vote.

## Answers to the blocking governance questions

### Q1 — Who can issue or delegate `implementation_authorized`?
**Owner-only for Cycle 0.** Delegation is deferred to a separately ratified, expiring policy and is
out of scope for Cycle 0 — exactly the STATE-CONTRACT proposed default, now accepted.

### Q2 — Required-lane roster and model-family minimum, including under provider unavailability
**Roster (required lanes):** codex (OpenAI family), claude (Anthropic family), antigravity (Gemini
family), local/Qwen. **Minimum for ratification:** two independent model-family lineages AND two
independent execution principals, assurance ≥ `ORCHESTRATOR_ATTESTED` — the drafted default, accepted.

**Degraded mode (F2 disposition, two-family concurred):** when fewer than two independent families are
available after a formally recorded waiver, ratification may proceed in a **bounded degraded mode**:
one independent family plus an explicit owner co-review, time-boxed to a maximum of 7 days,
non-renewable, always recorded as `DEGRADED` in the decision record, and automatically expiring back
to the full two-family requirement. A degraded-mode ratification can authorize only reversible,
non-privileged slices.

**Repair SLA:** the local/Qwen lane repair (wedge guards + F2.5 scheduler activation + the
direct-mode output-loss fix) is declared a **governance prerequisite for Cycle 1 ratification** — not
Cycle 3 optimization work. Cycle 0 slices may ratify without the local lane only via the formal
waiver + degraded-mode path above.

### Q3 — May a proxy satisfy procedural review while contributing no diversity?
**Yes** — procedural completion only, sharing the proxying model's lineage, zero diversity weight,
always labeled as proxy in the decision record. As drafted; both reviewing families concur.

### Q4 — Unanimity semantics for plan ratification
**Unanimity of eligible non-abstaining reviews within a formally closed roster.** Roster closure means
every required lane is terminal (landed, failed, or owner-waived with zero weight). Any eligible
`REJECT` blocks until adjudication produces a new subject revision. `APPROVE_WITH_CHANGES` never
approves; it obligates a new revision requiring fresh `APPROVE` reviews — as drafted, accepted.

### Q5 — Telemetry roots, environment fingerprint, retention owner for QA evidence
**Single canonical telemetry root:** the deployed root `/var/lib/ai-stack/hybrid/telemetry/` is
authoritative; the repo-side `.agents/telemetry/` is a development fallback only. One shared resolver
must yield exactly one root per invocation; a repo/deployed mismatch is **fail-closed** (already
amended into C0.2 — accepted as the F4 disposition). **Retention owner:** the QA evidence producer,
as proposed. **Initial retention values accepted:** 7 days / 64 artifacts soft, 64 MiB hard cap,
never prune the pointer target; revisit only through a new reviewed revision after measurement.

### Q6 — Measured runtime/RSS baselines
Numbers cannot be ratified before they exist. **The measurement protocol is ratified** (5 cold + 20
warm samples, idle then under one representative local-inference request; p50/p95 monotonic duration;
`/usr/bin/time -v` max RSS), and **capturing these baselines is the mandatory first act of each
slice's Intent Lock**. Missing measurement telemetry fails the budget gate — as drafted.

### Q7 — Unreadable Codex state DB classification
**Observer limitation, fixed.** Root cause was a live-writer WAL lock against a monitoring read;
resolved in commit c5ff4f02 (`immutable=1` first connection mode). Not a failure, not a
degraded-confidence skip.

### Q8 — Which writers own review completion, useful-token events, delegation completion?
**Not answerable by decree — this is C0.3's job.** The owner ratifies the C0.3 discovery semantics as
drafted: honest `SINGLE | SPLIT_BRAIN | UNKNOWN | UNOWNED` recording, no invented singleton
authorities, and every contested row requires an adjudicated target, owner, and resolution deadline
before C0.3 ratification. The completed read-only scan proving broad split-brain is accepted as
discovery evidence.

### Q9 — Concurrent-work ownership of C0 surfaces
Ownership preflight must baseline against **current HEAD at authorization time**, not any lane's last
read. Known overlaps at ratification time: `scripts/ai/lib/round_contribution.py` (orchestrator
capture-dedup, commit d5eae85f); switchboard/antigravity lane files (concurrent thread). The
no-overlap preflight in the authorization contract is accepted as mandatory and blocking.

## Answers to the DECISION-LOG governance questions not covered above

**Second human for critical override/promotion/privileged execution:** this is a single-operator
deployment; a second human does not exist. Pretending otherwise would be governance theater. Instead:
critical overrides and privileged executions require (a) an explicit attributed owner action on a
subject hash, and (b) for irreversible actions, a dual-confirmation pattern — the action must be
issued and then separately confirmed by the owner after the system presents the full blocking-reason
and blast-radius summary. Single-command irreversible overrides are forbidden. Revisit if a second
operator ever joins.

**Privacy classification / GC for evidence artifacts:** default `internal`; producer-side
allowlist/redaction/secret-scan before persistence; owner-read/write file modes; GC per the accepted
C0.2 retention rules with deletion evidence recorded. No evidence artifact may contain secrets,
prompts of external principals, or unbounded logs — as drafted, accepted.

**Waiver mechanics:** a lane waiver is per-round, attributed, expiring, and supplies zero votes. A
lane that is waived in two consecutive rounds triggers the degraded-mode clock and the repair-SLA
escalation (Q2) rather than becoming ambient policy.

## Conditions this ratification is bound to

1. These policies bind to the package lineage currently at root `0a2b0cce…` and all subsequent
   revisions of this round; a change to the *policy text itself* in STATE-CONTRACT.md requires a new
   owner ratification record.
2. The F1 freeze tool (`scripts/governance/aq-package-freeze`) must exist and verify the final root
   before any plan-ratification review is solicited — hand-stamped roots are no longer acceptable
   evidence after this date.
3. Remaining path to `plan_ratified`: codex completes dispositions (including Gemini N1–N3) →
   tool-freeze of the final root → fresh `APPROVE` reviews of that exact root from the Anthropic and
   Gemini lanes → ratification record referencing this policy.
4. `implementation_authorized` for C0.1 will be issued as a separate owner action only after (3).

`DECISION: GOVERNANCE POLICY RATIFIED — authorization ownership, quorum/waiver/proxy/degraded-mode,
identity assurance, telemetry-root, privacy/retention, and measurement-protocol policies are accepted
as specified above. Plan ratification and implementation authorization remain open, gated on the
final tool-frozen root and fresh two-family APPROVE reviews.`
