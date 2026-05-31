# Phase 86: Human-in-the-Loop Alert System PRD

## 1. Goal & Concept
The current system executes autonomous dispatches (`aq-drop-daemon`) and structural auto-commits (`apparmor-fix-agent`) without human intervention. This poses significant security and stability risks. Phase 86 implements a terminal-first, structured approval layer.
We are moving from "Auto-Dispatch" to "Propose-Then-Execute". The system will route high-risk/high-autonomy actions to a central file-based queue (`ATTENTION.json`). A human operator will review these via a new CLI suite and explicitly approve, defer, or reject them.

## 2. Autonomy Boundaries
Alerts and tasks are classified by their required autonomy boundary:
- **`auto_ok`**: System handled it autonomously. Written to archive for audit trail, never blocks.
- **`rebuild_required`**: System staged a change (e.g., modified a Nix file), pending human `nixos-rebuild` to activate.
- **`human_gate`**: System proposes an action, but MUST NOT execute it without explicit human approval via the `aq-approve` CLI.

## 3. Data Schema & Lifecycle

**Location:**
- Queue: `.agents/attention/ATTENTION.json` (Central, fcntl-locked queue)
- Archive: `.agents/attention/ATTENTION_ARCHIVE.jsonl` (Append-only completed/expired alerts)

**Lifecycle:**
1. **Creation**: Agent detects an issue and pushes to `attention_queue.py`. Duplicate checking prevents spam.
2. **Notification**: Zsh hook warns the user of pending alerts upon prompt render. Desktop notification (`notify-send`) fires for `critical` / `high` severity.
3. **Review**: Human runs `aq-alerts` to view the table and `aq-review <id>` to see details/diffs.
4. **Action**:
   - `aq-approve <id>`: Executes `executor` payload, marks `approved`, moves to archive.
   - `aq-reject <id> --reason <text>`: Marks `rejected`, moves to archive.
   - `aq-defer <id> --hours <N>`: Extends TTL, keeping it pending.
5. **GC**: Stale alerts are auto-archived upon the next queue push or via `aq-qa`.

**Unified Schema (`ATTENTION.json`):**
```json
{
  "schema_version": "1.0",
  "alerts": [
    {
      "id": "attn-<uuid4>",
      "source": "apparmor-fix-agent | health-spider | aq-drop-daemon | aq-qa",
      "severity": "critical | high | medium | low",
      "autonomy_boundary": "auto_ok | rebuild_required | human_gate",
      "title": "<80 chars summary>",
      "detail": "Full explanation string or description of issue",
      "payload": { "key": "Structured data from source (optional)" },
      "proposed_action": "Exact description of what happens on approval",
      "executor": "Optional shell cmd or Python callable string to run on approve",
      "status": "pending | approved | rejected | deferred | auto_executed | expired",
      "created_at": "ISO-8601",
      "expires_at": "ISO-8601",
      "resolved_at": null,
      "resolved_by": null
    }
  ]
}
```

## 4. File Inventory

### CREATE
- `scripts/ai/lib/attention_queue.py`: Single writer lib with `fcntl` lock, dedup logic, and GC push to archive. No direct writes to JSON allowed.
- `scripts/ai/aq-alerts`: Terminal CLI to list pending alerts (`--all`, `--count`).
- `scripts/ai/aq-review`: CLI `aq-review <id>` to show full details, diff, and proposed action.
- `scripts/ai/aq-approve`: CLI `aq-approve <id>` to mark approved, trigger `executor` payload, and move to archive.
- `scripts/ai/aq-reject`: CLI `aq-reject <id> --reason "..."` to reject.
- `scripts/ai/aq-defer`: CLI `aq-defer <id> --hours N` to extend TTL.
- `nix/modules/zsh-alert-hook.nix`: Shell hook for `aq-alerts --count` on terminal prompt.
- `.agent/PHASE-86-PRD.md`: This document.

### MODIFY
- `scripts/ai/aq-health-spider`: Replace `log.error` paths with `attention_queue.push()` for actionable findings.
- `scripts/automation/apparmor-fix-agent.py`: Remove direct `_git_commit()`. Replace with `attention_queue.push(autonomy_boundary=human_gate)`.
- `scripts/ai/aq-drop-daemon`: Divert `human_gate` drops to `attention_queue.push()` instead of executing them.
- `scripts/ai/_aq-qa-bash` & `scripts/testing/harness_qa/phases/phase0.py`: Add Phase 86 checks.
- `dashboard/backend/api/routes/aistack.py`: Add GET `/alerts/status`.
- `assets/dashboard.js` & `dashboard.html`: Add Attention card (secondary surface).
- `nix/modules/services/mcp-servers.nix`: Wire `libnotify` for `notify-send`; wire zsh hook.
- `nix/modules/roles/ai-stack.nix`: Include `zsh-alert-hook` module.
- `AGENTS.md`, `CLAUDE.md`, `.agent/GEMINI.md`, `.agent/WORKFLOW-CANON.md`: Update to reflect alert-check workflow and ban on blind auto-commits.

## 5. Concurrency Model
- **Locking**: `scripts/ai/lib/attention_queue.py` uses `fcntl.LOCK_EX` on the file descriptor for all reads and writes.
- **Retry**: Up to 3 retries with a max 50ms backoff on lock contention.
- **Safety**: `aq-approve` and `aq-reject` must acquire `LOCK_EX` and re-check `status == pending` before mutating.
- **Deduplication**: Hash `source` + `title` + `payload` on push; skip if a duplicate is already `pending`.

## 6. NixOS Shell Integration
**Zsh Hook (`nix/modules/zsh-alert-hook.nix`):**
```nix
programs.zsh.interactiveShellInit = ''
  if command -v aq-alerts &>/dev/null; then
    _aq_alert_count=$(aq-alerts --count 2>/dev/null || echo 0)
    if [[ $_aq_alert_count -gt 0 ]]; then
      echo ""
      echo "⚠  $_aq_alert_count alert(s) require your attention. Run: aq-alerts"
    fi
  fi
'';
```
**Notifications**: The queue library invokes `notify-send "AI Stack: Attention Required"` (via `subprocess`) when a `human_gate` alert with `critical` or `high` severity is logged.

## 7. QA Checks for Phase 86
- **86.1 `attention_queue_importable`**: Verify `attention_queue.py` imports cleanly.
- **86.2 `attention_json_created`**: Verify `ATTENTION.json` and `ATTENTION_ARCHIVE.jsonl` are created correctly on first push.
- **86.3 `lock_contention_safe`**: Spawn 10 concurrent subprocess writers. Verify exactly 10 alerts are recorded safely.
- **86.4 `aq_alerts_count`**: Verify `aq-alerts --count` exits 0 when empty and 1 when pending items exist.
- **86.5 `aq_approve_reject_resolution`**: Verify `aq-approve` executes payload and `aq-reject` resolves status correctly.
- **86.6 `apparmor_gates_correctly`**: Mock denials, verify no auto-commit occurs and a `human_gate` alert is queued.
- **86.7 `dashboard_endpoint_200`**: Verify `/alerts/status` endpoint returns a 200 OK.

## 8. Risk Register & Mitigations
1. **Risk:** Alert queue becomes a log graveyard nobody reads.
   **Mitigation:** `aq-alerts` is hooked into the prompt. `aq-qa` will fail if stale alerts >24h exist.
2. **Risk:** `apparmor-fix-agent` rewire breaks the only working auto-remediation.
   **Mitigation:** Use strict `executor` mapping in `aq-approve` handlers (e.g., `handle_apparmor_fix()`) to preserve the exact fix logic behind the approval gate.
3. **Risk:** Arbitrary code execution via `executor` field.
   **Mitigation:** `executor` strings must map to known, hardcoded safe callables in `aq-approve`, not raw shell `eval()` for `human_gate` actions from untrusted layers.

## 9. Implementation Sequence
1. **Slice 1:** Core Queue (`attention_queue.py`, schemas, dummy data generation, `ATTENTION.json` setup).
2. **Slice 2:** CLI Suite (`aq-alerts`, `aq-review`, `aq-approve`, `aq-reject`, `aq-defer`).
3. **Slice 3:** Agent Integration (Rewire `apparmor-fix-agent`, `aq-health-spider`, `aq-drop-daemon`).
4. **Slice 4:** NixOS Shell Integration (Zsh hook, `notify-send` for critical/high).
5. **Slice 5:** Dashboard read-only view and comprehensive QA validation.