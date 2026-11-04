# Agentic Routing Plan (FROZEN)

status: PLAN_READY_WITH_FOLLOWUPS
owner freeze: 2026-10-31 (decision "Freeze and build", hyperd)
reviewer: Codex codex-20261031-112916-b17nvu, disposition PASS_WITH_FOLLOWUPS
authors: three independent PRDs (Claude Sonnet architecture lens, Claude Sonnet operations lens, Gemini security/lanes lens); the local Qwen advisory perspective is pending (advisory, non-blocking)
sources: prd/PRD-claude-architecture.md, prd/PRD-claude-operations.md, prd/PRD-gemini-security-lanes.md, prd/COMPARISON-codex.md, prd/BRIEF.md, prd/inventory/INVENTORY.md

## Frozen exclusions
- Zero-review self-merge.
- Mandatory vendors (no role or gate permanently tied to one provider).
- Risk-driven flagship defaults (risk alone does not select a flagship implementer).
- Expanded system privileges.

## Corrections from the record
- The gemini agent CLI cannot watch video (capability probe 2026-10-31: it reads images, not mp4 or YouTube URLs). Media lanes therefore require transcript plus keyframes as input; modality support and account/tool authorization are separate facts.

The sections below are sections 3 and 4 of prd/COMPARISON-codex.md, verbatim.

## 3. Merged recommended plan

### Vocabulary and ownership

Use one work-class record with separate concerns:

- **Risk:** `low | medium | high | core`, selecting review and validation requirements.
- **Complexity:** existing names, selecting required implementation capability through existing model tiers.
- **Role:** implementer, reviewer, architect, research and existing role definitions.
- **Kind/modality:** capability and access requirements, such as code, research, image or PDF.
- **Authority requirements:** explicit privileged, destructive or outward actions, governed by existing owner boundaries.

Priority and urgency order work; they do not reduce gates. Severity may raise requirements. Classify the reviewed change separately from the reviewer’s read-only operation: a read-only review can concern a core subject.

Extend `risk_tier.py` and `risk-tier-policy.json`. Keep concrete model IDs in `model-coordinator.json`, and availability, eligibility and independence resolution in the existing role router. Compute through one implementation at successive stages, with versioned inputs; “one computation point” does not mean trusting a stale pre-work classification forever.

Start with existing rules plus precise core rules for canonical instructions, classifier/policy, review acceptance and relevant hooks. Defer broad keyword-based escalation, novelty inference and config allowlists until tested against a representative corpus.

### Assignment matrix

Lane names are preferences resolved at dispatch, never permanent role owners.

| Risk | Implementation | Review | Effort and gates |
|---|---|---|---|
| Low | Cheapest healthy eligible model; bounded local first where qualified, otherwise fast remote | Preserve current applicable PR review baseline | Low effort where supported; existing tier0 |
| Medium | Qualified bounded local or balanced remote | One qualified independent reviewer; local where demonstrated eligible | Medium default; tier0 and targeted tests |
| High | Cheapest demonstrated eligible implementer, commonly balanced; risk alone does not justify flagship | One qualified independent reviewer; use remote when local lacks qualification | Higher review effort where useful; existing security rubric, validation set and freeze requirements |
| Core | Bounded implementation by cheapest eligible model following independent design review | Two qualified independent reviewers satisfying explicit identity and lane rules | Hash-bound acceptance and existing core validation set; owner acts for privileged or irreversible activation |

Research and media overlay this matrix with demonstrated modality support and actual tool/account access. Read-only work is not automatically harmless or exempt from quality review.

Initially preserve the checker’s current author/reviewer lane inequality. Fresh same-provider sessions cannot silently satisfy a rule the current checker rejects. Any later relaxation needs explicit identity semantics and tests.

Keep the Codex review reserve. Prefer scarce review capacity for high/core work without banning a necessary qualified substitution elsewhere. Record requested and effective lane, model and effort; unsupported effort is `n/a`.

### Enforcement and anti-gaming

Use four checkpoints:

1. **Planning:** declared scope produces provisional requirements.
2. **Dispatch:** wrappers validate eligibility, actual assembled context size, explicit model selection and capability profile.
3. **Review:** the real diff raises or confirms requirements.
4. **Merge:** trusted CI recomputes requirements and verifies review evidence.

CI must use trusted classifier code **and** policy from the event’s trusted base revision, under a trusted workflow. Loading only base policy while executing PR-modified classifier code leaves the protection incomplete. Include old and new paths for renames and deletions.

Missing or unreadable policy, rubric or required evidence blocks enforcing consumers with a specific error. It must not silently become high risk, an empty checklist or a pass.

Add a backward-compatible structured receipt collection. Validate each review’s subject, disposition and independence, deduplicate reviewers, and count eligible reviews. Preserve legitimate existing head-equivalence exceptions explicitly. Candidate changes cannot weaken their own acceptance requirements.

Agent-tool coverage requires a tested adapter: pre-dispatch intent plus completion/stop correlation where supported. A shell helper cannot intercept an in-session tool by itself. Trusted role metadata should drive enforcement; a prompt’s `ROLE:` or exception sentence is not an authorization mechanism.

### Telemetry and scoping

Normalize existing registry fields rather than replacing them. Minimum useful fields are:

`dispatch_id`, stable work/series ID, source, role, risk, complexity, model, effort, requested/effective lane, classification/policy versions, substitution reason, subject/review references and outcome.

Record refusals and classification failures. Keep unavailable usage as `unknown`, and unsupported fields as `n/a`. The registry has mutable lifecycle records; do not describe it as an immutable event ledger. Use existing usage events where event history is needed.

Log counts, identifiers and hashes rather than full prompts or credentials. Measure explicit-model coverage separately from cheapest-eligible compliance.

Introduce launch profiles only through actual child configuration and tool permissions. Mandatory approval and write guards remain invariant. Advertising fewer skills reduces payload; it does not establish filesystem, network or MCP authorization boundaries. Neither a broken-server observation nor suspected unused plugin warrants bundled global removal.

### MVP slices

The smallest independently useful slice is the local preflight guard; the full MVP must also close the classification-to-review and classification-to-assignment loops.

1. **Local preflight and normalized dispatch evidence.** Check the assembled prompt, harness/tool overhead and output allowance against context limits. Use a conservative byte guard where token measurement is unavailable, label that limitation, and refuse before inference. Add minimal live integration QA and a dashboard state for refusals.
2. **Core classification and review enforcement.** Add precise core paths, structured multi-review evidence and trusted CI consumption. Exercise shadow comparisons, then activate core enforcement after acceptance evidence. Preserve existing review requirements elsewhere.
3. **Assignment defaults and Agent coverage.** Connect wrappers to the shared record, record substitutions and enforce explicit eligible model selection. Enable Agent enforcement only after its hook and lifecycle behavior are demonstrated live.

Ship required QA, observability and canonical parity with their corresponding changes. Record dated activation deferrals where necessary. Do not promise a line count for these cross-cutting integrations.

Later phases cover launch profiles, modality probes, wider enforcement, calibrated content signals, coordinator/tracker integration and shadow-based lane qualification. Avoid a routing-library rewrite and automated security eligibility changes.

### Review-cost control

Adopt initial reshape triggers of two rounds for medium and three for high/core, subject to measured adjustment. At six core rounds, pause automatic repetition for explicit escalation.

Counters follow a stable work/series ID across lane substitutions and subject revisions. Track design and reshape costs as well as formal reviews. A findings ledger should preserve unresolved findings and sufficient current-patch context; delta-only prompts must not conceal interactions. Final acceptance still evaluates the exact current subject.

### Acceptance tests and metrics

Required tests:

- Canon changes become core while a one-line implementation can remain trivial complexity.
- Empty scope, corrupt policy and missing required rubric produce explicit blocked states.
- A PR weakening classifier or policy cannot weaken its own acceptance.
- Duplicate, stale, author-conflicting or insufficient receipts fail; two valid eligible reviews satisfy core requirements.
- Oversize local work is refused before launch; accepted work fits total context and output allowance.
- Codex cooldown selects a qualified independent substitute; no eligible substitute yields a blocker.
- Real CLI and Agent dispatches produce correlated records with honest model, effort and completion state.
- Review counters survive substitutions and subject changes; reshape never clears unresolved findings.
- Live QA, dashboard state and operator controls reflect actual outcomes.

Report:

- Dispatch coverage by source, with unknowns visible.
- Rule 17 compliance against recorded eligibility and availability—not merely presence of a model flag.
- Review rounds, total review/design cost and escaped defects by risk class.
- Codex reserve/headroom and measured usage; label cost proxies.
- Local refusal, completion, first-pass acceptance and failure rates separately.
- Reclassification and classifier false-positive/false-negative findings.

Establish distributions from adequate samples before setting p90 improvement claims. Activate broader enforcement from demonstrated correctness and compatibility, not calendar age alone.

## 4. Remaining risks and freeze follow-ups

- Reviewer identity remains declarative without stronger attestation; receipt consistency cannot prove independent inspection.
- Unwrapped dispatches and incomplete Agent lifecycle data can leave audit gaps. Coverage claims must identify their denominator.
- Diff signals miss intent, cumulative effects across PRs and runtime authority. They supplement existing security boundaries.
- Prompt guards reduce predictable overload but do not establish local semantic reliability.
- Capability probes become stale; model modality support and account/tool authorization are separate facts.
- Qualified reviewer scarcity can block core acceptance. Advisory catch-up reviews cannot substitute for required binding acceptance.
- Review budgets and agreement metrics can reward superficial convergence unless paired with defect and finding-resolution evidence.

Freeze the merged vocabulary, ownership, matrix and bounded slices above. Carry Agent-hook verification, structured-review migration and qualified-lane measurements as explicit implementation acceptance gates. Exclude zero-review self-merge, mandatory vendors, risk-driven flagship defaults and expanded system privileges from the frozen scope.

Review-Disposition: PASS_WITH_FOLLOWUPS
