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

---

## Phase 164 — Stages B, C, D: Context Compression Toolchain

### Stage B — RTK Shell Output Compression

RTK (Rust Token Killer) is installed as a NixOS system package and auto-detected by
`run_command`. When `rtk` is in PATH, every `run_command` call wraps the command with
`rtk <cmd>` before execution, compressing output 60-90% before it enters LLM context.

```nix
# Already in ai-stack.nix — enabled after nixos-rebuild:
(pkgs.callPackage ../../pkgs/rtk.nix {})
```

Controls: `SWB_RTK_ENABLED=0` disables wrapping; `RTK_BIN=/path/to/rtk` overrides binary path.

**Hash resolution required** (run after nixos-rebuild download error):
```bash
nix-prefetch-url https://github.com/rtk-ai/rtk/releases/download/v0.42.3/rtk-x86_64-unknown-linux-musl.tar.gz
# Replace lib.fakeHash in nix/pkgs/rtk.nix with printed hash
```

### Stage C — headroom Context Compression Proxy (pending packaging)

NixOS module added at `nix/modules/services/headroom-proxy.nix`. When
`mySystem.aiStack.headroomProxy.enable = true`, switchboard routes completions through
headroom (`:8787`) which compresses payloads before forwarding to llama.cpp.

**Packaging incomplete** — blocked by nixpkgs-25.11 litellm@1.69.0 (need ≥1.86.2)
and missing `magika`, `sqlite-vec`, `ast-grep-cli` packages. Options:
- Wait for nixpkgs update
- Use `poetry2nix` with headroom's `pyproject.toml`
- Add local `fetchPypi` derivations for the missing deps

### Stage D — lean-ctx MCP Server

lean-ctx installed as NixOS system package. After rebuild, run once per user:
```bash
lean-ctx init --agent claude   # registers MCP in ~/.claude.json, installs rules
lean-ctx setup                 # shell + editor + verification setup
```

62 MCP tools available: `ctx_read` with modes `signatures`, `map`, `lines:N-M`,
`density:X`, `diff`. Session memory persists across chats. See `lean-ctx doctor`
for diagnostic checks.

**Hash resolution required**:
```bash
nix-prefetch-github --owner yvgude --repo lean-ctx --rev v3.3.7
# Replace lib.fakeHash in nix/pkgs/lean-ctx.nix with printed hashes
```

## Agent Loop Reliability (Phase 165)

### Per-Chunk SSE Timeout (LLAMA_CHUNK_TIMEOUT)

`aq-agent-loop` sets `LLAMA_CHUNK_TIMEOUT = max(900, timeout_secs × 2)` (seconds).

This timeout fires when the llama.cpp server is **silent** for that many seconds between
SSE data chunks. It does NOT fire during continuous token generation.

**Why 900s minimum?**  After 2+ tool calls the context grows to ~2500 tokens.  On Renoir APU
at ~5 tok/s prefill, that requires ~500s of prefill before the first response token is
emitted.  A 300s timeout (old default) fired during prefill, producing `httpx.ReadTimeout`
with no message → `task.error = ""`, `task.status = failed`.

### Retry Logic

`_execute_with_tools` retries a failed LLM call once with a 512-token budget.  If the
retry also fails or returns an empty response, a descriptive `RuntimeError` is raised.

### Debugging Failures

| `task.error` value | Likely cause |
|--------------------|--------------|
| `LLM prefill/generation timeout: server silent for >Xs` | Context too large for chunk timeout; increase `LLAMA_CHUNK_TIMEOUT` |
| `LLM returned empty response at call N` | Model emitted EOS with no content; check llama.cpp logs |
| `LLM connection refused at ...` | llama.cpp not running; check `systemctl status ai-llama-cpp` |
