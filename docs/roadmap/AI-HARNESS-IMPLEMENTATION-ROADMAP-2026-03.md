# AI Harness Implementation Roadmap — 2026-03

## Purpose

Turn the current AI stack into a fully utilized local-first harness with:
- reliable continue/editor agent flows
- stronger hybrid-coordinator orchestration
- explicit delegation between local, coding, and remote agents
- retrieval and embedded-memory paths that are actively used, measured, and improved
- optional BitNet acceleration where hardware/model fit makes it worthwhile
- skill/lesson evolution loops inspired by EvoSkill without adding an uncontrolled parallel training stack

This roadmap is execution-oriented. Each track is broken into discrete tasks with concrete validation.
None of the tracks below are optional. If upstream support blocks a full rollout, the fallback requirement is to leave the declarative wiring, harness contracts, validation, monitoring, and deploy scaffolding in place so the capability is ready to activate when the blocker clears.

## Source-Informed Design Inputs

Primary references used for this roadmap:
- BitNet repository: https://github.com/microsoft/BitNet
- EvoSkill paper: https://arxiv.org/html/2603.02766v1
- Building AI Coding Agents for the Terminal: https://arxiv.org/html/2603.05344v1
- Agent Skills / agentskill.sh:
  - install and `/learn`: https://agentskill.sh/install
  - Codex usage guide: https://agentskill.sh/codex
- OpenRouter docs:
  - quickstart: https://openrouter.ai/docs/quickstart
  - provider routing: https://openrouter.ai/docs/provider-routing
  - responses API: https://openrouter.ai/docs/api/reference/responses/overview
  - tool calling: https://openrouter.ai/docs/guides/features/tool-calling
  - Auto Exacto: https://openrouter.ai/docs/guides/routing/auto-exacto
  - Codex CLI integration: https://openrouter.ai/docs/guides/guides/coding-agents/codex-cli

Applied architecture conclusions:
- separate scaffolding from runtime harness concerns
- keep context engineering and memory as first-class runtime systems
- reuse one shared lesson/hint promotion pipeline instead of building a second training brain
- prefer provider-routed tool-calling and fallback control through OpenRouter rather than ad hoc remote integrations
- treat BitNet as a targeted inference/runtime optimization track, not a blanket replacement for llama.cpp

## Current Gaps To Close

1. Continue/editor agent options still fail intermittently and are not treated as a first-class validated surface.
2. Hybrid-coordinator orchestration exists, but delegation policy, reviewer gates, and runtime execution blueprints are still only partially closed.
3. Retrieval, tree search, and memory recall are instrumented, but not yet fully optimized or intentionally selected for each query class.
4. OpenRouter remote usage exists, but advanced agent/tool-routing capabilities are not fully exploited through the local harness.
5. Cross-agent lessons are visible in reports, but not yet promoted through a formal skill/lesson lifecycle.
6. BitNet is not yet evaluated as a deployable local backend option.
7. Several recent agent surfaces are only partially integrated into the local harness and must be reviewed against the shared runtime contract before they are treated as complete.
8. Shared third-party skill ingestion is not normalized; there is no single approved path to expose `agentskill.sh` and other SKILL.md ecosystem content across AIDB, the harness, Continue, and delegated remote agents.

## Tracking Conventions

Status values:
- `planned` — defined but not started
- `in_progress` — active implementation or validation work
- `validated_local` — repo changes validated locally, not yet confirmed live
- `validated_live` — deployed and confirmed through runtime checks
- `blocked` — waiting on upstream support, runtime fix, or explicit user input

Tracking fields to update after each slice:
- `Track Status`
- `Last Updated`
- `Current Slice`
- `Next Validation`
- `Open Risks / Blockers`

## Active Blockers

| Area | Status | Evidence | Next Action |
| --- | --- | --- | --- |
| Flagship agent CLI coverage | in_progress | Continue CLI packaging and HM activation are now fixed again; Codex/Qwen/Gemini/Claude CLI delivery still mixed between declarative, external, and scaffolded | keep support matrix current and package or explicitly classify each remaining surface |
| OpenRouter prompt-contract tuning | in_progress | free-capable aliases are live across remote lanes, and `remote-tool-calling` now has a bounded post-tool finalization pass; broader delegated prompt classes still need the same tightening so repeated empty/generic replies do not keep landing in the failure ledger | extend prompt-contract revision beyond tool-calling into free/reasoning/coding micro-task templates and keep validating with live delegated smokes |
| Continue/local web research lane | in_progress | bounded `/research/web/fetch`, `/research/workflows/curated-fetch`, and `/research/web/browser-fetch` lanes are now live; the browser-assisted fallback successfully rendered a real Calflora page, the curated manifest includes a California-native pack, and source-level fetch policy now lets approved workflows escalate only the weak sources to browser fallback, while broader source-pack coverage remains incomplete | expand approved source packs beyond the current U.S./California seeds and keep challenge/captcha handling in compliant fallback lanes without implementing anti-bot evasion |
| Shared skill ingestion and registry | validated_live | local shared skills sync into approved AIDB registry entries through a repo-native path, a pinned `agentskill.sh` source (`learn`) is imported through the same governed manifest path, and the coordinator now exposes the approved catalog directly; broader remote-agent export/install surfaces remain incomplete | extend governed manifest coverage and broader remote-agent export/install surfaces |

## Execution Ledger

| Date | Slice / Commit | Status | Notes |
| --- | --- | --- | --- |
| 2026-03-13 | `d9f3e06` agent-review corrective pass | validated_local | fixed broken Continue CLI packaging, fixed Tier 0 pre-deploy file detection, added required implementation roadmap and agent surface matrix |
| 2026-03-13 | route-search retrieval breadth batch | validated_live | bounded route-search collection selection and retrieval-breadth reporting are live |
| 2026-03-13 | provider fallback health batch | validated_live | recovered provider fallbacks are reported separately from local backend failures |
| 2026-03-13 | continuation memory and prewarm batches | validated_live | continuation queries use memory recall more explicitly and report recall misses |
| 2026-03-13 | agentskill.sh planning slice | validated_local | added a shared skill-registry track so approved third-party SKILL.md content can be exposed consistently across local and remote agents |
| 2026-03-13 | unattended sudo flake-first fix | validated_local | moved bounded autonomous sudo rules into tracked `nix/hosts/nixos/deploy-options.nix` after confirming pure flake evaluation cannot see `deploy-options.local.nix` |
| 2026-03-13 | ai-coordinator runtime-refresh corrective pass | validated_local | fixed stale default runtime records and local-lane alias handling in the new ai-coordinator delegation surface before live activation |
| 2026-03-13 | scoped sudo + coordinator live validation | validated_live | confirmed `sudo -n` works for the bounded command set, `nixos-quick-deploy.sh --preflight-only` runs unattended, `/control/ai-coordinator/status` is live, and both `remote-free` and `continue-local` delegation succeed |
| 2026-03-13 | free-lane alias corrective pass | validated_live | host defaults now point at free-capable aliases, `remote-coding`/`remote-reasoning` live validation no longer depends on paid-lane configuration, and current OpenRouter work has moved on to prompt-contract quality instead of alias drift |
| 2026-03-13 | remote-free fallback hardening | validated_live | `remote-coding` fallback now retries bounded coding requests on `remote-free` when `qwen/qwen3-coder:free` rate-limits; live delegation returned `MODEL_OK` with `fallback.applied = true` |
| 2026-03-13 | continue-cli + home-manager activation corrective pass | validated_live | removed invalid disabled `home.file` stubs for legacy COSMIC units, fixed `nix/pkgs/continue-cli.nix` to use a valid `sha256` fetch source, and revalidated `home-manager switch` plus full quick-deploy system/home phases |
| 2026-03-13 | retrieval QA acceptance pass | validated_local | `aq-qa` now reuses `aq-report` JSON to assert recent retrieval posture, retrieval breadth metadata, and memory-recall share directly in Phase 1 instead of leaving retrieval acceptance purely report-visible |
| 2026-03-13 | remote tool-call finalization corrective pass | validated_live | `remote-tool-calling` now forbids tool-call-only output in its contract and performs a bounded post-tool finalization pass; live delegation returned a final artifact with `finalization.applied=true` and no remaining failure classes |
| 2026-03-13 | ai-gap-auto-remediate writable-state fix | validated_live | moved gap-remediation logging off the hardened service’s read-only `${HOME}` path and into the declarative optimizer state directory, then revalidated full quick-deploy with `aq-qa 0` back to `33 pass, 0 fail` |
| 2026-03-13 | delegated lesson reference runtime pass | validated_live | active promoted lessons are now surfaced as compact `active_lesson_refs` on delegated coordinator responses, and a live `remote-free` smoke returned the current promoted lesson key on `/control/ai-coordinator/delegate` |
| 2026-03-13 | remote profile utilization reporting pass | validated_local | `aq-report` now summarizes delegated remote profile usage from live tool-audit metadata and `nixos-quick-deploy.sh` surfaces the top recent remote lane, so Track H now has explicit remote-profile utilization visibility instead of only routing/failure side signals |
| 2026-03-13 | delegated research bootstrap for next tracks | validated_live | exercised `/control/ai-coordinator/delegate` on `remote-free` for bounded BitNet/EvoSkill/coding-agent synthesis so next planning slices use the live remote lane instead of only local reasoning |
| 2026-03-13 | continue/editor phase-0 observability pass | validated_live | added explicit `aq-qa 0` probes for `cn --help`, generated Continue config correctness, Continue extension presence, and a `continue-local` switchboard smoke so editor/runtime failures become first-class QA signals |
| 2026-03-13 | delegated free-model lane tuning pass | validated_live | reviewed a bounded `remote-free` comparison task, verified current OpenRouter free model availability, removed the gitignored host-local alias shadow so tracked defaults win, and activated planner/review aliases to `arcee-ai/trinity-large-preview:free` and `nvidia/nemotron-3-super-120b-a12b:free` after live smokes showed StepFun returned reasoning-only output and several other candidates failed under current provider/privacy constraints |
| 2026-03-13 | repo-backed QA capability corrective pass | validated_live | hardened `aq-qa` so the service-backed `/qa/check` path resolves Continue CLI outside interactive shells and retries port probes briefly after restarts; post-flight quick-deploy capability verification now passes again with `33` phase-0 checks green |
| 2026-03-13 | continue/editor reporting visibility pass | validated_local | `aq-report` now reuses the `0.5.*` Continue/editor phase-0 checks and exposes one derived health block in JSON plus text, and `nixos-quick-deploy.sh` now surfaces that status in its completion summary |
| 2026-03-13 | bounded web research lane implementation pass | validated_live | added a declarative-limits-backed `/research/web/fetch` coordinator endpoint plus tooling-manifest, SDK, and RPC exposure; unit validation confirms robots-aware blocking, same-host pacing, and bounded extraction behavior, and live smokes confirmed successful HTTPS extraction plus redirect-to-HTTP policy enforcement |
| 2026-03-13 | BitNet feasibility probe scaffolding | validated_local | added a repo-native `aq-bitnet-feasibility` probe plus targeted test so this host now has measured prerequisites, supported-model heuristics, and bounded next actions before any runtime role is attempted |
| 2026-03-13 | delegated prompt-failure feedback loop | validated_live | OpenRouter/coordinator delegation now records prompt-contract failures plus salvageable commands/paths/excerpts, live provider-side `400` rejection was captured in `/control/ai-coordinator/delegate`, `aq-report` surfaces the recurring failure class, and PRSI can queue prompt-tightening actions instead of repeating the same waste |
| 2026-03-13 | runtime registry retention and stale-smoke cleanup | validated_live | ai-coordinator now prunes transient smoke/test runtime registrations on load with retention policy; live registry collapsed from 56 entries with 54 smoke artifacts to 6 real lanes after status reload |
| 2026-03-13 | delegated envelope tightening pass | validated_live | ai-coordinator now emits explicit sub-agent/evidence/anti-goal contracts for remote delegation; live `remote-free` smoke returned structured `result/evidence` output instead of an unconstrained generic reply |
| 2026-03-13 | deploy summary delegated-failure visibility | validated_local | `nixos-quick-deploy.sh` now surfaces delegated prompt-failure counts/class/profile in the AI stack report summary so remote prompt-contract drift is visible during normal deploy/preflight loops |
| 2026-03-13 | remote + local tool-calling lane wiring | validated_live | added first-class `remote-tool-calling` and preparatory `local-tool-calling` profiles across switchboard and ai-coordinator, activated them live, confirmed remote lane returns provider tool calls through OpenRouter, and confirmed local lane accepts bounded `tools` payloads while staying explicitly degraded until local backends prove native tool support |
| 2026-03-13 | tool-call-only failure classification refinement | validated_live | refined delegated failure capture so remote tool-call-only completions are recorded as `tool_call_without_final_text` with salvaged tool arguments instead of opaque `empty_content`, then revalidated the same live OpenRouter tool-calling smoke after coordinator restart |
| 2026-03-13 | governed lesson schema + promotion action pass | validated_local | `aq-report` now emits governed lesson candidate fields including state, scope, evidence count, materialization class, validation link, and traceability targets, and can surface a machine-readable `promote_agent_lesson` action when candidates meet the threshold |
| 2026-03-13 | persistent lesson registry + review surface | validated_local | `aq-report` now syncs lesson candidates into a durable pending-review/promoted/avoided/rejected registry, `/control/ai-coordinator/lessons` exposes that state live, and the coordinator now accepts bounded lesson-review updates instead of leaving promotion purely report-derived |
| 2026-03-13 | accepted lesson runtime surfacing pass | validated_local | hints now prefer accepted active lessons from the durable registry, and `nixos-quick-deploy.sh` surfaces accepted active lessons before transient candidates so reviewer-approved lesson state affects live operator feedback instead of remaining dormant metadata |
| 2026-03-13 | workflow blueprint coverage + reviewer gate metadata | validated_live | added the missing repo-refactor, deploy-safe, continue/editor rescue, and remote-reasoning blueprints, workflow runs now persist reviewer-gate snapshots so accepted/rejected review state becomes part of session telemetry and report summaries, and a live `continue-editor-rescue` smoke persisted an accepted reviewer gate with the expected blueprint title |
| 2026-03-13 | repo-backed workflow blueprint activation fix | validated_live | switched `WORKFLOW_BLUEPRINTS_FILE` from the baked store JSON to the mutable repo path so quick-deploy and repo-backed service restarts can activate blueprint edits live instead of serving stale declarative copies, then live-verified the running coordinator exported the repo path and served the expanded blueprint catalog |
| 2026-03-13 | workflow review-contract smoke | validated_local | added a dedicated end-to-end smoke for `/workflow/plan`, `/hints`, `/workflow/run/start`, `/review/acceptance`, and persisted `/workflow/run/{session_id}` retrieval so Track B now has one repo-native contract check that exercises the reviewer-gated run path directly |
| 2026-03-13 | retrieval acceptance checks in aq-qa | validated_local | extended `aq-qa` to reuse `aq-report` JSON for retrieval posture acceptance, so recent retrieval traffic now has an explicit QA assertion for `rag_posture`, retrieval breadth metadata, and memory-recall share instead of relying only on human-readable report output |
| 2026-03-13 | remote tool-call finalization pass | validated_live | tightened the `remote-tool-calling` delegation contract so tool-call-only output is explicitly insufficient, added a bounded post-tool finalization pass in the coordinator, and live-validated that `/control/ai-coordinator/delegate` now converts a tool-call-only reply into a final artifact without claiming tool execution |
| 2026-03-13 | delegated artifact recovery salvage pass | validated_live | `/control/ai-coordinator/delegate` now returns bounded `artifact_recovery` output for tool-call-only, reasoning-only, and partial-text delegated failures, preserving useful tool arguments and reasoning excerpts so failed remote calls still yield actionable local summaries |
| 2026-03-13 | BitNet declarative sidecar scaffold pass | validated_local | added a disabled-by-default `mySystem.aiStack.bitnet` and `mySystem.ports.bitnet` scaffold plus shared endpoint wiring so benchmark-only BitNet experiments now have a tracked host-local config surface without touching switchboard or replacing llama.cpp |
| 2026-03-13 | BitNet benchmark harness + baseline comparison pass | validated_local | added a repo-native `aq-bitnet-benchmark` path with pinned Python 3.12/devShell/toolchain/runtime-lib fixes plus direct local-llama baseline comparison via `aq-bitnet-compare`; host now builds BitNet and materializes a dummy GGUF, while direct BitNet benchmark execution still ends in `SIGSEGV` and remains a measured blocker rather than an assumed viable runtime |
| 2026-03-13 | shared skill registry sync bridge | validated_live | added a repo-native `aq-sync-shared-skills.py` path that imports local `.agent/skills` entries into AIDB and promotes them to approved visibility, added cache-busting drift reporting in `aq-report`, and live-verified `23/23` approved shared skills |
| 2026-03-13 | orchestrator boundary activation pass | validated_live | workflow runs now persist explicit `orchestration` policy for the human-prompted/top-level agent, delegated contracts forbid nested sub-agent fan-out, and a live `/workflow/run/start` smoke plus persisted session check confirmed `requested_by=continue`, `requester_role=orchestrator`, and `delegate_via_coordinator_only=true` |
| 2026-03-13 | governed external skill import bootstrap | validated_live | added a pinned external skill-source manifest, locked `agentskill-sh/learn` by commit, imported it through the same AIDB approval path, and live-verified `24/24` expected approved shared skills in `aq-report` |
| 2026-03-13 | coordinator shared-skill visibility surface | validated_live | added `/control/ai-coordinator/skills`, exposed shared skill summary in coordinator status, wired SDK/RPC/tooling-manifest support, and live-verified the coordinator returns the approved 24-skill catalog including `learn` |
| 2026-03-13 | curated research workflow layer | validated_live | added a manifest-backed `/research/workflows/curated-fetch` layer with SDK/RPC/tooling-manifest exposure, live-validated the first approved source pack, and classified empty-extract/bot-gated pages into explicit fallback signals instead of treating them as successful scraping |
| 2026-03-13 | browser-assisted research fallback lane | validated_live | added a bounded `/research/web/browser-fetch` lane with declarative runtime controls and live-validated rendered extraction against a real Calflora page; Chromium now runs inside the hardened service with a temporary profile and `--no-sandbox` because the systemd namespace sandbox already provides the outer containment |
| 2026-03-13 | california-native source pack bootstrap | validated_live | extended the curated research manifest with a `native-plants-california` pack centered on Calflora so California-native lookup is now a first-class approved workflow input instead of an ad hoc URL |
| 2026-03-13 | source-level fetch policy and browser fallback | validated_live | curated workflows now support per-source fetch policy plus browser fallback after empty extracts or bot-gate detection; live `native-plants-us` validation showed USDA escalated to browser automatically while the already-good Wildflower path stayed on the plain HTTP lane |
| 2026-03-13 | continue-local dense-context trimming fix | validated_live | fixed switchboard input estimation so dense no-whitespace prompts no longer evade `continue-local` trimming, added single-message truncation when dropping old turns is insufficient, and live validation confirmed the original 24k-character reproduction now returns `200` with `X-AI-Input-Trimmed=1` instead of `502 upstream_transport_error` |
| 2026-03-13 | continue/editor oversized-input QA coverage | validated_local | added a new `aq-qa 0.5.5` check for `continue-local` dense oversized prompt trimming, increased `aq-report` timeout so the heavier Continue/editor phase-0 batch still completes, and revalidated `aq-report` plus the five-check Continue/editor health block |
| 2026-03-13 | delegation caller identity and handoff telemetry | validated_live | delegated runtime responses now return normalized `orchestration` metadata, delegated failure telemetry records `requesting_agent`, `requester_role`, and `handoff_requested`, and `aq-report` now summarizes requester-role plus coordinator-handoff frequency for delegated remote traffic |
| 2026-03-13 | direct query caller identity propagation | validated_live | `/query` now normalizes caller identity at request entry, carries orchestration metadata into query responses and compact metadata blocks, and propagates requester-role fields into internal autorun audit rows so editor/human query traffic is not invisible until remote delegation happens |
| 2026-03-13 | continue editor path smoke + aq-hints restore | validated_live | restored the generated Continue `aq-hints` HTTP context provider, added a bounded `prompt -> hints -> workflow plan -> query -> feedback` Continue-facing smoke, and promoted that smoke into `aq-qa 0.5.6` so editor-path regressions become deploy-visible instead of anecdotal |
| 2026-03-13 | workflow reviewer acceptance telemetry | validated_local | `aq-report` now summarizes workflow requester-role mix, accepted/rejected review state by requester role, top reviewers, and accepted/rejected blueprints so reviewer-gated workflow health is measurable without reading raw session JSON |
| 2026-03-13 | remote profile trend and route latency reporting | validated_local | `aq-report` now materializes delegated remote-profile utilization as comparable 1h/24h/7d windows and adds a route_search latency decomposition block by backend, fallback, and status class so Track H has trend depth instead of a single recent summary |
| 2026-03-13 | deploy summary remote trend visibility | validated_local | `nixos-quick-deploy.sh` now surfaces 24h/7d remote-profile trend snapshots plus route_search p95/top-class latency context so Track H’s new report sections are visible in normal deploy loops |
| 2026-03-13 | retrieval breadth history and deploy summary | validated_local | `aq-report` now materializes route_search retrieval-breadth as 1h/24h/7d windows and `nixos-quick-deploy.sh` surfaces the 24h/7d breadth trend so Track H no longer depends on a recent-only breadth snapshot |
| 2026-03-13 | routing history and deploy summary | validated_local | `aq-report` now materializes routing history as 1h/24h/7d windows from route_search backend audit data and `nixos-quick-deploy.sh` surfaces the same routing trend in deploy summaries |

## High-Priority Tracks

### Required Foundation — Declarative Agent CLI and IDE Surface

Track Status: `in_progress`
Last Updated: `2026-03-13`
Current Slice: `Continue CLI derivation, Home Manager activation, repo-backed QA verification, report visibility, bounded web research, local shared skill sync, the first governed agentskill.sh import, coordinator shared-skill visibility, the generic curated research workflow layer, the browser-assisted fallback lane, the California-native source pack, and source-level fetch policy are live; the next gap is expanding approved source packs further`
Next Validation:
- `nix-build` for each packaged agent CLI
- `scripts/testing/verify-flake-first-roadmap-completion.sh`
- per-surface `--help` smoke where available
- `scripts/ai/aq-report --since=7d --format=json | jq '.continue_editor'`
Open Risks / Blockers:
- Codex/Qwen/Gemini/Claude CLI delivery is still inconsistent across declarative, external, and npm-global paths
- `pi` remains scaffolded, not validated as a real declarative package
- Home Manager is no longer blocked on Continue CLI, but future CLI package additions still need isolated `outPath`/activation validation before they are treated as safe for unattended deploys
- Continue/editor health now reaches `aq-report` and deploy summaries, and both generic curated workflows plus browser-assisted fallback are live, but broader approved source-pack coverage still needs expansion for databases such as California-native plant sources

Goal:
- make flagship agent CLIs, IDE companions, and remote-provider entrypoints declarative where possible, and explicitly scaffolded where upstream packaging still blocks full declarative rollout

Tasks:
1. Build and validate declarative packaging for every installable flagship CLI surface:
   - Continue CLI
   - Codex CLI
   - Qwen CLI
   - Gemini CLI
   - pi agent
   - any additional stable agent CLIs that can be packaged cleanly
2. Keep native/external-only surfaces explicitly classed instead of pretending they are declarative:
   - Claude native CLI/binary if upstream packaging remains external
   - any upstream agent with installer-only distribution
3. Maintain one support matrix for:
   - declarative package
   - external binary with harness integration
   - IDE companion/extension
   - remote-provider profile only
   - scaffold-only / blocked
4. Ensure every supported surface points at the local harness layer first:
   - switchboard/OpenAI-compatible proxy
   - hybrid-coordinator
   - local MCP config
5. Add validation so a broken declarative package never silently ships again.
6. Add a shared third-party skill import surface for supported SKILL.md ecosystems:
   - first target `agentskill.sh`
   - discovery via harness/AIDB, not per-agent ad hoc cloning
   - explicit approval state before install/sync

Validation:
- targeted `nix-build` or `nix eval` checks for each packaged CLI
- `bash scripts/testing/verify-flake-first-roadmap-completion.sh`
- per-surface command smoke where available:
  - `cn --help`
  - `codex --help`
  - `qwen --help`
  - `gemini --help`
  - `pi --help`
- support-matrix doc and runtime validation output remain aligned

Acceptance:
- every flagship agent surface is either:
  - declaratively installable and validated, or
  - explicitly marked as external/scaffolded with harness wiring and deployment guidance ready
- no agent surface is left in an ambiguous partially integrated state

### Track A — Continue and Editor-Agent Runtime Stabilization

Track Status: `in_progress`
Last Updated: `2026-03-13`
Current Slice: `continue/editor runtime now has reporting visibility, restored generated aq-hints provider wiring, a bounded Continue-facing prompt -> hints -> workflow -> query -> feedback smoke in Phase 0, bounded web research, generic curated workflows, browser-assisted fallback, a regenerated Continue config that matches the local llama.cpp context window, and a live switchboard fix for dense oversized prompts that used to bypass trimming and fail as 502 transport errors; the next gap is broader real agent/planning-mode acceptance inside the extension, not missing harness wiring`
Next Validation:
- `scripts/ai/aq-qa 0 --json | jq '.tests[] | select(.id | startswith("0.5."))'`
- `scripts/testing/smoke-continue-editor-flow.sh`
- `python3 scripts/testing/test-web-research-lane.py`
- `scripts/testing/test-switchboard-continue-context-window.sh`
- `python3 scripts/ai/aq-report --format json | jq '.continue_editor'`
- live `POST /research/web/fetch` smoke after deploy
Open Risks / Blockers:
- some approved public sources still need selector tuning or source substitution even though the browser-assisted fallback lane is now available
- CLI/package coverage is still mixed across agent surfaces
- Continue agent/planning mode still needs explicit live confirmation inside the extension after the transport-side trimming fix, even though the stale 4k generated config, missing aq-hints provider wiring, and dense-prompt switchboard failure are now fixed and covered by deploy-time smoke

Goal:
- make Continue/editor-driven agent flows a validated and observable first-class path

Tasks:
1. Add a dedicated continue/editor runtime diagnosis blueprint to hybrid-coordinator workflow planning.
2. Add continue/editor-specific health probes to `aq-qa` and deploy post-flight.
3. Audit current Continue config generation and MCP bridge assumptions for stale endpoint/model settings.
4. Surface continue/editor failure reasons separately in `aq-report` and deploy summary.
5. Add one bounded smoke script for prompt -> hints -> workflow plan -> query -> feedback via editor path.
6. Add a Continue-visible web research task lane for local-model workflows that need fetch -> extract -> organize -> summarize behavior.
7. Keep web research bounded and polite:
   - obey robots and site terms where applicable
   - enforce concurrency, rate, timeout, and retry-with-backoff limits
   - prefer targeted fetches over broad crawling
   - keep raw fetch/tooling separate from model summarization
8. Add one generic curated-workflow layer for bounded public-data tasks, then validate it with one real example such as native plant lookup for the user’s area using an approved source pack and explicit request limits rather than unconstrained site crawling.

Validation:
- `scripts/ai/aq-qa 0 --json`
- `scripts/testing/smoke-cross-client-compat.sh`
- `scripts/testing/check-runtime-plan-catalog.sh`
- `curl -sS http://127.0.0.1:8003/workflow/plan ...`
- `journalctl -u ai-hybrid-coordinator.service --since '15 minutes ago' --no-pager`
- `python3 scripts/testing/test-web-research-lane.py`
- live `curl -sS ... /research/web/fetch`

Acceptance:
- Continue/editor failures appear as explicit, categorized runtime signals
- one stable smoke path is green after deploy
- polite web research is validated as a bounded capability rather than an open-ended scraper
- if upstream/editor limits remain, diagnostics, smoke coverage, and harness handoff points still remain deploy-ready

### Track B — Hybrid-Coordinator Harness Completion

Track Status: `in_progress`
Last Updated: `2026-03-13`
Current Slice: `required runtime blueprints now cover repo refactor, deploy-safe ops, continue/editor rescue, and remote reasoning escalation, workflow sessions now persist reviewer-gate snapshots, live validation confirmed the coordinator reads blueprint definitions from the repo-backed path, and a dedicated repo-native smoke now verifies plan, hints, run start, review acceptance, and persisted run retrieval; the next gap is widening orchestration coverage across additional blueprint families and query classes`
Next Validation:
- `scripts/testing/check-runtime-plan-catalog.sh`
- `scripts/testing/smoke-workflow-review-contract.sh`
- live `/workflow/plan`, `/query`, `/hints` contract checks
- `python3 scripts/testing/test-workflow-blueprints.py`
- `python3 scripts/testing/test-workflow-review-gate.py`
Open Risks / Blockers:
- some newer agent surfaces were added before being fully normalized to the shared runtime contract

Goal:
- finish the separation between scaffolding and runtime harness behavior

Tasks:
1. Define an explicit runtime blueprint registry for common tasks:
   - debug/fix
   - repo refactor
   - deploy/rollback-safe ops
   - continue/editor rescue
   - remote-reasoning escalation
2. Ensure `/workflow/plan`, `/workflow/run/start`, `/query`, `/hints`, and `/feedback` all consume the same intent-contract vocabulary.
3. Add clearer reviewer-gate state to workflow execution metadata.
4. Distinguish construction-time agent configuration from runtime orchestration in docs and runtime reporting.
5. Add one end-to-end orchestration smoke that verifies:
   - plan generation
   - task run start
   - hint retrieval
   - validation evidence capture
6. Add a shared skill-registry abstraction in AIDB/harness:
   - searchable skill metadata in AIDB
   - coordinator visibility into approved installed skills
   - one sync/export path for agent skill directories

Validation:
- `scripts/testing/check-runtime-plan-catalog.sh`
- `scripts/testing/smoke-harness-sdk-packaging.sh`
- `scripts/ai/aq-hints "fix service restart regression" --format=json --agent=codex`
- `curl -sS -H "X-API-Key: $API_KEY" -X POST http://127.0.0.1:8003/workflow/plan ...`

Acceptance:
- plan/run/hints/report surfaces use one shared execution contract
- runtime orchestration is measurable separately from config scaffolding

### Track C — Retrieval, Embedded Memory, and RAG Utilization

Track Status: `in_progress`
Last Updated: `2026-03-13`
Current Slice: `retrieval breadth, continuation memory recall, report visibility, and a report-backed aq-qa acceptance check are live; the next gap is tightening reliability/remediation loops around recent route_search pressure rather than visibility alone`
Next Validation:
- `scripts/ai/aq-report --format text`
- `scripts/ai/aq-report --format json | jq '.rag_posture, .route_retrieval_breadth'`
- `scripts/ai/aq-qa 1 --json | jq '.tests[] | select(.id == "1.5.3")'`
- `scripts/ai/aq-qa 0 --json`
Open Risks / Blockers:
- `route_search` is still the main active recent reliability issue
- memory recall quality is improving, but miss-rate remediation is not complete

Goal:
- make retrieval selection intentional, cheap, and visible

Tasks:
1. Narrow route-search collection breadth by query class and continuation context.
2. Add retrieval-breadth reporting and deploy summary visibility.
3. Increase memory recall usage for continuation and long-horizon repo tasks.
4. Add explicit “memory weak vs memory unused” diagnosis in reports/hints.
5. Add prewarm candidates from actual retrieval profiles, not generic seeds.
6. Add retrieval-profile acceptance checks to the QA harness.

Validation:
- `scripts/ai/aq-report --format text`
- `scripts/ai/aq-report --format json | jq '.rag_posture, .route_retrieval_breadth'`
- `scripts/ai/aq-rag-prewarm`
- `scripts/ai/aq-qa 0 --json`
- `journalctl -u ai-hybrid-coordinator.service --since '20 minutes ago' --no-pager`

Acceptance:
- `route_search` recent p95 decreases materially
- retrieval breadth is visible and bounded
- memory recall share is healthy for continuation-class queries

### Track D — OpenRouter Agent API and Remote Delegation Utilization

Track Status: `in_progress`
Last Updated: `2026-03-13`
Current Slice: `all remote delegation lanes now use profile-specific compact completion rules, remote-tool-calling keeps the bounded post-tool finalization pass, and remote-reasoning now has a bounded reasoning-finalization pass for reasoning-only empty replies; the next gap is measuring whether the leaner envelopes materially reduce repeated failure classes and prompt footprint over time`
Next Validation:
- targeted remote tool-calling smokes with `tools` and `tool_choice`
- live finalization smoke where `/control/ai-coordinator/delegate` returns `finalization.applied=true` and `failure_classes=[]`
- targeted local tool-calling prep smokes with bounded fallback expectations
- explicit alias smokes for `arcee-ai/trinity-large-preview:free`, `qwen/qwen3-coder:free`, and `nvidia/nemotron-3-super-120b-a12b:free`
- `scripts/ai/aq-report --format json | jq '.provider_fallback_recovery, .delegated_prompt_failures, .routing'`
- bounded delegated research/review calls recorded through `/control/ai-coordinator/delegate`
- live `artifact_recovery` checks for tool-call-only and reasoning-heavy delegated replies
Open Risks / Blockers:
- the free remote tool-calling alias can still emit raw `tool_calls` first, so the coordinator-side finalization pass remains necessary until the provider lane itself consistently returns usable native final text
- recovery artifacts reduce wasted retries, but they are still coordinator-side fallbacks and must not be mistaken for provider-fulfilled contracts
- `qwen/qwen3-coder:free` remains the strongest coding lane and can still hit provider-side `429`, so observability should keep tracking fallback frequency and latency impact
- some high-ranking free models are not safe defaults here because they either fail under current provider/privacy constraints or return reasoning-only output without a final answer
- delegated prompt-contract failures are now recorded, but the highest-value next step is to feed repeated classes back into actual prompt template revisions and not just reporting
- the tighter envelope improves shape control, but prompt token footprint should still be tuned so small delegated tasks do not overpay for boilerplate
- the new compact lane rules tighten profile fit, but they still need time-window reporting to prove they lowered repeated delegated failure classes instead of only changing prompt text
- remote-reasoning can still depend on the coordinator-side finalization pass when the provider emits reasoning without final text, so that behavior must stay visible as remediation rather than true provider compliance

Goal:
- fully exploit OpenRouter as the remote tool-calling and provider-routing layer behind the local harness

Tasks:
1. Add explicit remote capability profiles for:
   - remote-free
   - remote-coding
   - remote-reasoning
   - remote-tool-calling
2. Add an ai-coordinator control surface that:
   - exposes available runtime lanes and readiness
   - selects a remote lane deliberately instead of relying on ad hoc headers
   - delegates bounded tasks through switchboard/OpenRouter with tool-calling payload support
3. Add Responses API compatibility planning for tool-calling and multi-step workflows.
4. Add provider-routing policy templates:
   - cheapest acceptable
   - lowest latency acceptable
   - tool-calling strict
   - coding high-throughput
5. Evaluate Auto Exacto for tool-using remote calls routed through switchboard.
6. Add report visibility for remote profile choice, fallback rate, and provider status mix.
7. Add validation for remote tool-calling parameter compatibility and fallback behavior.
8. Prefer stable OpenAI-compatible chat/tool-calling transport first; keep Responses API support classified as beta/scaffold until compatibility is proven in the harness.
9. Ensure remote delegation can consume the same approved skill catalog as local agents:
   - remote agents see harness-approved skill metadata
   - remote agents do not self-install unapproved third-party skills
10. Start using the remote lanes for bounded sub-agent work instead of keeping them as smoke-only paths:
   - `remote-free` for research synthesis and plan expansion
   - `remote-coding` for patch sketching and implementation drafts
   - `remote-reasoning` for architecture/review passes
   - local reviewer gate remains mandatory before code adoption or commit
11. Align coordinator task envelopes with coding-agent best practices:
   - small discrete task contracts
   - explicit expected artifact/evidence fields
   - resumable slices with reviewer acceptance/rejection
12. Add explicit local tool-calling prep surfaces so local agents can target tool-capable local backends as they become viable:
   - `local-tool-calling` profile exposed in switchboard and ai-coordinator
   - preparatory lane passes OpenAI-compatible `tools` and `tool_choice` payloads through to local backends
   - readiness remains degraded until current local runtimes prove tool support
   - tool use bounded by harness-approved capabilities only

Validation:
- `curl -sS ... /workflow/plan`
- `curl -sS ... /query`
- `curl -sS ... /control/ai-coordinator/status`
- `curl -sS ... /control/ai-coordinator/delegate`
- `scripts/ai/aq-report --format json | jq '.provider_fallback_recovery, .routing'`
- targeted switchboard smoke requests with profile headers

Acceptance:
- remote calls are profile-driven, not ad hoc
- provider fallback is visible and classed separately from local failures
- tool-calling capable remote paths are explicit and tested
- if full upstream agent orchestration is still incomplete, the local switchboard profiles, validation probes, and runtime contracts still remain deploy-ready

### Track E — Agent Lesson Promotion and EvoSkill-Inspired Skill Evolution

Track Status: `in_progress`
Last Updated: `2026-03-13`
Current Slice: `accepted lessons now feed back into the hint engine, deploy summary, and delegated response metadata from the durable registry; the next gap is broader direct routing/reference materialization beyond those first runtime consumers`
Next Validation:
- `scripts/ai/aq-report --format json | jq '.agent_lessons'`
- `python3 scripts/testing/test-agent-lesson-schema.py`
- `python3 scripts/testing/test-agent-lesson-registry.py`
- `python3 scripts/testing/test-hints-agent-lessons.py`
- `curl -sS ... /control/ai-coordinator/lessons`
- live `/control/ai-coordinator/delegate` smoke with `active_lesson_refs`
- hint/report traceability checks once schema lands
Open Risks / Blockers:
- accepted lessons now affect hints, deploy/operator summaries, and delegated response metadata, but direct routing/reference materialization remains incomplete beyond those first consumers

Goal:
- reuse the existing hint/report/feedback pipeline as a controlled lesson-promotion loop

Tasks:
1. Define an `agent lesson` schema with:
   - source agent
   - scope
   - evidence count
   - promote/avoid/reject state
   - validation link
2. Add a promotion gate from:
   - hint feedback
   - workflow reviewer results
   - task success/failure telemetry
3. Add skill-candidate materialization rules:
   - hint only
   - quick reference
   - skill draft
   - reject/noise
4. Add explicit “promoted lesson -> hint/routing/reference” traceability in reports.
5. Do not auto-promote raw chat content; require evidence and validation.
6. Separate internally promoted lessons from imported third-party skills:
   - imported skills require source metadata, approval state, and risk notes
   - first external source to normalize: `agentskill.sh`
7. Mirror the EvoSkill-style loop without relaxing governance:
   - candidate skill generation
   - bounded evaluation on held-out tasks
   - reviewer acceptance before promotion
   - retire or demote lessons that stop producing measurable value
8. Keep lesson promotion grounded in explicit task families:
   - planning/orchestration
   - implementation
   - review
   - retrieval/research
   - operational remediation

Validation:
- `scripts/ai/aq-report --format json | jq '.agent_lessons'`
- `scripts/ai/aq-hints ...`
- `scripts/testing/verify-flake-first-roadmap-completion.sh`

Acceptance:
- lesson promotion is one shared pipeline
- no separate opaque “self-training” subsystem is introduced
- if automated promotion remains partially blocked, the lesson schema, reviewer gate, and report visibility still remain deploy-ready

### Track F — BitNet Feasibility and Optional Runtime Integration

Track Status: `in_progress`
Last Updated: `2026-03-13`
Current Slice: `host-fit feasibility now includes a real benchmark shell/build path, direct dummy-GGUF materialization, and a local llama.cpp baseline comparison probe; the remaining gap is eliminating the current direct BitNet benchmark `SIGSEGV` before any sidecar runtime proof`
Next Validation:
- `python3 scripts/ai/aq-bitnet-feasibility.py --format json`
- `python3 scripts/testing/test-bitnet-feasibility.py`
- `python3 scripts/ai/aq-bitnet-compare.py`
- `python3 scripts/testing/test-bitnet-benchmark.py`
- `python3 scripts/testing/test-bitnet-compare.py`
- nix parse for the new `mySystem.aiStack.bitnet` and `mySystem.ports.bitnet` surfaces
Open Risks / Blockers:
- direct BitNet benchmark execution against the locally produced dummy GGUF currently dies with `SIGSEGV` inside upstream `llama-bench`
- must not destabilize existing llama.cpp service health
- declarative scaffold exists, but no executable bitnet.cpp sidecar service has been introduced yet because runtime parity is not proven

Goal:
- determine where BitNet can improve local inference economics without destabilizing the stack

Tasks:
1. Add a feasibility matrix:
   - supported hardware
   - supported BitNet models
   - performance delta vs llama.cpp on this host class
   - packaging/runtime implications for NixOS
   - CPU-first viability and RAM footprint tradeoffs for bitnet.cpp specifically
2. Prototype a non-default BitNet runtime role:
   - isolated service
   - explicit port option
   - no replacement of llama.cpp until validated
   - prefer sidecar benchmarking before any switchboard integration
3. Add benchmark scripts for:
   - tokens/sec
   - latency
   - power/CPU efficiency if available
   - model-loading behavior
   - cold-start and warm-start comparisons against the current llama.cpp lane
4. Add hybrid-coordinator backend abstraction checks so BitNet can be selected as a local backend profile if it proves viable.
5. Keep rollout behind a feature flag until parity and health checks pass.
6. Treat BitNet as optional even if viable:
   - keep llama.cpp as baseline
   - document measured reasons for any host class where BitNet is not worth enabling

Validation:
- benchmark script outputs under `scripts/ai/`
- `python3 scripts/ai/aq-bitnet-compare.py`
- declarative service checks in Nix modules
- side-by-side `/query` latency and health comparisons
- `scripts/ai/aq-qa 0 --json`

Acceptance:
- BitNet is either:
  - proven viable and introduced as an optional runtime profile, or
  - explicitly documented as deferred with measured reasons
- in either case, the backend abstraction, feature flag, and benchmark harness remain deploy-ready

## Medium-Priority Tracks

### Track G — Coding-Agent Workflow Effectiveness

Track Status: `in_progress`
Last Updated: `2026-03-13`
Current Slice: `workflow runs now persist live orchestrator policy for top-level callers, delegated runtime responses surface normalized caller identity, delegated failure telemetry records requester-role and handoff metadata, aq-report now summarizes workflow requester-role mix, accepted/rejected review state by requester role, top reviewers, and accepted/rejected blueprints, and `/query` returns compact orchestration metadata while propagating requester-role fields into internal autorun audit rows; the next gap is wider query/editor acceptance and patch-review telemetry across more agent/task classes`
Next Validation:
- live `/query` responses return normalized orchestration metadata for human and editor callers
- internal autorun audit rows inherit requester-role metadata from the parent query request
- `python3 scripts/testing/test-workflow-review-gate.py`
- `python3 scripts/ai/aq-report --format json | jq '.intent_contract_compliance'`
Open Risks / Blockers:
- top-level orchestrator identity is now explicit in workflow state, delegated responses, direct query responses, and workflow review summaries, but editor-specific acceptance and patch-review telemetry still needs broader coverage across more task classes
- the policy forbids nested sub-agent fan-out and both delegated plus direct-query caller telemetry now exist, but wider patch-review and acceptance telemetry for more agent/task classes is still unfinished

Tasks:
1. tighten delegator/reviewer evidence contracts
2. add more explicit sub-agent role boundaries to runtime blueprints
3. add cross-agent patch-review telemetry
4. measure acceptance rate by agent/profile/task class

Validation:
- `aq-report` lesson and tooling sections
- workflow run evidence payloads
- `python3 scripts/testing/test-workflow-review-gate.py`
- `python3 scripts/ai/aq-report --format json | jq '.intent_contract_compliance'`

### Track H — Monitoring and Reporting Expansion

Track Status: `in_progress`
Last Updated: `2026-03-13`
Current Slice: `aq-report now exposes remote-profile, routing, and retrieval-breadth history as 1h/24h/7d windows, route latency decomposition is report-visible, and nixos-quick-deploy surfaces compact remote/routing/breadth trend lines; the next gap is extending the same multi-window treatment to Continue/editor health and broader operator-facing consumers`
Next Validation:
- `python3 scripts/ai/aq-report --format json | jq '.remote_profile_utilization'`
- `python3 scripts/ai/aq-report --format json | jq '.remote_profile_utilization_windows, .route_search_latency_decomposition'`
- `python3 scripts/ai/aq-report --format json | jq '.route_retrieval_breadth_windows'`
- `python3 scripts/ai/aq-report --format json | jq '.routing_windows'`
- `python3 scripts/testing/test-remote-profile-utilization.py`
- `python3 scripts/testing/test-retrieval-breadth-history.py`
- `python3 scripts/testing/test-routing-history.py`
- deploy summary output
Open Risks / Blockers:
- multi-window trend coverage now exists for remote profiles, routing, route latency, and retrieval breadth, but Continue/editor health still lacks the same operator-facing time-window treatment

Tasks:
1. broader 24h/7d monitoring views for continue/editor health
2. remote profile utilization summary parity across all operator-facing consumers
3. retrieval-breadth summary parity across all operator-facing consumers
4. routing summary parity across all operator-facing consumers

Validation:
- `scripts/ai/aq-report --format json`
- `python3 scripts/ai/aq-report --format json | jq '.remote_profile_utilization_windows, .route_search_latency_decomposition'`
- `python3 scripts/ai/aq-report --format json | jq '.route_retrieval_breadth_windows'`
- `python3 scripts/ai/aq-report --format json | jq '.routing_windows'`
- deploy summary output

### Track I — Operator and Prompt-Writing Guidance

Track Status: in_progress
Last Updated: 2026-03-13
Current Slice: `compact prompt-coaching hints now teach route selection across local, remote-free, remote-coding, remote-tool-calling, and Continue/editor rescue lanes; the next gap is adding the same compact guidance to more task classes without inflating default hint payloads`
Next Validation: `scripts/ai/aq-hints "route local vs remote coding lane" --format json` and live `/hints?q=continue+editor+rescue`
Open Risks / Blockers:
- route-selection guidance is now explicit in hints, but broader task-class quick references still need the same compact treatment
- keep new operator coaching below the default hint noise floor so runtime signals still dominate when they are more urgent

Tasks:
1. teach progressive-disclosure prompt shapes by task class
2. add route-selection guidance for local vs remote vs coding agents
3. add concise quick references for continue/editor troubleshooting
4. keep all coaching compact by default, debug-expansive on demand

Validation:
- `scripts/ai/aq-hints ...`
- live `/hints` and `/query` checks

## Batched Execution Queue

### Batch J — Continue and Editor Runtime
- continue/editor blueprint
- continue/editor smoke
- continue/editor report visibility
- continue/editor deploy summary notes

### Batch K — Route-Search Breadth and Latency
- bounded collection selection
- retrieval-breadth telemetry
- report/deploy summary integration
- active latency watch refinement

### Batch L — OpenRouter Agent API Utilization
- remote tool-calling profile lane
- provider policy templates
- Responses API compatibility plan
- fallback and parameter-support smoke coverage

### Batch M — Lesson Promotion and EvoSkill Loop
- formal lesson schema
- promotion gate
- skill-draft candidate flow
- report traceability

### Batch O — Shared Skill Registry and agentskill.sh
- AIDB skill metadata schema
- `agentskill.sh` importer and approval workflow
- sync/export into local agent skill directories
- remote-agent visibility through harness/coordinator

### Batch N — BitNet Feasibility
- benchmark harness
- optional Nix service role
- backend abstraction compatibility checks
- measured go/no-go output

## Deployment and Validation Cadence

Per batch:
1. implement 3-5 repo-only slices
2. validate locally:
   - `python3 -m py_compile ...`
   - `bash -n ...`
   - `bash scripts/testing/verify-flake-first-roadmap-completion.sh`
   - `scripts/governance/repo-structure-lint.sh --staged`
3. activate:
   - `./nixos-quick-deploy.sh --host nixos --profile ai-dev`
4. verify live:
   - `scripts/ai/aq-report --format text`
   - `scripts/ai/aq-qa 0 --json`
   - targeted `curl` or CLI smoke for the changed surface

## Immediate Next Batch Recommendation

Run next in this order:
1. Batch J — Continue and Editor Runtime
2. Batch K — Route-Search Breadth and Latency
3. Batch L — OpenRouter Agent API Utilization
4. Batch M — Lesson Promotion and EvoSkill Loop
5. Batch O — Shared Skill Registry and agentskill.sh
6. Batch N — BitNet Feasibility

Why:
- Continue/editor failures are directly user-facing.
- Route-search latency is the current active live issue.
- OpenRouter orchestration can only be used effectively once the local harness/runtime path is stable.
- Shared third-party skill ingestion needs to be centralized before local and remote agents diverge in capability.
- EvoSkill-style lesson promotion should extend the existing pipeline after those runtime paths are reliable.
- BitNet should be integrated from a measured feasibility track, not as an assumption.
