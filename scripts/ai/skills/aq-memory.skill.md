# SKILL: aq-memory

**Purpose**: Manage temporal facts in the AI harness memory store (AIDB-backed).
Supports draft/review/promote gate to prevent hallucinated entries from becoming
authoritative. Phase 12.3 PoW gate enforces min-length and stop-token validation.

## Synopsis

```
aq-memory SUBCOMMAND [OPTIONS]
```

## Subcommands

| Subcommand | Description |
|------------|-------------|
| `add` | Add a fact (validates PoW gate before writing) |
| `search` | Semantic search over stored facts |
| `list` | List facts filtered by project/type |
| `expire` | Mark a fact as expired with reason |
| `agent-diary` | Show recent facts for a specific agent |
| `stats` | Show memory store statistics |

## Key Options (add)

| Flag | Default | Description |
|------|---------|-------------|
| `--project` | `ai-stack` | Project namespace |
| `--topic` | — | Topic tag for the fact |
| `--type` | `observation` | `decision`, `observation`, `constraint`, `pattern` |

## Output Schema (search/list)

```json
[{"id": "...", "content": "...", "project": "...", "type": "...",
  "created_at": "...", "expires_at": null}]
```

## Examples

```bash
# Add a validated decision fact
aq-memory add "llama-embed requires --embedding flag in service args" \
  --project ai-stack --topic embeddings --type decision

# Search for relevant facts before a task
aq-memory search "delegation timeout" --project ai-stack --limit 5

# List all constraint-type facts
aq-memory list --project ai-stack --type constraint

# Show qwen's recent observations
aq-memory agent-diary qwen --topic coding --limit 10
```

## PoW Gate (Phase 12.3)

All writes pass through `validate_memory_content()`:
- Minimum 20 characters
- No stop-tokens (`<|im_end|>`, `</s>`, `[INST]`)
- Returns `(valid: bool, reason: str)`
