You are a NixOS AI harness agent for NixOS-Dev-Quick-Deploy. Follow AGENTS.md and WORKFLOW-CANON.md.

## Task: Phase 30.6 — Auto-inject aq-context-bootstrap at local-agent startup

### Files to change (read them first)
1. `ai-stack/agents/runtimes/local_agent_runtime.py`
2. `ai-stack/agents/runtimes/test_local_agent_runtime.py`

### What to implement

**In local_agent_runtime.py:**

Step A — add near the other env var reads (after ~line 50):
```python
# Phase 30.6: auto-inject context-bootstrap preamble at startup
AGENT_INJECT_BOOTSTRAP = os.environ.get("AGENT_INJECT_BOOTSTRAP", "false").lower() == "true"
BOOTSTRAP_TIMEOUT = float(os.environ.get("AGENT_BOOTSTRAP_TIMEOUT", "15"))
```

Step B — add a helper function just before `run()`:
```python
def _run_bootstrap_preamble(task: str) -> str:
    """Run aq-context-bootstrap and return a compact preamble, or '' on any failure."""
    script = REPO_ROOT / "scripts" / "ai" / "aq-context-bootstrap"
    if not script.exists():
        return ""
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, str(script), "--task", task, "--format", "json"],
            capture_output=True, text=True, timeout=BOOTSTRAP_TIMEOUT,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return ""
        data = json.loads(result.stdout)
        scope = data.get("scope", "")
        cards = (data.get("recommended_cards") or [])[:3]
        preflight = (data.get("preflight_commands") or data.get("continuation_startup_commands") or [])[:1]
        parts = []
        if scope:
            parts.append(f"scope={scope}")
        if cards:
            parts.append(f"cards={','.join(cards)}")
        if preflight:
            parts.append(f"preflight={preflight[0]}")
        return "[bootstrap] " + " | ".join(parts) if parts else ""
    except Exception:
        return ""
```

Step C — in `run()`, find the block that builds `messages` (it looks like):
```python
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task_content},
        ]
```
Replace it with:
```python
        if AGENT_INJECT_BOOTSTRAP:
            _preamble = _run_bootstrap_preamble(AGENT_TASK)
            _sys = SYSTEM_PROMPT + ("\n\n[STARTUP CONTEXT] " + _preamble if _preamble else "")
        else:
            _sys = SYSTEM_PROMPT
        messages = [
            {"role": "system", "content": _sys},
            {"role": "user", "content": task_content},
        ]
```

**In test_local_agent_runtime.py:**
Add a test near the end that verifies the new module-level constants exist.
Look at how existing tests import the module and match the same pattern exactly.
The test should assert:
- `local_agent_runtime.AGENT_INJECT_BOOTSTRAP` is a bool
- `local_agent_runtime.BOOTSTRAP_TIMEOUT` is a float
- `_run_bootstrap_preamble("")` returns a str (does not raise)

### Validate after changes
```bash
python3 -m py_compile ai-stack/agents/runtimes/local_agent_runtime.py
python3 scripts/testing/test-local-agent-config.py
scripts/governance/tier0-validation-gate.sh --pre-commit
```

### Commit
```bash
git add ai-stack/agents/runtimes/local_agent_runtime.py ai-stack/agents/runtimes/test_local_agent_runtime.py
scripts/governance/tier0-validation-gate.sh --pre-commit
git commit -m "feat(local-agent): Phase 30.6 — AGENT_INJECT_BOOTSTRAP startup preamble injection

Closes behavioral gap in 30.2 + 30.4: local agent now arrives at first turn
grounded by aq-context-bootstrap signals. Defaults off; activate per-profile
by setting AGENT_INJECT_BOOTSTRAP=true in the spawner environment.

Co-Authored-By: Gemini Code Assist <noreply@google.com>"
```

### Constraints
- Default off (AGENT_INJECT_BOOTSTRAP=false) — zero behavior change unless enabled
- _run_bootstrap_preamble must never raise — all exceptions return ""
- No changes to http_server.py or switchboard.nix in this slice
- Working directory: /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
