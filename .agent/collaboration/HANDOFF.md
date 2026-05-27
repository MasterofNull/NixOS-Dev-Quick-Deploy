# HANDOFF MEMO — 2026-05-27 (updated Phase 72.y session)
## Status
Phase 72.y complete. nixos-rebuild switch done. AppArmor profiles active (complain mode).
Training loop: 10/12 PASS (83.3%) — full run verified with all lifecycle fixes.

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

## Training Loop Final Result (Phase 72.y)
- Run: loop-20260527-214248 · 10/12 PASS (83.3%) · 1 improvement proposal
- FAIL cases: tc3-feedback-validation (0.2, meta-harness strict match), tool-call-json-schema
- All lifecycle fixes verified: semaphore, streaming SSE, ghost reaper, cancel-on-timeout

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
