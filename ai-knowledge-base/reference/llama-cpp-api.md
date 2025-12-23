# llama.cpp API (OpenAI-Compatible)

**Last Updated:** 2025-12-21

This stack uses the official `ghcr.io/ggml-org/llama.cpp:server` container and exposes an
OpenAI-compatible API on `http://localhost:8080`.

## Endpoints

- `GET /health` - Service health (returns 200 when ready)
- `GET /v1/models` - List loaded/available models
- `POST /v1/chat/completions` - Chat completions
- `POST /v1/completions` - Text completions

## Example: List Models

```bash
curl -s http://localhost:8080/v1/models | jq
```

## Example: Chat Completion

```bash
curl -s http://localhost:8080/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
    "messages": [{"role": "user", "content": "Hello!"}]
  }' | jq
```

## Environment Variables

- `LLAMA_CPP_BASE_URL` - Base URL for clients (default: `http://localhost:8080`)
- `LLAMA_CPP_PORT` - Port exposed by the container (default: `8080`)
- `LLAMA_CPP_DEFAULT_MODEL` - Optional default model hint

## Notes

- The Lemonade Desktop App is optional and runs on the host for GUI access.
- The Lemonade Server (C++ router/CLI) is optional and separate from the llama.cpp container.
