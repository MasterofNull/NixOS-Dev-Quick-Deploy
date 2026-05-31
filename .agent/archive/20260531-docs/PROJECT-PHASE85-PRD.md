# Phase 85 PRD — PAEA Phase 2: Drop Zone Daemon + Intent Lock v2

**Status**: APPROVED FOR EXECUTION
**Date**: 2026-05-30
**Authored by**: Claude Sonnet 4.6 (Orchestrator)
**Architecture Review**: Gemini CLI (Architect) — panels ut1gch + ue1mpq
**Phase**: 85 / PAEA Phase 2

---

## Objective

Activate the second tier of the Persistent Autonomous Execution Architecture:
1. **Drop Zone Daemon** (`aq-drop-daemon`) — filesystem-watched intake for async background task dispatch
2. **Intent Lock v2** — TTL + heartbeat + agent identity on PENDING.json for multi-agent fault recovery
3. **CLI helper** (`aq-drop`) — single-command drop submission

These components transform the agent from reactive (user-triggered) to proactive (AFK intake), delivering the highest autonomy-per-day of any Phase 85 candidate.

---

## Phase 85 Slices

### Slice A — Drop Zone Directory Bootstrap & Schema

**Files touched**: `.agents/drops/` (dir), `.gitignore`

- Create directory tree: `.agents/drops/`, `.agents/drops/archive/`, `.agents/drops/failed/`
- `.gitignore`: track the dirs but not their contents (`*.drop.yaml` excluded from commit noise)
- Drop file schema (`.drop.yaml`):
  ```yaml
  objective: "Brief task description"    # required
  prompt: "Full detailed instructions"   # required
  role: "implementer|architect|reviewer" # required
  mode: "auto|agent|hybrid|direct"       # default: auto
  priority: 1-10                         # default: 5
  ttl_s: 3600                            # lock validity; default: 3600
  tags: []                               # optional metadata
  ```
- Schema validation: `pydantic` model `DropSpec` in `scripts/ai/lib/drop_spec.py`
- Security: reject any `prompt` field containing shell meta-characters `$(`, `` ` ``, `&&`, `||`, `;` at validation stage (OWASP injection)

### Slice B — `aq-drop-daemon` Core

**Files touched**: `scripts/ai/aq-drop-daemon`

- Python script, shebang `#!/usr/bin/env python3`
- Polling loop: 2s interval via `time.sleep(2)`
- Atomicity: `fcntl.flock` on `.agents/drops/.lock` during each scan cycle
- Dispatch flow:
  1. Glob `.agents/drops/*.drop.yaml` (sorted by mtime, oldest first)
  2. Parse + validate via `DropSpec`
  3. Call `dispatch_task()` from `scripts/ai/lib/dispatch.py` directly (no shell-out)
  4. On success: `os.rename(drop_file, archive_path)` (atomic)
  5. On validation failure: `os.rename(drop_file, failed_path)` + log error
- GC pass every 60 cycles (120s): scan `PENDING.json` for expired locks (`heartbeat_at + ttl_s * 1.5 < now`) → release via `task_registry.release_expired_locks()`
- Logging: structured JSON to stdout (picked up by systemd journal)
- Signals: handle `SIGTERM` cleanly (flush lock, exit 0)

### Slice C — Intent Lock v2

**Files touched**: `scripts/ai/lib/task_registry.py`

Extend `PENDING.json` task schema with:
```json
{
  "claimed_by":   "hostname-pid",
  "claimed_at":   "ISO-8601",
  "ttl_s":        3600,
  "heartbeat_at": "ISO-8601"
}
```

New functions:
- `acquire_lock(task_id, agent_id, ttl_s)` → bool
  - Task free (no `claimed_by`) OR `now > heartbeat_at + ttl_s * 1.5` → acquire
  - Uses existing `fcntl` lock around PENDING.json write
- `release_expired_locks()` → list[str] of released task IDs
- `heartbeat(task_id, agent_id)` → bool (updates `heartbeat_at`)

Heartbeat thread in `dispatch.py` `DirectRunner`:
- Background `threading.Thread(daemon=True)` updating `heartbeat_at` every `ttl_s / 3` seconds
- Thread started on dispatch, stopped on completion/error

### Slice D — `aq-drop` CLI Helper

**Files touched**: `scripts/ai/aq-drop`

```bash
#!/usr/bin/env bash
# Usage: aq-drop "prompt text" [--role implementer] [--mode auto] [--priority 5]
# Writes a .drop.yaml to .agents/drops/ and prints the filename.
```

- Parses `--role`, `--mode`, `--priority`, `--ttl` flags
- Generates UUID-named `.drop.yaml`
- Prints confirmation: `Dropped: .agents/drops/<uuid>.drop.yaml`

### Slice E — NixOS Service

**Files touched**: `nix/modules/services/drop-daemon.nix`, `nix/modules/roles/ai-stack.nix`

```nix
# nix/modules/services/drop-daemon.nix
{ config, pkgs, lib, ... }:
let cfg = config.services.ai-drop-daemon; in {
  options.services.ai-drop-daemon.enable = lib.mkEnableOption "AI Drop Zone Daemon";
  config = lib.mkIf cfg.enable {
    systemd.services.ai-drop-daemon = {
      description = "AI Drop Zone Daemon — watches .agents/drops/ for task files";
      wantedBy = [ "multi-user.target" ];
      after = [ "ai-hybrid-coordinator.service" ];
      serviceConfig = {
        Type = "simple";
        User = "hyperd";
        WorkingDirectory = "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy";
        ExecStart = "${pkgs.python3}/bin/python3 scripts/ai/aq-drop-daemon";
        Restart = "on-failure";
        RestartSec = "5s";
      };
    };
  };
}
```

- Wire `services.ai-drop-daemon.enable = true` in `nix/modules/roles/ai-stack.nix` alongside other AI services
- Add to `imports` in `nix/modules/roles/ai-stack.nix`

### Slice F — aq-qa Check

**Files touched**: `scripts/testing/harness_qa/phases/phase0.py`

New check `check_drop_daemon`:
- Verifies `ai-drop-daemon.service` is `active`
- Verifies `.agents/drops/`, `.agents/drops/archive/`, `.agents/drops/failed/` exist + writable
- Level: L1 (unit existence)

### Slice G — Dashboard Panel

**Files touched**: `dashboard.html`, `assets/dashboard.js`

New "Drop Zone" card in the AI Services tab:
- **Daemon status**: active/inactive badge
- **Queued**: count of `*.drop.yaml` in `.agents/drops/`
- **Archived**: count in `.agents/drops/archive/`
- **Failed**: count + last error (red badge if > 0)
- Backend route: `GET /api/aistack/drops/status` → `{daemon_active, queued, archived, failed, last_error}`

**Files touched**: `dashboard/backend/api/routes/aistack.py`

---

## Acceptance Criteria

| ID | Criterion |
|----|-----------|
| AC1 | Dropping valid YAML → task in PENDING.json within 3s |
| AC2 | Killed agent PID → lock expires, next daemon GC cycle requeues |
| AC3 | Two concurrent daemon instances → no double-dispatch (flock) |
| AC4 | `aq-qa 0` reports failure if `ai-drop-daemon.service` is inactive |
| AC5 | `task_registry.py list` shows `claimed_by` identity |
| AC6 | Dashboard Drop Zone card shows live queued/archived/failed counts |
| AC7 | `aq-drop "prompt"` writes valid YAML and daemon picks it up within 3s |

---

## Security Checklist (OWASP Agentic Top 10)

- [ ] Prompt field sanitized: reject `$(`, `` ` ``, `&&`, `||`, `;` at schema validation
- [ ] `dispatch_task()` called via Python import, not shell — no injection surface
- [ ] `.agents/drops/` dir owned by `hyperd`, mode `700`
- [ ] `aq-drop` validates `--role` against allowlist `{implementer,architect,reviewer,orchestrator}`
- [ ] `claimed_by` = `hostname + pid` — no secret material in lock identity
- [ ] `ttl_s` max enforced: cap at 86400s (24h) to prevent zombie locks

---

## Execution Order

```
Slice A → Slice B → Slice C → Slice D → Slice E → Slice F → Slice G → validate → commit
```

All slices in one PR. NixOS rebuild required after Slice E.

---

## Definition of Done

- `aq-qa 0`: 68+ checks PASS (new check_drop_daemon adds 1)
- Dashboard Drop Zone card showing live data
- `aq-drop "test prompt"` round-trip verified
- Intent lock TTL/heartbeat verified via unit test or manual kill test
- Tier0 gate passes
- Committed with `feat(paea): drop zone daemon + intent lock v2`
