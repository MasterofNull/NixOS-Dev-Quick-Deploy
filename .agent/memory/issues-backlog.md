[RESOLVED 2026-06-06] aq-report/query-gaps-display — Section "7. Top Query Gaps" showed "No gaps data (Postgres unavailable or table empty)" even when DB had rows, because all rows were suppressed by `_is_curated_stale_gap()`. Root cause: the else branch couldn't distinguish "DB down" from "all filtered." Fix: track `_gaps_raw_count` before the filter pipeline; set `_gaps_all_suppressed = raw_count > 0 and not gaps`; show distinct message in both `format_text()` and `format_md()`. Added `gaps_all_suppressed` kwarg to both formatters (default False).
  Severity: low (display only — no data loss)
  Files: scripts/ai/aq-report ~lines 8100-8106, 6612, 5740

[RESOLVED 2026-06-06] mcp/agent-connectivity — Claude/shared MCP config retained stale external-fetching server entries (`npx`, `nix run github:*`) and a placeholder GitHub token, causing startup-time MCP socket/API failures and noisy model-agent connection errors.
  Severity: high → resolved
  Action: Replaced bootstrap defaults with local `hybrid-coordinator` bridge + `osint-tools`. HM activation now repairs legacy configs (backup + rewrite). Repaired live `~/.mcp/config.json` and Claude settings. Added IDE smoke coverage for unsafe MCP entries. Validation: IDE adapter smoke 19 PASS / 0 FAIL; aq-qa phase 0 87 PASS / 0 FAIL / 3 SKIP. Requires home-manager switch to deploy activation script persistently.
  Files: nix/home/base.nix ~line 1835; scripts/testing/smoke-ide-adapter-compat.sh ~line 150; ai-stack/continue/config.json

[RESOLVED 2026-06-06] local-coding — switchboard local-coding profile deployed. QA 132.1 PASS. Also active: embedded-assist pre-context injection, adaptive query (debug/coding/general), Nix code validation, local-coding routing for implementation archetypes, adaptive embedded-assist.
  Severity: low → resolved
  Files: nix/modules/services/switchboard.nix, scripts/ai/lib/dispatch.py, config/switchboard-profiles.yaml
[RESOLVED 2026-06-03] ci — L5/L6 cognitive intelligence regression test fails on any memory_broker.py change — pytest not in Nix Python env
  Severity: medium (blocks commits that touch memory_broker.py or intent_classifier.py)
  Action: Added require_tool=pytest to cognitive-intelligence-regressions check in validation-check-registry.json. Check now SKIPs (not FAILs) when pytest absent. Long-term: add pytest to Nix Python env package set.
  File: config/validation-check-registry.json (cognitive-intelligence-regressions check)
[DONE] aq-report/delegation — historical delegated prompt failures surfaced as active remediation — `delegated_prompt_failure_windows` showed 0 failures in 1h and 24h, but recommendations and structured actions still emitted active OpenRouter prompt-contract remediation from 7d historical debt.
  Severity: medium
  Action: Wired delegated failure windows into recommendations/actions; historical-only failures now produce passive context and suppress active salvage/action guidance unless failures recur in 24h.
  File: scripts/ai/aq-report ~line 3893; scripts/testing/test-delegated-prompt-failure-history.py

[DONE] planning — Phase 93 PRD under-read Pi observability video context — First pass relied on title/oEmbed and adjacent references after transcript fetch failed, missing the YouTube description's core details: Markdown vs HTML vs visual HTML same-prompt races, useful-token framing, Pi observability event stream/server/DB/UI, swimlane/single-agent/race views, and full tool/system-prompt/token/trace visibility.
  Severity: medium
  Action: Extracted YouTube `shortDescription`, re-ran available agent reviews with the corrected context, amended Phase 93 PRD and parity plans to add Pi-style observability parity gaps and controlled spec-variant race slices.
  File: .agents/plans/EFFECTIVENESS-CENTERED-SYSTEM-IMPROVEMENT-PRD.md; .agents/plans/TECHNICAL-ANALYSIS-PRD.md

[DONE] hints-engine — compatibility wrapper did not re-export underscored filter helpers — `scripts/testing/test-hints-runtime-batch.py` imports `hints_engine` and expects `_is_synthetic_gap` / `_is_curated_stale_gap`; the top-level wrapper used `import *`, which omits underscored names even though `knowledge.hints_engine` exposes the helpers explicitly.
  Severity: low
  Action: Added explicit `_is_synthetic_gap` and `_is_curated_stale_gap` re-exports in `ai-stack/mcp-servers/hybrid-coordinator/hints_engine.py`.
  File: ai-stack/mcp-servers/hybrid-coordinator/hints_engine.py ~line 1

[DONE] aq-report/downshift — continuation downshift recommendation reported stale historical candidates as "recent" — `aq-report` showed 0/14 "recent candidates" even though all candidate events were from 2026-05-24 through 2026-05-27 and no 24h candidate traffic existed. This misrouted operators toward tuning a live downshift gate instead of running a fresh smoke after deploy/rebuild.
  Severity: medium
  Action: Added 24h freshness fields (`candidate_calls_24h`, `downshifted_calls_24h`, `last_candidate_at`, `stale_candidate_window`) and updated recommendations/hints to distinguish stale history from active failures.
  File: scripts/ai/aq-report ~line 1697; ai-stack/mcp-servers/hybrid-coordinator/knowledge/hints_engine_impl.py ~line 2183

[PENDING-REBUILD] dashboard/health-spider — Dashboard AppArmor denials degraded operator visibility while health-spider and auto-remediate did not catch/fix it promptly — Root cause: health-spider only checked `/api/health` every 7200s and auto-remediate only parsed `aq-qa 0`; dashboard passive firewall/status polling also attempted `sudo` reads under AppArmor, creating denial noise.
  Severity: high
  Action: Added dashboard semantic probes to `aq-health-spider`, reduced interval to 900s, removed success attention spam, made auto-remediate run health-spider before aq-qa, disabled sudo for passive firewall reads by default, and added `/proc/@{pids}/stat r,` AppArmor rule. Run `sudo nixos-rebuild switch --flake .#hyperd-ai-dev` to activate service/AppArmor/dashboard code.
  File: scripts/ai/aq-health-spider ~line 77; scripts/automation/auto-remediate.sh ~line 16; dashboard/backend/api/routes/firewall.py ~line 54; nix/modules/services/mcp-servers.nix ~line 1737

[DONE] cli-contract — documented machine/query flags rejected by local CLIs — `aq-report --machine` and `aq-hints --query ...` were documented workflow forms but argparse rejected them, blocking machine-mode parity and copied quick-start commands. Added compatibility aliases.
  Severity: medium
  Action: Added `--machine` as JSON alias in `scripts/ai/aq-report` and `--query` alias in `scripts/ai/aq-hints`; validate with CLI smoke commands and Python compile.
  File: scripts/ai/aq-report ~line 200; scripts/ai/aq-hints ~line 165

[RESOLVED 2026-05-31] workspace-isolation — cleanup_workspace() requires force=True for active workspaces — `WorkspaceManager.cleanup_workspace()` returns False and logs "Cannot cleanup active workspace" unless `force=True` is passed. Default cleanup in integration tests silently fails.
  Severity: low (no data loss; worktrees accumulate in /tmp/aq-worktree-test until manually cleared)
  Action: Pass `force=True` in cleanup calls, or add auto-deactivate before cleanup. File: ai-stack/orchestration/workspace_isolation.py
  File: ai-stack/orchestration/workspace_isolation.py (cleanup_workspace method)

[RESOLVED 2026-06-07] cross-project-contamination — mcp-bridge-hybrid workflow tools (retrofit, primer, brownfield, project-init) ran with cwd=REPO_ROOT, so --target . resolved to the NixOS harness root instead of the calling agent's project directory. Gemini CLI working in a fresh MakerSpace repo called aqd workflows retrofit --target . and polluted: .claude/CLAUDE.md (template reset), .agents/plans/README.md, .agent/commands/, .agent/PROJECT-PRD.md, .agent/GLOBAL-RULES.md, .agent/workflows/*.json, session-primer-summary.json.
  Severity: high (corrupts harness scaffolding silently; cross-project data contamination)
  Root cause: _run_local(argv) defaults cwd=REPO_ROOT; relative targets resolve to harness root not client CWD
  Fix: _resolve_workflow_target() normalizes target_dir to absolute path; all four workflow handlers now pass cwd=abs_target to _run_local; REPO_ROOT overlap triggers strong warning in tool response
  Files: scripts/ai/mcp-bridge-hybrid.py (Phase 136)
  Pattern: External agents MUST pass target_dir as absolute path; never --target . from a remote client

[OPEN] hardware — ROCm not available on Renoir APU (gfx90c) — ACCELERATE PRD assumed ROCm availability. Renoir iGPU is not a supported ROCm target. `rocminfo` absent. llama-cpp runs Vulkan only. Baseline: 2.71 tok/s.
  Severity: info (hardware constraint, not a bug — requires discrete RDNA2+ GPU for ROCm)
  Action: Document in hardware-profiles.json; remove ROCm acceptance criterion from ACCELERATE PRD. No code fix possible without hardware upgrade.
  File: .agent/PROJECT-ACCELERATE-PRD.md

[RESOLVED 2026-06-02] workflow — aq-session-start (and 8 others) missing from Codex/agent shell PATH — aiHarnessCliWrappers in ai-stack.nix did not include aq-session-start, aq-resume, aq-insights, aq-commit-facts, aq-skill-suggest, aq-alerts, aq-approve, aq-reject, aq-integrity-scan.
  Action: Added all 9 wrappers to aiHarnessCliWrappers (Phase 100.1). Requires nixos-rebuild to activate.
  File: nix/modules/roles/ai-stack.nix ~line 439

[RESOLVED 2026-05-30] ai_coordinator_delegate P95=244s — ceiling is enforced at ai_coordinator.py:706 (_LOCAL_MAX_TOKENS_HARD_CEILING=180). P95=244s is hardware-bound: 180 tok × ~1.35 tok/s on Renoir APU. Not a code bug. Anti-loop guardrails (repeat_penalty=1.08, repeat_last_n=64) confirmed in dispatch.py:79-80. No fix needed.

[DONE] observability — aq-report framed healthy hardware-bound delegate latency as generic cache/connection/model tuning — `ai_coordinator_delegate` P95 around 244s matches the local delegated-response token ceiling on current hardware, but the slow-tool recommendation implied a software tuning defect.
  Severity: low
  Action: Added delegate-specific latency contextualization and regression coverage so healthy high-P95 delegate calls point to bounded prompts/max_tokens rather than cache or connection-pool work.
  File: scripts/ai/aq-report ~line 4395

[DONE] delegation — local-tool-calling was excluded from coordinator local slot-busy retry — recent delegate 500s traced to transient local backend unavailability around `local-tool-calling`; coordinator local HTTP retry logic covered default/continue-local/embedded-assist but not local-tool-calling, and raised before the local_slot_busy wrapper could inspect 503 responses.
  Severity: medium
  Action: Return local_slot_busy 503 responses to the bounded retry wrapper before `raise_for_status`, include `local-tool-calling` in retryable local profiles, and refresh stale delegate static regressions to the current extension/workflow paths.
  File: ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py ~line 1467

[DONE] deploy — quick deploy interactive model prompt blocked non-interactive automation — `./nixos-quick-deploy.sh` preflight passed but deployment stopped at `read -r new_chat_key` because Phase 1 model selection prompted on non-interactive stdin.
  Severity: medium
  Action: Added documented `--skip-model-selection` flag and `SKIP_MODEL_SELECTION=true` env support to keep current facts.nix model choices during automated deploys.
  File: nixos-quick-deploy.sh ~line 70

[RESOLVED 2026-06-03] role-enforcement — AGENT_TYPE_ELIGIBLE_ROLES never validated at dispatch — Phase 58A.5 implemented: ineligible role assignments are now clamped to the agent_type default in LocalAgentExecutor.execute_task(). Logs warning on clamp. 6/6 regression tests pass.
  Action: Added eligibility check after auto-assign in execute_task(); added test-agent-executor-role-eligibility.py; registered in validation-check-registry.json.
  File: ai-stack/local-agents/agent_executor.py ~line 356; scripts/testing/test-agent-executor-role-eligibility.py

[RESOLVED 2026-06-03] role-enforcement — no reviewer_id tracking, self-review prevention aspirational — Role-matrix.md §8 states "a reviewer may not review their own work" but no reviewer_id field exists in Task/TaskConfig; self-review cannot be enforced at runtime.
  Severity: low → resolved
  Action: Phase 104 — added reviewer_id: Optional[str] = None to Task dataclass; execute_task() logs WARNING when reviewer_id == assigned_agent. Advisory check (no block) — orchestrator is responsible for not assigning self-reviews. 6/6 regression tests pass.
  File: ai-stack/local-agents/agent_executor.py ~line 140
  Test: scripts/testing/test-agent-executor-reviewer-id.py

[RESOLVED 2026-06-06] role-enforcement — domain-role eligibility not validated at task dispatch — DOMAIN-ROLE-MATRIX.md defines which agents may fill which roles per domain, but no enforcement exists at dispatch. Cross-domain mis-routing (e.g., Gemini as security reviewer for its own security implementation) is doc-only blocked.
  Action: Phase 132 — added _DOMAIN_ROLE_RESTRICTIONS table + validate_role_eligibility() to core/domain_router.py. Enforcement injected into handle_ai_coordinator_delegate() after profile selection. Security domain: Gemini blocked as reviewer, redirected to local fallback. 8/8 unit tests pass.
  Files: core/domain_router.py, extensions/ai_coordinator_handlers.py, tests/test_domain_role_enforcement.py
  Severity: low (policy gap, not immediate production risk)
  Action: Long-term: pass domain_shell in TaskConfig and validate against DOMAIN-ROLE-MATRIX at dispatch. Immediate: document constraint in delegation prompts.
  File: .agent/DOMAIN-ROLE-MATRIX.md (new), ai-stack/mcp-servers/coordinator/agent_executor.py

[RESOLVED 2026-06-02] hardware — CPU thermal tier = critical persistent (Renoir APU Tctl 81°C) — MLFQ level-2 (batch task class) was permanently blocked because _determine_thermal_tier() used a hardcoded critical threshold of 80°C and Renoir APU Tctl sensor reads ~81°C at idle.
  Severity: medium → resolved
  Action: Phase 99.1 — raised critical threshold from 80→83°C, warn from 70→73°C. Added THERMAL_CRITICAL_C / THERMAL_WARN_C / THERMAL_SHUTDOWN_C env var overrides. Shutdown stays at 88°C (safety boundary). 6/6 regression tests pass.
  File: ai-stack/mcp-servers/hybrid-coordinator/inference_param_manager.py ~line 155
  Test: scripts/testing/test-ipm-thermal-thresholds.py

[RESOLVED 2026-06-03] coordinator — circuit breaker trips logged but not surfaced to operator attention queue — core/circuit_breaker.py and shared/circuit_breaker.py both logged a warning on _trip() but never pushed to the attention queue, making silent qdrant/postgres/llm outages invisible to operators until they checked logs manually.
  Severity: medium → resolved
  Action: Phase 101 — added attention_queue.push(auto_ok, high) in both _trip() implementations; added ATTENTION_QUEUE_DIR env var override in attention_queue.py (Nix store path safety); wired ATTENTION_QUEUE_DIR + scripts/ai/lib into coordinator PYTHONPATH in mcp-servers.nix. 6/6 regression tests pass. Requires nixos-rebuild switch.
  File: scripts/ai/lib/attention_queue.py ~line 41; ai-stack/mcp-servers/hybrid-coordinator/core/circuit_breaker.py ~line 104; ai-stack/mcp-servers/shared/circuit_breaker.py ~line 228; nix/modules/services/mcp-servers.nix ~line 1302
  Test: scripts/testing/test-attention-queue-env-override.py

[RESOLVED 2026-06-03] coordinator — qdrant_upsert_failed TypeError on skills-patterns indexing — continuous_learning.py _upsert() inner function used `return await self.qdrant.upsert(...)` but server.py passes the sync QdrantClient whose upsert() returns UpdateResult directly (not a coroutine). Caused `TypeError: object UpdateResult can't be used in 'await' expression` on every _index_patterns() call, silently dropping all Qdrant pattern indexing.
  Severity: medium (learning pipeline silently non-functional)
  Action: Removed spurious `await`; _upsert() now calls self.qdrant.upsert() directly. 2/2 regression tests pass.
  File: ai-stack/mcp-servers/hybrid-coordinator/extensions/continuous_learning.py ~line 1231
  Test: scripts/testing/test-continuous-learning-qdrant-upsert.py

[DONE] dashboard/app-armor — dashboard GPU metrics triggered a live AppArmor denial after rebuild — `lspci` could execute but could not open `/sys/bus/pci/devices/`, so the dashboard process still emitted kernel audit denials even after the passive firewall sudo fix was active.
  Severity: medium
  Action: Added explicit `/sys/bus/pci/devices/` and `/sys/bus/pci/devices/**` read coverage to the `command-center-dashboard-api` profile; restart/rebuild required for live activation.
  File: nix/modules/services/mcp-servers.nix ~line 2609

[OPEN] agentic-mind — cross-model workflow behavior is not standardized or gated — Claude follows the workflow more reliably than Gemini/remote/local lanes, while current parity checks mostly verify transport/header availability and fallback recovery can hide first-pass contract failures.
  Severity: high
  Action: Implement Phase 148 agent task envelope, workflow-adherence golden corpus, first-pass contract evaluator, model-profile freshness gate, and dashboard/aq-report interop scorecard.
  File: .agent/PROJECT-AGENTIC-MIND-STANDARDIZATION-PRD.md

[OPEN] desktop-input — post-build cursor/text input instability required system build revert — user reported erratic text input and cursor selection after the last activation. Current read-only process scan found no active ydotool/xdotool/wtype/kmonad/keyd/warpd/dotool/xte-style process; COSMIC logs show missing input/cursor config keys and invalid shortcut action parsing near session start; VSCodium Gemini Code Assist A2A server is active but not proven causal.
  Severity: high
  Action: Before any next rebuild, compare generations 677/678, inspect COSMIC input and shortcut declarations, capture focused journal slices around activation, and add a rollback-safe desktop-input validation checklist/probe.
  File: .agents/plans/phase-148-agentic-mind-research.md

[DONE] rebuild-watch — activation exposed auto-remediate PRSI CLI drift, tmpfiles unsafe transitions, and dashboard AppArmor `/tmp/` denial noise — Root causes: `auto-remediate.sh` called removed `prsi-orchestrator.py queue`; tmpfiles repaired `/var/lib/nixos-ai-stack` after processing child paths and kept `/var/log/nixos-ai-stack` user-owned while service-owned child logs live under it; dashboard AppArmor allowed `/tmp/*.db` but not `/tmp/` directory reads; health-spider counted already-covered AppArmor denials as unresolved.
  Severity: high
  Action: Repo fixes applied and user rebuild activated the previous Nix/AppArmor/service-copy changes. auto-remediate uses `prsi-orchestrator.py cycle`; tmpfiles parent repair is ordered before child paths and AI log parent is `root:ai-stack`; dashboard profile allows narrow `/tmp/ r,`; health-spider returns cleanly when apparmor-fix-agent reports all paths already covered.
  File: scripts/automation/auto-remediate.sh; scripts/ai/aq-health-spider; nix/modules/core/base.nix; nix/modules/services/mcp-servers.nix; scripts/testing/test-boot-stability-regressions.py

[DONE] collaboration-state — Gemini resumed Phase 148 with useful direct edits but wrote malformed RESUME.json — Root causes: duplicate JSON keys, missing comma in todo_snapshot, and completion claims not matched by validation evidence made `aq-resume`/JSON tooling fail during handoff review.
  Severity: medium
  Action: Repaired RESUME.json as valid JSON, validated Gemini's code diff, tightened multi-document YAML loaders, and added static regression coverage for aq-chat no-think and YAML loader contracts.
  File: .agent/collaboration/RESUME.json; scripts/testing/test-local-agent-config.py

[DONE] agentic-standardization — Phase 148 repo fixes needed activation — Root cause: switchboard/service code runs from the Nix store; repository edits to `ai-stack/switchboard/switchboard.py`, config mirrors, and aq-qa wrapper were validated in repo but did not affect live services until rebuilt.
  Severity: medium
  Action: User rebuilt after commit df78604a. Post-rebuild validation passed: no failed units, aq-health-spider clean, payload discipline gate clean, aq-qa 0 --machine 94/0/2.
  File: ai-stack/switchboard/switchboard.py; scripts/ai/aq-chat; scripts/testing/harness_qa/phases/phase0.py

[DONE] coordinator-routing — continuation tasks routed to local-tool-calling instead of canonical default lane — Root cause: route_by_complexity() had a continuation override that converted continuation/general tasks to embedded-assist/local-tool-calling behavior under prefer_local, violating the existing continuation test contract and cross-agent compact-default lane expectation.
  Severity: medium
  Action: Patched continuation/general local routing to `default`; user rebuilt commit a23e1e24 and `aq-qa 0 --machine` passed 96/0/0.
  File: ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator.py ~line 604

[DONE] post-deploy-converge — focused CI artifact step could not find git in systemd PATH — Root cause: ai-post-deploy-converge.service path omitted `pkgs.git`, while run-focused-ci-checks.sh calls `git diff` to select changed files.
  Severity: medium
  Action: Live unit inspection after rebuild showed the first patch added `git` to ai-npm-security-monitor, not ai-post-deploy-converge. Corrected the actual post-deploy service path in repo, committed eeb47e49, rebuilt, and verified rendered PATH includes `/nix/store/...-git-2.51.2/bin`; no failed units, aq-alerts count 0, aq-qa 0 --machine 94/0/2 with report-backed checks skipped, aq-health-spider clean.
  File: nix/modules/services/mcp-servers.nix ~line 2016

[DONE] aq-chat-rendering — local aq-chat printed one token per line, making answers unreadable — Root cause: aq-chat defaulted to the switchboard `local-tool-calling` lane but flipped the payload back to `stream=True`; switchboard only executes the local tool loop for non-streaming local-tool-calling requests, so aq-chat consumed and printed raw SSE deltas exactly as emitted.
  Severity: medium
  Action: Keep local-tool-calling `stream=False`, consume the completed JSON response with `self.client.post()`, and render the final assistant content once through the Markdown renderer. Added static regression coverage and live switchboard smoke returned normal content `AQ_CHAT_RENDER_OK`.
  File: scripts/ai/aq-chat ~line 160; scripts/testing/test-aq-chat-local-tool-profile.py

[DONE] aq-chat-grounding — local aq-chat exhausted tool budget and recommended stale/false system fixes — Root cause: operational recommendation prompts were delegated to the model's local tool loop, so failures in individual tools or repeated tool calls were treated as current system facts and the answer could recommend rebuilds despite a clean live system.
  Severity: medium
  Action: Added deterministic local preflight snapshots for improvement/health/status prompts, bypassed the local tool loop when snapshot evidence is available, required answers to use only snapshot evidence for current-state claims, and bounded snapshot-grounded responses at 1024 tokens. Live non-interactive aq-chat smoke produced a bounded answer with no tool-budget exhaustion.
  File: scripts/ai/aq-chat ~line 45; scripts/testing/test-aq-chat-local-tool-profile.py

[DONE] aq-chat-brief — operators needed a deterministic local health brief without waiting on model inference — Root cause: aq-chat only exposed model-mediated operational recommendation prompts, so even simple current-state checks could spend local inference/tool budget.
  Severity: medium
  Action: Added `/brief`, reusing the trusted local preflight checks and rendering a concise Rich table without llama, switchboard, or hybrid calls. Static tests assert command registration, routing, and renderer presence.
  File: scripts/ai/aq-chat ~line 46; scripts/testing/test-aq-chat-local-tool-profile.py

[DONE] aq-chat-interrupt — Ctrl-C during an in-flight local request dumped an async traceback — Root cause: cancellation/keyboard interrupt handling was only scoped to the prompt loop, not the active inference request path.
  Severity: medium
  Action: Added explicit cancellation/KeyboardInterrupt handling so interrupted in-flight turns print a concise interruption message instead of a traceback.
  File: scripts/ai/aq-chat ~line 312

[DONE] aq-chat-tool-free — explicit "do not call tools" spec prompts still entered the slow local tool path — Root cause: local profile defaulted to switchboard local-tool-calling unless deterministic snapshot grounding was active.
  Severity: medium
  Action: Added an explicit tool-free/spec prompt detector that routes those turns directly to raw local inference with no tool calls, no live-state claims, `enable_thinking=false`, and a 1024-token bounded response budget.
  File: scripts/ai/aq-chat ~line 95

[OPEN] local-delegation-artifact — delegate-to-local reported a task id and output path that could not be found afterward — Root cause not yet isolated; `delegate-to-local --mode direct` printed `local-20260607-214905-ifsp88` and `.agents/delegation/outputs/local-20260607-214905-ifsp88.log`, but `--status/--check` returned "Task not found" and no output file existed.
  Severity: high
  Action: Audit delegate-to-local persistence paths and status lookup contract; add an aq-qa check that direct local delegation creates a retrievable output artifact or reports failure before returning an id.
  File: scripts/ai/delegate-to-local

[DONE] health-spider-systemd-coverage — aq-health-spider returned clean while `nix-optimise.service` was failed — Root cause: health-spider only checked declared HTTP zones and their service state on HTTP failure, so unrelated failed systemd units were invisible to the spider/dashboard health path.
  Severity: high
  Action: Added a global `systemctl --failed --no-legend --no-pager` probe that emits telemetry/attention and makes `aq-health-spider --once` fail when failed units exist. Inspected the live `nix-optimise.service` error (`missing ...coffeescript-2.7.0-npm-deps.drv`), reset the stale failed state, rejected the now-cleared attention item with evidence, and revalidated `systemctl --failed`, `aq-alerts --count`, `/brief`, and `aq-health-spider --once` as clean.
  File: scripts/ai/aq-health-spider; scripts/testing/test-boot-stability-regressions.py

[OPEN] software-factory-readiness — research discovery substrate exists but lacks candidate lifecycle, scoring, and adoption gates — Root cause: `ai-stack/data/knowledge-sources.yaml` and `scripts/data/sync-knowledge-sources` can fetch/import sources, but there is no enforced path from source update to trust scoring, candidate lifecycle state, flat-team PRD debate, eval sandbox, dashboard visibility, and governed adoption.
  Severity: high
  Action: Use `.agents/plans/WORLD_CLASS_SOFTWARE_FACTORY_READINESS_RESEARCH.md` as the Phase 150 shared brief; design source-registry overlay, candidate schema, `aq-research-spider --machine`, local-signal ingest, eval sandbox, dashboard cards, and RAG learning loop before implementation.
  File: .agents/plans/WORLD_CLASS_SOFTWARE_FACTORY_READINESS_RESEARCH.md

[OPEN] model-catalog-freshness — local model catalog is static and likely stale for current model velocity — Root cause: `ai-stack/mcp-servers/shared/model_catalog.py` contains hardcoded model specs and `config/model-profile.json` has a last-updated/probed timestamp but no freshness gate that forces review when model catalogs, local GGUF, or provider model capabilities drift.
  Severity: medium
  Action: Add model catalog/profile freshness metadata and aq-qa/dashboard checks; route new model candidates through sandbox evals before activation or download.
  File: ai-stack/mcp-servers/shared/model_catalog.py

[OPEN] discovery-agent-stub — proactive discovery agent is not doing opportunity analysis yet — Root cause: `ai-stack/local-agents/discovery_agent.py` declares `discover_opportunities()` but currently only logs and `pass`es, so idle discovery cannot surface query gaps, routing failures, tokenomics regressions, or research candidates as actionable work.
  Severity: medium
  Action: Implement a deterministic local-signal scanner that emits machine-readable candidates from aq-qa failures, health-spider anomalies, query gaps, dashboard blanks, routing failures, and stale source/model metadata.
  File: ai-stack/local-agents/discovery_agent.py

[OPEN] flat-collaboration-disabled — desired flat model-team workflow is documented but not enabled/enforced — Root cause: `config/local-agent-config.yaml` still has `multi_agent_collaboration: false` and `config/workflow-automation.yaml` still has `collaborative_workflows: false`, while active Gemini/direct paths can write PRD/policy artifacts without proposal, cross-review, consensus, validation-state, or reviewer separation gates.
  Severity: high
  Action: Create a flat PRD intake gate and Gemini/workflow mode detector before treating Gemini/local plans as consensus; do not enable broad autonomous collaboration until direct delegation artifacts and validation evidence gates are reliable.
  File: config/local-agent-config.yaml; config/workflow-automation.yaml; .agents/prompts/FLAT_MODEL_TEAM_PRD_PROTOCOL.md

[PENDING-REBUILD] observability-parity — Gemini Phase 149 completion claim missed schema drift, raw reasoning leakage, weak QA, dashboard logic gaps, and local-subprocess telemetry coverage — Root cause: implementation added runtime event labels and raw `<think>` extraction without updating the canonical schema/fixture, producing a planning event producer, protecting chain-of-thought, or adding behavior-level QA. The dashboard still lacked acceptable agent logic observability and live telemetry had no thought/planning events before activation. Post-rebuild live smoke also showed the local subprocess delegate branch returns before the HTTP-path telemetry producer in the deployed Nix-store copy.
  Severity: high
  Action: First corrective slice implemented: safe reasoning summary events, raw `<think>` stripping, shared coordinator route-planning events for HTTP and local subprocess paths, schema/fixture repair, dashboard thought/planning filters/rendering, sandboxed HTML previews, and behavioral 0.10.2 QA. Pending rebuild/live smoke and richer dashboard summary tiles.
  File: .agents/plans/OBSERVABILITY-PARITY-CONSENSUS-REVIEW.md

[DONE] local-subprocess-instruction-discipline — local coordinator delegate ignored exact-output instruction during smoke, then first remediation disabled capabilities too broadly — Root cause: `/control/ai-coordinator/delegate` with `profile=local-tool-calling`, `max_tokens=32`, and task "Return exactly PLANNING_SMOKE_OK" originally returned meta-reasoning text instead of the requested literal. Gemini's first Phase 150 fix forced `tools_enabled=false` and `thinking_mode=off` for all exact-output tasks, which made the smoke pass by trimming capabilities; follow-up commit 173b5f50 restored exact-output tool/reasoning capability unless the task is explicitly tool-free.
  Severity: medium
  Action: Hardened 0.10.3 to assert exact-output tasks do not disable tools/thinking unless explicitly tool-free; wired dashboard logic-discipline metric to delegation-feedback telemetry instead of defaulting missing data to 100%; rebuilt, restarted dashboard API with sudo, and verified live smoke plus aq-qa 0.
  File: ai-stack/agents/runtimes/local_agent_runtime.py; ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py

[DONE] dashboard-logic-discipline-no-data — Logic Discipline tile reported 100% without backend metric — Root cause: `assets/dashboard.js` used `analytics.logic_discipline_rate ?? 100` while `/api/insights/routing/analytics` did not produce `logic_discipline_rate`, hiding missing telemetry and making the error threshold unreachable (`<90` warning checked before `<70` error).
  Severity: high
  Action: Added backend `logic_discipline` summary from delegation-feedback JSONL, exposed nullable `logic_discipline_rate`, rendered `--` on missing data, made the `<70` error threshold reachable, and verified live `/api/insights/routing/analytics` returns sample/failure/score telemetry.
  File: dashboard/backend/api/services/ai_insights.py; assets/dashboard.js; dashboard.html

[DONE] manual-rebuild-source-backed-dashboard-reload — manual `nixos-rebuild switch` left command-center-dashboard-api serving stale repo-backed Python code until an explicit privileged restart — Root cause: the dashboard API unit runs from the repo path, so source-only backend edits are not activated by a plain NixOS switch unless the unit is restarted; unprivileged `systemctl start/reset-failed` can also hang on authorization.
  Severity: medium
  Action: Added a health-spider semantic routing-analytics probe with required `logic_discipline` keys so stale dashboard backends are detected as degraded, surfaced to attention/telemetry/RAG, and validated by boot-stability regression coverage. Manual source-only backend edits still require privileged service restart for activation.
  File: nix/modules/services/command-center-dashboard.nix; nixos-quick-deploy.sh; scripts/ai/aq-health-spider
