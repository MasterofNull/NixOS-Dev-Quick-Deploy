# Lemonade AI Server API Reference

## Overview

Lemonade is the standardized LLM inference runtime for NixOS-Dev-Quick-Deploy (December 2025 update). It provides an **OpenAI-compatible API** for local model execution via `llama.cpp`.

## Architecture

### Components

The Lemonade stack consists of three specialized containers:

1. **lemonade** (General Purpose)
   - Port: `8000`
   - Model: Qwen3-4B-Instruct-2507-Q4_K_M.gguf
   - Purpose: General reasoning and task execution
   - Base URL: `http://localhost:8000/api/v1`

2. **lemonade-coder** (Code Generation)
   - Port: `8001`
   - Model: Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf
   - Purpose: Advanced code generation and completion
   - Base URL: `http://localhost:8001/api/v1`

3. **lemonade-deepseek** (Code Analysis)
   - Port: `8003`
   - Model: Deepseek-Coder-6.7B-Instruct-Q4_K_M.gguf
   - Purpose: Code analysis and understanding
   - Base URL: `http://localhost:8003/api/v1`

### Model Storage

Models are cached in HuggingFace cache directories:
- Container path: `/root/.cache/huggingface`
- Host mount: Docker named volume `lemonade-hf-cache`
- User path: `~/.local/share/nixos-ai-stack/lemonade-models/`

## API Endpoints

### Health Check

```bash
GET /health

# Example
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "ok",
  "model": "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
}
```

### Chat Completions (OpenAI-compatible)

```bash
POST /api/v1/chat/completions

# Example
curl http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-4b",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Explain NixOS"}
    ],
    "temperature": 0.7,
    "max_tokens": 500
  }'
```

**Request Body:**
```json
{
  "model": "string",              // Model identifier (optional)
  "messages": [                   // Chat history
    {
      "role": "system|user|assistant",
      "content": "string"
    }
  ],
  "temperature": 0.7,             // Sampling temperature (0.0-2.0)
  "max_tokens": 500,              // Maximum tokens to generate
  "top_p": 0.9,                   // Nucleus sampling
  "frequency_penalty": 0.0,       // Repetition penalty
  "presence_penalty": 0.0,        // New topic encouragement
  "stop": ["string"],             // Stop sequences
  "stream": false                 // Enable streaming
}
```

**Response:**
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "qwen3-4b",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "NixOS is..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 20,
    "completion_tokens": 50,
    "total_tokens": 70
  }
}
```

### Text Completions

```bash
POST /api/v1/completions

# Example
curl http://localhost:8000/api/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "def fibonacci(n):",
    "max_tokens": 100,
    "temperature": 0.5
  }'
```

### Model Information

```bash
GET /api/v1/models

# Example
curl http://localhost:8000/api/v1/models
```

**Response:**
```json
{
  "data": [
    {
      "id": "qwen3-4b",
      "object": "model",
      "created": 1677652288,
      "owned_by": "unsloth"
    }
  ]
}
```

## Configuration

### Environment Variables

Located in `ai-stack/compose/.env`:

```bash
# Default model (HuggingFace identifier or registry name)
LEMONADE_DEFAULT_MODEL=Qwen/Qwen2.5-Coder-7B-Instruct

# Server configuration
LEMONADE_HOST=0.0.0.0
LEMONADE_PORT=8000
LEMONADE_LOG_LEVEL=info
LEMONADE_CTX_SIZE=4096            # Context window size

# API endpoints
LEMONADE_BASE_URL=http://lemonade:8000/api/v1
LEMONADE_CODER_URL=http://lemonade-coder:8001/api/v1
LEMONADE_DEEPSEEK_URL=http://lemonade-deepseek:8003/api/v1
```

### llama.cpp Server Options

Additional options can be passed via `LEMONADE_ARGS`:

```bash
LEMONADE_ARGS="--n-gpu-layers 0 --threads 4 --batch-size 512"
```

**Common Options:**
- `--n-gpu-layers N`: Number of layers to offload to GPU (0 for CPU-only)
- `--threads N`: Number of threads to use
- `--ctx-size N`: Context window size (default: 4096)
- `--batch-size N`: Prompt processing batch size
- `--mlock`: Lock model in RAM to prevent swapping
- `--numa`: Enable NUMA support for multi-socket systems

## Integration Examples

### Python (with httpx)

```python
import httpx
import asyncio

async def chat_completion(message: str):
    async with httpx.AsyncClient(base_url="http://localhost:8000/api/v1") as client:
        response = await client.post(
            "/chat/completions",
            json={
                "messages": [
                    {"role": "user", "content": message}
                ],
                "temperature": 0.7,
                "max_tokens": 500
            },
            timeout=120.0
        )
        return response.json()

# Usage
result = asyncio.run(chat_completion("Explain NixOS modules"))
print(result["choices"][0]["message"]["content"])
```

### JavaScript (with fetch)

```javascript
async function chatCompletion(message) {
  const response = await fetch('http://localhost:8000/api/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      messages: [
        { role: 'user', content: message }
      ],
      temperature: 0.7,
      max_tokens: 500
    })
  });

  return await response.json();
}

// Usage
const result = await chatCompletion('Explain NixOS modules');
console.log(result.choices[0].message.content);
```

### Bash (with curl)

```bash
#!/usr/bin/env bash

chat_completion() {
    local message=$1
    curl -s http://localhost:8000/api/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d "{
            \"messages\": [
                {\"role\": \"user\", \"content\": \"$message\"}
            ],
            \"temperature\": 0.7,
            \"max_tokens\": 500
        }" | jq -r '.choices[0].message.content'
}

# Usage
chat_completion "Explain NixOS modules"
```

## Parallel Inference Framework

The AIDB MCP Server includes a `ParallelInferenceEngine` that routes tasks to specialized models:

```python
from ai_stack.mcp_servers.aidb.parallel_inference import ParallelInferenceEngine, TaskType

engine = ParallelInferenceEngine({
    TaskType.GENERAL_REASONING: "http://lemonade:8000/api/v1",
    TaskType.CODE_GENERATION: "http://lemonade-coder:8001/api/v1",
    TaskType.CODE_ANALYSIS: "http://lemonade-deepseek:8003/api/v1"
})

# Route task to appropriate model
result = await engine.route_task(
    task_type=TaskType.CODE_GENERATION,
    prompt="Write a NixOS module for Nginx"
)
```

## Monitoring

### Health Checks

```bash
# Check all Lemonade services
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8003/health
```

### Container Logs

```bash
# Docker
docker logs -f lemonade
docker logs -f lemonade-coder
docker logs -f lemonade-deepseek

# Podman
podman logs -f lemonade
podman logs -f lemonade-coder
podman logs -f lemonade-deepseek
```

### Prometheus Metrics

Metrics exporters run on ports 9100-9102:

```bash
# Scrape lemonade metrics
curl http://localhost:9100/metrics

# Scrape lemonade-coder metrics
curl http://localhost:9101/metrics

# Scrape lemonade-deepseek metrics
curl http://localhost:9102/metrics
```

## Performance Tuning

### CPU Optimization

For CPU-only inference:
```bash
# Use all available cores
LEMONADE_ARGS="--threads $(nproc)"

# Enable memory locking
LEMONADE_ARGS="--threads $(nproc) --mlock"

# NUMA systems
LEMONADE_ARGS="--threads $(nproc) --numa"
```

### Context Window Tuning

Adjust based on available RAM:
```bash
# Smaller context (less RAM)
LEMONADE_CTX_SIZE=2048

# Larger context (more RAM required)
LEMONADE_CTX_SIZE=8192
```

### Batch Size Optimization

```bash
# Faster prompt processing (more RAM)
LEMONADE_ARGS="--batch-size 1024"

# Lower memory usage
LEMONADE_ARGS="--batch-size 256"
```

## Troubleshooting

### Model Not Loading

```bash
# Check if model downloaded
docker exec lemonade find /root/.cache/huggingface -name "*.gguf"

# Manually download model
docker exec lemonade python3 -c "from huggingface_hub import hf_hub_download; \
  hf_hub_download(repo_id='unsloth/Qwen3-4B-Instruct-2507-GGUF', \
  filename='Qwen3-4B-Instruct-2507-Q4_K_M.gguf')"
```

### Out of Memory

```bash
# Reduce context size
LEMONADE_CTX_SIZE=2048

# Reduce batch size
LEMONADE_ARGS="--batch-size 256"

# Check available RAM
free -h
```

### Slow Inference

```bash
# Increase threads
LEMONADE_ARGS="--threads $(nproc)"

# Enable mlock
LEMONADE_ARGS="--mlock"

# Check CPU usage
htop
```

## References

- **Docker Compose Config**: `ai-stack/compose/docker-compose.yml`
- **Environment Template**: `ai-stack/compose/.env.example`
- **AIDB Integration**: `ai-stack/mcp-servers/aidb/server.py`
- **Parallel Inference**: `ai-stack/mcp-servers/aidb/parallel_inference.py`
- **llama.cpp Docs**: https://github.com/ggerganov/llama.cpp
- **OpenAI API Spec**: https://platform.openai.com/docs/api-reference
