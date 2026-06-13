## OPEN ISSUES
<!-- Phase 165 behavioral contract hardening COMPLETE (2026-06-13):
  iter 16-21 resolved: slim-manifest, read-limit, backlog-update-step, embedded-newlines-parse, synthesis-guard@call0.
  aq-qa covers: 0.10.15-19 (5 new Phase 165 checks). Dataset=309. Backlog clear.
  Next: PENDING-REBUILD activation (nixos-rebuild required, all commits ready). -->

[OPEN] switchboard-useful-ratio-missing — switchboard token_usage events never emit useful_ratio; field is always null in telemetry (observability parity gap Phase 149)
  Root cause: switchboard.py emits token_usage events at two sites (~line 2944, ~line 2964) but neither
  includes useful_ratio in the tokens dict. The agent_run_events.py schema supports useful_ratio but
  switchboard passes only raw llama.cpp usage (prompt/completion/total tokens) or estimated counts.
  For local inference with enable_thinking=false, ALL output tokens are useful → useful_ratio=1.0.
  This means the dashboard Useful Token Gauge shows null/-- for 100% of local model requests.
  Live state: grep "useful_ratio" switchboard.py → no results (2026-06-13).
  Severity: medium (observability gap; does not affect response quality)
  Requires rebuild: YES (switchboard.py is a coordinator-side service)
  Action: In ai-stack/switchboard/switchboard.py, at both token_usage emission sites (~line 2944 and ~2964),
  add useful_ratio to the tokens dict:
    Site 1 (llama.cpp usage block, line ~2944): inject "useful_ratio": 1.0 into the usage dict before emit.
    Site 2 (estimated fallback, line ~2971): add "useful_ratio": 1.0 to the tokens dict.
  Justification: enable_thinking=false is system-wide for local inference (CLAUDE.md constraint);
  all output tokens are response tokens → useful_ratio is exactly 1.0.
  Files: ai-stack/switchboard/switchboard.py (~line 2944 and ~2971)
  Two surgical edits. No logic changes.

[DONE] health-spider-osi-layered-running-flag — health spider flags osi_layered_pending as degraded even when background task is actively running (running: True)
  Root cause: _semantic_probe_reason() check for "osi_layered_ready" returns "osi_layered_pending" whenever
  data.get("pending") is True, regardless of data.get("running"). But the layered endpoint is designed to
  return {pending: True, running: True} during its warm-up period (300-600s background aq-qa run).
  The rebuild resets the in-process cache → first post-rebuild request triggers background task →
  health spider hits during warm-up window → false-positive "degraded" alert (attn-0c6f15e9, 2026-06-12).
  Severity: low
  Action: In scripts/ai/aq-health-spider, edit _semantic_probe_reason() for the "osi_layered_ready" check:
  Old text (exact, line ~142-144):
    if check == "osi_layered_ready":
        if data.get("pending") is True:
            return "osi_layered_pending"
  New text:
    if check == "osi_layered_ready":
        if data.get("pending") is True and not data.get("running"):
            return "osi_layered_pending"
  Effect: Spider tolerates the warm-up window (running: True). Only flags as degraded when stuck (pending AND NOT running).
  Files: scripts/ai/aq-health-spider (_semantic_probe_reason, ~line 142)
  One surgical edit, no logic changes beyond the single condition.

[OPEN] ragas-faithfulness-zero-samples — faithfulness metric never computed; faithfulness_sample_count=0 across all 100 eval samples
  Root cause: http_server_impl.py _ragas_score() computes faithfulness only when _ctx is non-empty:
    `fs = await eval_runner.score_faithfulness_async(q, _ctx, r) if _ctx else None`
  _ctx is built from RAG documents returned by the coordinator. If AIDB returns no matching documents
  (sparse collections), _ctx is empty → faithfulness=None for that sample. All 100 samples evaluated
  with empty context → faithfulness_sample_count=0 → faithfulness_avg=null indefinitely.
  Live state (2026-06-13): ragas_metrics={answer_relevance_avg: 0.4747, faithfulness_avg: null, faithfulness_sample_count: 0, sample_count: 100}
  Root cause of empty context: RAG collections (error-solutions, skills-patterns, best-practices) may be
  stale or sparse for the types of queries flowing through the coordinator. Re-seed with current patterns.
  Severity: medium
  Action: Run seed-rag-knowledge.py --clear-wrong-type to refresh collections, then verify
  faithfulness_sample_count increases over the next 24h as coordinator queries hit populated collections.
  If collections are populated but faithfulness remains 0, investigate score_faithfulness_async for errors.
  Files: scripts/data/seed-rag-knowledge.py (immediate action); ai-stack/mcp-servers/hybrid-coordinator/http_server_impl.py _ragas_score (~line 2404) for deeper fix if needed.
  Non-blocking: answer_relevance and context_precision metrics are healthy (0.47 and 0.43).

[DONE] parse-tool-call-embedded-newlines — parse_tool_call_from_llama fails when model emits JSON with literal (unescaped) newlines in string values
  Root cause: When old_string/new_string span multiple Python source lines, the model may emit them
  as JSON string values containing literal `\n` characters instead of `\\n` escape sequences.
  `json.loads()` rejects literal control chars in strings → parse returns None → tool never executes.
  iter 19 (aq-1781332710) triggered this: old_string contained two Python source lines joined by `\n`.
  Synthesis guard did NOT fire because tool_call_count==0 (guard has `if tool_call_count > 0` guard).
  Severity: medium
  Action: In tool_registry.py parse_tool_call_from_llama, pre-process the raw string to escape
  literal newlines/tabs before json.loads(): replace raw `\n` (0x0a) with `\\n` inside the JSON
  string payload. Use regex or a custom sanitize step before json.loads().
  Also: remove the `tool_call_count > 0` guard from the synthesis guard in agent_executor.py so
  it fires even when the first response is an unexecuted JSON tool call.
  Files: ai-stack/local-agents/tool_registry.py parse_tool_call_from_llama (~line 583);
         ai-stack/local-agents/agent_executor.py synthesis guard (~line 723)
  Two surgical edits, one to each file.

[DONE] behavioral-contract-backlog-update-step — BEHAVIORAL CONTRACT STEP 6 adds issues-backlog.md to git but never marks the issue [DONE] first
  Root cause: STEP 6 says git_add([<changed-files>, '.agent/memory/issues-backlog.md']) but there is no
  step before git_add that calls edit_file to change [OPEN] to [DONE] in the backlog. The backlog is staged
  but unchanged, so [OPEN] issues remain [OPEN] after commit. Orchestrator has to manually update them.
  Severity: medium
  Action: In agent_executor.py, edit BEHAVIORAL CONTRACT to add a step between STEP 5 and STEP 6.
  Old text (exact):
    "        If gate fails, fix the problem and re-run. Gate passes → go to STEP 6 immediately.\n"
    "STEP 6: git_add([<changed-files>, '.agent/memory/issues-backlog.md'])\n"
  New text:
    "        If gate fails, fix the problem and re-run. Gate passes → go to STEP 5b immediately.\n"
    "STEP 5b: edit_file('.agent/memory/issues-backlog.md', '[OPEN] <issue-title>', '[DONE] <issue-title>')\n"
    "         Marks the fixed issue as done. Use the exact issue title from STEP 2.\n"
    "STEP 6: git_add([<changed-files>, '.agent/memory/issues-backlog.md'])\n"
  Files: ai-stack/local-agents/agent_executor.py (_get_system_prompt BEHAVIORAL CONTRACT)
  One edit_file call. No logic changes.

[DONE] behavioral-contract-read-limit — BEHAVIORAL CONTRACT lacks explicit READ LIMIT rule; model over-reads before editing
  Root cause: BEHAVIORAL CONTRACT general rules say "Read before writing" but this causes over-exploration.
  Iter 17 original ran 12 reads, 0 edits in 26+ minutes because the model kept reading different files
  instead of attempting edit_file. The exploration stagnation guard (Phase 165) catches this at 12 reads
  (hard abort) and nudges at 8, but the root fix is making the contract explicit.
  Severity: medium
  Action: In agent_executor.py, inside _get_system_prompt(), edit the BEHAVIORAL CONTRACT to add after the
  "- ALWAYS prefer edit_file over write_file" rule:
  Old text (exact):
    "- ALWAYS prefer edit_file over write_file for targeted changes.\n"
    "  edit_file(path, old_string, new_string) replaces old_string in place — no full-file regeneration.\n"
    "  Only use write_file if you must create a new file from scratch.\n"
  New text:
    "- ALWAYS prefer edit_file over write_file for targeted changes.\n"
    "  edit_file(path, old_string, new_string) replaces old_string in place — no full-file regeneration.\n"
    "  Only use write_file if you must create a new file from scratch.\n"
    "- READ LIMIT: At most 4 read_file calls per slice. After 4 reads, STOP reading — you have enough\n"
    "  context. Call edit_file immediately. If edit_file fails with 'old_string not found', THEN read more.\n"
  Files: ai-stack/local-agents/agent_executor.py (BEHAVIORAL CONTRACT in _get_system_prompt)
  One edit_file call. No logic changes.

[DONE] agent-step-complete-tool-call-result — synthesis guard added to agent_executor.py
  Fix: two-part — (1) training_ingest: added '"function"' + '"arguments"' to _STRUCTURED_MARKERS so JSON
  tool-call blobs score as structured (score≈0.80 vs 0.048 pre-fix). (2) agent_executor.py synthesis guard:
  if final response starts with '{"function"', request 256-token "COMPLETED:" prose synthesis.
  BEHAVIORAL CONTRACT DONE marker now requires "COMPLETED: <sentence>" prefix explicitly.
  Commit: 8694d6fc (feat(observability): wire context_sanitizer, synthesis guard, agent replay parity)
  Validated: iter 17 retry produced COMPLETED: sentence at step 8. training_ingest will pick up sample.

[DONE] aq-agent-loop-build-registry-docstring-drift — build_registry() docstring + argparse help updated to list 8 slim tools
  Fix: iter 17 retry (zyk4bj / aq-1781328865) — model used edit_file × 2, validate_before_commit, git_commit.
  7 steps in 475s. Commit: f3fb0e11 "docs(aq-agent-loop): update build_registry docstring + argparse help to list 8 slim tools"
  Key improvement vs iter 17 original: targeted prompt with exact old_string/new_string eliminated over-exploration.
  Original iter 17 ran 26+ minutes with 12 reads, 0 edits — killed and re-dispatched.

[DONE] progressive-tool-disclosure — aq-agent-loop exposed all 29 tools (~2507 tokens) in every self-improvement slice
  Root cause: build_registry() always registered all tools. Self-improvement slices only need 6 tools
  (read_file, write_file, run_command, git_add, git_commit, store_memory). Extra 23 tools added 1739
  tokens to the system prompt on every LLM call = 174s wasted prefill per call at 10 tok/s (Renoir APU).
  Over 7 calls per slice: ~20 minutes wasted per self-improvement iteration.
  Fix: Added --tool-manifest flag to aq-agent-loop with 'full' (default, 29 tools) and 'self-improvement'
  (6 tools). build_registry(tool_manifest=) unregisters excluded tools via registry.unregister().
  Slim schema: 3073 chars (~768 tokens) vs full 10031 chars (~2507 tokens). 1739 token savings per call.
  File: scripts/ai/aq-agent-loop (build_registry, run_task, argparser)
  Commit: feat(agents): progressive tool disclosure — --tool-manifest self-improvement (6 tools, save ~174s/call)

[DONE] agent-behavioral-contract-cleanup — contract updated with surgical finality (commit-on-pass, no post-fix cleanup)
  Gemini P2 finding (2026-06-12): BEHAVIORAL CONTRACT lacked explicit "commit on pass, no cleanup" mandate.
  Iter 7 timed out doing post-commit cleanup (RESUME.json, HANDOFF.md, PULSE.log updates), consuming ~3-4
  extra inference calls and hitting 3600s wall-clock. Fix: Added "SURGICAL FINALITY" rule and strengthened
  DONE step to explicit "STOP. Do not refactor. Do not update other files."
  Also: STEP 3 now instructs agent to use start_line/end_line for targeted reads (reduce context load).
  Also: STEP 6 now includes issues-backlog.md in git_add so the fix is committed with DONE marker.
  File: ai-stack/local-agents/agent_executor.py (_workflow_contract)
  Commit: fix(agents): strengthen behavioral contract with surgical finality + targeted reads

[DONE] agent-loop-wall-clock-timeout — agent tasks killed at 3600s fixed-wall-clock before completing 9 tool calls
  Root cause: iter 9 self-improvement run grew context to 7436 tokens by call 6-7 (Qwen3 SWA forces full
  re-prefill each turn, no KV cache reuse). At 10 tok/s prefill, each late call took 12+ minutes. Fixed 3600s
  wall-clock only allowed ~3 large calls. Context pruning at 24768 chars (~6192 tokens) didn't prevent growth.
  Fix A (dispatch.py): Dynamic wall-clock = min(per_call_budget × max_calls + 120, 10800s).
    per_call_budget = chunk_timeout (900s) + gen_budget (1200s) = 2100s.
    For 9 calls: min(9×2100+120=19020, 10800) = 10800s (3-hour hard cap = runaway safeguard).
    AGENT_WALL_CLOCK_SECS env var still overrides for ops/debug.
  Fix B (agent_executor.py): Lower context budget from 24768 chars (~6192 tokens) to 12000 chars (~3000 tokens).
    Keep only system + user + last 2 tool pairs (max 6 messages). Caps prefill at ~5 min per call.
    Tradeoff: agent loses older history; BEHAVIORAL CONTRACT already discourages re-reading.
  Files: scripts/ai/lib/dispatch.py, ai-stack/local-agents/agent_executor.py
  Identified: 2026-06-12 by analyzing llama.cpp slot print_timing logs during iter 9.

[DONE] agent-context-pinned-sliding — "last 2 pairs" context strategy dropped initial discovery by step 5-6
  Gemini FAIL verdict (2026-06-12 architectural review): reducing context to system+user+last-2-pairs was too
  aggressive. By step 5-6, the model had lost the initial grep output (which issue to fix), causing it to read
  the backlog file again → extra tool call, context refill, potentially triggering stagnation loop.
  Root cause: messages[:2] + messages[-4:] discards messages[2:3] = first assistant call + first tool result.
  Those contain the grep discovery that anchors the entire slice.
  Fix (agent_executor.py _execute_with_tools): Replace with "Pinned + Sliding" strategy:
    PINNED  = messages[0:4]  — system + user + first_assistant_call + first_tool_result (task anchor)
    SLIDING = messages[-4:]  — last 2 assistant+tool pairs (most recent work)
    Trigger: _ctx_chars > 12000 AND len(messages) > 8. Fallback shed-oldest-pair for len 6-8.
  Impact: model retains which issue it targets across all steps; no re-reads of already-seen content.
  File: ai-stack/local-agents/agent_executor.py (_execute_with_tools, Pinned+Sliding block)
  Commit: feat(agents): pinned+sliding context + stagnation detection
  Follow-up (Gemini FAIL d5235778): removed dead overlap dedup guard (overlap=4+4-len<0 always when len>8).
  Commit: fix(agents): remove dead overlap guard + tune stagnation thresholds

[DONE] agent-stagnation-detection — no guard against runaway same-tool loops in agent_executor
  Root cause: agent could call read_file or run_command 20+ times with identical result (e.g. after context
  pruning dropped the tool result, model re-reads the same file in a tight loop). No detection, no early exit.
  Gemini recommendation (2026-06-12): terminate if same tool called N consecutive times with no state change.
  Fix (agent_executor.py _execute_with_tools): _recent_tools list tracks (tool_name, result[:200]) for last N
  calls. Threshold is tool-specific: read_file=3 (pure observation, 3 identical reads = stuck),
  run_command=5 (polling loops like tail/systemctl legitimately repeat). If all N have same result prefix,
  logger.warning and return stagnation_msg early.
  File: ai-stack/local-agents/agent_executor.py (_execute_with_tools, stagnation detection block)
  Commit: fix(agents): remove dead overlap guard + tune stagnation thresholds

[DONE] training-ingest-routing-rules-lost — training_ingest.py perpetuated routing_rules loss due to non-truthy check
  Root cause: training_ingest.py lines 493-495 — `break` at col 12 was OUTSIDE the inner
  `isinstance(_existing.get("routing_rules"), dict)` check. An empty dict {} passes `isinstance({}, dict)`,
  so _existing_routing_rules = {} and break fired → empty state preserved forever on every subsequent rewrite.
  Fix: Changed condition to truthy `_existing.get("routing_rules")` and moved `break` INSIDE the success branch.
  Both config/harness-prompt-extensions.json and .yaml still carry routing_rules (grep -c confirms).
  File: ai-stack/local-agents/training_ingest.py (lines 493-495)
  Commit: fix(training-ingest): truthy check prevents perpetuating empty routing_rules on rewrite

[DONE] training-ingest-write-race — concurrent training_ingest runs shared a fixed temp file path causing lost writes
  Root cause: training_ingest.py lines 519-527 used fixed .tmp paths:
  `_target.with_suffix(".tmp")` for YAML, `_target.with_suffix(".json.tmp")` for JSON.
  Two concurrent processes wrote to the same .tmp file; process B overwrote A's content before A's os.replace().
  Fix: Both blocks replaced with tempfile.NamedTemporaryFile(dir=_target.parent, delete=False, suffix=".tmp").
  Each process gets a unique temp path. os.replace() remains the atomic final rename.
  Note: iter 11 identified and attempted the fix but called write_file with only a 24-line snippet, destroying
  573 lines of the file. Restored from git; fix applied surgically by orchestrator (Edit tool).
  File: ai-stack/local-agents/training_ingest.py (lines 516-531)
  Commit: fix(training-ingest): use NamedTemporaryFile for atomic write to eliminate concurrent-write race

[DONE] agent-telemetry-permission-drop — agent_step_complete / agent_thinking / agent_tool_call events silently dropped
  Root cause: agent_executor.py wrote per-step telemetry to /var/lib/ai-stack/hybrid/telemetry/hybrid-events.jsonl
  (owned ai-hybrid:ai-stack 0640). aq-agent-loop runs as hyperd (ai-stack group, read-only) → PermissionError
  on every write, silently suppressed by try/except. All agent observability events were dropped — dashboard and
  training_ingest never received agent-loop telemetry. Identified 2026-06-12 by analyzing group permissions.
  Fix: _HYBRID_EVENTS in agent_executor.py redirected to .agents/telemetry/hybrid-events.jsonl (owned hyperd:users
  0644, fully writable). REPO_ROOT env var respected for Nix store compatibility. training_ingest.py already reads
  this path as USER_EVENTS_SPOOL — no ingest changes needed.
  File: ai-stack/local-agents/agent_executor.py (lines 41-46)
  Commit: fix(telemetry): redirect agent event spool to user-writable path

[DONE] dispatch-timeout-env-undocumented — AGENT_WALL_CLOCK_SECS env var documented in .env.example
  Fixed by agent commit 73f8102b.

[DONE] aq-agent-loop/doc-drift — module docstring advertised wrong --max-calls default
  Auto-resolved by pre-commit hook during Phase 165 commit (03e5f950). Docstring line 18
  now reads "[default: 50]" matching argparse default=50.

[DONE] slim-manifest-missing-validate-before-commit — _SLIM_TOOLS in aq-agent-loop excludes validate_before_commit but BEHAVIORAL CONTRACT header says "validate_before_commit MUST pass before git_add"
  Root cause: when build_registry(tool_manifest="self-improvement") unregisters tools not in _SLIM_TOOLS,
  validate_before_commit is removed (it's registered by register_git_tools, not in the frozenset).
  The BEHAVIORAL CONTRACT general rule still tells the model to call it, creating a tool-not-found
  failure on the validation step. STEP 4/5 correctly use run_command as fallback, but the top-level
  rule is inconsistent and will cause model confusion on the first iteration that strictly follows the header.
  Severity: medium
  Action: Add "validate_before_commit" to _SLIM_TOOLS frozenset in scripts/ai/aq-agent-loop (line 70-73).
  One-line change: add "validate_before_commit" to the frozenset. No other files need to change.
  File: scripts/ai/aq-agent-loop lines 70-73 (_SLIM_TOOLS frozenset)
  Resolved: iter 16 model commit 19176f6f (2026-06-12) — Qwen3-35B used edit_file to add "validate_before_commit" to _SLIM_TOOLS. First successful autonomous self-improvement iteration.

## PENDING-REBUILD

[PENDING-REBUILD] continue-local-injecthints-regression — `aq-qa 0 --machine` failed 0.5.2, 0.5.4, and 0.5.5 after Phase 164G changed `continue-local.injectHints` to true — Root cause: the compact editor/tab lane must remain hint-free; injecting harness hints into `continue-local` breaks Continue config parity and context trimming expectations.
  Severity: high
  Action: Restored `continue-local.injectHints=false` in the switchboard profile catalog while leaving `local-tool-calling.injectHints=true`. Requires switchboard reload/rebuild for live `/health` and aq-qa 0.5 checks to reflect the fix.
  File: config/switchboard-profiles.yaml ~25

[PENDING-REBUILD] coordinator-qa-check-wrapper-empty-capture — after rebuild, the deployed `aq-qa` wrapper and `_aq-qa-bash` both emitted JSON when run directly, but live `/qa/check` still reported `parse_error: aq-qa produced empty stdout` for the wrapper command — Root cause: unresolved live coordinator capture/scheduler mismatch on the wrapper path; no fresh AppArmor denial was observed, and the direct deployed wrapper produced JSON with failure evidence.
  Severity: high
  Action: Added a JSON-mode recovery path in `run_qa_check_as_dict`: when wrapper stdout is empty, rerun the deployed `_aq-qa-bash` fallback directly and preserve wrapper exit/stderr metadata. Requires NixOS rebuild/switch to activate in the live endpoint.
  File: ai-stack/mcp-servers/hybrid-coordinator/extensions/mcp_handlers.py ~265

[PENDING-REBUILD] coordinator-qa-check-drop-spec-abort — post-rebuild `/qa/check` still returned `parse_error: aq-qa produced empty stdout` after AppArmor denials were resolved — Root cause: `_aq-qa-bash` ran the Phase 85.2 `drop_spec.py` injection probe in an unguarded command substitution under `set -euo pipefail`; when the coordinator subprocess resolved plain `python3` to a thinner system Python without `yaml`, the script exited before `_render_results` emitted JSON. The same PATH drift also made Phase 0 governance tests miss `httpx` and `psutil` inside `/qa/check`.
  Severity: high
  Action: Guarded the `drop_spec.py` probe so import/test failures become normal `CheckResult` rows and added `hybridPython` to the `ai-hybrid-coordinator` service path so child QA probes inherit the coordinator's packaged Python dependencies. Requires NixOS rebuild/switch before live `/qa/check` can use the new service path and patched store source.
  File: scripts/ai/_aq-qa-bash ~1190; nix/modules/services/mcp-servers.nix ~1034

[PENDING-REBUILD] tool-registry-readonly-home-default — `test-local-agent-store-memory-contract.py` failed only inside the coordinator-like environment with `PermissionError: /var/lib/ai-stack/hybrid/.local/share/...` — Root cause: `ToolRegistry()` defaulted its SQLite audit DB under `Path.home()/.local/share`, but coordinator service hardening sets `HOME=/var/lib/ai-stack/hybrid` and does not make that nested home data path writable; existing writable state is exposed through `XDG_STATE_HOME`/`DATA_DIR`.
  Severity: high
  Action: Changed the default audit DB path to prefer `XDG_STATE_HOME` then `DATA_DIR`, preserving the interactive `XDG_DATA_HOME`/home fallback. Requires NixOS rebuild/switch for deployed coordinator subprocesses.
  File: ai-stack/local-agents/tool_registry.py ~46

[PENDING-REBUILD] coordinator-qa-check-store-script-exec-denial — post-switch `/qa/check` advanced past proc-net but still returned `parse_error: aq-qa produced empty stdout` — Root cause: coordinator phase 0 runs from the deployed Nix-store source path, so existing AppArmor exec rules for live-repo `scripts/ai/aqd` did not match `/nix/store/*-source/scripts/ai/aqd`; phase 0 also invokes `git` from Python checks.
  Severity: high
  Action: Added inherited-profile exec rules for `/nix/store/*-source/scripts/ai/{aqd,aq-alerts}` and `/nix/store/**/bin/git`. Requires NixOS rebuild/switch to activate.
  File: nix/modules/services/mcp-servers.nix

[PENDING-REBUILD] coordinator-qa-check-ss-procnet-denial — post-rebuild `/qa/check` still aborted before machine JSON while direct git sync was already clean — Root cause: the new AppArmor exec rule allowed `ss`, but inherited `ai-hybrid-coordinator` confinement denied `ss -tlnp` reads of `/proc/<pid>/net/tcp`, so repeated phase 0 listener probes still failed in the service sandbox. The handler correctly exposed `parse_error: aq-qa produced empty stdout`.
  Severity: high
  Action: Added explicit read rules for per-process net tables used by `ss` (`tcp`, `tcp6`, `udp`, `udp6`, `unix`) and the THP status file also reported by health-spider. Follow-up after rebuild: first patch placed the rules in the dashboard profile block, not `ai-hybrid-coordinator`; moved them into the correct profile. Requires NixOS rebuild/switch to activate.
  File: nix/modules/services/mcp-servers.nix

[PENDING-REBUILD] coordinator-qa-check-empty-json — `/qa/check` returned `qa_result: {}` with empty stdout/stderr while direct `aq-qa 0 --json` produced machine JSON — Root cause: the enforced `ai-hybrid-coordinator` AppArmor profile denied exec for phase 0 probe tools (`ss`, `psql`, `redis-cli`, `getent`) and repo-local `scripts/ai/aqd`; the denied `aqd --version` pipeline ran under `set -euo pipefail`, aborting `_aq-qa-bash` before JSON emission. The coordinator handler also parsed empty stdout as `{}`, hiding the root cause.
  Severity: high
  Action: Added explicit AppArmor exec rules for the phase 0 probe tools, made the `aqd` version probe failure-tolerant, and changed `/qa/check` JSON parsing to report `parse_error: aq-qa produced empty stdout` when subprocess output is empty. Requires NixOS rebuild/switch to activate the profile changes.
  File: nix/modules/services/mcp-servers.nix; scripts/ai/_aq-qa-bash; ai-stack/mcp-servers/hybrid-coordinator/extensions/mcp_handlers.py

[PENDING-REBUILD] observability-parity — Gemini Phase 149 completion claim missed schema drift, raw reasoning leakage, weak QA, dashboard logic gaps, and local-subprocess telemetry coverage — Root cause: implementation added runtime event labels and raw `<think>` extraction without updating the canonical schema/fixture, producing a planning event producer, protecting chain-of-thought, or adding behavior-level QA. The dashboard still lacked acceptable agent logic observability and live telemetry had no thought/planning events before activation. Post-rebuild live smoke also showed the local subprocess delegate branch returns before the HTTP-path telemetry producer in the deployed Nix-store copy.
  Severity: high
  Action: First corrective slice implemented: safe reasoning summary events, raw `<think>` stripping, shared coordinator route-planning events for HTTP and local subprocess paths, schema/fixture repair, dashboard thought/planning filters/rendering, sandboxed HTML previews, and behavioral 0.10.2 QA. Pending rebuild/live smoke and richer dashboard summary tiles.
  File: .agents/plans/OBSERVABILITY-PARITY-CONSENSUS-REVIEW.md

## IN-FLIGHT

[IN-FLIGHT] flat-collaboration-disabled — desired flat model-team workflow is documented but not enabled/enforced — Root cause: `config/local-agent-config.yaml` still has `multi_agent_collaboration: false` and `config/workflow-automation.yaml` still has `collaborative_workflows: false`, while active Gemini/direct paths can write PRD/policy artifacts without proposal, cross-review, consensus, validation-state, or reviewer separation gates.
  Severity: high
  Action: Added first-pass `aq-flat-prd-gate` and aq-qa 0.10.6 to require at least two model proposals, two cross-reviews, and consensus PRD/slice/decision artifacts before a topic can be treated as integrated consensus. Broad collaboration flags remain disabled until direct delegation artifacts and validation evidence gates are reliable.
  File: scripts/ai/aq-flat-prd-gate; scripts/testing/test-flat-prd-gate.py; config/local-agent-config.yaml; config/workflow-automation.yaml; .agents/prompts/FLAT_MODEL_TEAM_PRD_PROTOCOL.md

## RESOLVED / DONE

[DONE] local-agent/store-memory-contract — Local agent capability test retried `store_memory` because the tool schema advertised `context_type` as note/decision/observation while the coordinator requires canonical memory tiers; `milestone` failed with `memory_store_invalid` before retrying as episodic.
  Severity: medium
  Action: Updated local `store_memory` schema to expose canonical memory tiers, added alias normalization for legacy context labels including milestone->episodic, and added aq-qa/focused-CI coverage as 0.10.14.
  File: ai-stack/local-agents/builtin_tools/ai_coordination.py; scripts/testing/test-local-agent-store-memory-contract.py; scripts/testing/harness_qa/phases/phase0.py; scripts/ai/_aq-qa-bash

[DONE] pre-push/failure-mode-check — `git push` was blocked by quick lint "Known failure-mode checks" after host facts became local-only. Root cause: host defaults still imported ignored `facts.nix` unconditionally, so pure flake source evaluation failed; once fixed, the checker also exposed context-bearing `ExecStart` eval fragility.
  Severity: high
  Action: Made host `facts.nix` imports optional, changed npm security monitor `ExecStart` to `lib.escapeShellArgs`, and updated `check-dryrun-failure-modes.sh` to disable eval-cache and read `ExecStart` via JSON.
  File: nix/hosts/hyperd/default.nix; nix/hosts/nixos/default.nix; nix/hosts/sbc-minimal/default.nix; nix/modules/services/mcp-servers.nix; scripts/testing/check-dryrun-failure-modes.sh

[DONE] agent-memory/state — Raw training-loop outputs and agent state surfaces lacked a single authority registry, letting agents confuse local runtime state, curated memory, RAG facts, old planning summaries, and raw feedback artifacts.
  Severity: medium
  Action: Added `config/agent-memory-surface-registry.json`, documented `docs/operations/agent-memory-state-standard.md`, untracked local training-loop outputs, and wired `scripts/testing/test-agent-memory-surface-registry.py` into aq-qa 0.10.8 plus validation registry.
  File: config/agent-memory-surface-registry.json; docs/operations/agent-memory-state-standard.md; scripts/testing/test-agent-memory-surface-registry.py

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

[DONE-2026-06-10] dashboard/health-spider — Dashboard AppArmor denials degraded operator visibility while health-spider and auto-remediate did not catch/fix it promptly — Root cause: health-spider only checked `/api/health` every 7200s and auto-remediate only parsed `aq-qa 0`; dashboard passive firewall/status polling also attempted `sudo` reads under AppArmor, creating denial noise.
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

[DONE] local-delegation-artifact — delegate-to-local reported a task id and output path that could not be found afterward — Root cause: dispatch.py registered the task inside dispatch_task(), so an OOM-kill or import crash before that point left the ID unreachable. Phase 159 fix: pre-register in main() before dispatch_task(), add pre_registered=True guard to skip duplicate write.
  Severity: high
  Action: Moved registry.append()/record_dispatch() to main() before dispatch_task(); added pre_registered param to dispatch_task(); added aq-qa 0.10.9 regression coverage.
  File: scripts/ai/lib/dispatch.py; scripts/testing/test-local-delegation-artifact.py

[DONE] health-spider-systemd-coverage — aq-health-spider returned clean while `nix-optimise.service` was failed — Root cause: health-spider only checked declared HTTP zones and their service state on HTTP failure, so unrelated failed systemd units were invisible to the spider/dashboard health path.
  Severity: high
  Action: Added a global `systemctl --failed --no-legend --no-pager` probe that emits telemetry/attention and makes `aq-health-spider --once` fail when failed units exist. Inspected the live `nix-optimise.service` error (`missing ...coffeescript-2.7.0-npm-deps.drv`), reset the stale failed state, rejected the now-cleared attention item with evidence, and revalidated `systemctl --failed`, `aq-alerts --count`, `/brief`, and `aq-health-spider --once` as clean.
  File: scripts/ai/aq-health-spider; scripts/testing/test-boot-stability-regressions.py

[DONE-2026-06-11] software-factory-readiness — Resolved by Phase 150-153: CandidateLifecycleManager state machine, trust scoring engine, eval sandbox, aq-review CLI, aq-propose, dashboard /api/aistack/candidate-pipeline, and 108/108 QA checks. 14 candidates scored and active in pipeline.
  File: .agents/plans/WORLD_CLASS_SOFTWARE_FACTORY_READINESS_RESEARCH.md

## Software Factory Readiness Gaps (Phase 150)

- [ ] **Candidate Siloing:** Knowledge sources imported via `sync-knowledge-sources` are stored in AIDB but do not automatically surface as candidates in `candidates.json`.
- [ ] **Lack of Eval Sandbox:** No restricted runtime environment exists to safely test new tools or models before adoption.
- [ ] **Manual Scoring:** Trust and relevance scoring for new tools/research is currently human-mediated and non-deterministic.
- [ ] **Disconnected Governance:** Proposal and review workflows for candidates are not linked to the candidate lifecycle state.
- [ ] **Dashboard Invisibility:** The candidate pipeline (proposed -> evaluated -> adopted) is not visible to operators in the Command Center.
- [ ] **Stale Model Catalog:** The model catalog remains a static Python file, disconnected from the research discovery loop.
- [ ] **Missing Trust Provenance:** Knowledge in AIDB lacks a clear trust-tier and license-posture metadata that can drive autonomous decision-making.

[DONE] model-catalog-freshness — local model catalog is static and likely stale for current model velocity — Root cause: `ai-stack/mcp-servers/shared/model_catalog.py` contains hardcoded model specs and `config/model-profile.json` had a last-updated/probed timestamp but no freshness gate that forces review when model catalogs, local GGUF, or provider model capabilities drift.
  Severity: medium
  Action: Added catalog/profile freshness metadata, dashboard `/api/models.freshness`, Model Lifecycle freshness rows, focused CI coverage, and aq-qa 0.10.5; refreshed discovery candidates so stale model-catalog work no longer appears after validation.
  File: ai-stack/mcp-servers/shared/model_catalog.py; config/model-profile.json; dashboard/backend/api/routes/models.py; assets/dashboard.js; scripts/testing/test-model-catalog-freshness.py

[DONE] discovery-agent-stub — proactive discovery agent was not doing opportunity analysis yet — Root cause: `ai-stack/local-agents/discovery_agent.py` declared `discover_opportunities()` but only logged and `pass`ed, so idle discovery could not surface query gaps, routing failures, tokenomics regressions, or research candidates as actionable work.
  Severity: medium
  Action: Implemented deterministic local-signal scanner that emits dashboard-compatible `.agents/improvement/candidates.json` from issues backlog, health-spider events, delegation feedback, and stale model-profile metadata. Added focused regression coverage, focused-CI registry entry, and aq-qa 0.10.4.
  File: ai-stack/local-agents/discovery_agent.py

[DONE] agent-artifact-distribution — local day-to-day agent artifacts are tracked as repo state — Root cause: live collaboration, attention, delegation, comms, telemetry, and host facts files were tracked, so new deployments could inherit stale locks, local routing history, active-session context, and host-specific hardware facts.
  Severity: high
  Action: Added distribution policy, local-only ignore rules, collaboration templates, and aq-qa/focused-CI gate 0.10.7; untracked local runtime artifacts and host facts with `git rm --cached` while preserving local copies.
  File: .gitignore; docs/operations/agent-artifact-distribution-policy.md; scripts/testing/test-agent-artifact-policy.py

[DONE] dashboard-logic-discipline-no-data — Logic Discipline tile reported 100% without backend metric — Root cause: `assets/dashboard.js` used `analytics.logic_discipline_rate ?? 100` while `/api/insights/routing/analytics` did not produce `logic_discipline_rate`, hiding missing telemetry and making the error threshold unreachable (`<90` warning checked before `<70` error).
  Severity: high
  Action: Added backend `logic_discipline` summary from delegation-feedback JSONL, exposed nullable `logic_discipline_rate`, rendered `--` on missing data, made the `<70` error threshold reachable, and verified live `/api/insights/routing/analytics` returns sample/failure/score telemetry.
  File: dashboard/backend/api/services/ai_insights.py; assets/dashboard.js; dashboard.html

[DONE] manual-rebuild-source-backed-dashboard-reload — manual `nixos-rebuild switch` left command-center-dashboard-api serving stale repo-backed Python code until an explicit privileged restart — Root cause: the dashboard API unit runs from the repo path, so source-only backend edits are not activated by a plain NixOS switch unless the unit is restarted; unprivileged `systemctl start/reset-failed` can also hang on authorization.
  Severity: medium
  Action: Added a health-spider semantic routing-analytics probe with required `logic_discipline` keys so stale dashboard backends are detected as degraded, surfaced to attention/telemetry/RAG, and validated by boot-stability regression coverage. Manual source-only backend edits still require privileged service restart for activation.
  File: nix/modules/services/command-center-dashboard.nix; nixos-quick-deploy.sh; scripts/ai/aq-health-spider

[DONE-2026-06-11] token-usage-coverage-gap — coordinator token_usage events had null token counts (19/378 = 5% coverage) — Root cause: `body.get("usage")` omits the usage block for streaming/SSE responses; token counts defaulted to 0 then None. Additionally, no model_call event was emitted by the coordinator (only planning + token_usage), causing cross-source metric mismatch with race-harness model_call events.
  Severity: medium
  Action: Phase 149 fix in ai_coordinator_handlers.py: (1) emit model_call event per delegation with estimated tokens (char_count//4 fallback); (2) token_usage now uses same fallback — no_data_reason="estimated" when API omits usage block. Added aq-qa check 0.10.2 + test-token-usage-coverage.py measuring coordinator model_call token coverage ≥50%. Requires coordinator service restart to activate.
  File: ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py

[DONE] aq-alerts-json-contract — `aq-alerts --json` printed the human table instead of machine-readable JSON — Root cause: the CLI usage and downstream agent workflow expected JSON, but `scripts/ai/aq-alerts` had no `--json` argparse option and always rendered the table unless `--count` was used.
  Severity: medium
  Action: Added `--json` output with `{pending, alerts}` and regression coverage using an isolated `ATTENTION_QUEUE_DIR`.
  File: scripts/ai/aq-alerts; scripts/testing/test-aq-alerts-json.py

[DONE] local-subprocess-instruction-discipline — local coordinator delegate ignored exact-output instruction during smoke, then first remediation disabled capabilities too broadly — Root cause: `/control/ai-coordinator/delegate` with `profile=local-tool-calling`, `max_tokens=32`, and task "Return exactly PLANNING_SMOKE_OK" originally returned meta-reasoning text instead of the requested literal. Gemini's first Phase 150 fix forced `tools_enabled=false` and `thinking_mode=off` for all exact-output tasks, which made the smoke pass by trimming capabilities; follow-up commit 173b5f50 restored exact-output tool/reasoning capability unless the task is explicitly tool-free.
  Severity: medium
  Action: Hardened 0.10.3 to assert exact-output tasks do not disable tools/thinking unless explicitly tool-free; wired dashboard logic-discipline metric to delegation-feedback telemetry instead of defaulting missing data to 100%; rebuilt, restarted dashboard API with sudo, and verified live smoke plus aq-qa 0.
  File: ai-stack/agents/runtimes/local_agent_runtime.py; ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py

[DONE] health-spider-dashboard-semantic-coverage — dashboard showed operator-visible degradation while aq-health-spider reported clean cycles — Root cause: the spider only probed broad dashboard endpoints and did not validate the specific card payload semantics for OSI layer readiness, RAGAS faithfulness, operator audit integrity, or degraded child service statuses inside aggregate health.
  Severity: high
  Action: Added dashboard semantic probes for `/api/health/layered`, `/api/eval/trend`, `/api/audit/operator/integrity`, and child statuses in `/api/health/aggregate`; added regression coverage so enabled faithfulness with missing/zero values, OSI 0/0 pending, unsealed audit chains, and degraded service children surface as `dashboard_degraded` alerts.
  File: scripts/ai/aq-health-spider; scripts/testing/test-boot-stability-regressions.py

[DONE] switchboard-health-metrics-blocking — dashboard aggregate marked ai-switchboard degraded while switchboard `/health` returned 200 — Root cause: switchboard `/health` synchronously included optional llama.cpp `/metrics`, which can block behind active local inference for ~4s and exceed the dashboard aggregate probe budget.
  Severity: medium
  Action: Changed switchboard `/health` to use a sub-second optional metrics probe while preserving immediate semaphore/active-request telemetry; added regression coverage.
  File: ai-stack/switchboard/switchboard.py; scripts/testing/test-boot-stability-regressions.py

[DONE] dashboard-osi-aq-qa-opaque-exit — OSI layer health stayed pending and dashboard logs only reported `aq-qa exited 126` — Root cause: dashboard `qa_runner.py` discarded stdout/stderr for unexpected aq-qa exit codes, making service confinement/environment failures impossible to diagnose from logs.
  Severity: medium
  Action: Include stderr/stdout snippets in unexpected aq-qa RuntimeError messages and cover the diagnostic contract in boot-stability regression checks. Direct host `aq-qa 0 --json` passes, while dashboard service execution used `/run/current-system/sw/bin/aq-qa`; added the exact AppArmor ix rule for that symlink path. Requires rebuild to validate live OSI cache population.
  File: dashboard/backend/api/services/qa_runner.py; nix/modules/services/mcp-servers.nix; scripts/testing/test-boot-stability-regressions.py

[DONE] ragas-faithfulness-null-render — dashboard rendered RAGAS faithfulness as `0.0%` when faithfulness scoring produced no non-null samples in the latest trend window — Root cause: `/eval/trend` exposed total eval `sample_count` but not non-null faithfulness sample count, so the frontend could not distinguish "0 score" from "not scored / unavailable".
  Severity: medium
  Action: Added `faithfulness_sample_count` to global and per-model RAGAS trend output, rendered faithfulness as `N/A` when no faithfulness samples exist, and made health-spider alert on enabled scoring with `faithfulness_sample_count=0`.
  File: ai-stack/mcp-servers/hybrid-coordinator/eval_runner.py; assets/dashboard.js; scripts/ai/aq-health-spider; scripts/testing/test-ragas-faithfulness-guard.py

[DONE] aq-approve-apparmor-already-committed — approving an AppArmor alert after manually committing the proposed rule failed instead of resolving the alert — Root cause: `aq-approve` always delegated to `apparmor-fix-agent --commit-staged`, and the fixer tried to `git add` ignored `.agent/collaboration/HANDOFF.md`, violating the local-artifact ignore policy.
  Severity: medium
  Action: `aq-approve` now resolves AppArmor alerts when all proposed rules are already present in `mcp-servers.nix`; `apparmor-fix-agent` only stages `HANDOFF.md` when it is not ignored or is already tracked.
  File: scripts/ai/aq-approve; scripts/automation/apparmor-fix-agent.py; scripts/testing/test-boot-stability-regressions.py

## DEFERRED — requires hardware, external investigation, or multi-phase project work
## (not valid targets for grep-[OPEN] self-improvement slices)

[DEFERRED] hardware — ROCm not available on Renoir APU (gfx90c) — no code fix possible
  Severity: info (hardware constraint)
  Note: ACCELERATE PRD assumed ROCm. Renoir iGPU (gfx90c) not a supported ROCm target.
  rocminfo absent. llama-cpp runs Vulkan only. Baseline 2.71 tok/s.
  Action: requires discrete RDNA2+ GPU. Deferred until hardware upgrade.

[DEFERRED] agentic-mind — cross-model workflow standardization — multi-phase PRD project
  Severity: high (but requires Phase 148 envelope + corpus + evaluator — not a slice fix)
  Action: defer to dedicated phase. References: .agent/PROJECT-AGENTIC-MIND-STANDARDIZATION-PRD.md

[DEFERRED] desktop-input — post-build cursor/text input instability (gens 697-700, Jun 8)
  Severity: high (but gen 701, Jun 10, appears stable — may be self-resolved by rebuild)
  Action: pre-rebuild checklist: close VSCodium, capture journalctl -u cosmic-session,
  compare ~/.config/cosmic/ shortcut configs between generations.
  Note: gen 701 stable; defer until next rebuild shows regression.

[DONE] stagnation-detect-varied-loop — agent burned 50 calls on hardware issue with no progress; stagnation not triggered because varied run_command commands changed result prefix
  Root cause: iter 12 picked [OPEN] hardware (first in file, now DEFERRED), tried .agent/PROJECT-ACCELERATE-PRD.md
  (not found), then varied grep/find/ls patterns 40+ times. Each command was slightly different,
  resetting the ring buffer. Same file returned ok=False 3+ times across 50 calls.
  Fix: Added _failed_reads dict to agent_executor execute_task loop. If the same read_file path
  returns ok=False >= 3 times in a session, abort with "File-not-found stagnation" message.
  File: ai-stack/local-agents/agent_executor.py (_failed_reads dict + FAILED_READ_LIMIT check)
