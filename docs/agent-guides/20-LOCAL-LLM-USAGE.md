# Local LLM Usage

**Purpose**: Manage and query host-local AI models (Qwen3.6-35B, BGE-M3).

## Chat & Embedding Endpoints

| Service | Port | Endpoint | Role |
|---------|------|----------|------|
| **llama-cpp** | 8080 | `/v1/chat/completions` | Primary Chat/Reasoning |
| **llama-embed** | 8081 | `/v1/embeddings` | RAG/Memory Embeddings |
| **Switchboard** | 8085 | `/v1/chat/completions` | Profile-routed Proxy |

### Chat Completion Example
```bash
curl -fsS http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "qwen3.6-35b",
    "messages": [{"role": "user", "content": "Explain NixOS flakes."}],
    "temperature": 0.2
  }' | jq
```

## Local Chat with Built-in Tools

`aq-chat --profile local` now uses Switchboard's `local-tool-calling` lane by
default instead of talking directly to llama.cpp. This gives the local model
server-side built-in tools for bounded inspection and validation work. Use
`--no-tools` only when you intentionally need a raw llama.cpp chat session.

```bash
# Harness-aware local chat with server-side built-in tools
scripts/ai/aq-chat --profile local

# Raw llama.cpp fallback, no built-in tool execution
scripts/ai/aq-chat --profile local --no-tools

# Live smoke; keep bounded because local 35B tool calls can be slow
SWB_TOOL_CALL_TIMEOUT_SECONDS=120 scripts/testing/test-switchboard-local-tool-calling.sh
```

## Service Management

```bash
# Check status
systemctl status llama-cpp.service
systemctl status llama-cpp-embed.service

# View live metrics
curl -fsS http://127.0.0.1:8889/api/ai/metrics | jq
```

## Troubleshooting (GPU & VRAM)

If inference is slow or failing:

1.  **Check VRAM Allocation**:
    ```bash
    aq-llama-debug --check-vram
    nvidia-smi  # or rocm-smi
    ```
2.  **Verify Model Integrity**:
    ```bash
    aq-llama-debug --verify-models
    ```
3.  **Check Logs for Crashes**:
    ```bash
    journalctl -u llama-cpp -n 100 --no-pager
    ```

### High-Latency Note
Local inference on 35B models can take **90-120s**. Ensure your client timeouts are set to at least **300s**.

---

## Best Practices

- **Declarative Swap**: Change models via `mySystem.aiStack.llamaCpp.activeModel` in Nix modules.
- **Avoid Hardcoding**: Read ports from `nix/modules/core/options.nix` or environment variables.
- **GPU Offload**: Ensure `gpuLayers` matches your VRAM capacity (default 12 for Qwen3.6-35B).
- **dispatch.py watch**: Monitor running `delegate-to-local` tasks in real time:
  ```bash
  dispatch.py watch <task-id> --delegation-dir .agents/delegation
  ```
  Shows streamed output + live progress metrics (tokens/elapsed/tok_per_sec/eta).
- **Timeout scaling (Phase 163)**: Timeout auto-scales from token budget —
  `max(explicit, ceil(max_tokens/LOCAL_TOK_PER_SEC)+60)`. At 1 tok/s:
  code tasks (1200 tok) get 1260s; reasoning tasks (1800 tok) get 1860s.
  Override rate calibration: `LOCAL_TOK_PER_SEC=1.5 delegate-to-local ...`
- **Progress sidecar**: `<output>.progress.json` updated every 10 tokens with
  status/tokens_out/max_tokens/elapsed_s/tok_per_sec/eta_s. Also readable via
  `tail -f <output_file>` (incremental writes, not all-at-end).

---

## Phase 164 — Local Agent Capability Lift (Stage A)

Changes to unblock high-level multi-step tasks (self-improvement slices, full dev cycles).

### Tool Call Ceiling Raised

| Constant | Before | After | Env Override |
|---|---|---|---|
| `LOCAL_TOOL_CALL_LIMIT` | 16 | 40 | `SWB_LOCAL_TOOL_CALL_LIMIT` |
| `ACTIVE_TOOL_SCHEMA_LIMIT` | 7 | 12 | `SWB_ACTIVE_TOOL_SCHEMA_LIMIT` |
| `CONTEXT_OUTPUT_GC_MIN_CHARS` | 2400 | 5000 | `SWB_CONTEXT_OUTPUT_GC_MIN_CHARS` |
| `aq-chat --max-tools` default | 16 | 40 | `--max-tools N` CLI flag |

### `harness_dev` Composite Bundle

New tool bundle combining search + file_edit + harness_analysis + git into a single working set.
Avoids bundle-swap lease calls that burn tool budget mid-task:

```
harness_dev = get_hint, query_context, harness_health, get_working_memory,
              search_files, read_file, list_files, write_file, run_command,
              git_status, git_diff, validate_before_commit
```

Triggers automatically for:
- Self-improvement / slice tasks (`improvement`, `slice`, `self-improve`)
- Compound edit+commit requests (`fix ... and validate`, `refactor ... and test`, etc.)

### REPO_ROOT Path Map in System Prompt

`aq-chat` now injects an explicit path map into the system prompt at session start, showing
the agent exactly where scripts/, tests/, config/, nix/, .agent/, and docs/ live.
Prevents the "searched /nix instead of REPO_ROOT/scripts" discovery failure seen in Phase 164
diagnosis.
