# S5 — Durable delegation artifact guard

## 1. Objective and acceptance

Implement J5: all four delegation wrappers reject volatile or outside-root prompt files before checking existence, with a `.agents/delegation/` recovery pointer. Guard derived delegation directories and explicit output overrides, and move local-review prompts to durable storage.

## 2. Discovery and reuse

Inspected the owned shared resolvers, wrapper prompt gates, local-review temporary-file call, existing sandbox environments, and CI manifest. Reused the git-common-dir main-root resolver and existing `AQ_ALLOW_VOLATILE_DIR=1` test escape hatch. No new dependencies or services.

## 3. Plan and scope

Add matching Bash/Python path validators, integrate the four wrappers, move the production prompt producer, adjust only existing volatile test environments, add J5 regressions, and register CI coverage. Only the twelve assigned surfaces are changed. Plan and progress were recorded in the delegation conversation; shared PULSE/RESUME files were excluded by the explicit scope lock.

## 4. Implementation

Resolve symlinks and parent traversal before validating artifact paths. Reject `/tmp`, `/var/tmp`, and `/dev/shm` even when supplied as allowlisted roots. Permit only resolved nonvolatile delegation, main-repository plan, and Claude persistent temporary roots.

Preserve the resolver contract: derived volatile delegation directories require `AQ_ALLOW_VOLATILE_DIR=1`; explicit `AQ_DELEGATION_DIR` remains the caller's choice for isolated test fixtures. Wrapper startup uses that explicit override without artifact validation. Prompt-file validation remains strict in all four wrappers, including when the explicit delegation override itself is volatile. Codex also validates explicit `DELEGATE_OUTPUTS_DIR`.

Preserve local prompt absolute-path conversion and local-review `finally` cleanup. Allocate local-review prompts in `AQ_DELEGATION_DIR/outputs/local-review`. The ten guard regressions cover derived-directory refusal and escape hatch, explicit volatile delegation compatibility, prompt refusal across all four wrappers with durable and volatile overrides, symlink escapes, and explicit volatile output refusal.

## 5. Verification commands and output

All twelve requested commands passed in this worktree. Full captured output and exit codes follow; warnings and fixture diagnostics are retained.

```text
$ bash -n scripts/ai/lib/delegation-dir.sh scripts/ai/delegate-to-codex scripts/ai/delegate-to-gemini scripts/ai/delegate-to-local scripts/ai/delegate-to-claude
(no output)
exit: 0
```

```text
$ shellcheck scripts/ai/lib/delegation-dir.sh
(no output)
exit: 0
```

```text
$ python3 -m py_compile scripts/ai/lib/delegation_dir.py scripts/ai/aq-local-review scripts/testing/test-no-tmpfs-guard.py scripts/testing/test-brief-caps.py scripts/testing/test-delegate-wrapper-shell-safety.py
(no output)
exit: 0
```

```text
$ ruff check scripts/ai/lib/delegation_dir.py scripts/ai/aq-local-review scripts/testing/test-no-tmpfs-guard.py scripts/testing/test-brief-caps.py scripts/testing/test-delegate-wrapper-shell-safety.py
All checks passed!
exit: 0
```

```text
$ basedpyright scripts/ai/lib/delegation_dir.py scripts/testing/test-no-tmpfs-guard.py
0 errors, 0 warnings, 0 notes
exit: 0
```

```text
$ python3 scripts/testing/test-no-tmpfs-guard.py
.WARN: git unavailable; delegation dir falls back to script-relative path
.........
----------------------------------------------------------------------
Ran 10 tests in 2.653s

OK
exit: 0
```

```text
$ python3 scripts/testing/test-brief-caps.py
[aq-agent-loop] Task: aq-1795721001-68d886
[aq-agent-loop] Objective: [HARNESS CONTEXT]
# Harness Grounding Supplement (canonical SSOT — all agents)

This file is injected into every agent d...
[aq-agent-loop] Tool calls: progress-guarded (no fixed ceiling)
[aq-agent-loop] Fallback: disabled (local only)
[aq-agent-loop] Running...


[aq-agent-loop] Status:     completed
[aq-agent-loop] Elapsed:    1.3s
[aq-agent-loop] Tool calls: 0

--- Result ---
COMPLETED: capped answer

[aq-agent-loop] Summary written to: /tmp/tmp055gh5uh/agent.log
/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/delegation/worktrees/codex-20261126-112230-6ysew2/scripts/testing/test-brief-caps.py:379: ResourceWarning: unclosed file <_io.BufferedReader name=4>
  ok = dispatch.AgentRunner(ROOT / "scripts/ai").run(config, "Reply with OK.", out_file, max_calls=1)
ResourceWarning: Enable tracemalloc to get the object allocation traceback
.........................
----------------------------------------------------------------------
Ran 25 tests in 11.949s

OK
exit: 0
```

```text
$ python3 scripts/testing/test-delegate-wrapper-shell-safety.py
/run/current-system/sw/bin/true: /run/current-system/sw/bin/true: cannot execute binary file
PASS registry: transactional writers, no truncation under concurrent reader
PASS wrappers: no inline registry rewrite / bash -c / discarded launch stderr
PASS codex worker: bad launch dir error preserved, status failed
PASS codex: nasty prompt byte-identical, nothing executed
PASS codex: failing launch error preserved in task log
PASS codex/full: prompt byte-identical (trailing newline kept), nothing executed
PASS codex/lean: prompt byte-identical (trailing newline kept), nothing executed
PASS codex/auto: prompt byte-identical (trailing newline kept), nothing executed
PASS gemini: nasty prompt byte-identical, nothing executed
PASS gemini: failing launch error preserved in task log
PASS gemini: yolo->auto, auto_edit->accept-edits, plan->plan, no --approval-mode
PASS gemini: noise-only output reported as 0 meaningful bytes, no arithmetic error
PASS gemini: oversize prompt rejected with clear error, provider never invoked
PASS gemini: --wait non-zero exit reaches failure handling, status failed, stderr in log
ALL PASS
exit: 0
```

```text
$ python3 scripts/testing/test-aq-land.py
.....................................................................................
----------------------------------------------------------------------
Ran 17 tests in 55.650s

OK
.....
----------------------------------------------------------------------
Ran 16 tests in 59.514s

OK
.....
----------------------------------------------------------------------
Ran 16 tests in 63.258s

OK
...........
----------------------------------------------------------------------
Ran 16 tests in 67.836s

OK
........
----------------------------------------------------------------------
Ran 17 tests in 70.329s

OK
....
----------------------------------------------------------------------
Ran 16 tests in 72.228s

OK
......
----------------------------------------------------------------------
Ran 16 tests in 77.462s

OK
......
----------------------------------------------------------------------
Ran 16 tests in 98.660s

OK
exit: 0
```

```text
$ python3 scripts/testing/test-rsi-repair-lane.py
test_gemini_rsi_is_read_only_plan_lane (__main__.IsolationPreflightTests.test_gemini_rsi_is_read_only_plan_lane) ... ok
test_missing_delegate_fails_isolation_preflight (__main__.IsolationPreflightTests.test_missing_delegate_fails_isolation_preflight) ... ok
test_supported_lanes_pass_isolation_preflight (__main__.IsolationPreflightTests.test_supported_lanes_pass_isolation_preflight) ... ok
test_claude_role_contract_validation (__main__.LaneTests.test_claude_role_contract_validation) ... ok
test_explicit_gemini_lane_fails_closed_before_launch (__main__.LaneTests.test_explicit_gemini_lane_fails_closed_before_launch) ... ok
test_incident_store_uses_environment (__main__.LaneTests.test_incident_store_uses_environment) ... ok
test_invalid_policy_lane_fails_before_launch (__main__.LaneTests.test_invalid_policy_lane_fails_before_launch) ... ok
test_lane_selection_and_execution_receipt (__main__.LaneTests.test_lane_selection_and_execution_receipt) ... ok
test_multi_lane_cooldown_fallback (__main__.LaneTests.test_multi_lane_cooldown_fallback) ... ok
test_non_agentic_producer_skipped (__main__.LaneTests.test_non_agentic_producer_skipped) ... ok
test_stale_running_reconciled_at_dispatch_start (__main__.LaneTests.test_stale_running_reconciled_at_dispatch_start) ... ok
test_strict_lane_receipts (__main__.LaneTests.test_strict_lane_receipts) ... ok
test_timeout_kills_process_group (__main__.LaneTests.test_timeout_kills_process_group) ... ok

----------------------------------------------------------------------
Ran 13 tests in 0.582s

OK
exit: 0
```

```text
$ python3 scripts/testing/test-aq-review-receipt.py
.............................................
----------------------------------------------------------------------
Ran 45 tests in 36.390s

OK
exit: 0
```

```text
$ bash scripts/governance/tier0.d/check-ci-test-coverage.sh
[tier0.d/check-ci-test-coverage] PASS (814 tests: 722 declared, 92 exempt)
exit: 0
```

### Round 3 re-verification (review `gemini-20261126-113132-8k8moq`, REQUEST_CHANGES)

Fixes: both budget fixtures that point `DELEGATE_OUTPUTS_DIR` at a temporary directory now set `AQ_ALLOW_VOLATILE_DIR=1`; the two-argument Bash `validate_durable_artifact_path` honors `AQ_DELEGATION_DIR`; seven guarded sources were added to `tests-aq.paths`. This run supersedes the earlier ten-test guard run (now eleven tests).

Before the fixes, `test-delegate-headless-budget.py` reported `5/7 tests passed` (exit 1), and the new two-argument regression failed (exit 1, `--prompt-file ... is outside durable work roots`).

`ruff check` on the budget test exits 1 with 12 findings (2 F401, 10 F541). The same counts are reported on the `4a34c13ac` version of the file and are recorded in `config/python-check-baseline.json`; this round adds none and does not clean them up.

```text
$ bash -n scripts/ai/lib/delegation-dir.sh
(no output)
exit: 0

$ shellcheck scripts/ai/lib/delegation-dir.sh
(no output)
exit: 0

$ python3 -m py_compile scripts/testing/test-delegate-headless-budget.py scripts/testing/test-no-tmpfs-guard.py
(no output)
exit: 0

$ ruff check --output-format concise scripts/testing/test-delegate-headless-budget.py scripts/testing/test-no-tmpfs-guard.py
scripts/testing/test-delegate-headless-budget.py:18:8: F401 [*] `json` imported but unused
scripts/testing/test-delegate-headless-budget.py:21:8: F401 [*] `shutil` imported but unused
scripts/testing/test-delegate-headless-budget.py:55:15: F541 [*] f-string without any placeholders
scripts/testing/test-delegate-headless-budget.py:59:15: F541 [*] f-string without any placeholders
scripts/testing/test-delegate-headless-budget.py:74:15: F541 [*] f-string without any placeholders
scripts/testing/test-delegate-headless-budget.py:167:19: F541 [*] f-string without any placeholders
scripts/testing/test-delegate-headless-budget.py:176:15: F541 [*] f-string without any placeholders
scripts/testing/test-delegate-headless-budget.py:243:15: F541 [*] f-string without any placeholders
scripts/testing/test-delegate-headless-budget.py:247:15: F541 [*] f-string without any placeholders
scripts/testing/test-delegate-headless-budget.py:250:11: F541 [*] f-string without any placeholders
scripts/testing/test-delegate-headless-budget.py:260:11: F541 [*] f-string without any placeholders
scripts/testing/test-delegate-headless-budget.py:270:11: F541 [*] f-string without any placeholders
Found 12 errors.
[*] 12 fixable with the `--fix` option.
exit: 1

$ ruff check scripts/testing/test-no-tmpfs-guard.py
All checks passed!
exit: 0

$ basedpyright scripts/testing/test-no-tmpfs-guard.py
0 errors, 0 warnings, 0 notes
exit: 0

$ python3 scripts/testing/test-delegate-headless-budget.py
PASS: harness-grounding.sh syntax valid
PASS: delegate-to-codex syntax valid
PASS: grounding DELEGATE MODE section: 459 bytes
PASS: budget parsing: 15100 tokens from 3 logs
PASS: --effort flag recognized with levels
PASS: --budget-check-only flag behavior correct
PASS: rolling window, review reserve, force-budget, next-free time

7/7 tests passed
exit: 0

$ python3 scripts/testing/test-no-tmpfs-guard.py
.WARN: git unavailable; delegation dir falls back to script-relative path
..........
----------------------------------------------------------------------
Ran 11 tests in 1.346s

OK
exit: 0

$ bash scripts/governance/tier0.d/check-ci-test-coverage.sh
[tier0.d/check-ci-test-coverage] PASS (814 tests: 722 declared, 92 exempt)
exit: 0

$ python3 -m json.tool config/ci-checks.json /dev/null
(no output)
exit: 0
```

## 6. Security and failure modes

Arguments are quoted; filesystem paths are passed as arguments rather than interpolated shell code. Prefix boundaries, parent traversal, symlink escapes, missing volatile prompts, volatile allowlist roots, and explicit volatile output overrides are covered. No secrets, URLs, ports, or dependencies were added. The environment escape hatch remains explicit and is enabled only in the existing sandbox test environments.

## 7. Activation and limitations

The existing wrapper execution paths invoke the guard immediately; no service activation or rebuild is required. Regression tests execute the real wrappers up to rejection and inspect the real local-review prompt file through a mocked inference subprocess. No live inference claim is made. All requested checks passed, including ShellCheck on the shared Bash helper. Brief-caps emits a ResourceWarning; shell-safety emits a fixture diagnostic about executing true. Their captured output and successful exit codes are preserved above. Full tier0 and independent review remain with the orchestrator, per headless instructions.

## 8. Handoff

All thirteen slice files (twelve original, plus the budget test added in round 3) are delivered as unstaged working-tree changes, including executable `test-no-tmpfs-guard.py`. No commit or staging is performed. The CI coverage check initially identified a missing `tests-aq.tests` declaration; both the path trigger and executable test list now include the new regression. No unrelated ShellCheck cleanup was attempted. Orchestrator: review this slice and run integration gates before committing.

Modified files:

- `scripts/ai/lib/delegation-dir.sh`
- `scripts/ai/lib/delegation_dir.py`
- `scripts/ai/delegate-to-codex`
- `scripts/ai/delegate-to-gemini`
- `scripts/ai/delegate-to-local`
- `scripts/ai/delegate-to-claude`
- `scripts/ai/aq-local-review`
- `scripts/testing/test-brief-caps.py`
- `scripts/testing/test-delegate-headless-budget.py`
- `scripts/testing/test-delegate-wrapper-shell-safety.py`
- `scripts/testing/test-no-tmpfs-guard.py` (new, mode 0755)
- `config/ci-checks.json`
- `docs/harness-first/evidence/2026-11-26-s5-no-tmpfs-guard.md` (new)
