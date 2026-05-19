# Agent Tool Contract

## Purpose

Every agent lane should begin from the same small, reliable tool surface so it does not waste turns rediscovering avoidable environment differences.

## Canonical default tool order

| Task | Preferred path | Bounded fallback |
|---|---|---|
| Search repo contents | `agrep` | `rg` |
| Discover paths | `als` | `fd` |
| Read bounded file slices | `acat` | native read tool or `sed -n` |
| Summarize file structure | `asum` | targeted read + local summary |
| Inspect JSON | `jq` | Python only when transformation exceeds simple queries |
| Inspect YAML | `yq` | Python only when transformation exceeds simple queries |

## Universal baseline

The default coding/research baseline should expose:

- `agrep`, `als`, `acat`, `asum`
- `rg`, `fd`
- `jq`, `yq`
- `bash`, `python3`, `git`

Readonly lanes may expose only non-mutating tools from that set. Execute lanes may add mutation-capable orchestration tools, but should keep the same discovery/read preferences.

## Token-efficiency rules

1. Use the preferred repo-native tool first.
2. If it is unavailable, use one documented fallback and move on.
3. If both preferred and fallback tools are unavailable, record the missing capability once and use the approved lane equivalent; do not spend multiple turns rediscovering the same absence.
4. Do not retry the same failed tool call without changing the hypothesis.
5. Prefer bounded reads and bounded listings over full dumps.

## Security boundary

Tool presence is not permission. Network access, write access, and destructive actions remain governed by the lane policy and approval boundary even when binaries are available.

## Per-agent tool availability (SSOT — prevents turn-wasting on unavailable tools)

This table documents what tool names each agent lane actually exposes. Calling a tool not in your lane's row will fail immediately and waste a turn.

| Agent | Available tools | Banned (will fail) | Shell access |
|---|---|---|---|
| **Claude** (this session) | Read, Edit, Write, Bash, Glob, Grep, WebFetch, Agent, TodoWrite | — | Full via Bash tool |
| **Gemini** (`delegate-to-gemini` default `yolo`) | file tools plus approved shell/tool calls | use `auto_edit` only for no-shell tasks | Via approved Gemini CLI shell tools |
| **Gemini** (`auto_edit`) | `read_file`, `write_file`, `replace`, `grep_search`, `list_directory`, `update_topic` | `run_shell_command` ← DNE | None — no shell tool |
| **Codex** | `read_file`, `write_file`, `replace`, `grep_search`, `list_directory`, `run_shell_command` | — | Via `run_shell_command` |
| **Local/Qwen** | `read_file`, `write_file`, `list_files`, `search_files`, `run_command` (whitelist), `run_shell_command` alias | `invoke_agent` | Via whitelisted `run_command` / `run_shell_command` alias |

### Gemini-specific rules

- `delegate-to-gemini` defaults to `yolo` mode because many implementation/review prompts require shell validation.
- `run_shell_command` **does not exist** in Gemini CLI `auto_edit` mode. It returns "Tool not found". Use `auto_edit` only for pure read/edit tasks that require no shell validation.
- Ripgrep is not available as a binary in the Gemini environment. Use `grep_search` (the tool) instead of trying to call `rg` via shell.
- File scope is the repo root only. Paths under `/var/lib/`, `/run/`, or system paths will fail with "outside workspace".
- `.agents/delegation/outputs/*.log` files are gitignored — `read_file` will fail. Use `grep_search` to scan them.
- Write-mode is `replace` (in-place find/replace) or `write_file` (full overwrite). Always verify the exact string before `replace`; a "string not found" error means the source has drifted — re-read the file first.

### Local/Qwen-specific rules

- `run_shell_command` is a compatibility alias for `run_command`; both still enforce the same command whitelist.
- `invoke_agent` is blocked — implementer role may not route other agents. Escalate to orchestrator.
- Whitelisted `run_command` targets: `bash -n`, `python3 -m py_compile`, `nix-instantiate --parse`, `git status/diff/add/log`, `aq-qa`, `agrep`, `als`, `acat`.

### When a tool is unavailable

1. Record the missing tool **once** in your output or PULSE.log.
2. Switch immediately to the approved fallback from the table above.
3. Do **not** retry the same unavailable tool call again in the same session.
4. Do **not** spend multiple turns probing for the tool under different names.

## Why this exists

The repo standardizes on Agentic CLI tools because they are more context-efficient than raw Unix defaults. Each agent lane has a distinct tool API — treating them as identical wastes turns on "Tool not found" errors that cannot be retried. This table is the SSOT for resolving those differences at session start, not mid-task.
