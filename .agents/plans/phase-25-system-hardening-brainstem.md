# Phase 25 — System Hardening & Brain-Stem Completion

## Context
This document is a handoff for a new agent session. Read it fully before acting.
Phase 24 (impeccable + tradingagents integration) is structurally complete but has
uncommitted drift, a broken dev workflow, and several identified security/safety gaps.

---

## System State at Handoff

### ✅ Done & Committed
- `auto_tool_select_handlers.py` — `/skills/list`, `/skills/{slug}/content`, `/tools/auto-select`, `/tools/catalog`
- `trading_handlers.py` — `/trading/analyze`, `/trading/forecast`, `/trading/debate`, `/trading/history`, `/trading/tools`
- `tooling_manifest.py` — impeccable + trading keyword blocks in `workflow_tool_catalog()`
- `aq-delegate` — universal tool catalog + impeccable + trading context blocks injected
- `docs/agent-guides/50-TOOL-SELECTION-MATRIX.md` — full matrix published
- `.agent/skills/impeccable/SKILL.md` and `.agent/skills/tradingagents/SKILL.md` — canonical skill files
- `ai-stack/trading-agents/` — full 5-team pipeline (analysts, researchers, trader, risk, portfolio)
- `aq-qa` phases 0–10: 39 pass, 0 fail, 1 skip (last known clean state)

### ⚠️ Uncommitted Working Tree Drift
Two files modified but not yet committed (confirmed via `git diff`):

1. **`scripts/ai/mcp-bridge-hybrid.py`** (+170 lines)
   - 8 new MCP tool definitions: `list_skills`, `get_skill_content`, `auto_select_tools`,
     `tool_catalog`, `trading_analyze`, `trading_forecast`, `trading_tools`, `impeccable_design`
   - Corresponding `_call_tool()` handlers for all 8

2. **`scripts/ai/skills/impeccable.skill.md`**
   - Updated synopsis to HTTP-first invocation
   - Fixed canonical skill path reference (`.agent/skills/impeccable/SKILL.md`)

### ❌ Broken (Active Regression)
**`~/.continue/config.json` is broken** — commit `d1561d6b` was reverted. The
home-manager rewrite left only "Continue Local (Primary)" which throws 503.
`aq-qa 0` check `0.5.2` is currently **FAILING**.

Root cause: `nix/home/base.nix` controls Continue config via home-manager. The
previous hand-edited `~/.continue/config.json` had the full model roster; when
home-manager took ownership it replaced everything with a minimal single-model entry.

The `aq-qa` `_continue_config_ok()` function validates:
- `__configVersion` ∈ `{23.0, 24.0, 25.0}`
- A model with `apiBase = "http://127.0.0.1:8085/v1"` + correct `contextLength` + `maxTokens`
- A model with `X-AI-Profile: continue-local` header
- `tabAutocompleteModel` pointing to switchboard ingress (`:8085/v1`)
- Context provider `name: aq-hints`, `endpoint: http://127.0.0.1:8003/hints`

Fix: restore the full model roster inside the nix home module so it survives
every `home-manager switch`. Do NOT hand-edit `~/.continue/config.json`.

### ⏳ Pending Execution (scripts exist, never run)
- `scripts/ai/ingest-impeccable-references.sh` → AIDB project `impeccable-design` (≥30 docs)
- `scripts/ai/ingest-trading-knowledge.sh` → AIDB project `trading-knowledge` (≥10 docs)
- `python3 scripts/ai/aq-sync-shared-skills.py` → syncs `.agent/skills/` into AIDB registry

### 🔴 Security / Safety Gaps (confirmed, not yet implemented)
See Section III below for full designs.

---

## Task List (Ordered by Priority)

### P25-001 — Commit Phase 24 Residual Drift
```
python3 -m py_compile scripts/ai/mcp-bridge-hybrid.py
python3 -m py_compile scripts/ai/skills/impeccable.skill.md  # N/A — bash -n for .md
git add scripts/ai/mcp-bridge-hybrid.py scripts/ai/skills/impeccable.skill.md
git commit -m "feat(mcp-bridge): add Phase 24 tool discovery + skill registry tools

- list_skills, get_skill_content: agent-agnostic skill registry via MCP
- auto_select_tools, tool_catalog: tool discovery without explicit naming
- trading_analyze, trading_forecast, trading_tools: financial analysis pipeline
- impeccable_design: design intelligence command with AIDB reference retrieval
- Fix impeccable.skill.md canonical path + HTTP-first synopsis"
```

### P25-002 — Fix Continue Config (Unblocks aq-qa 0.5.2)
1. Read current state: `cat ~/.continue/config.json | python3 -m json.tool | head -80`
2. Read current nix home module: `cat nix/home/base.nix | grep -A 50 'continue'`
3. Restore the full model roster in the nix home module (not hand-edited)
4. Apply: `home-manager switch`
5. Verify: `aq-qa 0` — check `0.5.2` must PASS

### P25-003 — AIDB Ingestion + Skill Registry Sync
```bash
# Run after confirming services are healthy (aq-qa 0)
bash scripts/ai/ingest-impeccable-references.sh
bash scripts/ai/ingest-trading-knowledge.sh
python3 scripts/ai/aq-sync-shared-skills.py

# Verify
curl -s http://127.0.0.1:8002/documents?project=impeccable-design \
  | python3 -c "import json,sys; print(json.load(sys.stdin).get('total',0))"
# Expected: ≥ 30

curl -s http://127.0.0.1:8002/documents?project=trading-knowledge \
  | python3 -c "import json,sys; print(json.load(sys.stdin).get('total',0))"
# Expected: ≥ 10
```

### P25-004 — SafeCommandExecutor (Agent Immune System)
Create `ai-stack/mcp-servers/hybrid-coordinator/safe_command_executor.py`:

```python
"""Code-level guardrail for all agent terminal command execution."""
import re, json, time
from pathlib import Path
from typing import Tuple

BLOCKLIST = [
    r"\brm\s+-rf\b",
    r"\bdd\s+if=",
    r"\bmkfs\b",
    r"\bchmod\s+777\b",
    r"\bgit\s+push\s+.*--force\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bsudo\s+rm\b",
    r"\btruncate\b.*--size=0",
    r"\bshred\b",
    r">\s*/dev/sd[a-z]",
]

AUDIT_LOG = Path("/var/log/nixos-ai-stack/agent-commands.jsonl")

def check_command(command: str) -> Tuple[bool, str]:
    for pattern in BLOCKLIST:
        if re.search(pattern, command, re.IGNORECASE):
            _log(command, allowed=False, blocked_by=pattern)
            return False, f"Blocked by safety policy (pattern: {pattern})"
    _log(command, allowed=True, blocked_by=None)
    return True, "ok"

def _log(command: str, allowed: bool, blocked_by):
    try:
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_LOG, "a") as f:
            f.write(json.dumps({
                "ts": time.time(), "command": command[:512],
                "allowed": allowed, "blocked_by": blocked_by,
            }) + "\n")
    except OSError:
        pass
```

Wire into `mcp-bridge-hybrid.py` `run_terminal_command` handler:
```python
from safe_command_executor import check_command
# At top of handler:
ok, reason = check_command(command)
if not ok:
    return _format_result({"error": reason, "blocked": True})
```

Add aq-qa check:
```bash
# In run_phase_5():
_check "5.7.1" "safe_command_executor importable" \
  python3 -c "import sys; sys.path.insert(0,'${REPO_ROOT}/ai-stack/mcp-servers/hybrid-coordinator'); import safe_command_executor"
```

### P25-005 — Nix Simulation Tools (MCP)
Add two new tools to `mcp-bridge-hybrid.py` TOOLS list:
- `simulate_nix_change` — runs `nix build .#<derivation> --dry-run` via `_run_local()`
- `validate_service_config` — runs `nix eval .#<option-path>` via `_run_local()`

Both go through `SafeCommandExecutor.check_command()` before subprocess invocation.
Both are flagged as REQUIRED steps in `AUTONOMOUS-OPERATIONS-POLICY.md` before any
autonomous `.nix` file modification.

### P25-006 — Agent Safety Test Suite
Create `scripts/testing/test-agent-safety.sh`:
- Posts adversarial prompts through the system and asserts they are blocked
- Adversarial cases: `rm -rf`, `git push --force`, `sudo rm -rf`, `delete all logs`
- Each test asserts response body contains `"blocked": true` or `"safety policy"`
- Integrated into `aq-qa` as phase `5.8`

### P25-007 — Context Summarization Endpoint
Create `ai-stack/mcp-servers/hybrid-coordinator/context_summary_handlers.py`:
- `POST /agent/summarize-context` — accepts `{history: [...], max_tokens: 2000}`
- Calls local LLM to compress history into a structured summary
- Returns `{summary: "...", key_decisions: [...], open_questions: [...]}`

Register route in `http_server.py`.

Add MCP tool `summarize_context` to `mcp-bridge-hybrid.py`.

Create `working_memory.json` sidecar pattern:
- Agents write key findings to `~/.agent/working_memory.json` between tool calls
- Read it back at session start to avoid re-scanning full history
- Format: `{session_id, timestamp, key_facts: [...], decisions: [...], next_steps: [...]}`

---

## III. Security Gap Designs (Reference)

### Gap 1: Guardrail Illusion
- **Problem**: `run_terminal_command` in `mcp-bridge-hybrid.py` executes any command
- **Fix**: P25-004 above — `SafeCommandExecutor` with pattern blocklist + audit log

### Gap 2: Flake Eval Performance
- **Problem**: `check-package-count-drift.sh` runs full flake eval unconditionally
- **Fix**: Add `--changed-only` flag that skips eval when no `*.nix` files changed:
  ```bash
  # Insert before ${GENERATOR} call:
  if [[ "${CHANGED_ONLY:-false}" == "true" ]]; then
    changed_nix=$(git diff --name-only HEAD -- '*.nix' 2>/dev/null || true)
    if [[ -z "$changed_nix" ]]; then
      echo "No .nix files changed — skipping package count eval."
      exit 0
    fi
  fi
  ```

### Gap 3: Context Window Trap
- **Problem**: Long agent sessions accumulate raw tool output with no compression
- **Fix**: P25-007 above — `/agent/summarize-context` endpoint + `working_memory.json` sidecar

### Gap 4: No Simulation Before Nix Edits
- **Problem**: Agents edit `.nix` files and commit without any build validation
- **Fix**: P25-005 above — `simulate_nix_change` + `validate_service_config` MCP tools

### Gap 5: No Adversarial Agent Tests
- **Problem**: No test suite validates that safety guardrails actually block attacks
- **Fix**: P25-006 above — `test-agent-safety.sh` + aq-qa phase 5.8

---

## IV. Key File Locations (Quick Reference)

```
scripts/ai/mcp-bridge-hybrid.py              MCP stdio bridge (TOOLS list + _call_tool)
scripts/ai/aq-delegate                        Context injection for sub-agents
scripts/ai/aq-qa                              QA phase runner (phases 0-10)
scripts/ai/aq-sync-shared-skills.py          Skill registry AIDB sync
scripts/ai/ingest-impeccable-references.sh   AIDB ingestion for impeccable-design project
scripts/ai/ingest-trading-knowledge.sh        AIDB ingestion for trading-knowledge project
ai-stack/mcp-servers/hybrid-coordinator/
  auto_tool_select_handlers.py               /skills/*, /tools/* routes
  trading_handlers.py                        /trading/* routes
  tooling_manifest.py                        Keyword → tool matching
  http_server.py                             Route registration (large file, ~28k tokens)
  prompt_injection.py                        Existing prompt injection scanner
ai-stack/trading-agents/                     5-team trading pipeline (Python package)
.agent/skills/impeccable/SKILL.md            Canonical impeccable skill (all agents)
.agent/skills/tradingagents/SKILL.md         Canonical tradingagents skill (all agents)
docs/agent-guides/50-TOOL-SELECTION-MATRIX.md Agent-agnostic tool catalog
nix/home/base.nix                            Home-manager config (LARGE — controls Continue)
docs/operations/AUTONOMOUS-OPERATIONS-POLICY.md Autonomous ops policy
```

## V. Validation Gates (Run Before Committing Anything)

```bash
# Syntax check all modified Python files
python3 -m py_compile scripts/ai/mcp-bridge-hybrid.py
python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/safe_command_executor.py

# QA smoke (must be 0 failures before and after changes)
aq-qa 0

# After all P25 tasks complete:
aq-qa all
# Expected: ≥ 39 pass, 0 fail (was 39/0/1 before P25)
