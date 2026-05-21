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
