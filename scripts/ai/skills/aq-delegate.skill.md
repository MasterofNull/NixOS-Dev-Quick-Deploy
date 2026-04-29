# SKILL: aq-delegate

**Purpose**: Inject project context before delegating tasks to sub-agents (qwen/codex).
Prevents the failure mode where agents respond generically instead of searching the repo.

## Synopsis

```
aq-delegate [FLAGS] AGENT "TASK"
```

## Key Flags

| Flag | Description |
|------|-------------|
| `--auto-approve` | Pass `-y` to qwen (auto-approve all changes) |
| `--dry-run` | Print enriched prompt without invoking agent |
| `--no-context` | Skip context injection (bare task) |
| `--format=prefixed|system|piped` | Prompt format (default: `prefixed`) |

## Agents

| Agent | When to use |
|-------|-------------|
| `qwen` | Multi-file refactors, implementation, Nix config changes |
| `codex` | Currently QUOTA EXHAUSTED — routes to fallback |

## Examples

```bash
# Delegate implementation to qwen with auto-approve
aq-delegate --auto-approve qwen "find the PRSI queue handlers and fix timeout"

# Dry-run to inspect what context is injected
aq-delegate --dry-run qwen "add embeddings flag to llama-embed service"

# Bare delegation (no context injection — rarely correct)
aq-delegate --no-context qwen "what is 2+2"
```

## CRITICAL

**Never use bare `qwen -y "..."` without aq-delegate.** The agent receives no project
context and responds generically. `aq-delegate` injects file paths, search mandates,
and PRSI/dashboard/Nix context based on keyword detection.

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Agent invocation succeeded (or dry-run) |
| `1` | Usage error |
| `2` | Agent not found in PATH |
