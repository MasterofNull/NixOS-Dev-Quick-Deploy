# Evidence: Local Agent Tooling, IPM Polling, and `test-aq-confine` / `ai-stack-health-monitor` Fixes (2026-11-10)

## Objective
Resolve five runtime and agentic infrastructure bugs uncovered during live QA and local-agent delegation:
1. Pin `SCRATCH = tempfile.mkdtemp(prefix="aqc-test-", dir="/tmp")` in `scripts/testing/test-aq-confine.py` and raise `ai-stack-health-monitor` `MemoryMax` from `896M` to `1280M` in `nix/modules/roles/ai-stack.nix`.
2. Add `-H` (`cmd = ["grep", "-rnH", pattern, path]`) in `ai-stack/local-agents/builtin_tools/file_operations.py` so single-file searches emit `filepath:lineno:text`.
3. Exempt bounded `read_file` outputs (<16,000 chars) from `many_lines` / `html_snapshot` compaction and preserve newlines in `read_file` previews (`scripts/ai/lib/context_risk.py` & `ai-stack/local-agents/agent_executor.py`).
4. Forward `max_tool_calls=max_calls, wall_budget_s=float(timeout)` to `executor.execute_task()` in `scripts/ai/aq-agent-loop`.
5. Fix `InferenceParamManager` (`ai-stack/mcp-servers/hybrid-coordinator/inference_param_manager.py`) `_is_idle()` slot-processing check and raise `/metrics` & `/slots` poll timeout from `0.2s` to `2.0s`.

## Workflow/Session IDs
- Wave: `wave-20261110-c1`
- Implementer delegation: `codex-20261110-115855-7bttsk`

## Delegation Decision
- Delegated implementation to Codex (`scripts/ai/delegate-to-codex --role implement --mode edit`) in isolated worktree `.agents/delegation/worktrees/codex-20261110-115855-7bttsk` per Rule 17.

## Commands Executed
```bash
python3 scripts/testing/test-aq-confine.py
python3 scripts/testing/test-context-compaction-sandwich.py
python3 scripts/testing/test-ipm-thermal-thresholds.py
./scripts/governance/ci-clean-env.sh --all --only harness-first-static-gates
```

## Validation Evidence
```text
$ python3 scripts/testing/test-aq-confine.py
SUMMARY: 213 checks ran, 0 failed, 0 behavioral groups skipped (preflight: ok)

$ python3 scripts/testing/test-context-compaction-sandwich.py
PASS: context-risk routing uses switchboard artifacts and aq-context-manage resume guidance

$ python3 scripts/testing/test-ipm-thermal-thresholds.py
7/7 tests passed
```

## Rollback Plan
- Revert the squash commit on `main` and redeploy via `scripts/maintenance/aq-deploy-current`.

## Residual Risk
- `ai-stack-health-monitor` `MemoryMax = "1280M"` and `ai-hybrid-coordinator` `InferenceParamManager` changes take effect in the running systemd units on the next `aq-deploy-current` activation.

## Hint Feedback
- Live `journalctl -u llama-cpp -u ai-hybrid-coordinator` and `local-20261110-102740-22m6u5` delegation logs directly exposed the 200ms IPM timeout storm and single-file `search_files` / `read_file` compaction bugs.
