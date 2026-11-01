# PRD (architecture / failure-mode lens): classify agentic work once, assign from the classification

Author lane: claude architect (independent proposal, 2026-10-31). Read-only on the repo. Inputs: BRIEF.md, INVENTORY.md, `scripts/ai/lib/risk_tier.py`, `config/factory/risk-tier-policy.json`, `config/model-coordinator.json`, `scripts/governance/check-review-disposition.py`, `scripts/ai/aq-review-request`, `scripts/ai/aq-delegation-registry`.

Thesis in one sentence: the repo already has one classifier with the right shape (`risk_tier.classify`, never self-lowers, policy in JSON) and one complexity-to-model ladder (`tier_routing` -> `tiers`); the failure is that nobody consumes them. Fix that by widening the classifier's inputs, making its output the single record every consumer reads, and enforcing in CI where the agent cannot edit the inputs. Add no new classifier, no new config tree, no new daemon.

## 1. Problem (with inventory evidence)

1. The classifier is a dead end (INV gap 1). `risk_tier` is `report-only`; its policy fields `min_reviewers`, `independent_reviewer_required`, `validation_set`, `lock` are read by `risk_tier.py` only. `aq-review-request` takes `--lane codex|local` by hand; `check-review-disposition.py` checks Author-lane != Reviewed-by and receipt integrity, never how many reviews the change needed. Rule 23 (no decorative code) is violated by the current state.
2. Inputs are path regexes plus diff size (gap 2). `config/` is always high, a `.md` that edits CLAUDE.md canon is low. No signal for blast radius, reversibility, novelty, outward-facing action.
3. Assignment is manual and unlogged (gaps 3, 4). Registry rows carry agent/role/status/tokens only. The Agent tool (where all Claude Sonnet/Haiku implementers ran 10/29-31) writes no row, so Rule 17 compliance is unmeasurable and lane share is mis-measured (registry shows 0 claude rows while 41+30 PULSE entries are claude).
4. Observed cost of unclassified review: sudo/security slice 5 REQUEST_CHANGES rounds, #667 8 rounds, versus a low-risk flag change at 1 local pass. Depth tracked orchestrator judgment, not a computed tier; there is no early signal that a slice will be a 5-9 round slice, so design review is not front-loaded for it.
5. Seven vocabularies with no mapping (gap 5): risk low/medium/high/core; complexity trivial..critical; fast/balanced/flagship; local Tier A/B/C; AIDB tool risk; PRSI action risk; role x agentType; switchboard profiles; coordinator ModelRole. Two of them (risk tier, complexity) are already central and sufficient.
6. Local lane dispatch has no pre-flight (gap 7): 5 of 49 local reviewers failed or orphaned, matching the documented ~22KB ceiling.
7. Capability surfaces load for everything (gap 8): 4-5 MCP servers, clangd-lsp, ~90 skills.

## 2. Goals / non-goals

Goals
- G1. One vocabulary, two orthogonal axes: **risk** (what review and gates the change needs) and **complexity** (what capability the implementer needs). Every other dimension in the owner's list is a *signal* feeding one of the two axes, not a third class system.
- G2. One computation point, `risk_tier.py`, producing one record (the **work-class record**) that every consumer reads or re-derives with the same function.
- G3. Fail closed: unknown, missing or unparseable inputs resolve to the higher class; claimed values can only raise.
- G4. Enforcement lives where the agent cannot rewrite the inputs: CI recomputation from the diff, plus registry rows that are written by the wrapper, not the agent.
- G5. Auditable assignment: every dispatch (including Agent-tool) logs class, lane, model id, effort, and substitution reason.
- G6. MVP changes real behavior within one slice.

Non-goals
- No new service, daemon, DB, or second policy file tree. No ML classifier; deterministic rules only (local Qwen is not in the classification path: 8k context and flakiness make a stochastic gate wrong for a fail-closed role).
- Not rewriting `aq-role-route`, `model_tiering`, switchboard profiles, AIDB tool risk, PRSI `_risk_tier`. They are mapped (section 3.4), not replaced, except where listed as retired.
- Not turning on the owner-only security boundary (activation signer, sudo policy). Class `core` routes to owner-visible gates; it never self-activates.
- Not per-task MCP hot-unloading inside a live session (Claude Code cannot do it). Scoping is by launch profile (section 6).

## 3. Classification model

### 3.1 Two axes

**Risk axis** = existing `tier_order`: `low < medium < high < core`. Unchanged names; they already appear in policy, CLI, gate-runner and docs. Meaning, restated by consequence rather than by path:
- low: reversible by git revert, no runtime effect, no authority/trust surface.
- medium: runtime code or tests-affecting change, reversible by revert, bounded to one service.
- high: affects deploy/boot/security/dependency surface, or crosses services, or is hard to reverse at runtime.
- core: changes the machinery that decides whether other changes are safe (gates, hooks, classifier, trunk protection, review/receipt, activation, sudo/signer) or is an outward-facing/irreversible action.

**Complexity axis** = existing `tier_routing` keys `trivial|simple|medium|complex|critical|creative` -> `fast|balanced|flagship|creative` -> concrete ids in `tiers`. Unchanged. This answers "which model", never "how much review".

Rationale for exactly two axes: review depth must not depend on how clever the implementer is, and implementer capability must not be inflated by risk (a one-line change to tier0 is *core risk, trivial complexity*: cheap implementer, maximum review). Collapsing them is the root cause of Rule 17 pressure ("security so use flagship to implement"). Keeping them separate lets Rule 17 hold while review scales with risk.

### 3.2 Signals (inputs). Automatic first, declared second

Computed by one function `signals(paths, diff, declared)` in `risk_tier.py`. Each signal either sets a **risk floor** or a **complexity floor**; final value = max of floors (never an average, never lowered by a declaration).

| Dimension (owner list) | Signal, automatic | Feeds | Floor rule |
|---|---|---|---|
| security sensitivity | existing path tags (`security`, `vulnerability`), plus content scan of the diff for new `sudo`, `chmod`, `token`, `secret`, `subprocess(shell=True)`, `eval` in added lines | risk | any hit => >= high |
| blast radius | count of distinct top-level owners touched (service dirs under `ai-stack/`, `nix/modules/`, `scripts/`), plus `.nix` or `systemd` => host-wide | risk | >=3 owners => >= high; host-wide nix => high (existing) |
| reversibility | diff touches migrations, `DROP`/`rm -rf`/`DELETE FROM` in added lines, secrets/keys files, `git push`/`gh pr merge`/outbound-account scripts, activation/signer paths | risk | any => >= high; activation/signer/gate machinery => core |
| severity / impact | **declared** `--severity` (S1..S4 = incident, degraded, annoyance, none) from the issue/backlog entry the slice cites; automatic fallback: slice cites an issues-backlog entry with Severity CRITICAL/HIGH | risk | S1 => >= high; can only raise |
| importance / priority | not a class input (priority orders the queue; it must not change gates, or urgency becomes a bypass). Left to tracker.json, section 10 Q3 | none | none |
| size | changed lines / files (existing 400/25) plus new: prompt-size estimate in bytes (local ceiling) | risk (existing) + complexity | >=400 lines => risk escalate one (existing); files >=4 or lines >400 => complexity >= medium; > local ceiling => `local_eligible=false` |
| novelty | no prior analog: touched paths have < N commits in 180 days, or new top-level path/file type, or new dependency | complexity, risk | novel path => complexity >= complex and `design_review_first=true`; new dependency => risk >= high (existing vulnerability tag) |
| policy-doc change | path in a small `policy_paths` list: `CLAUDE.md`, `.agent/{CODEX,LOCAL-AGENT,GEMINI,WORKFLOW-CANON}.md`, `canon/`, `docs/architecture/role-matrix.md`, `config/factory/` | risk | => core (fixes "md is low"; canon rules govern every agent) |
| media / research type | **modality** tag from declared `--modality` or detected input (URL host youtube/video file, PDF, image, audio, web research, none) | lane filter (3.3) | not a floor; a capability requirement |
| external-account / outward action | declared `--outward` or detection of `gh pr`, `git push`, send-mail, publish in the dispatched command set | risk | => core review (different-model) per role-matrix rule 3 |
| urgency | not an input (see priority) | none | none |

Fail-closed rules (G3):
- Missing `--paths` and no staged diff and no declared class => risk `high`, complexity `medium`, reason `unclassified`. (Today unknown input yields `medium` via "code/config" for unknown paths; unlisted-but-real paths stay medium, but *no input at all* must not read as low.)
- Unreadable policy JSON, signal scan exception, or unknown claimed value => the exception handler returns `high` with reason `classifier-error`, never `low`. (Contrast `_prsi_baseline` falls back to `kind`, which is the same value; that is fine, but the outer classify has no try/except at all so a crash currently yields no tier.)
- Declared values only raise: existing `claimed` logic is reused for severity, complexity and modality-implied floors.

### 3.3 Modality and lane capability (replaces ad-hoc "Gemini can't read YouTube" knowledge)

Add `config/factory/risk-tier-policy.json` -> `lane_capabilities` (one small table, edited when a probe shows a change):
```
"lane_capabilities": {
  "local":  {"max_prompt_bytes": 22000, "max_files": 1, "modalities": ["text"], "can_write": true},
  "codex":  {"modalities": ["text","code"], "can_write": true},
  "claude": {"modalities": ["text","code","image","pdf"], "can_write": true},
  "gemini": {"modalities": ["text","code"], "video": false, "can_write": true, "modes_unavailable": ["auto"]},
  "antigravity": {"modalities": ["text","code","image","video"], "can_write": "advisory-only"}
}
```
Values are initial claims from the inventory; each is overwritten by a probe result (section 7, phase 2) so the table is measured, not asserted. A class whose modality no healthy lane supports resolves to `blocked: no-capable-lane` and the dispatcher refuses with the named blocker (instead of a failed run).

### 3.4 Reconciliation of existing vocabularies

| Existing | Disposition |
|---|---|
| risk low/medium/high/core | THE risk axis. Extended with signals. |
| complexity trivial..critical + fast/balanced/flagship/creative | THE complexity axis. `model_tiering.estimate_task_complexity` keyword heuristic is retained only as a *floor-raiser* when no declared complexity exists; its output is passed to `classify` instead of competing with it. |
| local Tier A/B/C | Derived, not declared: Tier A = `local_eligible` and files==1 and lines<=200 and risk<=medium; Tier B = files<=4 and lines<=400 and risk<=medium; Tier C otherwise or risk>=high implementer. The doc keeps its prose; the numbers become the computed predicate. |
| PRSI `_risk_tier(action)` | Stays the baseline inside `risk_tier.py` (already composed). Not a consumer-facing vocabulary. |
| AIDB `_tool_risk_tier` | Different object (tool call risk at runtime). Keep; documented as out of scope. Same names low/medium/high are intentional and must not be merged with change risk. |
| coordinator `ModelRole` / `classify_task` | Role intent for the runtime coordinator; unchanged. |
| switchboard profiles | Endpoint-level; profile selection for local lane is *derived from the work-class record* in delegate-to-local (section 5), not client-chosen. |
| role-matrix "Model Defaults (Illustrative, Not Binding)" | Retired as a table; replaced by a pointer to the assignment block in policy JSON (section 4). The doc keeps role definitions and axes. |
| `aq-role-route` eligibility table | Kept as the *availability and independence* resolver. It is given `(role, class)` and returns the lane; its cost ordering is fed from the assignment block rather than its own copy (one place to edit). |

## 4. Assignment matrix

Assignment lives in `risk-tier-policy.json` as an `assignment` block keyed by risk tier, with complexity resolved separately through `model-coordinator.json`. Concretely, the policy already holds `min_reviewers`, `independent_reviewer_required`, `validation_set`, `lock`; add the following per-tier fields, so one table per tier, no new file.

| Class | review depth (reviewers x rounds budget) | reviewer lane preference (independent, cheapest-first, Rule 18) | implementer | effort (codex / gemini / claude) | design gate | required gates |
|---|---|---|---|---|---|---|
| low | 0 reviewers; tier0 only. Self-merge allowed if tier0 green | n/a; optional local reviewer if `local_eligible` | cheapest eligible: local if Tier A, else claude `fast`/`balanced` | low | none | tier0-pre-commit |
| medium | 1 independent reviewer, 2 round budget | local reviewer if prompt <= ceiling and local-eligible, else codex | `tier_routing[complexity]` capped at `balanced` unless complexity>=complex | medium | none | + targeted-tests |
| high | 1 independent reviewer, non-local (codex or fresh claude flagship or gemini), 4 round budget; `lock: freeze` | codex first; fallback chain recorded | `balanced` default; `flagship` only with recorded capability-insufficiency (Rule 17) | high | PRD-lite: written plan + one design reviewer before edits if `novelty` or blast radius >= 3 | + security-review + high-risk-rubric |
| core | 2 independent reviewers on **different lanes**, non-local for at least one, `lock: hash-bound`, up to 6 rounds, then escalate to owner via `aq-approve` | codex + fresh claude flagship (or gemini); substitution recorded | `balanced` implementer is acceptable (complexity axis); `flagship` architect for design | high | full design round before edits (PLAN_READY), per the MVP SOP | + live-e2e + tier0-pre-deploy |

Notes on the matrix
- Review depth tracks risk; implementer model tracks complexity. The `core` row reaching `balanced` implementers is deliberate: observed 5-9 round slices are review/design problems, not implementer-strength problems. The fix for round counts is front-loaded design (design gate column), not a bigger implementer.
- Round budget is a *trigger*, not a cap: at budget exhaustion the dispatcher stops auto-dispatching more review rounds and writes an escalation (to orchestrator for medium, `aq-approve` for core). This addresses #667 (8 rounds) by forcing an explicit root-cause stop (Rule 19) rather than a silent 9th round.
- Codex budget: only `high`/`core` consume codex review slots (existing 40% review reserve in delegate-to-codex stays); low and most medium use local or Claude lanes. This is how the class system conserves the shared Codex budget with no new mechanism.
- Effort: single field `effort` in the record, mapped per lane by one small dict (codex `--effort`, gemini `thinking_level` from `gemini_3_8_flash_efforts`, claude Agent-tool has no effort flag so it is recorded as `n/a`, with the thinking budget controlled by model tier).

Escalation rules (all raise-only)
1. Review finding severity CRITICAL/HIGH on a `medium` change reclassifies it `high` for the remainder of the slice (recorded as `escalated_from`).
2. Round budget exhausted => escalate as above; never silently continue.
3. Complexity: an implementer failing the same acceptance test twice (Rule 6 budget) moves complexity up one tier with a recorded reason; never skip tiers to flagship without reason.
4. Local failure (failed/orphaned/stagnant) => next lane per `aq-role-route`, recorded as substitution (Rule 18).

Substitution rules: the dispatcher records `lane_requested`, `lane_used`, `substitution_reason` (down, quota-cooldown, ineligible-modality, independence-conflict). Independence is evaluated on `Author-lane`; a substitute that equals the author is skipped, and if no independent lane remains the result is `BLOCKED`, not a downgrade.

## 5. Enforcement: one computation point, many readers

### 5.1 Single computation

`scripts/ai/lib/risk_tier.py` gains `classify_work(paths, diff, declared) -> record` where `declared` = `{severity, complexity, modality, outward, claimed_risk}` (all optional). It calls the existing `classify` for risk, adds signals (3.2), resolves complexity floor, reads `assignment` from the policy and `tiers` from `model-coordinator.json` for concrete model ids, and returns the **work-class record**:

```
{ "schema": 1, "risk": "high", "complexity": "medium", "tier": "balanced",
  "modality": "text", "local_eligible": false,
  "signals": ["stability: nix/modules/...", "novelty: new path"], "reasons": [...],
  "review": {"min_reviewers": 1, "independent": true, "non_local": true, "round_budget": 4},
  "implementer": {"lane": "claude", "model": "claude-sonnet-5-5", "effort": "medium"},
  "validation_set": [...], "design_gate": true,
  "profile": "standard-code",           # section 6
  "digest": "<sha256 of canonical json of inputs+policy version>" }
```
CLI `aq-risk-tier` gets `--work` (json record) and keeps its present modes unchanged for gate-runner. No change to the classify() signature; `classify_work` is additive, so existing callers keep working (minimal blast radius for a `core` file, which per its own rule needs 2 reviewers).

### 5.2 Consumers (every record field has a reader; Rule 23)

| Consumer | Reads | Behavior |
|---|---|---|
| `delegate-to-codex`, `-claude`, `-gemini`, `-antigravity`, `-local` (via a shared tiny shell/python helper `lib/dispatch_class.sh` calling `aq-risk-tier --work`) | implementer lane/model/effort, `local_eligible`, `modality`, profile | Resolve defaults from the record when flags absent; warn when explicit flags are *cheaper-than-required* (e.g. local for risk>=high implementer) and refuse in enforce mode; pre-flight refuse oversize local dispatch (fixes gap 7). Write class + effort + model into registry row |
| `aq-delegation-registry begin` | adds optional fields `risk`, `complexity`, `effort`, `model`, `class_digest`, `lane_requested`, `substitution_reason` | Extends the existing `task_class` field (already a required arg) rather than a new store |
| **Agent-tool dispatches** | `PreToolUse` hook matcher `Agent` in `.claude/settings.json` -> `aq-agent-dispatch-hook` | Reads `model` and `subagent_type` from tool input, appends a registry row (agent=claude, role from subagent_type, model, source=agent-tool). Report mode first; enforce mode denies an Agent call for an implementer role with no `model` (Rule 17 mechanically enforced). Extends the existing hook pattern (`aq-approval-ask-hook`), not a new mechanism |
| `aq-review-request` | `review.min_reviewers`, lane preference, `non_local` | `--lane` becomes optional (default from record); refuses a lane the record forbids (e.g. local-only review of a high change). Emits `Review-Risk-Tier: <tier>` and `Review-Class-Digest` into the PR body review block |
| `check-review-disposition.py` (CI, the enforcement point) | recomputes risk from `git diff base...head` itself using the same `risk_tier` | Fails when the PR's `Review-Risk-Tier` trailer < computed tier (never self-lowered, G3), when distinct reviewer count < `min_reviewers`, when `non_local` required and all receipts are local, or core lacking two distinct lanes. Mode flag `report-only|warn|enforce` taken from the policy `mode`, per-tier (e.g. `{"high":"enforce","core":"warn"}` while rolling out) |
| `tier0-validation-gate.sh --pre-commit` | `validation_set` | New `tier0.d/check-risk-class`: computes tier of staged diff and runs/asserts the validation set; WARN in pre-commit for freshness-class per Rule 19, HARD only for "tier recorded lower than computed". Replaces nothing |
| `templates/factory-kit/gate-runner` (and factory-gate-bundle copy) | `risk`, `mode` | Already calls classify; switches from "would require" print to honoring `mode`. Copy parity per the existing bundle pattern |
| `aq-role-route` | `(role, risk, modality)` | Receives modality and non-local constraint in its eligibility filter; reads lane preference from the policy assignment; keeps health/cooldown logic |
| `aq-collab-round` | class record at round start | Number of reviewers and lanes per round from `review`; writes the record into `round.json` so later rounds cannot lower it |
| coordinator `get_hints` | `risk`, `design_gate` | Hints for core/high include the design-gate and rubric workflows; no change to coordinator code beyond passing the tier as a param (optional, phase 2) |

### 5.3 Telemetry

One append-only row per dispatch and per review in the existing `registry.jsonl`; aggregate with a `aq-delegation-registry stats --by risk,lane,model` subcommand (new subcommand on the existing tool, no new store). Dashboard/health-spider reads that, satisfying Rule 15 observable. Fields: `risk, complexity, model, effort, lane_requested, lane_used, substitution_reason, class_digest, rounds, verdicts, escalated_from, source (cli|agent-tool|collab-round)`.

Intervenable: `aq-risk-tier --explain` prints each signal and the floor it set; owner can raise a class with `claimed` and can switch a tier's mode between warn and enforce by editing one JSON key (reviewable change; the policy file is itself `core`).

## 6. Tool/skill/MCP/plugin scoping per class

Constraint: a live Claude Code session cannot unload MCP servers or plugins. Therefore scoping is a **launch profile** chosen from the record's `profile`, and a **payload budget** for subagents; not runtime toggling.

Profiles (small table in `risk-tier-policy.json -> profiles`, each is a list of MCP servers, plugins, skill allow-list, hook set):

| profile | used by classes | MCP | plugins | skills (allow-list) | hooks |
|---|---|---|---|---|---|
| `docs-light` | low, modality text | lean-ctx | none | minimal-code, wiki-navigation | project defaults |
| `standard-code` | medium, high code | lean-ctx, hybrid-coordinator, semgrep | language plugin matching repo (not clangd) | per-role skills (debug-workflow, testing-patterns, slice-authoring) | project defaults + write guard |
| `security-core` | high security tag, core | lean-ctx, hybrid-coordinator, semgrep | none | security-audit, reviewer-gate, role-contracts, escalation-protocol | defaults + owner-approval hook strict, no `bypass` modes |
| `media-research` | modality video/pdf/image/web | lean-ctx, claude.ai connector or lane that supports modality | none | pdf, deep-research | defaults |

Mechanism, no new system: (a) delegate-to-claude (headless) passes `--mcp-config`/allowed-tools derived from the profile; (b) Agent-tool dispatch guidance for the orchestrator is a one-line `profile` in the printed record (`aq-risk-tier --work` output is what the orchestrator pastes into subagent briefs, which Rule 5 already limits to slice-relevant context); (c) `aq-payload-audit` gains a check "loaded surface > profile": it already audits always-on payload, so this extends it with the profile as the expected set. Measured loop: skill usage telemetry (Skill-tool invocations are not recorded today) is added by the same PostToolUse matcher `Skill`; pruning decisions wait for two weeks of data (MVP does not prune; it only measures). Deferred honestly: `clangd-lsp` removal is a settings change the owner can do now; no profile machinery is needed for that one.

## 7. Migration, MVP scope, later phases

Principle: report mode first, then enforce per tier, because the policy says "until owner activates". Each phase is independently useful and has a consumer.

**MVP (one slice, ~250 lines changed; changes real behavior)** - risk: it touches `risk_tier.py` and policy JSON (both `core` under current rules, so this slice itself needs 2 reviewers and a design round: it eats its own cooking).
1. `risk_tier.py`: add `classify_work`, signals (policy-paths, reversibility patterns, blast-radius count, fail-closed on no-input and exception), `assignment` and `lane_capabilities` read from policy. Existing `classify` untouched.
2. Policy JSON: add `assignment`, `policy_paths`, `signal_patterns`, `lane_capabilities`, per-tier `mode`. Version 1.1.
3. `aq-delegation-registry`: accept the new optional fields; add `stats --by`.
4. `aq-agent-dispatch-hook` (PreToolUse `Agent`): log-only, writes registry row. This alone gives Rule 17 measurability and corrects lane share.
5. `check-review-disposition.py`: recompute tier from diff; `Review-Risk-Tier` and reviewer-count checks in `warn` for medium, `enforce` for **core only** (smallest surface with the clearest need: canon, tier0, hooks, sudo/signer paths already take 5-9 rounds, so a required 2-lane review is already the practice).
6. Canon block text (Rule 16 parity): one short rule "work class" in `canon/blocks/` landing in all five agent files in the same PR; update `role-matrix.md` to retire the illustrative defaults table and point at policy.

What the MVP deliberately omits: profile-driven MCP launch, tier0.d check, delegate-to-* default resolution, modality probes. Those are phase 2-3.

**Phase 2**: shared dispatch helper + delegate-to-* default resolution and local pre-flight refusal; `aq-review-request` default lane; tier0.d `check-risk-class`; Agent-hook flips to enforce for missing `model`; enforce `high`.
**Phase 3**: `lane_capabilities` probes (probe script records what each CLI can do; writes the measured table to the policy via a PR, never silently); profiles + `aq-payload-audit` extension; Skill-tool telemetry.
**Phase 4**: tracker.json optional `risk` and `severity` editorial fields consumed by `classify_work` declared inputs (Q3); feed round counts back to retune thresholds (RSI loop).

Retire list (state explicitly, per brief): role-matrix illustrative model table (replace by pointer); `model_tiering` private complexity heuristic as a competing classifier (becomes input floor); per-script cost ordering copies in `aq-role-route` (read assignment block). Extend: risk_tier.py, risk-tier-policy.json, aq-risk-tier, check-review-disposition.py, aq-delegation-registry, aq-role-route, aq-payload-audit, `.claude/settings.json` hooks. New files: one hook script, one tiny shared helper, one tier0.d check, tests. Nothing else.

## 8. Failure modes, gaming risks, detection

| Risk | Mechanism | Mitigation / detection |
|---|---|---|
| Orchestrator splits a core change into many low slices to stay under thresholds | size and path signals apply per diff, not per task | CI recomputes on the PR diff (the unit of merge); registry stats flag a series of low-risk commits from one `task_id` touching one directory within 24h (detector in `stats`, WARN) |
| Declared inputs used to lower (severity S4, complexity trivial) | declared values are raise-only; computed floors dominate | `claimed rejected: never self-lowered` is logged; count of rejected lowerings per lane is a metric; spikes are an RSI finding |
| Agent edits policy to relax gates | policy is `core`; CI recomputes using the *base branch* copy of the policy, so a PR cannot relax its own rules | check-review-disposition loads policy from `origin/main` blob; a policy diff that lowers a tier mode or min_reviewers is itself classified core and needs 2 lanes |
| Forged trailers / receipts | known: Author-lane/Reviewed-by are declarative (WR-REVIEW-1) | not solved here; this PRD does not add trust in trailers: it only adds recomputation (hard to forge from the diff) and reuses receipts. Per-lane signing remains WR-REVIEW-1 |
| Hook skipped (Agent dispatch with no hook) | hook can be disabled in settings | `aq-payload-audit` checks the hook is present in project settings; registry-vs-PULSE lane-share reconciliation (agents named in PULSE with no registry rows in same day) is a daily health check that makes silent bypass visible |
| Classifier false positives inflate review (everything `high` because `config/` is high) | existing coarse rule | per-tier metric "high but approved with zero findings in round 1" > 60% for a path pattern triggers a rule-refinement ticket; thresholds change by PR, not at runtime |
| Classifier false negatives (content scan misses) | regex signals are finite | fail-closed defaults on unknown; REQUEST_CHANGES with CRITICAL/HIGH finding on a medium triggers reclassification and is counted as a miss (escalation rule 1), so miss rate is measured |
| Local lane given work it cannot do | gap 7 | pre-flight refusal with named reason; failed/orphaned local count per class is a metric |
| Enforcement bricks the repo (CI red on classifier bug) | new gate on trunk | rollout per tier via `mode`; classifier exception => high plus a visible CI annotation, not a crash; one-line kill switch (`mode: report-only`) via PR; Rule 19: the gate fails only on regression the change introduced, not on expiries |
| Mode flip to enforce never happens (Rule 23 dormant again) | tends to rot | the MVP ships core in enforce; activation attestation (Rule 15) lists each tier's mode; `stats` shows per-tier "would have failed" counts so the flip decision is data-driven |
| Complexity axis gamed to keep high-cost model (everything `complex`) | declared complexity only raises | Rule 17 compliance metric: share of implementer dispatches at flagship with no recorded reason |
| Review shopping (retry until a lenient lane approves) | lane choice is free after a REQUEST_CHANGES | round counter is per class digest and carries across lanes; a REQUEST_CHANGES from any lane must be dispositioned (existing Review-Disposition) before another lane's approve counts |

## 9. Acceptance tests and metrics

Tests (all runnable locally with fixtures; each exercised against a real diff in the live repo before merge, per commit discipline):
1. `classify_work([])` with no diff => high / reason `unclassified`; with corrupt policy JSON => high / `classifier-error`.
2. Staged diff touching `CLAUDE.md` => core. Touching only `docs/foo.md` => low. Touching `.githooks/commit-msg` + one line => core, complexity trivial.
3. Declared `claimed=low` on a core diff => core, reason `never self-lowered`. Declared `severity=S4` cannot lower a path-computed high.
4. Diff adding `sudo` or `rm -rf` to a `.md` => >= high (content signal).
5. Local dispatch with a 30KB prompt => refused with `exceeds local ceiling`, no process started.
6. check-review-disposition: PR touching core with one local receipt => fail; with codex + claude receipts => pass; with trailer `Review-Risk-Tier: low` on a core diff => fail.
7. PR that edits `risk-tier-policy.json` to set core `min_reviewers: 1` => CI computed against base policy, tier core, requires 2 lanes.
8. Agent-tool call without `model` for an implementer role => registry row with `model: null, source: agent-tool` in report mode; denied in enforce mode.
9. Role-route with modality video and gemini lane marked `video:false` => antigravity or claude chosen, or `blocked: no-capable-lane`; substitution recorded.

Metrics (read from registry via `stats`, reported weekly in an existing health report, not a new dashboard):
- Rule 17 compliance rate = implementer dispatches with explicit model and tier <= required / all implementer dispatches. Target >= 95% by the end of phase 2; denominator now includes Agent-tool rows.
- Review rounds per risk tier (median, p90). Baseline: core 5-9, low 1. Target after front-loaded design gate: core p90 <= 6, high p90 <= 4. Rounds beyond budget must show an escalation record 100%.
- Cost per class: tokens in/out and (where known) codex slots per class; target codex review slots consumed by low/medium = 0.
- Classification accuracy: reclassification rate (escalated_from) < 10% of medium; downward-rejection count tracked.
- Local failure rate (failed + orphaned) per class: target < 2% on Tier A after pre-flight (baseline 5/49).
- Coverage: share of dispatches with a class record >= 99% (measures bypass).
- Substitution rate and reasons, to detect a perpetually degraded lane.

## 10. Open questions

1. Where do outward actions get detected reliably? Declared `--outward` is gameable; command-set detection only covers wrapped dispatches. Proposal: treat any slice whose acceptance includes `gh pr merge`/`git push`/account action as outward by wrapper allow-list; needs owner view on false-negative tolerance.
2. Should the content-scan signals (regexes on added lines) live in policy JSON (editable, reviewable) or in code? Proposal: JSON (consistent with SSOT rule), with a test corpus.
3. Should priority/severity live in tracker.json editorial fields (gap 10) or only be declared per dispatch? Proposal: tracker field in phase 4; MVP uses the declared flag so we do not touch the PM schema.
4. How do we treat the claude.ai connectors (Gmail, Drive, Docs) loaded in orchestrator sessions: they are not repo-scoped MCP servers and the profile mechanism does not cover them. Owner decision on disabling at account level.
5. Is `core` requiring two *lanes* achievable when codex is in cooldown and gemini is advisory-only (untrusted)? Proposal: claude flagship (fresh, not author) + local counts as second only if rubric-checklist-only review; else BLOCKED until codex returns, with catch-up queue per Rule 18. Needs owner call on what "independent" means for local.
6. Is the 400-line/25-file diff escalation still right now that most slices are small? Defer to measured data after phase 1.

## Trade-offs stated for the comparing lane

- I chose two axes plus signals over a multi-dimensional scorecard. Gain: one vocabulary, simple audit, reuses existing names. Loss: some dimensions (urgency, importance) are deliberately not classes, which a reader may find under-expressive.
- I chose CI recomputation as the enforcement spine over wrapper-side enforcement. Gain: agents cannot bypass it; reuses the one live trunk gate. Loss: feedback arrives at PR time, so pre-flight consumers (delegate-to-*) are warn-first and phase 2.
- I chose deterministic regex/path/diff signals over any model-assisted classification. Gain: reproducible, fail-closed, no 8k-context local dependency. Loss: finite pattern coverage; mitigated by measured reclassification rate.
- I put review depth on risk and implementer model on complexity, letting `balanced` implement core changes under 2-lane review. Gain: Rule 17 holds and the round problem is attacked where it originates. Loss: depends on the design gate actually reducing rounds, to be verified by the rounds-per-class metric.
- MVP is core-only enforcement plus Agent-tool logging, giving real behavior change (two-lane review required for gate/canon/hook changes; Rule 17 measurable) before touching the broader dispatch scripts.
