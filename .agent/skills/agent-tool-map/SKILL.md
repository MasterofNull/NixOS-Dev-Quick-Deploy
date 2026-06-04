---
name: agent-tool-map
description: "Agent Tool Map Skill"
---

# Agent Tool Map Skill
## Tags
gemini, codex, claude, tools, tool-names, grep_search, run_shell_command, read_file, replace
## When to Use
Writing prompts for Gemini or Codex; tool call failing with "Tool not found"; unsure which
tool name to use in a delegation prompt for a specific agent.

---

## 1. Tool Name Mapping by Agent

Each agent has different tool names for the same operation. Use the correct name when writing
prompts or delegation instructions.

| Operation | Claude Code | Gemini CLI | Codex CLI | Local (Qwen3) |
|-----------|------------|------------|-----------|---------------|
| Read file | Read | `read_file` | `read_file` | `read_file` / Read |
| Search content | Grep | `grep_search` | `grep_search` | `grep_search` |
| Find files | Glob | `find_files` | `find_files` | `find_files` |
| Edit file | Edit | `replace` | `apply_patch` | `replace` |
| Write new file | Write | `write_file` | `write_file` | `write_file` |
| Run shell cmd | Bash | **does not exist** | Bash | `run_command` |
| Web fetch | WebFetch | `web_fetch` | n/a | n/a |

### Critical: Gemini `run_shell_command` Does Not Exist
In Gemini CLI `auto_edit` mode, `run_shell_command` is NOT available. Any attempt returns
"Tool not found" and wastes a turn.

**When writing Gemini delegation prompts:**
```
WRONG: "Run `python3 -m py_compile file.py` to validate"
RIGHT: "Validate by reading file.py and checking for obvious syntax errors with grep_search"

WRONG: "Execute the tier0 validation gate"
RIGHT: "Read the gate script and verify the conditions it checks are met in the files"
```

For validation in Gemini prompts, rely on:
- `read_file` to verify file contents
- `grep_search` to find patterns
- `replace` + re-read to confirm edits took effect

---

## 2. Gemini CLI Modes and Tool Availability

| Mode | Tools available | Use for |
|------|----------------|---------|
| `auto_edit` | read_file, write_file, grep_search, find_files, replace, web_fetch | Code editing, review, analysis |
| `default` | read_file, grep_search, find_files, web_fetch | Read-only research |
| `yolo` | ALL tools, auto-approved | Full autonomous operation |

**Current harness usage**: Gemini is primarily `auto_edit` mode. Design delegation prompts
that do not rely on shell execution.

---

## 3. Codex CLI Notes

Codex requires stdin from `/dev/null`:
```bash
scripts/ai/delegate-to-codex --prompt "..." < /dev/null
```

Large prompts must go in a file:
```bash
scripts/ai/delegate-to-codex --prompt-file /tmp/prompt.txt < /dev/null
```

Codex uses `apply_patch` for edits (unified diff format). When writing Codex prompts for
code changes, describe the change and let Codex generate the patch — don't ask for `replace`.

---

## 4. Local Agent (Qwen3) Tool Notes

Local agent running via `--mode agent` has access to the coordinator's MCP tools:
- `hybrid_search` — searches AIDB collections
- `recall_agent_memory` — retrieves from memory broker
- `store_agent_memory` — writes to memory broker
- `get_hints` — gets contextual hints
- `ai_coordinator_delegate` — delegates to sub-agent (recursive)

Local agent in `--mode direct` has NO tool access — it receives only the prompt and produces
text. Do not ask it to "check the service status" or "run the QA" in direct mode.

---

## 5. Prompt Design by Agent

### For Gemini (auto_edit)
- Be explicit about which files to read and edit
- Include acceptance criteria as readable conditions ("the file should contain X")
- Avoid asking for shell validation — use file verification instead
- Keep prompts under 2000 tokens to avoid routing classifier failure (429)

### For Codex
- Always include the full edit scope in a separate file (`--prompt-file`)
- Specify exact file paths
- Request a specific output format ("output a commit message at the end")

### For Local (direct mode)
- Use focused prompts under 512 tokens for best results
- No tool calls — analysis/reasoning only
- Ask for structured output (JSON/YAML) for programmatic use

### For Claude (this agent)
- Full tool access — use Grep/Glob/Read/Edit/Bash freely
- Can run any validation commands directly
