Reviewed-subject: agentic-routing PRD round 2026-10-31

## 1. Comparative assessment

The architecture proposal provides the strongest foundation. Adopt its separation of risk from complexity, combine it with the operations proposal’s dispatch defaults and review-cost controls, and retain Gemini’s containment concerns without its fixed vendor assignments or expanded privileges.

| Dimension | Claude architecture | Claude operations | Gemini security/lanes |
|---|---|---|---|
| Classification model | Existing risk and complexity axes; modality filters eligibility. Best fit with existing artifacts. | Risk × kind cards; derives complexity from risk, novelty and size. This loses useful separation. | New C0–C3 and complexity vocabulary create a parallel classification system. |
| Single computation point | Extends `risk_tier.py`; consumers recompute through the same function. | Extends `risk_tier.py` behind a new `aq-route` entry point. Useful interface, but another CLI is unnecessary initially. | Introduces `dispatch_gate.py`, then proposes merging routing libraries. Larger migration than needed. |
| Assignment matrix | Cheap implementer independent of risk; review scales with risk. | Convenient cards and defaults; several require Codex unnecessarily. | Fixed provider specializations and flagship core implementers conflict with Rules 17/18. |
| Enforcement and anti-gaming | Strongest proposal: CI recomputation, raise-only declarations, base-policy protection. Must also protect classifier code and CI execution. | Good dispatch feedback and override accounting; warn-only rollout leaves review enforcement deferred. | Immediate mode flip is insufficient; consumers must implement enforcement. |
| Telemetry, including Agent tool | Normalized registry fields plus Agent hook. Needs lifecycle correlation and actual-model verification. | Most complete operational telemetry, including unknown outcomes. Too many fields for MVP. | Correct coverage goal, but assumes an interception mechanism and demands non-null values that may be unavailable. |
| Tools, skills and MCP | Launch profiles acknowledge session limitations. | Measures usage before scoping; strongest sequencing. Global removals need separate evidence. | Strong containment intent, but payload profiles are presented as stronger security boundaries than demonstrated. |
| Local lane | Explicit eligibility and substitution. Initial capability table contains unverified assumptions. | Conservative preflight, decomposition and later measured graduation. Best operational treatment. | Useful guardrails, but inconsistent 20/22 KB limits and automatic Gemini fallback are unsupported. |
| Review-cost control | Risk-based budgets trigger escalation. | Strongest reshape and findings-ledger approach. Must retain final subject-wide review. | Little control beyond reserving Codex quota. |
| MVP size | Claimed ~250 lines understates several integration changes; some outputs lack initial consumers. | Three useful slices, but ~400 lines is similarly optimistic. | Small stated MVP omits mechanisms required to deliver its enforcement claims. |
| Rollout safety | Per-tier rollout is sensible; immediate core enforcement needs migration evidence. | Shadow/warn operation is safer, but activation should depend on evidence rather than 14 elapsed days. | Broad immediate enforcement, new vocabulary and unproven lane assumptions make rollout unsafe. |

## 2. Consensus, conflicts and verified corrections

### Consensus to adopt

All three correctly identify the main gap: classification exists, but does not determine dispatch and review requirements. Extend the current classifier, policy, model tiers, registry and review machinery; add no routing service or parallel policy hierarchy.

Also adopt:

- Automatic signals before declarations; declarations cannot lower computed requirements.
- Explicit protection for canonical instructions and the machinery governing acceptance.
- Local preflight before expensive inference starts.
- Registry coverage for in-session Agent dispatches.
- Recorded substitutions, independent review and Codex review-budget protection.
- Measured capability and tool usage rather than provider reputation.

### Conflicts to resolve before freezing

| Conflict | Recommended resolution |
|---|---|
| Risk determines model strength versus independent complexity | Keep risk and complexity separate. A one-line gate change can require core review while remaining suitable for a bounded inexpensive implementation. |
| Canonical instructions are high versus core | Treat instructions that govern agent behavior, and acceptance machinery, as core. Ordinary architecture documentation does not automatically become core. |
| New C0–C3 vocabulary versus existing tiers | Retain `low`, `medium`, `high`, `core`. Keep existing complexity names and model-tier mappings. Kind and modality are capability tags, not replacement risk classes. |
| Mandatory Codex versus substitutable roles | No provider is mandatory. Require qualified, independent reviewers; select healthy eligible lanes and record substitutions. Insufficient qualified reviewers means blocked acceptance. |
| Zero-review low changes versus existing review checks | Preserve the existing PR review baseline in MVP. Reducing ceremony is a separate policy decision requiring evidence. |
| Round caps versus correctness | Budgets trigger reshape or escalation. They never produce PASS, erase findings or justify deferring a blocking defect. |
| Immediate enforcement versus warn-only operation | Validate the complete consumer path in shadow mode, then activate core enforcement through the existing owner process. Avoid both an inert mode flip and indefinite warning-only operation. |
| Capability profiles versus privilege grants | Profiles narrow child capabilities. Higher risk never grants sudo, signer access or unrestricted system access. |
| Lane promotion through agreement metrics | Use shadow results to propose eligibility changes. Reviewer agreement alone is not correctness evidence or security qualification. |

### Claims corrected against the repo

1. **Registry model telemetry is not entirely absent.** The Claude wrapper already writes `requested_model_tier` and `resolved_model`. Zero Claude rows in the sampled window establishes a coverage gap, not absence of model fields. Preserve and normalize those fields. [Claude registry writer](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/delegate-to-claude:109)

2. **Multiple review trailers do not currently implement multiple reviewers.** The checker selects the last matching field and processes one reviewer/receipt pair. Supporting core dual review requires an explicit receipt collection and distinct-reviewer counting—not merely a policy lookup. [Review checker](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/governance/check-review-disposition.py:155)

3. **Current receipts do not authenticate reviewer identity or independently verify the declared subject SHA-256 against the patch.** They provide head binding, receipt consistency and declarative lane separation, with documented receipt-only and merge-only exceptions. They cannot establish that a reviewer actually inspected the change. [Documented trust limits](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/governance/check-review-disposition.py:8)

4. **Empty classifier input currently produces low risk.** Unknown claims are ignored rather than rejected; policy failures can raise exceptions, while rubric-loading failures can yield an empty checklist. Returning `high` for every error would still be unsafe where the unavailable result could have been core. Enforcing consumers should block with a named classification error. [Classifier](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/lib/risk_tier.py:48)

5. **The current policy already specifies review requirements, but does not enforce them.** Its low/medium/high/core reviewer counts are 0/1/1/2. `check-review-disposition.py` itself currently falls under the broad high governance rule; it needs explicit core treatment in the proposed trust-chain rules. Changing `mode` to a new string cannot create these consumers. [Existing policy](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/config/factory/risk-tier-policy.json:8)

6. **Complexity-based model routing already exists.** The configured mapping sends trivial/simple to fast, medium to balanced, and complex/critical to flagship. Replace neither the vocabulary nor the concrete model-ID source merely to introduce dispatch cards. [Tier routing](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/config/model-coordinator.json:69)

7. **Several capability and baseline claims exceed the evidence.** Unsupported Gemini modes do not establish that every Gemini invocation is nonfunctional. Antigravity media support, Google account access and binding-review eligibility need separate verification. Likewise, five failed/orphaned local reviews out of 49 are a sampled observation; prompt overflow is not a demonstrated explanation for every failure. Two expensive review examples do not establish a class-wide p90. [Inventory](/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/delegation/outputs/agentic-routing/INVENTORY.md)

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
