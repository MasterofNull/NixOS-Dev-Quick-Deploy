# Independent Review: PR #386 (Crystallizer Client-Side Extraction & Secret Redaction)

- **Reviewer**: Antigravity (independent, non-author)
- **Target Subject**: PR #386, branch `origin/fix/crystallizer-client-side-extraction-20261007` vs `origin/main` (`8058ffc3`..`839774c2`)
- **Changed Files**:
  - `ai-stack/mcp-servers/hybrid-coordinator/session_transcripts.py`
  - `ai-stack/mcp-servers/hybrid-coordinator/memory_crystallizer.py`
  - `ai-stack/mcp-servers/hybrid-coordinator/tests/test_memory_crystallizer_sessions.py`
  - `scripts/ai/aq-crystallize`
  - `scripts/testing/test-rsi-lane-quota.py`
  - `scripts/testing/test-rsi-repair-lane.py`

---

## Architecture & Context Verification

- **Security & Privilege Boundary**:
  - The coordinator service (`ai-hybrid-coordinator`) runs unprivileged as user `ai-hybrid` and cannot read `/home/hyperd/.claude` or user project directories (mode `0700`).
  - PR #386 shifts session transcript discovery and extraction to `aq-crystallize` (running under user `hyperd`), which extracts and redacts chat history client-side before POSTing `{history, session_hash, session_path}` to `/memory/crystalline/run`.
  - When `history` is present in the payload, the coordinator routes directly to `_crystallize_dict_payload`, which **never** opens or reads `session_path` from disk.
- **Server-Side File Access**:
  - Confirmed: zero filesystem reads performed by `_crystallize_dict_payload`. The legacy file-path branch (`_crystallize_file_session`) handles unreadable files safely by catching `(PermissionError, OSError)` and returning `{"status": "error", "reason": "unreadable_session_path"}` without crashing.
- **Deduplication & Retry Semantics**:
  - SHA256 session hash is verified against `crystallized_sessions` table / memory cache before distillation.
  - The hash is inserted **only** when distillation status is `"complete"` or `"skipped"`. On error (e.g. LLM timeout, dependency failure), the hash is not recorded, ensuring automatic retry on subsequent runs.
- **Compute & Token Bounding**:
  - Messages clamped to 1,200 chars; history capped to 20 messages; LLM completion capped to 500 tokens; facts capped to 10; nightly execution bounded by `max_sessions=10`.
- **Review Follow-up Fixes**:
  - `test-rsi-lane-quota.py` and `test-rsi-repair-lane.py` now isolate `AQ_DELEGATION_DIR` to a temporary directory in `_DELEGATION_TMP`, fixing the previous host cooldown state leak.
  - Subagent metadata (`*.meta.json`) and index files are properly skipped in discovery.
  - `crystallized_from` metadata context in `memory_crystallizer.py:248-256` now properly falls back across `session_id` -> `session_path` -> `session_hash` -> `"unknown"`.

---

## Concrete Defects

### 1. `scripts/ai/aq-crystallize:158, 168, 173, 178, 182, 193, 195` — Fatal script abort under `set -e` on initial variable increment
- **Failure Scenario**:
  `scripts/ai/aq-crystallize` initializes `selected=0; posted=0; skipped=0` (lines 151-153) under `set -euo pipefail` (line 2). In bash arithmetic `(( var++ ))`, the expression returns the *previous* value of `var`. When `var` is 0, the expression evaluates to 0, which bash evaluates as status code 1. Because `set -e` is active, the script aborts immediately with exit code 1 upon the first increment.
- **Evidence**:
  Running `/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.claude/worktrees/agent-a13465b719139b802/scripts/ai/aq-crystallize --dry-run` halts on the very first session line with exit code 1:
  ```
  + [[ 1 -eq 1 ]]
  + printf '%s\n' /home/hyperd/.claude/projects/.../c30f6c3c.jsonl
  + (( selected++ ))
  (exited with code 1)
  ```
- **Remediation**:
  Replace all `(( var++ ))` with `(( var += 1 ))`, `(( ++var ))`, or `var=$(( var + 1 ))`.

### 2. `ai-stack/mcp-servers/hybrid-coordinator/session_transcripts.py:21` — Redaction gap for GitHub Fine-Grained Personal Access Tokens
- **Failure Scenario**:
  The token redaction regex `r'gh[pousr]_[A-Za-z0-9]{20,}'` matches only classic GitHub token prefixes (`ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`). Modern GitHub fine-grained Personal Access Tokens use the prefix `github_pat_` (e.g. `github_pat_11...`). These tokens survive redaction entirely and are sent in plaintext history to the coordinator and local LLM.
- **Remediation**:
  Expand pattern: `r'(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{20,}'`.

---

## Verification Results

- `pytest` on `test_memory_crystallizer_sessions.py`: 23/23 PASSED (1.21s).
- `test-rsi-repair-lane.py`: 15/15 PASSED (0.35s).
- `test-rsi-lane-quota.py`: 19/19 PASSED (0.04s).
- `bash -n scripts/ai/aq-crystallize`: Syntax valid, but execution fails on line 158/182 due to Defect 1.

---

VERDICT REQUEST_CHANGES
