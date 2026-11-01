# PRD (operations / cost / operator-experience lens): work classification -> assignment

Author lane: independent architect, Claude Sonnet 5.5. Date 2026-10-31. Inputs: BRIEF.md, INVENTORY.md, `scripts/ai/lib/risk_tier.py`, `config/factory/risk-tier-policy.json`, `config/model-coordinator.json` (`tier_routing`), registry tail. No other PRD read.

Thesis: the cheapest correct system is one that makes the right choice the default and makes deviation visible. The expensive failure today is not misclassification; it is ceremony that nobody budgeted (5-9 Codex rounds on security slices, 8 on #667) and a classifier whose output reaches no one. So this PRD ships the smallest "class -> default dispatch card -> logged outcome" loop, caps review ceremony per class, and grows lane share from measured outcomes.

---

## 1. Problem (evidence from INVENTORY)

1. Classifier outputs reach nobody (gap 1). `risk_tier.classify` is report-only; `min_reviewers`, `independent_reviewer_required`, `validation_set` are read by no dispatcher or gate. Core/high and docs travel the same gate path.
2. Review ceremony is unbudgeted. Sudo boundary: 5 REQUEST_CHANGES + 3 design revs. #667: 8 rounds. Low-risk herdr flag: 1 local pass. The cost spread (1 vs 8-9 Codex rounds) tracks orchestrator judgment, and Codex headroom (shared, 40% reserved for reviews) is the scarce resource.
3. Assignment is unmeasurable (gaps 3, 4). Registry rows carry agent/role/status/tokens only: no model, effort, tier, class, rounds. Claude Agent-tool dispatches (the actual Sonnet/Haiku implementers) are absent, so Rule 17 compliance and lane share are unknown. Registry shows 49 local reviewers, 26 local implementers, 37 codex, 0 claude/gemini.
4. Local lane wastes time on ineligible work (gap 7): 3 failed + 2 orphaned of 49 reviewers; prompts over ~22KB; Tier A/B/C is docs only.
5. Vocabularies do not map (gap 5): risk low..core, complexity trivial..critical, fast/balanced/flagship, Tier A/B/C, role-matrix axes.
6. Path-only inputs (gap 2): a `.md` canon-rule change is "low"; every `config/*` file is "high". Both mis-spend review budget in opposite directions.
7. Capability surfaces load globally (gap 8); no skill telemetry, so nobody can prune with data.

Operator view today: the orchestrator decides lane, effort, review depth and rounds from memory notes each time; the owner is prompted ad hoc. Nothing shows "was this assignment good".

## 2. Goals / non-goals

Goals
- G1 One class per task, computed automatically at dispatch time in under 1 second, with a one-line override that is logged.
- G2 Every class has a default Dispatch Card (lane, model tier, effort, reviewers, round cap, gates). Following it costs zero decisions.
- G3 Every dispatch, including Agent-tool, writes a registry row with class and card fields. Rule 17 compliance becomes a query.
- G4 Review ceremony has a per-class round cap and escalation, so a 9-round slice trips a reshape step at round 3 instead of silently continuing.
- G5 Lane share is a function of measured per-(lane, kind, tier) outcomes, promoted and demoted by rule (Rule 21), not by opinion.
- G6 Owner prompts only for core class and for irreversible or outward actions.

Non-goals
- No new classifier engine, no ML, no LLM-based classification in MVP (local model cannot afford it; 8k ctx, 5 tok/s).
- No new gate system: reuse tier0, check-review-disposition, risk-tier-policy.
- No replacement of model-coordinator tiers or role-matrix; they remain id and role SSOT.
- No per-class MCP/plugin hot-swap in MVP (see section 6: audit and prune first, scope second).
- No changes to owner-only security boundary or activation signer.

## 3. Classification model

### 3.1 Principle
Two computed axes plus up to three boolean flags. Everything else (severity, blast radius, reversibility, novelty) is folded into these through cheap signals, because dimensions nobody can measure automatically will be declared inconsistently and gamed.

Axis A, TIER (existing vocabulary, extended): `low < medium < high < core` from `risk_tier.classify`. Kept as the single risk vocabulary. Extensions (all additive escalations, never lowering):

| Signal | Source (automatic) | Effect |
|---|---|---|
| Path rules | existing | baseline tier |
| Diff size | existing (400 lines / 25 files) | +1 for low/medium |
| Policy-text docs | new rule: `^CLAUDE\.md$`, `^\.agent/(CODEX|LOCAL-AGENT|GEMINI|WORKFLOW-CANON)`, `^canon/`, `docs/architecture/role-matrix.md`, `.claude/settings` | floor `high` (fixes gap 2 mis-low) |
| config narrowing | new: `^config/` stays high only if file is not in a low-allowlist (`config/*.md`, dashboards, prompts); allowlist is data in policy JSON | prevents over-review of benign config |
| Reversibility | new: touches migrations, `DROP`, `rm`, deployment/activation, data stores (`postgres|qdrant|redis` in diff or path) | floor `high`; irreversible-data => `core` |
| Blast radius | new: count of distinct top-level subsystems touched (`nix/`, `ai-stack/`, `scripts/governance`, `scripts/ai`) >=3 | +1 |
| Security sensitivity | existing security patterns + `sudo|polkit|setuid|apparmor|sops|activation` in diff added lines | floor `high`; owner-boundary words (`sudo`, `timestamp_timeout`, activation signer) => `core` |
| Declared | `--tier X` or tracker `risk` | max(declared, computed); never lowers (existing behavior) |

Axis B, KIND (what sort of work; selects the capability profile, not the review depth):
`code` (default), `doc` (md only), `research` (no repo write; web/paper/analysis), `media` (video/audio/image input), `ops-outward` (touches external accounts, PRs, pushes, sends), `design` (PRD/plan/architecture, no code). Derived from: paths in diff, `--role research`, presence of a URL with media host in the task text, explicit `--kind`. Default `code`.

Flags (booleans, computed): `novel` (no prior registry row with same kind+primary directory in 30 days AND no matching AIDB `error-solutions` hit; the cheap proxy for novelty), `urgent` (declared only, logged), `local_ok` (see 3.3).

### 3.2 Resulting classes (one vocabulary)
Class = `<TIER>.<KIND>[+novel]`, rendered like `high.code+novel`. Only 4x6 combinations exist and most map to one of six cards below, so operators learn six cards, not 24 classes.

Mapping of existing vocabularies (all retained, none parallel):

| Existing | Mapping |
|---|---|
| risk low/medium/high/core | TIER, unchanged |
| complexity trivial/simple | cost lane `fast`; allowed only when TIER=low or medium |
| complexity medium | `balanced` |
| complexity complex/critical | `flagship` for plan/design/review roles only (Rule 17); never default for implement |
| Local eligibility Tier A/B/C | becomes `local_ok` flag: A => ok implement+review; B => ok review, implement only after decomposition; C => no |
| AIDB tool risk | separate (tool call risk); out of scope, noted only |
| role-matrix role | unchanged; the card picks the role instances |

Complexity is not a second axis any more: it is derived from TIER+novel+size for model-tier selection (section 4). `estimate_task_complexity` keyword heuristic is retired as an input to dispatch (it has no caller there) and remains only inside the coordinator.

### 3.3 `local_ok` pre-flight (fixes gap 7)
Computed from: estimated prompt bytes (task text + attached file bytes) <= 18KB (margin under 22KB), files to edit <= 1 for implement, review diff <= 400 lines. If not ok, wrapper refuses with an actionable message ("decompose or route to X") instead of launching a doomed run. Replaces memory-note folklore with a check.

## 4. Assignment matrix (Dispatch Cards)

Roles per Rule 18; lane names are preferences in order, substitution recorded. "Rounds cap" is the ceremony budget: reaching it forces the escalation step, not a stop.

| Card | Class(es) | Implementer (Rule 17) | Reviewer(s) | Effort | Rounds cap | Required gates | Owner prompt |
|---|---|---|---|---|---|---|---|
| C0 trivial | low.doc, low.code (size small) | local Qwen if `local_ok`, else claude `haiku` | none beyond tier0; local reviewer sampled 1 in 5 | low | 0 | tier0 pre-commit | no |
| C1 routine | low.code, medium.code, medium.doc | local Qwen (decomposed) or claude `sonnet`; codex implement only when headroom > reserve | 1 local reviewer (read-only); independent of implementer | medium | 2 | tier0, targeted tests | no |
| C2 significant | medium.code+novel, high.doc, high.code (no security flag) | claude `sonnet` (or codex implement) | 1 Codex review (or Gemini/fresh Claude if codex down, substitution recorded) + local reviewer as pre-screen | medium | 3 | tier0, targeted tests, security-review checklist | no |
| C3 sensitive | high.code with security/reversibility flag, high.design | claude `sonnet`; design by flagship | 1 Codex + 1 distinct second reviewer (independent lane) | high for review, medium for implement | 3 then reshape | adds high-risk-rubric, freeze lock | on merge only |
| C4 core | core.* | claude `sonnet` implement, flagship design review pre-implementation | 2 independent reviewers, one Codex; hash-bound | high | 3 then reshape, hard stop at 6 | full validation_set incl. live-e2e, tier0 pre-deploy | yes, via `aq-approve` |
| CR research | any.research, any.media | Gemini lane for media only if capability probe shows support; else local/Claude research role with web tools; output advisory | reviewer only if findings drive a change (then re-classified as code/design) | medium | 1 | provenance fields (source URLs, probe result) | no |
| CX outward | any.ops-outward | orchestrator-owned, no delegation | owner | n/a | n/a | confirm irreversible/outward (Fable-parity rule 9) | yes |

Model-tier selection rule (one place): implement -> `balanced` (Sonnet) unless card says local/haiku; plan/design/review -> `flagship` only for C3/C4 design and C4 review; `fast` for C0 and mechanical single-file with checkable result. This is `tier_routing` applied to card role, not to keyword complexity.

Effort rule: default per card as above; higher effort allowed only with a one-line `--why`; effort and outcome are logged so the correlation can be read later (today effort is not recorded at all).

### 4.1 Escalation
- Rounds reach cap without PASS: wrapper emits RESHAPE: stop reviewing the same diff; orchestrator must (a) split the slice, or (b) return to design (flagship, one pass), or (c) file the unresolved finding class as follow-up with a dated deferral (Rule 15). Evidence: sudo and #667 patterns are findings that are really design gaps discovered late. Round 4+ reviews only the delta against enumerated prior findings (reviewer prompt carries a findings ledger, shrinking prompts and cost).
- Review disputed finding: one rebuttal round, then second-lane tiebreak, not a third round of the same reviewer.
- Local implementer fails twice on the same slice: promote to `sonnet`, record as a capability observation for that (lane, kind, tier) cell.
- Reviewer false-positive rate high for a lane in this cell (section 9): reviews from that lane become advisory-only for the cell until recovery.

### 4.2 Substitution (Rule 18)
Lane unavailable (`.<lane>-down`, codex cooldown, quota reserve): next eligible lane from `aq-role-route` that is independent of the implementer. The substitution is recorded as `substituted_from` on the registry row and, for C3/C4, a PULSE line. Local Qwen is the floor for C0/C1 only; for C3/C4 the floor is a fresh Claude flagship review, never local-only. If no independent lane exists, the slice queues in `AGENT-CATCHUP-QUEUE.md` rather than self-review.

## 5. Enforcement and telemetry

### 5.1 Single computation point
New thin entry `aq-route` (about 150 lines, wraps existing code; Rule 20): inputs = changed paths (from `git diff --name-only` of the slice branch, or declared paths for pre-work), task text, `--kind/--tier` optional; calls `risk_tier.classify` extended with the signals in 3.1 (the extension lives in `risk_tier.py` and `risk-tier-policy.json`, so there is no second classifier); outputs a Dispatch Card JSON: `{class, tier, kind, flags, card, implementer_lane, model_tier, effort, reviewers[], rounds_cap, gates[], reasons[]}`. Extends: `risk_tier.py`, `risk-tier-policy.json`, `aq-role-route` (lane health/independence), `model-coordinator.json` (tier ids). Retires: ad hoc review-depth decisions and the `estimate_task_complexity` dispatch use.

Two moments: pre-dispatch (declared paths/task text, to pick implementer) and pre-review (real diff, to confirm or escalate; class can only go up, same never-self-lower rule).

### 5.2 Consumers (Rule 23: every output has one)

| Output field | Consumer | Behavior |
|---|---|---|
| `implementer_lane/model_tier/effort` | `delegate-to-*` via `--card <file|auto>`; `--model/--effort` flags remain and win but are logged as overrides | defaults come from card |
| `local_ok` | `delegate-to-local` | refuse oversize/multi-site with decompose hint |
| `reviewers[]`, `rounds_cap` | `aq-review-request` (accepts `--lane` from card; adds `gemini`/`claude` lanes), `aq-collab-round` | picks lane, tracks round count in review ledger |
| `tier`, `gates[]` | `tier0 --pre-commit` new check `check-route-card` | WARN in mode 1, HARD in mode 2 (below): commit tier must be >= computed tier; required validation_set evidence present |
| `tier`, reviewers needed | `check-review-disposition.py` | min_reviewers and independent_reviewer_required read from policy: count of non-author Reviewed-by lines >= policy; this is where report-only becomes enforced |
| `class`, `card` | PR template field `Route-Card:` and commit trailer `Route-Class:` | auditable on every merge |
| `rounds_used` | review ledger -> RESHAPE trigger | section 4.1 |
| class, lane, model, effort, outcome | registry + dashboard | section 5.4 |

Enforcement mode follows risk-tier-policy `mode`: `report-only` (today) -> `warn` (MVP ships here; tier0 prints and records but passes) -> `enforce` (owner flips one field after the MVP metrics in section 9 hold for 14 days). Gate corollary of Rule 19: gate only on regressions the change introduces; nothing here is time-based.

### 5.3 Agent-tool dispatches (gap 4)
The in-session Agent tool is where Rule 17 lives and it is invisible. Add a `PreToolUse` hook matcher `Agent` (settings.json, declarative via the existing hook wiring in Nix/`.claude`) calling `aq-hook-agent-dispatch`:
- Reads `subagent_type`, `model`, prompt length, and infers role from the first 400 chars via an explicit `ROLE:` header the dispatch template already carries (templates updated by canon change so every agent file gets it, Rule 16). Missing `ROLE:` => treated as `implementer` (conservative).
- Appends a registry row: `agent:"claude-agent-tool"`, `model`, `role`, `card`, `class` (from env `AQ_ROUTE_CARD` or computed from prompt-declared paths), `created`.
- If role is implementer and `model` is unset or equals the orchestrator tier: mode `warn` prints a one-line rebuke and logs `rule17_violation:true`; mode `enforce` returns a block with the fix ("pass model: sonnet"). Exception token `--why` equivalent: prompt line `RULE17_EXCEPTION: <reason>`, logged.
- A matching `PostToolUse` Agent hook (or SubagentStop) writes completion status and token usage when the harness provides them; if not, status stays `unknown` and the dashboard shows it as unknown, not as done (no faked completion).
This is the single highest-leverage ops change: it converts Rule 17 from prose to a measured rate for under 100 lines.

### 5.4 Registry and telemetry fields
Append to registry rows (additive, old rows tolerated; reader treats missing as `unknown`):
`class, tier, kind, flags[], card, model, model_tier, effort, reviewers_planned[], rounds_cap, rounds_used, substituted_from, override{field,why}, rule17_violation, reviewer_verdict, finding_count, findings_by_severity, rework_rounds, wall_seconds, tokens_in/out, codex_budget_delta_pct`.
Review records (existing `aq-review-receipt`) add `round`, `findings_ledger_id`, `verdict`, `false_positive_marked` (set when a finding is later withdrawn with rebuttal, like the apparmor case).
`aq-usage` gets one event `route-card` per computation, so routing is auditable even if no dispatch follows.

### 5.5 Dashboard / operator surface
One CLI first (`aq-route report [--since 7d]`), then a panel on the existing dashboard (no new service):
- Table per class: count, median wall time, median review rounds, % at cap, % RESHAPE, local share, Codex round spend, cost proxy (tokens x lane weight from coordinator cost fields).
- Rule 17 panel: implementer dispatches by model tier, violations, exceptions with reasons.
- Lane share panel: share of implement and review by lane per tier, with promotion/demotion state (section 5.6).
- Overrides panel: where operators deviated from the card and what happened (override outcome vs card outcome). If overrides beat cards, the card is wrong and gets edited; that is how the matrix self-corrects without a committee.
- Codex budget gauge with reserve line (reuses `--budget-check-only`).
Every panel field is fed by the registry fields above; any blank "--" is a bug per owner principle.

### 5.6 Lane growth ledger (Rule 21 stewardship)
Capability cells: `(lane, kind, tier-band)` where tier-band in {low-medium, high, core}. Per cell, from registry and review receipts over a trailing window of 30 attempts: `first_pass_accept_rate` (accepted with <=1 review round), `rework_rounds_mean`, `failure_rate` (failed+orphaned), `reviewer_agreement` (for reviewers: share of verdicts matching the final binding reviewer's verdict on the same subject).

Promotion rules (a lane's share grows automatically, as help not reward):
- Local implementer, cell (code, low-medium): starts at Card C0 only for `local_ok`. After >=20 attempts with accept rate >= 85% and failure rate <= 10%, `local_ok` ceiling lifts: C1 default implementer becomes local-first for medium.code (Sonnet becomes fallback). After the same bar on medium with decomposition, `local_ok` max lines rise 200 -> 400. Demotion if accept rate < 65% over 20, with a scaffold response (add verify gate, smaller slices, front-loaded context) recorded as the remediation, never as punishment.
- Local reviewer: runs in shadow on 1 in 3 C2 reviews (verdict recorded, not binding). When agreement with the binding reviewer >= 85% over 20 shadows, local becomes the pre-screen whose clean PASS lets C2 drop to a single Codex round with delta-only prompt; at >= 90% over 40 it may be the sole reviewer for C1 (already the default) and a counted second reviewer for C2. Never sole reviewer for C3/C4 (role-matrix rule 3; security).
- Codex: reserved for review rounds on C2-C4 and for implement only above reserve; as local pre-screening absorbs C2 first rounds, Codex rounds per class should fall, and that is the measured payoff.
- Gemini/Antigravity: graduate from untrusted-advisory per memory: shadow-only until a capability probe (below) and agreement bar are met; then eligible for research (non-media) and C2 second-reviewer substitution.
- Capability probe: `aq-lane-probe` (small, fixture-based, weekly + on-demand) records per lane what it can do (YouTube/media read, `--mode auto`, max prompt size, tool use) into `config/lane-capabilities.json` consumed by `aq-route` for CR and media routing. Without it, media tasks route to the local/Claude research path with a recorded `probe: unsupported`.
Thresholds live in `config/factory/route-policy.json`, not code; they are the tunable surface.

## 6. Tool/skill/MCP/plugin scoping per class

Honest position: with no skill/MCP usage telemetry, per-class scoping now would be guessing. Order is measure, prune globally, then scope.

MVP (measurement + free wins)
- Log skill and MCP-server usage per dispatch: extend `aq-hook-post-tool` to record tool-name prefix (`mcp__<server>__`, `Skill`) into `aq-usage` with the active `class`. This is the telemetry that makes later pruning evidence-based.
- Remove `clangd-lsp` from default `enabledPlugins` (declaratively, in the settings source); keep it available via a profile. The repo is Python/Nix; `aq-payload-audit` check 4 already flags it. Rule 19: fix the producer, not annotate.
- `rea` MCP currently CONNECTION_CLOSED: drop it from the default `.mcp.json` and make it opt-in by kind (`research` with binary analysis). A permanently failing server costs startup time and noise on every task.

Phase 2 profiles (a profile is a named set, applied by the dispatch wrapper through the child's settings/MCP config, not by prose):

| Profile | Used by cards | MCP | Skills advertised | Hooks |
|---|---|---|---|---|
| `lean` | C0, C1 | lean-ctx only (+hybrid-coordinator for hints) | role skill only | write guard, approval ask |
| `standard` | C2 | lean-ctx, hybrid-coordinator, github | role + domain skill | + post-tool telemetry |
| `secure` | C3, C4 | lean-ctx, hybrid-coordinator, semgrep, github | reviewer-gate, security-audit, role-contracts | + review-ledger, route-card checks |
| `research` | CR | lean-ctx, hybrid-coordinator, web fetch, (rea/osint on request) | research skills | read-only write guard |
Local lane gets a strict allowlist because of 8k context: skill descriptions and tool schemas are a direct tax. The existing `aq-skill-suggest` auto-suggestion in local prompts is kept but capped at 2.

Skills are advertised per profile from a list in policy JSON; unknown skills remain reachable via `get_skill_content` (nothing is removed from the system, only from the always-on payload; "update don't remove used capabilities").

## 7. Migration, MVP, later phases

### MVP (one cycle, three slices; smallest change in real behavior)
Slice M1 (implementer: Sonnet; no Codex implement) `aq-route` + risk_tier extensions
- Extend `risk_tier.py` with new signals (policy-text floor, reversibility, blast radius, owner-boundary words), data in `risk-tier-policy.json`; unit tests with the 10/29-31 slices as fixtures (sudo => core, #667 => high, herdr enable => low/medium, CLAUDE.md edit => high).
- `aq-route` emits the card; `aq-route report` reads the registry.
- Mode: `warn`.
Slice M2 `delegate-to-*` + registry fields + Agent-tool hook
- Registry gets the section 5.4 fields from all delegates; `delegate-to-codex` records effort; `delegate-to-local` gets `local_ok` pre-flight (refuse oversize).
- `aq-hook-agent-dispatch` PreToolUse/PostToolUse on `Agent`; warn mode only.
- Canon change (Rule 16): `ROLE:` header and `RULE17_EXCEPTION:` convention in `canon/blocks/` -> CLAUDE.md, CODEX, LOCAL-AGENT, GEMINI, WORKFLOW-CANON in the same cycle.
Slice M3 review ceremony
- `aq-review-request` reads card (lanes, rounds cap), maintains the review ledger (round count, findings ledger, delta-only prompt for round >=3), prints RESHAPE at cap; `check-review-disposition` counts reviewers against policy in warn mode; `tier0.d/check-route-card` (warn).
- PR template and commit trailer `Route-Class:`.

MVP outcome that changes real behavior: Agent-tool dispatches become visible and Rule 17 warns; local refuses doomed dispatches; reviews stop at round 3 with a forced reshape; every merge states its class; the first report shows per-class review rounds and Codex spend.

Out of MVP: enforce mode, profiles, lane growth automation, dashboard panel (CLI report only), lane probe, tracker.json fields.

### Phase 2 (after 14 days of MVP data)
- Flip `mode` to `enforce` for tier0 route-card and review-disposition counts (owner single field change, documented in aq-approve).
- Tool/MCP/plugin profiles (section 6) and per-class skill advertising.
- Dashboard panels; lane growth ledger computing promotions as proposals (a PR to `route-policy.json` that the owner/orchestrator approves), not self-modifying behavior.
- `aq-lane-probe` and Gemini/Antigravity shadow mode.
### Phase 3
- tracker.json optional `risk`/`priority` fields consumed by `aq-route` as declared input (max-only).
- Shadow reviews to graduate local review share; automatic card edits proposed from override-vs-card outcomes.
- Novelty flag upgraded with AIDB similarity once the cheap proxy has a measured error rate.

Retired / replaced: free-form per-slice review-depth decisions; keyword complexity as a dispatch input; `--lane codex|local` binary choice in `aq-review-request` (extended to lane list); memory-note-only local limits (now a check). Extended: risk_tier.py, risk-tier-policy.json, aq-role-route (independence and substitution recording), delegate-to-*, check-review-disposition, tier0, registry schema. Not touched: model-coordinator.json tier ids, role-matrix roles, owner security boundary.

Cost of the system itself: about 400 lines of new code, no new daemon, no new service, no model calls in classification.

## 8. Failure modes, gaming risks, detection

| Risk | Detection / mitigation |
|---|---|
| Orchestrator declares a low tier to dodge review | never-lower rule; `check-route-card` recomputes from real diff at commit; `tier_mismatch` count on report; trailer vs recomputed diff |
| Path-split gaming (big change as many small PRs) | blast-radius and diff size computed per branch, plus per-author-per-day rolling sum of core-adjacent paths; report flags clusters |
| Vacuous rule17 hook (model set but arbitrary) | model validity checked against `model-coordinator.json` tiers; violations list includes `model==orchestrator tier`; weekly audit compares dispatch model with outcome |
| Override abuse | every override requires `--why`, appears in overrides panel; override rate per operator over 15% triggers a card review |
| Round cap used to rush bad merges | RESHAPE is not a pass: PASS verdict is still required; cap only changes the next action. Hard stop at 6 for core |
| Reviewer collusion or fabricated review (known from 10/27 audit) | review-disposition requires distinct lane + `Reviewed-subject-sha256`; independent_reviewer_required enforced; receipt must exist in review ledger with transcript path (fabricated claims have none) |
| Local reviewer false negatives raising false confidence | shadow agreement metric; local never sole on C3/C4; sampled Codex re-review of 1 in 5 local-only C1 passes |
| Classifier thrash (over-escalating everything to high) | class histogram on report; if C3+C4 exceed 25% of 14-day volume, signals are over-broad; policy tuning is data-only |
| Metrics gamed by cheap trivial tasks | cost and rework metrics reported per class and per tier-band, never as a global average |
| Hook failure blocks all Agent dispatches | hook fails open in warn mode (logs `hook_error`); in enforce mode fails closed only for implementer-role with explicit message; kill switch `AQ_ROUTE=0` logged |
| Registry rows incomplete / unknown completion | `unknown` shown as unknown; dashboard "% rows with full fields" is itself a metric (target 95%) |
| Stale thresholds | thresholds in policy JSON with `last_reviewed` date; stale = freshness WARN only (Rule 19 corollary), never a commit blocker |
| Gemini/Antigravity untrusted advisory pollutes agreement stats | advisory lanes counted in shadow only; excluded from binding-review metrics until probe and agreement bar pass |

## 9. Acceptance tests and metrics

Acceptance tests (all runnable, with real dependencies where it matters)
1. Fixture classification: the 10/29-31 slice set yields sudo boundary = core, #667 = high.code (security), apparmor parser = high, deploy-current = medium/high, herdr enable = low or medium, CLAUDE.md canon edit = high (was low). Tier never lowered by `--tier low`.
2. Card determinism: same inputs produce identical card JSON; every card field has a registered consumer (a test greps the consumers table and fails on an unconsumed field, enforcing Rule 23).
3. Registry completeness: after one real dispatch per lane (local, codex, claude Agent-tool), each row has class, model, effort, card; Agent-tool row exists (live test, not mock).
4. Rule 17 hook: an implementer Agent dispatch without `model` is logged `rule17_violation:true` in warn mode and blocked in enforce mode; with `model: sonnet` passes; with `RULE17_EXCEPTION:` passes and logs reason.
5. `delegate-to-local` refuses a 30KB prompt and a 3-file implement with a decompose hint; accepts a 10KB single-file task; refusal rate recorded.
6. Review cap: a synthetic review ledger reaching round 3 on C3 emits RESHAPE, round 4 prompt contains findings ledger only plus delta (prompt size less than 50% of round 1).
7. Substitution: with `.codex-quota-cooldown` present, a C3 review routes to the next independent lane and records `substituted_from`; with no independent lane, slice queues in catch-up queue.
8. `check-review-disposition` in warn mode reports a core change with one Reviewed-by as under-reviewed; in enforce mode (test branch only) blocks.
9. `aq-route report` prints non-blank values for every column on real registry data.
10. Rule 15 attestation for the MVP: integrated (called from delegate-to-*, tier0, review-request), ON (warn mode live), validated end to end on one real slice, observable (report + usage events), intervenable (`AQ_ROUTE=0`, mode field, per-dispatch override).

Metrics and targets (reviewed weekly from `aq-route report`)

| Metric | Baseline (INVENTORY) | Target after 30 days |
|---|---|---|
| Rule 17 compliance (implementer dispatches with explicit non-orchestrator model) | unmeasurable | 95% measured, exceptions justified |
| Agent-tool dispatches present in registry | 0% | >= 95% |
| Registry rows with full class fields | ~0% | >= 95% |
| Mean Codex review rounds, C3 | 5-9 | <= 3.5 (RESHAPE absorbs the rest) |
| Mean Codex review rounds, C2 | unknown (2 observed) | <= 1.5 |
| Codex rounds spent on low/medium | not tracked | < 10% of Codex rounds |
| Local dispatch failure+orphan rate | 5/49 reviewers (10%) | < 3% via pre-flight |
| Local share of implement + review at C0/C1 | ~70% of registry | stable or rising, with accept rate >= 85% |
| Cells with enough data to evaluate promotion | 0 | >= 6 of 9 (lane x tier-band) |
| Override rate; override-beats-card rate | untracked | override < 15%; card edited when override-beats-card > 60% over 10 |
| Owner prompts per task | ad hoc | 0 for C0-C3 (merge excluded), exactly 1 for C4/CX |
| Median time-to-merge by class | unknown | tracked; no regression for C0/C1 vs. baseline |
| Escaped defects (post-merge fix commits referencing the slice within 7 days) per class | untracked | tracked; C0/C1 escaped-defect rate must not exceed baseline, otherwise caps loosen is reverted |

Guardrail: if escaped defects in a lowered-ceremony class rise, caps and sampling revert for that class automatically (policy value) until reviewed; savings must not be bought with quality.

## 10. Open questions

1. Is the Agent-tool `PreToolUse` hook allowed to read `model` and block, in this Claude Code build? (Test in M2 before relying on enforce mode; fallback: orchestrator wrapper script `aq-dispatch-agent` that prints the Agent call parameters and logs them.)
2. Should RESHAPE at round 3 apply to C2 or only C3/C4? This PRD says C2 cap is 3 and C3/C4 reshape after 3; owner may prefer cap 2 for C2 to save Codex.
3. Policy-text docs floor to `high` (CLAUDE.md etc.): confirm this is wanted, since it brings Codex review to every canon edit. Alternative: `medium` plus a mandatory second agent-lane read for Rule 16 parity.
4. Exact shadow-review sampling (1 in 3) trades Codex-free signal against local time at ~5 tok/s; acceptable only if shadow runs are asynchronous and never block the pipeline.
5. Who flips `mode` to enforce (owner field vs. automatic after metrics hold)? Rule 21/SOP-enforced-by-system suggests automatic proposal via PR, owner-acknowledged; confirm.
6. Does `tracker.json` risk field belong in this program, or do we prefer computed-only (less to rot)? This PRD defers it.
7. Cost proxy: tokens x lane weight is crude. Is there a real Codex/Claude quota readout to replace it, or should the reserve gauge stay the only hard budget signal?
8. Media routing: with Gemini CLI unable to read YouTube, is the interim path "local/Claude with transcript tools" acceptable, or should an external transcript fetcher be wired as a declared tool (a producer fix per Rule 19)?

## Trade-offs stated for the comparing lane
- Chose to reuse and extend `risk_tier` (path + few extra signals) over a rich multi-dimension scorer: cheaper, auditable, but weaker on genuine severity/novelty judgment; novelty is a proxy only.
- Chose round caps with forced reshape over unlimited review: saves Codex budget and addresses root cause (late design findings), but risks pressure to pass; mitigated by PASS still required.
- Chose to ship in warn mode first, enforcement later on data: slower to bite, but avoids a new gate that blocks real work on day one.
- Chose measurement before profile scoping for MCP/skills: delays payload savings except the obvious (clangd, rea), but avoids guessing with no telemetry.
- Lane share growth is rule-driven but proposed through PR, not self-editing: slower autonomy, preserves auditability and owner trust.
