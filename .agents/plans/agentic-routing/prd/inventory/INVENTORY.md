# Agentic routing inventory (read-only discovery, 2026-10-31)

Paths relative to repo root. "Live?" = who calls it + evidence. Evidence counts come from `.agents/telemetry/aq-usage.jsonl` (93.6k rows), `.agents/delegation/registry.jsonl` (1569 rows), `.agent/collaboration/PULSE.log`.

## 1. Classification

| Artifact | Path | What it classifies | Live? |
|---|---|---|---|
| risk_tier.classify | `scripts/ai/lib/risk_tier.py` (94 lines) | Path-based tier low<medium<high<core; diff escalation (>=400 lines or >=25 files, low/medium only); never self-lowers a claimed tier. Baseline via `prsi-orchestrator._risk_tier` | Partly. Callers: `scripts/ai/aq-risk-tier` CLI, `templates/factory-kit/gate-runner` + `factory-gate-bundle/gate-runner`. `risk-tier` appears 1302x in aq-usage. Mode is **report-only**: gate-runner prints "would require" and never changes exit code. No other consumer found (rg of scripts/, .githooks, tier0.d) |
| Risk policy | `config/factory/risk-tier-policy.json` | Per tier: min_reviewers (0/1/1/2), independent_reviewer_required, validation_set, lock (none/freeze/hash-bound); rubric `config/prsi/high-risk-approval-rubric.json` for high/core | Read by risk_tier.py only. `mode: report-only` ("until owner activates enforcement"). Not read by aq-review-request, check-review-disposition, delegate-to-*, aq-collab-round |
| Tier ladder is path-only | same | Rules key off regex on file paths (`.nix`, `^config/`, `secret|token|auth` etc. => high; tier0/.githooks/config/factory => core; md/docs/tests => low) | Inputs are paths and diff size only. No severity, blast radius, reversibility, novelty, or user-impact signal |
| tier0 risk handling | `scripts/governance/tier0-validation-gate.sh`, `tier0.d/*` | Check classes warn/live/freshness/hard (WARN vs HARD by mode). Not a change-risk classifier | Live on every commit. No call to aq-risk-tier (rg found none) |
| PRSI `_risk_tier(action)` | `scripts/automation/prsi-orchestrator.py:324` | low/medium/high for PRSI actions (safe/type) | Live inside PRSI at line 636 |
| AIDB tool risk | `ai-stack/mcp-servers/aidb/server.py:183 _tool_risk_tier` | Per-MCP-tool risk, gates medium/high tools by policy | Live in AIDB tool execution and telemetry. Separate vocabulary from change risk |
| tracker.json schema | `templates/factory-kit/pm-tracker/tracker.schema.json` (also factory-gate-bundle copy) | No risk/severity/priority field found (rg "risk|severity|priority" empty). `aq-pm-tracker` projects status from git | Schema live; carries no classification |
| Complexity (trivial..critical) | `config/model-coordinator.json` `tier_routing` (trivial/simple->fast, medium->balanced, complex/critical->flagship, creative) | Complexity -> model tier -> concrete id via `tiers` (Claude fable/opus/sonnet/haiku, Gemini 3.8-flash efforts low/med/high, GPT-6 astra/sol/luna) | Consumed by `scripts/ai/lib/model_tiering.py` (`estimate_task_complexity`, health-aware ladder local->codex->claude, imports aq-role-route lane health) and `hybrid-coordinator/extensions/model_coordinator.py`. `delegate-to-claude --model-tier` resolves tier from this file. Codex and Gemini delegates do not read it |
| Complexity estimator | `scripts/ai/lib/model_tiering.py:83` | Keyword heuristic on query/tool names | Called from `model_tiering` only inside scripts/ai/lib; no delegate-to-* caller found |
| Task-type classifier | `scripts/ai/lib/dispatch.py:450 classify_task_type` (code/reasoning/structured/lookup); `scripts/ai/lib/task_config.py` TaskConfig + normalize_role | Picks llama payload profile (thinking budget, tokens) for local lane | Live for local dispatch (delegate-to-local -> dispatch.py) |
| Coordinator role classifier | `ai-stack/mcp-servers/hybrid-coordinator/extensions/model_coordinator.py:140 ROLE_SIGNALS, classify_task:166`; `hybrid-coordinator/intent_classifier.py` | Keyword role/intent -> ModelRole (fast_chat, reasoning, coding) | Live in coordinator routing |
| Switchboard profiles | `config/switchboard-profiles.yaml` (369 lines): default, continue-local, local-agent, remote-default/free/coding/reasoning/tool-calling, antigravity-collective, local-tool-calling, embedding-local, embedded-assist, coordinator-internal, local-coding. `routing-decisions.jsonl` (804 rows) logs local vs profile | Token budgets/routing/profile cards per endpoint | Live (switchboard). Client-selected profile, not derived from change risk |
| Local eligibility Tier A/B/C | `docs/architecture/local-agent-task-eligibility.md` (skill `task-eligibility`) | A: 1 file <=200 lines autonomous + flagship review; B: <=4 files <=400 lines review gate; C: ineligible | Documentation. No code enforcement found; `local_delegation_reliability.py` is adjacent |
| Role matrix | `docs/architecture/role-matrix.md` (262 lines): roles, 4 orthogonal axes (role, agentType, capability class, review eligibility), "Model Defaults (Illustrative, Not Binding)", rule 3 (destructive/dual-use/external-account work reviewed by a different model) | Doc SSOT; axes are not computed from a task |
| aq-role-route | `scripts/ai/aq-role-route` | Role -> eligible lane by availability x eligibility table x independence (`--exclude`) x cost; lane-down flags + codex cooldown | Live but light: `role-route` 23 rows in aq-usage; callers `model_tiering.py`, `dispatch_consult.py`. No delegate-to-*, aq-collab-round or aq-review-request call |
| Canon rules 17/18 | `CLAUDE.md` (+ `.agent/CODEX.md`, `LOCAL-AGENT.md`, `GEMINI.md`, `WORKFLOW-CANON.md`) | 17: cheapest eligible implementer, explicit model override; 18: agent-agnostic roles + catch-up queue | Text rules. Enforcement by orchestrator discipline; no hook checks Agent calls for a model override |
| aq-hints | `scripts/ai/aq-hints`, `scripts/ai/skills/aq-hints.skill.md` | Ranked workflow hints by query/domain/agent type | Live (coordinator `get_hints`, MCP). Not risk-aware |
| Approval hook | `scripts/ai/aq-approval-ask-hook` (1805 rows), `aq-worktree-write-guard` (89 rows) | Command/path gating at PreToolUse | Live, `.claude/settings.json` |

## 2. Assignment levers

| Lever | Path | Controls | Live? |
|---|---|---|---|
| delegate-to-codex | `scripts/ai/delegate-to-codex` | `--mode safe|edit`, `--model`, `--role implement|review|research`, `--effort low|medium|high` (default medium), budget: `--budget-check-only`, `DELEGATE_CODEX_REVIEW_RESERVE_PCT` (default 40% reserved for `--role review`, other roles refused when headroom is gone), quota cooldown file | Live (37 codex registry rows 10/29-31: 21 review, 16 implement). Effort is not recorded in registry rows, so effort usage is unauditable |
| delegate-to-claude | `scripts/ai/delegate-to-claude` | `--role plan|implement|review|research|rsi`, `--model-tier flagship|flagship_fallback|balanced|fast|creative` (resolved via model-coordinator.json), slot cap, slot-0 reserved for review | Live. Zero claude rows in 10/29-31 registry window: Claude work was done through the in-session Agent tool, which is not in the registry |
| Agent tool (in-session) | Claude Code | `model` override (sonnet/haiku/opus/fable), `subagent_type`, effort | Rule 17 says always pass model. Not logged to registry; compliance not measurable |
| delegate-to-gemini | `scripts/ai/delegate-to-gemini` | `--mode auto_edit|yolo`, `--model`, `--role` (4 roles) | Zero registry rows in window. gemini CLI cannot reach YouTube; `--mode auto` "not available for this account" (issues-backlog line ~7182) |
| delegate-to-antigravity | `scripts/ai/delegate-to-antigravity` | `--role`, `--mode fast|...` mapped to `_MODEL_MAP`, `--backend inbox|switchboard`, `--model` | Live (15 receipts in `.agent/collaboration/antigravity-inbox/receipts`, untrusted-advisory per memory). Not in window registry |
| delegate-to-local | `scripts/ai/delegate-to-local` | `--mode auto|agent|hybrid|direct|ralph`, `--role` incl. `auto`, `--wait` | Heavily live: 73+37 local-direct rows (43 reviewer done, 25 implementer done, 3 failed, 2 orphaned) |
| delegate-fanout | `scripts/ai/delegate-fanout` | parallel dispatch | Used (`.agents/delegation/fanout`) |
| aq-collab-round | `scripts/ai/aq-collab-round` | Multi-agent rounds, manifest round.json, codex dispatched with `--shared` (payload-audit check 8) | Live; no effort/risk/model flags |
| Review request/receipt | `scripts/ai/aq-review-request` (`--lane codex|local` only), `aq-review-receipt`, `scripts/governance/check-review-disposition.py`, `.github/pull_request_template.md`, `.githooks/commit-msg` | Records Review-Disposition, Reviewed-subject-sha256, non-author Reviewed-by | Live trunk protection. Lane choice is binary; not derived from risk tier; min_reviewers from policy not applied |
| Local review (localq) | `localq.py` not found by fd. Local reviews run through delegate-to-local `--role reviewer` | read-only reviewer | Live, 43 successes |
| Model-key / lane health | `scripts/ai/lib/model_tiering.py` `_LANE_MODEL_KEYS`, `.agents/delegation/.<lane>-down`, `.codex-quota-cooldown` | Availability | Live, filesystem-only |
| aq-approve | `scripts/ai/aq-approve` (43 rows) | Owner decision channel | Live |

## 3. Capability surfaces

| Surface | Where | Live? |
|---|---|---|
| Project hooks | `.claude/settings.json`: PreToolUse (Write/Edit/MultiEdit/NotebookEdit/ctx_edit + Bash -> `aq-worktree-write-guard`, `aq-approval-ask-hook`), SessionStart `aq-hook-session-start`, Stop `aq-hook-stop`, PostToolUse (edits) `aq-hook-post-tool`. `settings.local.json` has SessionStart only | Live, uniform for all work regardless of class |
| User hooks | `~/.claude/settings.json`: PreToolUse `lean-ctx hook rewrite` and `lean-ctx hook redirect` (RTK/lean-ctx rewrite) | Live |
| Git hooks | `.githooks/`: commit-msg, pre-commit, pre-push, pre-merge-commit, post-checkout, post-merge; tier0 `--pre-commit`; `scripts/governance/tier0.d/*` | Live, same gate set for all commits (WARN/HARD by class, not by change risk) |
| MCP servers (project `.mcp.json`) | hybrid-coordinator, lean-ctx, rea (currently CONNECTION_CLOSED), semgrep. User scope (`~/.claude.json`): github, hybrid-coordinator, lean-ctx, osint-tools. Session also has claude.ai connectors (Gmail, Calendar, Drive, Hugging Face, Docs) | Live; all servers attach to every session; no per-task selection |
| Plugins | `enabledPlugins`: `clangd-lsp@claude-plugins-official` (project and user). `aq-payload-audit` check 4 flags language coverage mismatches | Live; global. clangd-lsp in a Python/Nix repo is a likely unused payload item |
| Skills | `scripts/ai/skills/*.skill.md` (8: aq-delegate, aq-hints, aq-memory, aq-qa, aq-report, aq-runtime-diagnose, impeccable, tradingagents); `ai-stack/agents/skills/*/SKILL.md` (24 incl. pdf, pptx, xlsx, brand-guidelines, slack-gif-creator, template-skill); session skill list adds ~60 more (task-eligibility, escalation-protocol, role-contracts, reviewer-gate, slice-authoring, etc. have no file at repo paths found; likely served by the coordinator `list_skills`/`get_skill_content`). Slash commands `.claude/commands/` (11) | Usage telemetry for skills is thin: `skill-suggest` 18 rows, `subagent-interactive` 21 rows. Claude Code Skill-tool invocations are not recorded in aq-usage. Which skills are actually used is unknown |
| aq-tool | `scripts/ai/aq-tool` | Live reach-any-package escape hatch |
| CAPABILITY-INDEX | `docs/agent-guides/CAPABILITY-INDEX.md` + `config/capability-index.json`: 20 capability/audit, 70 agents/delegation, 53 MCP tools, 51 other, 86 systemd units | Generated catalog, live via `capability-catalog` (570 rows), `capability-gap` (1032) |
| Tooling manifest | hybrid-coordinator `tooling_manifest`, `tool_catalog`, `auto_select_tools` MCP tools | Exist; `auto_select_tools` is the only per-task tool selector, no evidence of use in this session |
| Payload audit | `scripts/ai/aq-payload-audit` | Live audit of always-on payload; reports, does not assign |
| aq-usage top commands | delegation-registry 4872, provider-projection 3087, approval-ask-hook 1805, flat-prd-gate 1780, epoch-bump 1755, eval 1678, risk-tier 1302, antigravity-inbox 1243, pm-tracker 1144 | |

## 4. Observed orchestrator behavior, 2026-10-29..31

Registry (id date 20261029-31, 114 rows, no effort/model/risk fields recorded; keys: agent, role, status, tokens_in/out only):
- local-direct reviewer 49 (43 done, 3 failed, 2 orphaned, 1 running); local-direct implementer 26; codex review 21; codex implement 16; codex unlabeled 2. Zero claude/gemini/antigravity registry rows. Claude implementers (Sonnet/Haiku) ran through the Agent tool, outside the registry.
- PULSE.log 10/29-31: 73 entries (claude-opus 41, claude 30, local training loop 2). 10 mention REQUEST_CHANGES.

Review rounds by slice (from PULSE):
- sudo/security boundary design: Codex rev3 -> rev4 -> rev5 (1 CRITICAL, 3 HIGH); implementation: PASS only after 5 REQUEST_CHANGES rounds (6233d7ac).
- false-green audit/MCP integrity (#667): PASS after 8 rounds (83c07bdf).
- activation core: REQUEST_CHANGES on deployment_id enforcement, CI skip, malformed envelope.
- deploy-current / apparmor parser (medium): 2 rounds, one finding disputed with rebuttal then withdrawn.
- low-risk enable-herdr package flag: single local Qwen review, no rework.
Pattern: security/core slices (all high or core under risk_tier path rules) consume 5-9 Codex rounds; low-risk config gets 1 local pass. Review depth tracks the orchestrator's judgment, not a computed tier.

Known failure patterns: local Qwen reviews fail on large prompts (>~22KB, memory note; 3 failed + 2 orphaned local reviewers); local read-stagnation; false positive on P5.1 B (local review REQUEST_CHANGES false positive); Codex finding artifact from an a2a-guard marker in the prompt (round 3 sudo); Gemini CLI cannot read YouTube and `--mode auto` unavailable; the video PRD first pass under-read context.

## 5. Gaps, ranked by impact

1. Classifier outputs reach nobody. `risk_tier` is report-only and its policy (min_reviewers, independent reviewer, validation_set, lock) is not read by aq-review-request, check-review-disposition, delegate-to-codex/claude, aq-collab-round or tier0. Core/high work (sudo, tier0, .githooks) gets the same gate path as docs. Rule 15/23 (no dormant code) applies.
2. Classification inputs are path regexes only. Missing: severity/impact, blast radius (services touched, host vs user), reversibility, security sensitivity beyond filename patterns, novelty, size beyond diff lines, urgency. A `.md` doc that changes policy (e.g. CLAUDE.md canon rules) classifies as low; `config/` always high.
3. Assignment is manual. Review depth (rounds, which lane, how many reviewers) is chosen by the orchestrator per slice; effort (`--effort`) and Agent-tool model are free-form and not logged (registry has no effort/model/tier fields), so Rule 17 compliance and effort/outcome correlation cannot be measured.
4. Claude Agent-tool dispatches are invisible to registry/telemetry; the registry shows only codex and local, so lane share is mis-measured.
5. Conflicting or parallel vocabularies: risk tiers low/medium/high/core; complexity trivial..critical + fast/balanced/flagship; local eligibility Tier A/B/C; AIDB tool risk low/medium/high; roles x agentType; switchboard profiles; coordinator ModelRole. No mapping between them. role-matrix defaults are "illustrative, not binding"; model-coordinator tier text is the actual id SSOT; `aq-role-route` and `model_tiering` each hold their own eligibility ladder.
6. No defined gates for several classes: no spec for novel/exploratory work, external-account or outward-facing actions beyond role-matrix rule 3, research/video/analysis tasks (no routing for modalities such as YouTube/media that Gemini CLI cannot read), or docs that change policy.
7. Local lane eligibility (Tier A/B/C, ~22KB prompt ceiling, single-file edits) is documentation; no pre-flight check refuses oversized or multi-site local dispatch, producing failed/orphaned runs (5 of 49 reviewers).
8. Capability surfaces are global, not per class: hooks, MCP servers (4-5 always attached, `rea` currently down), plugins (clangd-lsp in a non-C repo), and skills (~90 listed) load for every task. `auto_select_tools` exists but no evidence it drives selection. Skill usage is not telemetered, so pruning has no data.
9. Gemini and Antigravity lanes have no registry presence in the window and are treated as untrusted-advisory; no capability probe records what each CLI cannot do (YouTube, `--mode auto`).
10. tracker.json has no priority/severity/risk fields, so PM projection cannot feed routing.
