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

## Why this exists

The repo already standardizes on Agentic CLI tools because they are more context-efficient than raw Unix defaults. Runtime policy and instruction text must agree; otherwise agents pay a recurring tax in failed calls, fallback chatter, and broader context usage.
