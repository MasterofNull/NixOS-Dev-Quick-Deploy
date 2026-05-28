# HANDOFF MEMO — 2026-05-27 (updated Phase 72.z + agent-loop validation)
## Status
Phase 72.z complete. Training loop 12/12 PASS baseline. Local coding agent validated end-to-end.
AppArmor profiles active (complain mode). Enforce deadline: 2026-05-30.

## Phase 72.z Session 2 — Agent Loop Full Fix Chain — latest commit cfadf882

### 9-commit fix chain — agent now validated end-to-end
1. **Progressive disclosure** (b4b758f9): `_minimal_tool()` reduces system prompt from 709→~330 tokens (~8 tok/tool, names+params only). Full schemas in tool_registry for server-side validation.
2. **agent_spawner gap** (ab3642da): `agent_spawner.py` had `max_tokens=4096` + no `chat_template_kwargs` → 68-min slot lock risk. Fixed: `build_llama_payload()` + `LLAMA_MAX_TOKENS` env.
3. **SSOT: shared/llm_config.py** (5f421fbe): `build_llama_payload()` created as single source of truth for ALL llama.cpp calls. Wired to 8 call sites: `agent_executor`, `agent_spawner`, `local_agent_runtime` (×2), `eval_runner`, `model_probe`, `context_lifecycle_manager`, `switchboard`. No more inline dicts.
4. **Mixed prose+JSON parse** (6e9e0b67): `parse_tool_call_from_llama` did `json.loads(full_output)` — failed when model prepended prose. Fix: `rfind('{"function"')` extracts JSON from within mixed responses. Loop no longer stalls after first tool call.
5. **role:tool + clean assistant turn** (cfadf882): Tool results injected as `role:"function"` — NOT in Qwen3's chat template → silently dropped → model hallucinated on every turn. Fix: `role:"tool"`. Also strips prose from assistant turn before appending to messages. VALIDATED: 1 tool call, correct result consumed, accurate summary generated.

### Validation result (aq-1779941325)
- Task: read first 5 lines of `ai-stack/mcp-servers/shared/llm_config.py`
- Tool calls: 1 (read_file, directly, no unnecessary precondition checks)
- Tool result: consumed correctly
- Final answer: accurate description of SSOT docstring content
- Elapsed: 386s (expected: Renoir APU ~1-2 tok/s, 512-token cap)
- Status: COMPLETED ✅

### Remaining learning loop gaps (not fixed this session)
- `samples_added: 0` on all training runs — ingest pipeline extracts no positive samples
- Phase 5/6 (apply improvements) is a stub
- MemoryBroker write not wired from agent_executor on task completion

### Continuous learning state
- `harness-prompt-extensions.yaml`: 2 patterns from 74 failures — injected into every agent call ✅
- `training-loop-results.jsonl`: 3 runs (10/12, 2/12, 12/12) ✅
- Training dataset: empty (samples_added=0) — ingest not extracting samples ❌
- Improvement apply: stub ❌

## Phase 72.y Fixes (this session) — latest commit 1958ca44
- **enable_thinking wrong param**: `"enable_thinking": false` at top level silently ignored by
  llama.cpp. Must be `"chat_template_kwargs": {"enable_thinking": false}`. Fixed in delegate-to-local.
- **run_direct SSE streaming**: switched from blocking stream:false to SSE stream:true.
  SLOT_WAIT_S=45s detects queue saturation fast. Per-line socket timeout after first token.
  Event-driven: first token = hook signal that slot was acquired.
- **Ghost task reaper**: `_reap_orphans()` Phase B cancels live-PID tasks whose age >
  DEFAULT_TASK_TIMEOUT_S. Catches orphans from killed training runs that hold llama.cpp slot.
- **Auto-cancel on timeout**: `_cancel_task()` called in `_wait_for_task` after timeout; kills
  background nohup process + children via `delegate-to-local --cancel`.
- **Env-driven token limits**: `DIRECT_MAX_TOKENS=4096` default (production), overridden to
  `EVAL_MAX_TOKENS=512` by training loop for direct-mode eval tasks.
- **Results log fallback**: PermissionError on telemetry dir (ai-hybrid:ai-stack mode 750) →
  falls back to DELEGATION_DIR/training-loop-results.jsonl.
- **Checkpoint/resume**: `_checkpoint_save()` after each task; `--resume` flag skips completed
  cases; SIGTERM/SIGHUP handler logs intent; `_checkpoint_clear()` on success.
  Usage after rebuild/hibernate: `aq-local-training-loop --resume --verbose`

## Rebuild Completed (2026-05-27)
- `sudo nixos-rebuild switch --flake .#hyperd-ai-dev` — DONE
- AppArmor profiles now attached to ai-hybrid-coordinator + command-center-dashboard-api
- Post-rebuild check: zero /home violations in complain mode — safe to enforce 2026-05-30
- All 6 services active: coordinator, dashboard, ralph-wiggum, aidb, aider-wrapper, llama-cpp

## Pending Actions (user — privileged)
- 2026-05-30: `sudo aa-enforce /etc/apparmor.d/ai-hybrid-coordinator` (enforce deadline)
- 0.1.2: `sudo systemctl start ai-prompt-eval.service` to re-run with fixed exit code
- 0.8.1: Self-healing — switchboard running; delegate rate recovers as calls succeed

## Training Loop Final Result (Phase 72.z)
- Run 1: loop-20260527-214248 · 10/12 PASS (83.3%)
- Run 2: loop-20260527-222203 · 2/12 PASS (17%) — regression: SLOT_WAIT_S=45s fired during external llama.cpp occupancy
- Run 3: loop-20260527-231814 · **12/12 PASS (100%)** — baseline established
- Fix: pre-poll GET /slots (3s interval) until is_processing=False before submitting; SLOT_WAIT_S=full timeout_secs as safety net only
- Lowest scorer: nix-overlay-pattern (0.6) — passes threshold, watch for drift
- 0 improvement proposals — nothing to fix at baseline

## Completed Tasks (Phase 72)
- SSE streaming for local agent executor (per-chunk 120s timeout, no wall-clock cap)
- training_ingest.py: activates all 3 telemetry streams
- aq-local-training-loop: eval/improve/validate cycle with daemon mode + checkpoint/resume
- config/training-manifest.yaml: agent-agnostic SSOT for eval packs
- aq-chat /rate command: activates delegation-feedback stream
- Continue IDE timeout fix: 300s→1200s, maxTokens 1024→4096
- aq-report: WAL-resilient SQLite fallback + /tmp write fallback
- aq-prompt-eval: holistic exit code
- config/qa-xfail.yaml: governance mechanism for runtime-blocked failures

## Pending Tasks (requires privileged ops)
- 0.1.2: `sudo systemctl start ai-prompt-eval.service`
- 0.8.1: Self-healing (switchboard running)

## Confirmed Non-Bugs
- event_type "coercion" at agent_service.py:100 + http_server_impl.py:1832 is intentional
[2026-05-28T15:56:11Z] [dispatch] id=local-20260528-085016-y02yz2 agent=local-hybrid output=.agents/delegation/outputs/local-20260528-085016-y02yz2.log obj="Role standardization debate — Qwen3 position + gap analysis JSON"
[2026-05-28T15:56:55.062084Z] [dispatch] id=test-smoke-001 agent=gemini output=.agents/delegation/outputs/test-smoke-001.log obj="smoke test objective"
[2026-05-28T15:56:55.141301Z] [done] id=test-smoke-001
