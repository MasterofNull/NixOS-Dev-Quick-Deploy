# Phase 86: Human-in-the-Loop Alert System Design Document

## 1. Goal & Concept
The current system executes autonomous dispatches (`aq-drop-daemon`) and structural auto-commits (`apparmor-fix-agent`) without human intervention. This poses significant security and stability risks. Phase 86 implements a terminal-first, structured approval layer. 
The system will route high-risk/high-autonomy actions to a central spool. A human operator will review these via a new CLI (`aq-alerts`) and explicitly approve or reject them.

## 2. Autonomy Boundaries
Alerts and tasks are classified by their required autonomy boundary:
- `auto_ok`: System handled it autonomously. Informational notification only.
- `rebuild_required`: System staged a change (e.g., modified a Nix file), but requires human `nixos-rebuild` to activate.
- `human_gate`: System proposes an action, but MUST NOT execute it without explicit human approval.

## 3. Data Schema & Lifecycle
**Location:** `.agents/attention/ATTENTION.json`
*Using a dedicated directory for standard isolation, matching the pattern of `.agents/drops` and `.agents/telemetry`.*

**Lifecycle:**
1. **Creation:** Agents (spider, drop-daemon, fix-agent) acquire an exclusive lock via `fcntl.flock`, append the alert, and release the lock.
2. **Notification:** A zsh hook or background daemon notifies the human.
3. **Review:** Human runs `aq-alerts` to view pending alerts.
4. **Action:** Human runs `aq-approve <alert_id>` or `aq-reject <alert_id>`.
5. **Resolution:** Alert status is updated to `approved`/`rejected`. If approved, the payload is executed.
6. **Archive:** Completed alerts are moved/archived to maintain a lean active queue.

**Schema (`ATTENTION.json`):**
```json
{
  "version": "1.0",
  "alerts": {
    "al-12345678": {
      "source": "apparmor-fix-agent",
      "timestamp": "2026-05-30T10:00:00Z",
      "severity": "high",
      "boundary": "human_gate",
      "title": "AppArmor Fix Proposal: command-center-dashboard-api",
      "description": "Auto-added 3 rules. Needs review before commit.",
      "payload": {
         "action_type": "apparmor_fix",
         "rules_proposed": ["/sys/devices/** r,"],
         "profile": "command-center-dashboard-api",
         "denials_trigger": ["/sys/devices/system/cpu/"]
      },
      "status": "pending"
    }
  }
}
```

## 4. Required File Changes

### New Files
- `scripts/ai/aq-alerts`: CLI to list pending items from `ATTENTION.json`.
- `scripts/ai/aq-approve`: CLI to approve and execute the payload of an alert.
- `scripts/ai/aq-reject`: CLI to reject an alert.
- `scripts/ai/lib/attention.py`: Shared library for thread-safe read/write to `ATTENTION.json` using `fcntl`.
- `.agents/plans/PHASE-86-HITL-DESIGN.md`: This design document.

### Modified Files
- `scripts/automation/apparmor-fix-agent.py`: 
  - *Change*: Remove `_git_commit` and immediate `_push_memory_fact`. Instead, formulate the proposed rules and push an alert to `attention.py` with boundary `human_gate`.
  - *Risk*: The payload execution logic must be transferred to `aq-approve`.
- `scripts/ai/aq-health-spider`:
  - *Change*: Ensure it correctly triggers `apparmor-fix-agent` but understands that the fix is now asynchronous/pending approval. It should not log "Fix committed".
- `scripts/ai/aq-drop-daemon`:
  - *Change*: Identify drops that exceed standard safety constraints (e.g., highly destructive drops, mode `agent` drops when `DROP_ALLOW_AGENT=false`) and push them to `ATTENTION.json` for approval rather than failing them immediately.
- `nix/modules/services/mcp-servers.nix` & `nix/modules/roles/ai-stack.nix`:
  - *Change*: Add AppArmor rules or service configs if we deploy an alert daemon or add permissions for `aq-alerts`.

### Dead Code / Orphaned Features
- `apparmor-fix-agent.py`'s `_git_commit` function will be orphaned unless relocated to a shared library for `aq-approve`.
- The synchronous "wait for fix" logic in `aq-health-spider._fix_apparmor` will be orphaned because fixes are now deferred.

## 5. Concurrency Strategy
- **File**: `.agents/attention/ATTENTION.json`
- **Locking**: Python `fcntl.flock(fd, fcntl.LOCK_EX)` strictly used for ALL reads and writes inside `lib/attention.py`.
- **Mitigation**: Writers must hold the lock for `< 50ms`. We use atomic reads/writes on the JSON structure.

## 6. Shell / System Integration
- **Zsh Hook**: Provide a snippet for `.zshrc` (e.g., in `cli-enhanced.sh`) that checks `ATTENTION.json` on prompt rendering (`precmd`), printing a tiny indicator (e.g., `[ 🔔 2 PENDING ALERTS ]`) if pending `human_gate` items exist.
- **Desktop Notifications**: `lib/attention.py` can invoke `notify-send "AI Stack: Attention Required"` via `subprocess` when a high-severity alert is logged.

## 7. QA Checks for Phase 86
1. **86.1 `attention_schema_valid`**: Ensure `ATTENTION.json` schema is parseable and valid.
2. **86.2 `lock_contention_safe`**: Spawn 10 background writers to `attention.py`, ensure exactly 10 alerts are recorded safely without corruption.
3. **86.3 `apparmor_gates_correctly`**: Run `apparmor-fix-agent` with mock denials, verify no git commit occurs and `ATTENTION.json` gets a `human_gate` alert.
4. **86.4 `aq_approve_executes`**: Verify `aq-approve` successfully applies a mocked `human_gate` payload (e.g., applying the AppArmor fix and committing).

## 8. Documentation Gaps
- `AGENTS.md`: Must be updated to state that agents cannot auto-commit structural fixes anymore; they must propose them via `ATTENTION.json`.
- `WORKFLOW-CANON.md`: Update the Execute step to require the HITL gate for sensitive operations.

## 9. Top 3 Implementation Risks
1. **Risk**: Payload execution mapping in `aq-approve`.
   *Mitigation*: Use strict `action_type` identifiers in the payload. `aq-approve` uses a dispatch table to hardcoded handler functions (e.g., `handle_apparmor_fix(payload)`), preventing arbitrary code execution.
2. **Risk**: Concurrency corruption of `ATTENTION.json`.
   *Mitigation*: Mandate that NO script parses the JSON directly. They MUST import and use `lib/attention.py` which enforces the `fcntl` lock on the file descriptor.
3. **Risk**: `ATTENTION.json` becomes a graveyard of stale alerts.
   *Mitigation*: `aq-alerts` should visually flag stale items (> 48h). Future phases can implement an auto-archive or TTL daemon.
