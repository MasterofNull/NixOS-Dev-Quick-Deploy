You are a NixOS AI harness agent for NixOS-Dev-Quick-Deploy.
Follow AGENTS.md and WORKFLOW-CANON.md.

## Task: Phase 33.4 — Tool Output Compression in local_agent_runtime.py

Large tool outputs bloat the context window. Cap tool results to 800 chars by default
so the agent spends tokens on reasoning, not raw file dumps.

### Step 1 — Read these files
- `ai-stack/agents/runtimes/local_agent_runtime.py` (focus on `_dispatch_tool` and `_run_harness_cli`)
- `ai-stack/agents/runtimes/test_local_agent_runtime.py`

### Step 2 — Add output compression

Add a module-level constant near the other env vars (~line 53):
```python
# Phase 33.4: cap tool output injected back into context (tokenmaxxing — reduce wasted tokens)
TOOL_OUTPUT_MAX_CHARS = int(os.environ.get("AGENT_TOOL_OUTPUT_MAX_CHARS", "800"))
```

Add a helper just before `_dispatch_tool`:
```python
def _compress_tool_output(output: str, max_chars: int = TOOL_OUTPUT_MAX_CHARS) -> str:
    """Trim tool output to max_chars, appending a truncation notice if needed."""
    if len(output) <= max_chars:
        return output
    half = max_chars // 2
    return output[:half] + f"\n...[truncated {len(output) - max_chars} chars]...\n" + output[-half:]
```

In `_dispatch_tool`, wrap ALL return values (except errors) through `_compress_tool_output`.
Look for every `return` statement inside `_dispatch_tool` that returns a result string,
and wrap: `return _compress_tool_output(result_string)`.

Do NOT compress error messages (lines starting with "tool_error(" or "unknown_tool:").

### Step 3 — Add test
In `test_local_agent_runtime.py`, add:
```python
def test_compress_tool_output_truncates_long_output():
    module = _load_runtime()
    long = "x" * 2000
    compressed = module._compress_tool_output(long, max_chars=100)
    assert len(compressed) < 200  # allows for truncation notice overhead
    assert "truncated" in compressed

def test_compress_tool_output_passes_short_output():
    module = _load_runtime()
    short = "hello world"
    assert module._compress_tool_output(short, max_chars=100) == short
```

### Step 4 — Validate
```bash
python3 -m py_compile ai-stack/agents/runtimes/local_agent_runtime.py
python3 -m pytest ai-stack/agents/runtimes/test_local_agent_runtime.py -q
scripts/governance/tier0-validation-gate.sh --pre-commit
```

### Step 5 — Commit
```bash
git add ai-stack/agents/runtimes/local_agent_runtime.py ai-stack/agents/runtimes/test_local_agent_runtime.py
git commit -m "feat(local-agent): Phase 33.4 — tool output compression (tokenmaxxing)

Cap tool results to 800 chars (AGENT_TOOL_OUTPUT_MAX_CHARS) before injecting
into context. Prevents file dumps from consuming the entire context window.
Configurable via env var. Part of Phase 33 tokenmaxxing standardization.

Co-Authored-By: Gemini Code Assist <noreply@google.com>"
```

Working directory: /home/hyperd/Documents/NixOS-Dev-Quick-Deploy
