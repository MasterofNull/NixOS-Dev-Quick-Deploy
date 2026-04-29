# SKILL: aq-hints

**Purpose**: Ranked workflow hints for any agent. Surfaces relevant prompts from the
registry, runtime gap signals, and feedback history. Use before planning any task.

## Synopsis

```
aq-hints [QUERY] [--format=json|text] [--context=DOMAIN] [--max=N] [--agent=TYPE]
```

## Key Options

| Flag | Default | Description |
|------|---------|-------------|
| `--format` | `text` | `json` for machine consumption, `text` for terminal |
| `--context` | — | Domain filter: `.nix`, `.py`, `rag`, `aider`, `systemd`, `nixos` |
| `--max` | `4` | Max hints to return |
| `--agent` | `human` | `claude`, `qwen`, `codex`, `aider`, `continue` — adjusts verbosity |
| `--compact` | off | Truncate hint content for token-constrained contexts |

## Environment

| Variable | Purpose |
|----------|---------|
| `REGISTRY_PATH` | Override path to `prompts/registry.yaml` |
| `HYBRID_URL` | Coordinator base URL for REST fallback |

## Output Schema (JSON)

```json
[{"id": "...", "content": "...", "score": 0.85, "source": "registry|gap|runtime",
  "tags": ["nix", "module"], "feedback_contract": {...}}]
```

## Examples

```bash
# Get hints for a NixOS module task (terminal)
aq-hints "conflicting nixos module option" --context=nixos

# Machine-readable hints for qwen delegation
aq-hints "fix delegation timeout" --format=json --agent=qwen --max=3

# Runtime-signal hints (surfaces aq-report recommendations)
aq-hints "why is cache hit rate low" --format=json
```

## Notes

- Falls back to `GET ${HYBRID_URL}/hints?q=...` if local engine is unavailable.
- Submit feedback after task: `POST ${HYBRID_URL}/hints/feedback` with `hint_id` + `helpful`.
