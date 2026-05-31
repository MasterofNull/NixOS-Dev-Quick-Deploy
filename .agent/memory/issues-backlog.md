[DONE] aq-report/delegation — historical delegated prompt failures surfaced as active remediation — `delegated_prompt_failure_windows` showed 0 failures in 1h and 24h, but recommendations and structured actions still emitted active OpenRouter prompt-contract remediation from 7d historical debt.
  Severity: medium
  Action: Wired delegated failure windows into recommendations/actions; historical-only failures now produce passive context and suppress active salvage/action guidance unless failures recur in 24h.
  File: scripts/ai/aq-report ~line 3893; scripts/testing/test-delegated-prompt-failure-history.py

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

[OPEN] workflow — aq-session-start missing from Codex shell PATH — Session initialization command returned `command not found`; likely PATH/wrapper deployment gap for current execution environment.
  Severity: medium
  Action: Confirm aiHarnessCliWrappers exposes aq-session-start or document the supported absolute path fallback for Codex sessions.
  File: nix/modules/roles/ai-stack.nix ~line 240

[RESOLVED 2026-05-30] ai_coordinator_delegate P95=244s — ceiling is enforced at ai_coordinator.py:706 (_LOCAL_MAX_TOKENS_HARD_CEILING=180). P95=244s is hardware-bound: 180 tok × ~1.35 tok/s on Renoir APU. Not a code bug. Anti-loop guardrails (repeat_penalty=1.08, repeat_last_n=64) confirmed in dispatch.py:79-80. No fix needed.

[DONE] observability — aq-report framed healthy hardware-bound delegate latency as generic cache/connection/model tuning — `ai_coordinator_delegate` P95 around 244s matches the local delegated-response token ceiling on current hardware, but the slow-tool recommendation implied a software tuning defect.
  Severity: low
  Action: Added delegate-specific latency contextualization and regression coverage so healthy high-P95 delegate calls point to bounded prompts/max_tokens rather than cache or connection-pool work.
  File: scripts/ai/aq-report ~line 4395

[OPEN] role-enforcement — AGENT_TYPE_ELIGIBLE_ROLES never validated at dispatch — Matrix is defined in agent_executor.py but no runtime check blocks ineligible role assignments. Any AgentType can receive any role without error.
  Severity: low (aspirational per role-matrix.md §7 — enforcement is a future capability)
  Action: Phase 58A.5 TODO — add eligibility validator in dispatch_task() before TaskConfig is finalized. Until then, policy is doc-only.
  File: ai-stack/mcp-servers/coordinator/agent_executor.py ~line 356

[OPEN] role-enforcement — no reviewer_id tracking, self-review prevention aspirational — Role-matrix.md §8 states "a reviewer may not review their own work" but no reviewer_id field exists in Task/TaskConfig; self-review cannot be enforced at runtime.
  Severity: low (process-enforced via orchestrator discipline, not technically blocked)
  Action: Add reviewer_id to TaskConfig + check in dispatch that reviewer != original implementer task id. Phase 58A.5 candidate.
  File: ai-stack/mcp-servers/coordinator/agent_executor.py, ai-stack/mcp-servers/shared/task_config.py

[OPEN] role-enforcement — domain-role eligibility not validated at task dispatch — DOMAIN-ROLE-MATRIX.md defines which agents may fill which roles per domain, but no enforcement exists at dispatch. Cross-domain mis-routing (e.g., Gemini as security reviewer for its own security implementation) is doc-only blocked.
  Severity: low (policy gap, not immediate production risk)
  Action: Long-term: pass domain_shell in TaskConfig and validate against DOMAIN-ROLE-MATRIX at dispatch. Immediate: document constraint in delegation prompts.
  File: .agent/DOMAIN-ROLE-MATRIX.md (new), ai-stack/mcp-servers/coordinator/agent_executor.py
