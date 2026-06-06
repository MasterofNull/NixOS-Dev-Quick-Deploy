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

[DONE] cli-contract — documented machine/query flags rejected by local CLIs — `aq-report --machine` and `aq-hints --query ...` were documented workflow forms but argparse rejected them, blocking machine-mode parity and copied quick-start commands. Added compatibility aliases.
  Severity: medium
  Action: Added `--machine` as JSON alias in `scripts/ai/aq-report` and `--query` alias in `scripts/ai/aq-hints`; validate with CLI smoke commands and Python compile.
  File: scripts/ai/aq-report ~line 200; scripts/ai/aq-hints ~line 165

[RESOLVED 2026-05-31] workspace-isolation — cleanup_workspace() requires force=True for active workspaces — `WorkspaceManager.cleanup_workspace()` returns False and logs "Cannot cleanup active workspace" unless `force=True` is passed. Default cleanup in integration tests silently fails.
  Severity: low (no data loss; worktrees accumulate in /tmp/aq-worktree-test until manually cleared)
  Action: Pass `force=True` in cleanup calls, or add auto-deactivate before cleanup. File: ai-stack/orchestration/workspace_isolation.py
  File: ai-stack/orchestration/workspace_isolation.py (cleanup_workspace method)

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
