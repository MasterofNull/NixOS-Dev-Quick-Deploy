# Harness-First Task Evidence

Date: 2026-10-09
Task ID: HF-20261009-030

## Objective
- Plan items ci-1 and ci-4.
- **ci-1, root cause:** the writer (repo `.agents/telemetry/aq-usage.jsonl`) and the reader (`/var/lib/.../aq-usage.jsonl`) used different files. The shim was sourced by only 1 of ~190 aq-* scripts (aq-qa), and agents call aq-* directly, bypassing the logging router.
- **ci-1, fix:** a one-line hook in 185 aq-* scripts (a bash shim; aq_usage.py for Python). It does one O_APPEND line per call and never logs argument values. The kill switch AQ_USAGE_TELEMETRY=0 and the router double-log guard still apply. The audit reads the repo ledger, and prefers it once it covers at least 10 tools.
- **ci-4:** a deterministic `aq-capability-index` produces docs/agent-guides/CAPABILITY-INDEX.md (386 entries, 29.7KB) and config/capability-index.json. They are wired into the tooling manifest (`capability_index`, in the default top-6), a progressive-disclosure `capability-reuse` domain, and the hint rule `check_capability_index_before_new_code`.

## Workflow/Session IDs
- Session ID: c30f6c3c-e25f-4e8e-8ce5-b4faa7687d3f

## Delegation Decision
- Sonnet implementer. The orchestrator syntax-checked all 187 codemodded files (0 bad) and smoke-ran aq-hints, aq-rsi and aq-capability-audit (all logged).

## Commands Executed
```bash
python3 scripts/testing/test-aq-usage-logging.py; test-capability-index.py; test-capability-audit.py (12 OK); test-aq-router.sh (ALL PASS); test-tooling-manifest.py; check-agent-instruction-parity.py OK
bash -n / py_compile over 187 changed scripts   # 0 failures
```

## Validation Evidence
- Re-audit: UNDISCOVERABLE 114 → 3 (the remaining 3 are systemd units of external MCPs). Instruction files are untouched (23888 / 23900 of 24000 bytes).

## Rollback Plan
- Revert the commit, or set AQ_USAGE_TELEMETRY=0 to stop logging.

## Residual Risk
- Exit codes are not logged (an EXIT trap would clobber the host script's traps). Worktree runs log to their own ledger unless AQ_USAGE_LEDGER is set. config/capability-index.json (~80KB) may be picked up by config scanners.

## Hint Feedback
- None.
