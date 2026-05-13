## Phase 30.6 — Auto-inject aq-context-bootstrap at local-agent startup

### Objective
Wire `aq-context-bootstrap` as an automatic reflex at local-agent startup so the agent
is grounded by observed signals before its first reasoning turn — no LLM compliance required.

### Files to change
1. `ai-stack/agents/runtimes/local_agent_runtime.py`
2. `ai-stack/agents/runtimes/test_local_agent_runtime.py`

### Step 1 — Read these files first
- `ai-stack/agents/runtimes/local_agent_runtime.py` (full file)
- `ai-stack/agents/runtimes/test_local_agent_runtime.py` (full file)
- `scripts/ai/aq-context-bootstrap` (understand the output schema)

### Step 2 — Implement bootstrap injection in local_agent_runtime.py

Add at module level (near other env var reads, ~line 40):
```python
# Phase 30.6: auto-inject context-bootstrap preamble at startup
AGENT_INJECT_BOOTSTRAP = os.environ.get("AGENT_INJECT_BOOTSTRAP", "false").lower() == "true"
BOOTSTRAP_TIMEOUT = float(os.environ.get("AGENT_BOOTSTRAP_TIMEOUT", "15"))
```

Add a helper function (before `run()`):
```python
def _run_bootstrap_preamble(task: str) -> str:
    """Run aq-context-bootstrap and return a compact preamble string, or '' on failure."""
    script = REPO_ROOT / "scripts" / "ai" / "aq-context-bootstrap"
    if not script.exists():
        return ""
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, str(script), "--task", task, "--format", "json"],
            capture_output=True, text=True, timeout=BOOTSTRAP_TIMEOUT
        )
        if result.returncode != 0 or not result.stdout.strip():
            return ""
        data = json.loads(result.stdout)
        scope = data.get("scope", "")
        preflight = data.get("preflight_commands") or data.get("continuation_startup_commands") or []
        cards = data.get("recommended_cards") or []
        parts = []
        if scope:
            parts.append(f"[bootstrap] scope={scope}")
        if cards:
            parts.append(f"cards={','.join(cards[:3])}")
        if preflight:
            parts.append(f"preflight={preflight[0]}")
        return " | ".join(parts) if parts else ""
    except Exception:
        return ""
```

In `run()`, after building `task_content` (~line 548) and BEFORE building `messages`, add:
```python
        if AGENT_INJECT_BOOTSTRAP:
            preamble = _run_bootstrap_preamble(AGENT_TASK)
            if preamble:
                system_content = SYSTEM_PROMPT + f"\n\n[STARTUP CONTEXT] {preamble}"
            else:
                system_content = SYSTEM_PROMPT
        else:
            system_content = SYSTEM_PROMPT
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": task_content},
        ]
```

IMPORTANT: Remove the existing `messages = [...]` line that this replaces.

### Step 3 — Add tests in test_local_agent_runtime.py

Add a new test function at the end of the file (before any `if __name__` block):
```python
def test_bootstrap_preamble_env_var_respected(monkeypatch, tmp_path):
    """AGENT_INJECT_BOOTSTRAP env var should be parsed at module level."""
    import importlib
    import ai_stack_agents_runtimes  # adjust import if needed
    # Just verify the module-level constant exists and is bool
    import ai-stack.agents.runtimes.local_agent_runtime as rt
    assert isinstance(rt.AGENT_INJECT_BOOTSTRAP, bool)
    assert isinstance(rt.BOOTSTRAP_TIMEOUT, float)
```

NOTE: The test file may use a different import path. Look at existing tests to match the pattern
exactly. The test just needs to verify AGENT_INJECT_BOOTSTRAP and BOOTSTRAP_TIMEOUT are present.

### Step 4 — Validate
```bash
python3 -m py_compile ai-stack/agents/runtimes/local_agent_runtime.py
python3 -m pytest ai-stack/agents/runtimes/test_local_agent_runtime.py -q
python3 scripts/testing/test-local-agent-config.py
bash -n scripts/ai/aq-context-bootstrap
scripts/governance/tier0-validation-gate.sh --pre-commit
```

### Step 5 — Commit
```bash
git add ai-stack/agents/runtimes/local_agent_runtime.py ai-stack/agents/runtimes/test_local_agent_runtime.py
git commit -m "feat(local-agent): add AGENT_INJECT_BOOTSTRAP startup preamble injection (Phase 30.6)

Auto-run aq-context-bootstrap at agent startup when AGENT_INJECT_BOOTSTRAP=true.
Closes behavioral gap in 30.2 (introspection preflight) and 30.4 (session summary
injection) — agent now arrives at first turn already grounded by observed signals.

Co-Authored-By: Qwen3.6-35B <noreply@harness.local>"
```

### Constraints
- Do NOT modify http_server.py or switchboard.nix (those need nixos-rebuild; scope this to runtime only)
- Do NOT break existing tests
- AGENT_INJECT_BOOTSTRAP defaults to false — zero behavioral change unless explicitly enabled
- _run_bootstrap_preamble must never raise — all errors return ""
- Keep the preamble compact (single line injected into system prompt, not full JSON dump)

### Working directory
/home/hyperd/Documents/NixOS-Dev-Quick-Deploy
