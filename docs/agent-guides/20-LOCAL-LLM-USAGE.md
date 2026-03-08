# Local LLM Usage

The current stack exposes host-local OpenAI-compatible endpoints. No Kubernetes port-forward step is required for normal local use.

## Chat Completions

```bash
curl -fsS http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "local-model",
    "messages": [
      {"role": "user", "content": "Explain what this repository does in one paragraph."}
    ],
    "temperature": 0.2
  }' | jq
```

## Embeddings

```bash
curl -fsS http://127.0.0.1:8081/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "local-embed",
    "input": "NixOS declarative AI stack"
  }' | jq
```

## Service Checks

```bash
systemctl status llama-cpp.service --no-pager
systemctl status llama-cpp-embed.service --no-pager
curl -fsS http://127.0.0.1:8889/api/ai/metrics | jq
```

## Notes

- Read ports from Nix options and injected environment where possible.
- Prefer `config/service-endpoints.sh` and existing scripts over new hardcoded URLs.
- If requests fail, check `aq-qa 0 --json` and `bash scripts/ai/ai-stack-health.sh`.
