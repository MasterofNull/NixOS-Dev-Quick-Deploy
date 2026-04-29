# SKILL: aq-runtime-diagnose

**Purpose**: Generic service/package/runtime diagnosis loop. Probes a service or
preset configuration, reports health findings, and (with `--store-findings`) persists
results to AIDB so agents can recall previous failure patterns.

## Synopsis

```
aq-runtime-diagnose [--service=NAME] [--preset=NAME] [--store-findings] [--dry-run]
```

## Key Flags

| Flag | Description |
|------|-------------|
| `--service=NAME` | Target systemd service (e.g. `ai-hybrid-coordinator`) |
| `--preset=ai-stack` | Run preset check suite for the full AI stack |
| `--preset=llama` | Probe llama.cpp inference service |
| `--preset=embeddings` | Probe embedding server (port 8081) |
| `--store-findings` | Emit findings to AIDB `project=runtime-diagnose` |
| `--dry-run` | Print AIDB payload without writing |

## Presets

| Preset | Services probed |
|--------|----------------|
| `ai-stack` | coordinator, AIDB, llama, embed, qdrant, redis |
| `llama` | llama-server on :8080 (chat inference) |
| `embeddings` | llama-embed on :8081 (vector embeddings) |

## Output Schema

```
runtime diagnose: ai-hybrid-coordinator
  service: active (running)
  endpoint: ok (200 in 0.8s)
  smoke: PASS
  finding: service healthy
```

## Examples

```bash
# Probe the full AI stack
aq-runtime-diagnose --preset=ai-stack

# Store findings to AIDB for agent recall
aq-runtime-diagnose --preset=ai-stack --store-findings

# Dry-run to inspect AIDB payload
aq-runtime-diagnose --service=ai-hybrid-coordinator --store-findings --dry-run

# Check just the embedding server
aq-runtime-diagnose --preset=embeddings
```

## Notes

- `--store-findings` writes to AIDB `POST /documents` with `project=runtime-diagnose`.
- The coordinator's `route_handler.py` prepends recent diagnose findings for
  failure-related queries (Phase 13.5).
- Suppress storage if confidence < `AI_RETRIEVAL_MIN_CONFIDENCE` (default: 0.65).
