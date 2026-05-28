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

Two teammates have already we"

TASK: Agent "

## YOUR EXACT TASK

Make two targeted file"

## CONTEXT (inlined — do not try to read fil"
[2026-05-28T15:56:11Z] [dispatch] id=local-20260528-085016-y02yz2 agent=local-hybrid output=.agents/delegation/outputs/local-20260528-085016-y02yz2.log obj="Role standardization debate — Qwen3 position + gap analysis JSON"
[2026-05-28T15:56:55.062084Z] [dispatch] id=test-smoke-001 agent=gemini output=.agents/delegation/outputs/test-smoke-001.log obj="smoke test objective"
[2026-05-28T15:56:55.141301Z] [done] id=test-smoke-001
[2026-05-28T16:01:44.397446Z] [dispatch] id=local-20260528-090144-pv73a4 agent=local-direct output=.agents/delegation/outputs/local-20260528-090144-pv73a4.log obj="Role standardization debate — your turn (Qwen3/local-agent position).
[2026-05-28T16:01:54.248015Z] [done] id=local-20260528-085016-y02yz2
[2026-05-28T16:07:20.885024Z] [done] id=local-20260528-090144-pv73a4
[2026-05-28T16:08:38.116758Z] [cancelled] id=local-20260528-090144-pv73a4
[2026-05-28T16:11:17.538513Z] [dispatch] id=gemini-20260528-091117-1ki09u agent=gemini output=.agents/delegation/outputs/gemini-20260528-091117-1ki09u.log obj="You are a full cross-functional product team convened to produce a spec-driven PRD for agent role st"
[2026-05-28T16:12:26.838457Z] [done] id=gemini-20260528-091117-1ki09u
[2026-05-28T16:50:28.700372Z] [failed] id=gemini-20260528-091117-1ki09u
[2026-05-28T16:51:15.375623Z] [dispatch] id=gemini-20260528-095115-lh0s8h agent=gemini output=.agents/delegation/outputs/gemini-20260528-095115-lh0s8h.log obj="You are a cross-functional product team. Speak as each specialist, then produce a PRD.
[2026-05-28T16:52:22.178146Z] [done] id=gemini-20260528-095115-lh0s8h
[2026-05-28T17:14:04.497437Z] [dispatch] id=local-20260528-101404-h1g9sf agent=local-direct output=.agents/delegation/outputs/local-20260528-101404-h1g9sf.log obj="Reply with exactly: SMOKE_OK"
[2026-05-28T17:14:15.771015Z] [done] id=local-20260528-101404-h1g9sf
[2026-05-28T17:18:28.881646Z] [dispatch] id=local-20260528-101828-ikdqnz agent=local-direct output=.agents/delegation/outputs/local-20260528-101828-ikdqnz.log obj="Say: FIXED"
[2026-05-28T17:18:32.802330Z] [done] id=local-20260528-101828-ikdqnz
[2026-05-28T17:27:27.215757Z] [dispatch] id=gemini-20260528-102727-6jfxeq agent=gemini output=.agents/delegation/outputs/gemini-20260528-102727-6jfxeq.log obj="You are an implementer agent for NixOS-Dev-Quick-Deploy.
[2026-05-28T17:27:46.272301Z] [dispatch] id=local-20260528-102746-z2rtm1 agent=local-direct output=.agents/delegation/outputs/local-20260528-102746-z2rtm1.log obj="BOUNDED TASK: Write a Python snippet (no external imports, just stdlib) that reads the last 20 lines"
[2026-05-28T17:27:46.470725Z] [dispatch] id=local-20260528-102746-v5raum agent=local-direct output=.agents/delegation/outputs/local-20260528-102746-v5raum.log obj="BOUNDED TASK: In ai-stack/local-agents/agent_executor.py, find the code that runs after task complet"
[2026-05-28T17:29:46.075290Z] [done] id=local-20260528-102746-z2rtm1
[2026-05-28T17:31:18.409585Z] [done] id=local-20260528-102746-v5raum
[2026-05-28T17:34:33.312014Z] [dispatch] id=gemini-20260528-103433-ic8rvr agent=gemini output=.agents/delegation/outputs/gemini-20260528-103433-ic8rvr.log obj="You are an architect agent for NixOS-Dev-Quick-Deploy.
[2026-05-28T17:34:48.528946Z] [dispatch] id=local-20260528-103448-h2vifl agent=local-direct output=.agents/delegation/outputs/local-20260528-103448-h2vifl.log obj="What is your role? Reply with exactly: ROLE=implementer"
[2026-05-28T17:34:57.407461Z] [done] id=local-20260528-103448-h2vifl
[2026-05-28T17:34:57.595628Z] [dispatch] id=local-20260528-103457-qruig5 agent=local-direct output=.agents/delegation/outputs/local-20260528-103457-qruig5.log obj="What is your role? Reply with exactly: ROLE=architect"
[2026-05-28T17:35:02.689649Z] [done] id=local-20260528-103457-qruig5
[2026-05-28T17:35:22.588689Z] [done] id=gemini-20260528-103433-ic8rvr
[2026-05-28T17:54:11.681048Z] [dispatch] id=local-20260528-105411-pesr03 agent=local-direct output=/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/delegation/outputs/local-20260528-105411-pesr03.log obj="In one sentence, confirm you received a role-injected system message and state what role you were as"
[2026-05-28T17:54:29.991555Z] [done] id=local-20260528-105411-pesr03
[2026-05-28T17:54:57.411279Z] [dispatch] id=local-20260528-105457-17oac7 agent=local-direct output=/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/delegation/outputs/local-20260528-105457-17oac7.log obj="In one sentence, state your assigned role and one primary responsibility it carries."
[2026-05-28T17:55:14.321974Z] [done] id=local-20260528-105457-17oac7
[2026-05-28T17:55:23.794011Z] [dispatch] id=local-20260528-105523-7age5r agent=local-direct output=/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/delegation/outputs/local-20260528-105523-7age5r.log obj="Reply with exactly: BACKGROUND_OK"
[2026-05-28T17:55:31.680904Z] [done] id=local-20260528-105523-7age5r
[2026-05-28T17:55:33.452417Z] [dispatch] id=local-20260528-105533-1jfx40 agent=local-hybrid output=/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/delegation/outputs/local-20260528-105533-1jfx40.log obj="What is the default llama.cpp port used in this harness? Answer in one line."
[2026-05-28T17:55:38.658617Z] [done] id=local-20260528-105533-1jfx40
[2026-05-28T18:00:13.179236Z] [dispatch] id=local-20260528-110013-2fhmag agent=local-direct output=/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/delegation/outputs/local-20260528-110013-2fhmag.log obj="Reply: TOKEN_TEST_OK"
[2026-05-28T18:00:21.409021Z] [done] id=local-20260528-110013-2fhmag
[2026-05-28T18:09:00.527420Z] [dispatch] id=local-20260528-110900-zoabwj agent=local-direct output=/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/delegation/outputs/local-20260528-110900-zoabwj.log obj="List three specific improvements to make the local model dispatch chain more reliable. Be concrete."
[2026-05-28T18:12:04.306572Z] [done] id=local-20260528-110900-zoabwj
[2026-05-28T18:27:07.399477Z] [dispatch] id=local-20260528-112707-mtxbgm agent=local-direct output=/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/delegation/outputs/local-20260528-112707-mtxbgm.log obj="You are an architect reviewing ai-stack/mcp-servers/hybrid-coordinator/core/route_handler.py.

TASK:"
[2026-05-28T18:27:22.013800Z] [dispatch] id=local-20260528-112721-7vngql agent=local-direct output=/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/delegation/outputs/local-20260528-112721-7vngql.log obj="You are an architect for the NixOS-Dev-Quick-Deploy AI stack.

TASK: Design the mode auto-selection "
[2026-05-28T18:27:37.333120Z] [dispatch] id=local-20260528-112737-vgm741 agent=local-direct output=/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/delegation/outputs/local-20260528-112737-vgm741.log obj="You are a reviewer for the NixOS-Dev-Quick-Deploy AI stack.

CONTEXT: aq-report shows 'Continuation-"
[2026-05-28T18:27:52.397430Z] [cancelled] id=gemini-20260528-102727-6jfxeq
[2026-05-28T18:28:19.568998Z] [done] id=local-20260528-112707-mtxbgm
[2026-05-28T18:29:55.394430Z] [done] id=local-20260528-112721-7vngql
[2026-05-28T18:32:32.726193Z] [done] id=local-20260528-112737-vgm741
[2026-05-28T18:41:40.015948Z] [dispatch] id=local-20260528-114139-xuraeu agent=local-direct output=/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/delegation/outputs/local-20260528-114139-xuraeu.log obj="Write a Python one-liner that prints the first 10 Fibonacci numbers."
[2026-05-28T18:55:13.280203Z] [done] id=local-20260528-114139-xuraeu
[2026-05-28T19:00:59.594924Z] [dispatch] id=local-20260528-120059-my61s3 agent=local-direct output=/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/delegation/outputs/local-20260528-120059-my61s3.log obj="Write a Python one-liner that prints the first 10 Fibonacci numbers."
[2026-05-28T19:01:29.055870Z] [done] id=local-20260528-120059-my61s3
