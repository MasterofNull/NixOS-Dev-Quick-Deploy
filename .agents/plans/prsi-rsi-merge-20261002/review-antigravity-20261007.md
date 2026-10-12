# Independent Review: PRSI / RSI Merge Wave 2 Branches

- **Reviewer**: Antigravity (independent, non-author)
- **Date**: 2026-10-07
- **Target Subject**: Origin branches merged into `main` (`1d6ca16b`..`139535c7`)

---

## 1. fix/rsi-dispatch-skip-deterministic-producers-20261007

### Scope
Skip non-agentic incident producers (e.g. `github-code-scanning:nix-closure`) in `cmd_rsi_dispatch` and expand Claude quota detection regex to catch weekly limit resets.

### Analysis & Code Verification
- **Quota Regex (`scripts/automation/prsi-orchestrator.py:980`)**:
  `_LANE_UNAVAILABLE = re.compile(r"hit your (?:\w+ )?limit|quota cooldown active|rate limit(ed)? exceeded", re.I)` correctly matches `"You've hit your weekly limit · resets 2am (America/Los_Angeles)"` as verified by unit test `test_claude_weekly_limit`.
- **Deterministic Producer Skip (`scripts/automation/prsi-orchestrator.py:1082-1117, 1195-1206`)**:
  `_rsi_non_agentic_filter` correctly extracts `producer` from `_RSI_INCIDENTS`, matches exact or `prefix:*` wildcards against `non_agentic_producers`, sets `row["execution"]["result"] = "skipped_deterministic_lane"`, increments skip counters, and saves queue state via `_merge_save(queue, candidates, ("execution",))`.
- **Data Integrity & State**:
  Row status remains `rsi_pending` so external deterministic automation can resolve the underlying CVE incident without agent token spend.

### Follow-ups
- **`scripts/testing/test-rsi-repair-lane.py:32-44` / `scripts/testing/test-rsi-lane-quota.py`**:
  *Failure scenario*: When run on a development or CI host where `.agents/delegation/.codex-quota-cooldown` exists, `_lane_cooldown_until("codex")` reads the live cooldown file because `AQ_DELEGATION_DIR` is not mocked/isolated in `setUp`. Tests fail with `AssertionError: 0 != 1` (`output["executed"] == 0`).
  *Recommendation*: Set `AQ_DELEGATION_DIR` to a temporary directory or mock `_lane_cooldown_until` in test fixtures.

**VERDICT**: `PASS_WITH_FOLLOWUPS`

---

## 2. fix/optimizer-override-reload-20261007

### Scope
Prevent failed `sudo systemctl restart` invocations from unprivileged optimizer process (`NoNewPrivileges=true`) by delegating environment reload to a root-level systemd path unit watching `overrides.env`.

### Analysis & Code Verification
- **Optimizer Code (`scripts/ai/aq-optimizer:92-107, 148-167`)**:
  `_write_overrides` compares existing file contents against new content before writing, returning `False` on identical content. For services in `_OVERRIDE_RELOAD_CONSUMERS` (`ai-hybrid-coordinator`, `ai-switchboard`), outcome is set to `reload_declared` without invoking any subprocess calls. Non-consumers report `applied_pending_restart`.
- **Systemd Declarations (`nix/modules/roles/ai-stack.nix:2450-2472`)**:
  - `systemd.paths.ai-optimizer-overrides-reload` watches `PathChanged = "${mutableOptimizerDir}/overrides.env"` and triggers `ai-optimizer-overrides-reload.service`.
  - Service runs as root with `Type = "oneshot"` and executes `systemctl try-restart ai-hybrid-coordinator.service ai-switchboard.service`.
  - Rate limiting via `StartLimitIntervalSec = 300` and `StartLimitBurst = 3` protects against restart loops.
- **Data Integrity & Stability**:
  `try-restart` restarts services only if already active, avoiding unintended service activation. Content change check prevents spurious inotify reloads. All 6 unit tests in `test-optimizer-override-reload.py` pass.

**VERDICT**: `PASS`

---

## 3. chore/prsi-archive-legacy-paths-20261007

### Scope
Migrate runtime state and purge audit log defaults from legacy `/var/lib/nixos-ai-stack/prsi/` to canonical `/var/lib/nixos-ai-stack/optimizer/prsi/`.

### Analysis & Code Verification
- **Path Consistency (`hints_engine_impl.py`, `aq-delegate`, `aq-prsi-review`, `prsi-orchestrator.py`, `check-prsi-budget-discipline.sh`)**:
  All default paths for `PRSI_STATE_PATH` and `PRSI_PURGE_AUDIT_LOG` now point to `/var/lib/nixos-ai-stack/optimizer/prsi/runtime-state.json` and `/var/lib/nixos-ai-stack/optimizer/prsi/purge-audit.jsonl`.
- **Static Verification (`scripts/testing/test-prsi-queue-path-ssot.py`)**:
  Test suite thoroughly asserts canonical paths across scripts, verifies Nix declarations in `ai-stack.nix`, and scans the repository for any legacy path regressions. Script runs clean and exits 0.
- **Risk Assessment**:
  Zero risk of split-brain queue or state files between optimizer and orchestrator.

**VERDICT**: `PASS`

---

## 4. feat/memory-crystallizer-real-sessions-20261007

### Scope
Extract and distill atomic facts from real Claude Code, Codex, and Continue session transcripts via local LLM into MemoryBroker semantic memory, bounded by a nightly systemd service (≤10 sessions/night, last 25 hours).

### Analysis & Code Verification
- **Transcript Extraction (`ai-stack/mcp-servers/hybrid-coordinator/memory_crystallizer.py:18-107`)**:
  `_extract_history` parses Claude Code JSONL (`obj["type"] in {"user", "assistant"}`), Codex JSONL (`obj["type"] == "response_item"`), and Continue JSON (`obj["history"]`). Text blocks are properly extracted, thinking/tool blocks handled gracefully, message length clamped to 1,200 chars, and the window capped to the latest 20 messages.
- **Distillation Bounding & Idempotency (`memory_crystallizer.py:165-208, 210-268`)**:
  SHA256 session hash deduplicates runs via `crystallized_sessions` table in Postgres / in-memory cache. Distillation prompt constrains local Qwen output to 3-10 bullet facts. Facts under 10 chars are filtered out.
- **Test Coverage**:
  13 pytest tests in `test_memory_crystallizer_sessions.py` and `test_memory_crystallizer.py` pass 100%.

### Concrete Defects & Follow-ups
1. **Defect — Non-session metadata consumption of session budget (`scripts/ai/aq-crystallize:47-51`)**:
   - *File:Line*: `scripts/ai/aq-crystallize:49`
   - *Failure scenario*: In `~/.claude/projects/`, subagent metadata files (`*.meta.json`) and project indices (`sessions-index.json`) match the `*.json` find pattern. When sorted by mtime, these metadata files consume up to 30–50% of the `--max-sessions 10` quota (e.g. 3 of the 10 files in live dry-run were `*.meta.json`). This starves actual session transcripts (`*.jsonl`) from being processed.
   - *Remediation*: Exclude metadata and index patterns in the find command: `find "${dir}" -type f \( -name '*.json' -o -name '*.jsonl' \) ! -name '*.meta.json' ! -name '*index*.json'`.
2. **Defect — Context field `crystallized_from` resolves to None (`memory_crystallizer.py:244-248`)**:
   - *File:Line*: `ai-stack/mcp-servers/hybrid-coordinator/memory_crystallizer.py:245`
   - *Failure scenario*: `context={"crystallized_from": metadata.get("session_id") if metadata else "unknown", ...}` looks up `"session_id"`, but caller at line 177 only passes `metadata={"session_path": str(path), "session_hash": session_hash}`. Because `"session_id"` is absent, `crystallized_from` is always stored as `None` instead of the session path or hash.
   - *Remediation*: Fallback to `metadata.get("session_id") or metadata.get("session_path") or metadata.get("session_hash")`.
3. **Performance Inefficiency (`scripts/ai/aq-crystallize:42-53`)**:
   - *File:Line*: `scripts/ai/aq-crystallize:42-53`
   - *Failure scenario*: The script first gathers all hundreds of session files across all time, then iterates over each file individually spawning `find "${session_path}" ... | wc -l` (650+ subprocess forks taking ~4.3s).
   - *Remediation*: Pass `-mmin "-$(( SINCE_HOURS * 60 ))"` directly to the initial directory `find` invocation.

**VERDICT**: `PASS_WITH_FOLLOWUPS`

---

## Verdict Summary

VERDICT fix/rsi-dispatch-skip-deterministic-producers-20261007 PASS_WITH_FOLLOWUPS
VERDICT fix/optimizer-override-reload-20261007 PASS
VERDICT chore/prsi-archive-legacy-paths-20261007 PASS
VERDICT feat/memory-crystallizer-real-sessions-20261007 PASS_WITH_FOLLOWUPS
