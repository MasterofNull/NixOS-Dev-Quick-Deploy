# Editor State Recovery Runbook

Status: Active
Owner: AI Harness Team
Last Updated: 2026-05-08

## Overview

This runbook covers recovery from IDE freeze, oversized editor-local agent state, and
Continue/Codex extension failures. The canonical recovery tool is `aq-editor-rescue`.

## Symptom Triage

| Symptom | Likely cause | Go to |
|---------|-------------|-------|
| VSCodium freezes on workspace open | Oversized Continue session or Gemini/Qwen state | [Section: Extension State Overflow](#extension-state-overflow) |
| Continue context limit errors mid-session | Active session file too large | [Section: Continue Session Growth](#continue-session-growth) |
| Codex extension fails to load or migrate | Stale local state DB migration | [Section: Codex State DB Reset](#codex-state-db-reset) |
| aq-qa check `0.5.2` fails | Continue config version stale after repair | [Section: Continue Config Regeneration](#continue-config-regeneration) |
| Extension host crashes repeatedly | Multiple root causes — run full rescue | [Section: Full Rescue Workflow](#full-rescue-workflow) |

---

## Full Rescue Workflow

Run `aq-editor-rescue` to checkpoint, diagnose, and optionally repair in one command.

### Plan mode (checkpoint + diagnose, no repair)

```bash
aq-editor-rescue --task "VSCodium freeze after large Continue session"
```

Output sections:
- **Checkpoint**: harness memory record of current slice state
- **aq-report**: editor corpus sizes (Continue session, Gemini/Qwen state, stale markers)
- **aq-qa phase 0**: pass/fail count; lists QA failures and recommended next actions
- **Fresh-session resume**: commands to start a clean editor session from memory

### Execute mode (checkpoint + diagnose + repair)

```bash
aq-editor-rescue --task "VSCodium freeze" --execute
```

This runs `vscodium-repair` in addition to checkpointing. `vscodium-repair` performs:
- Archives oversized Continue sessions (keeps last 2 hot sessions)
- Prunes Gemini/Qwen global state payloads
- Clears stale `.obsolete` extension markers
- Backs up and resets the Codex local state DB

### With Continue config regeneration

Use `--regenerate-continue-config` when aq-qa reports `0.5.2` failing (Continue config
version stale after repair):

```bash
aq-editor-rescue --task "VSCodium freeze" --execute --regenerate-continue-config
```

This runs `home-manager switch --flake .` after repair to regenerate `~/.continue/config.json`,
then re-runs `aq-qa 0` to confirm 0.5.2 passes before printing resume commands.

Custom regeneration command (if home-manager path differs):
```bash
aq-editor-rescue --task "VSCodium freeze" --execute \
  --regenerate-continue-config \
  --regenerate-command "home-manager switch --flake /path/to/repo"
```

### JSON output for scripting

```bash
aq-editor-rescue --task "describe failure" --format json | jq .summary
```

Key fields in `.summary`:
- `state_budget`: Continue editor corpus health from aq-report
- `qa_phase_0`: `{passed, failed, skipped}` counts
- `qa_failures`: list of `{id, description}` for failed checks
- `next_actions`: ordered remediation steps based on failure pattern
- `repair.ok`: whether vscodium-repair succeeded
- `regenerate_continue_config.ok`: whether home-manager regeneration succeeded

### Inspect recent rescue loops

`aq-editor-rescue` now writes compact JSONL telemetry to
`/var/lib/ai-stack/hybrid/telemetry/editor-rescue-history.jsonl`. `aq-report`
surfaces that as `editor_rescue_windows`.

Quick inspection:
```bash
aq-report --format json | python3 -c "
import json, sys
d = json.load(sys.stdin)
for label, summary in ((d.get('editor_rescue_windows') or {}).get('windows') or {}).items():
    if not summary.get('available'):
        continue
    print(label, 'runs=', summary.get('samples'),
          'final_ok_pct=', summary.get('final_ok_pct'),
          'qa_healthy_pct=', summary.get('qa_healthy_pct'),
          'top_qa_failures=', summary.get('top_qa_failures'))
"
```

Use this when freezes keep recurring and you need to distinguish:
- state-budget drift (`continue_hot_corpus`, stale markers)
- stale Continue config after repair (`0.5.2`)
- repeated rescue attempts against the same task signature

---

## Extension State Overflow

**Symptoms**: VSCodium freezes at startup; extension host crash loop; `aq-qa 0.5.7` fails.

**Check corpus sizes**:
```bash
aq-report --format json | python3 -c "
import json, sys
d = json.load(sys.stdin)
eb = (d.get('continue_editor') or {}).get('state_budget') or {}
print('Continue corpus:', eb.get('total_size_bytes', 'n/a'), 'bytes')
print('Budget checks:', eb.get('passed_n'), '/', eb.get('total_checks'))
"
```

**Repair**:
```bash
aq-editor-rescue --task "Extension state overflow — corpus size exceeded budget" --execute
```

**Archive paths** (created automatically by vscodium-repair):
- Continue sessions: `~/.continue/sessions-backup-<timestamp>/`
- Hot sessions retained: last 2 by modification time

**Rollback** (if repair is too aggressive):
```bash
# Restore archived Continue sessions
ls ~/.continue/sessions-backup-*/
cp -r ~/.continue/sessions-backup-<timestamp>/* ~/.continue/sessions/

# Restart VSCodium
vscodium
```

---

## Continue Session Growth

**Symptoms**: `message exceeds context limit` in Continue chat; session file > 8 MiB.

**Detect**:
```bash
du -sh ~/.continue/sessions/*.json | sort -rh | head -10
```

**Checkpoint current session state before archiving**:
```bash
aq-editor-rescue --task "Continue session too large — context limit errors"
```

**Archive manually** (without full repair):
```bash
BACKUP=~/.continue/sessions-backup-$(date +%Y%m%d-%H%M%S)
mkdir -p "$BACKUP"
# Move all but the 2 most recent sessions
ls -t ~/.continue/sessions/*.json | tail -n +3 | xargs mv -t "$BACKUP"
```

**Start a fresh Continue session** using the resume commands from `aq-editor-rescue` output.

---

## Codex State DB Reset

**Symptoms**: Codex extension fails to load; migration error in extension host logs.

**Check**:
```bash
sqlite3 ~/.codex/state_5.sqlite "PRAGMA integrity_check;" 2>&1 | head -5
```

**Reset** (vscodium-repair handles this automatically):
```bash
aq-editor-rescue --task "Codex extension migration failure" --execute
```

vscodium-repair backs up the DB before reset:
```
~/.codex/state_5.sqlite.pre-vscodium-repair-<timestamp>
```

**Rollback**:
```bash
cp ~/.codex/state_5.sqlite.pre-vscodium-repair-<timestamp> ~/.codex/state_5.sqlite
```

---

## Continue Config Regeneration

**Symptoms**: `aq-qa 0.5.2` fails — "Continue config targets switchboard ingress".

This happens when vscodium-repair rewrites the Continue config but the declarative
home-manager version hasn't been applied yet, leaving the config at an older schema version.

**Check**:
```bash
python3 -c "import json; d=json.load(open('/home/hyperd/.continue/config.json')); print(d.get('__configVersion'))"
```

Valid versions: 23.0 – 30.0.

**Fix**:
```bash
home-manager switch --flake /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
```

Or use the integrated flag:
```bash
aq-editor-rescue --task "Continue config stale after repair" --execute --regenerate-continue-config
```

**Verify**:
```bash
aq-qa 0 2>&1 | grep "0\.5\.2"
```

---

## Validation Sequence

After any recovery action:

```bash
# 1. Confirm editor-state budgets are within bounds
aq-qa 0 --json | python3 -c "
import json, sys
d = json.load(sys.stdin)
fails = [t for t in (d.get('tests') or []) if t.get('status') == 'FAIL']
print(f\"Passed: {d.get('passed')} Failed: {d.get('failed')}\")
for f in fails:
    print(f\"  FAIL {f['id']}: {f.get('description','')}\")
"

# 2. Relaunch VSCodium and open the workspace
vscodium /home/hyperd/Documents/NixOS-Dev-Quick-Deploy

# 3. Confirm extension host is stable (no crash loop in first 30s)
journalctl --user -u vscodium.service --since "30 seconds ago" -n 20 2>/dev/null || \
  journalctl -xe | grep -i "vscodium\|extension-host" | tail -10
```

---

## Rollback Reference

| What was changed | Backup location | Restore command |
|-----------------|-----------------|-----------------|
| Continue sessions | `~/.continue/sessions-backup-<ts>/` | `cp -r ~/.continue/sessions-backup-<ts>/* ~/.continue/sessions/` |
| Codex state DB | `~/.codex/state_5.sqlite.pre-vscodium-repair-<ts>` | `cp <backup> ~/.codex/state_5.sqlite` |
| Gemini/Qwen state | Not archived (pruned in-place) | Recreated on next extension load |
| Continue config | Regenerated via home-manager | `home-manager switch --flake .` (idempotent) |

---

## Related Documentation

- `scripts/ai/aq-editor-rescue --help` — full flag reference
- `docs/operations/CONTEXT-LIMIT-HANDLING.md` — context-limit handling and slice-boundary checkpoint rule
- `docs/development/IDE-AGENT-STATE-STABILITY-PDR-2026-05-08.md` — problem statement and design rationale
- `scripts/ai/vscodium-repair` — low-level repair steps
