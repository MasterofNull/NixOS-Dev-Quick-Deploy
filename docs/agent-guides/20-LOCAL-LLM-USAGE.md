# Local LLM Usage - llama.cpp & Embeddings

**Purpose**: Use local LLMs for inference and embeddings without remote API costs

---

## Services Overview

| Service | Port | Purpose | Models |
|---------|------|---------|--------|
| **llama.cpp** | 8080 | GGUF inference | Qwen Coder 7B, Qwen 4B, DeepSeek 6.7B |
| **Sentence Transformers** | n/a | Embeddings | all-MiniLM-L6-v2 |

---

## llama.cpp (GGUF Inference)

### Chat Completions API

```bash
# Simple chat
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-coder",
    "messages": [
      {"role": "user", "content": "Explain NixOS in one sentence"}
    ],
    "max_tokens": 100,
    "temperature": 0.7
  }' | jq
```

### Python Usage

```python
import requests

def query_local_llm(prompt, max_tokens=500, temperature=0.7):
    """Query llama.cpp local LLM"""

    url = "http://localhost:8080/v1/chat/completions"

    payload = {
        "model": "qwen-coder",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": temperature
    }

    response = requests.post(url, json=payload, timeout=30)
    result = response.json()

    return result["choices"][0]["message"]["content"]

# Example
answer = query_local_llm("What is a NixOS module?")
print(answer)
```

### Streaming Responses

```python
def stream_local_llm(prompt):
    """Stream response from local LLM"""

    url = "http://localhost:8080/v1/chat/completions"

    payload = {
        "model": "qwen-coder",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 500,
        "stream": True  # Enable streaming
    }

    response = requests.post(url, json=payload, stream=True, timeout=30)

    for line in response.iter_lines():
        if line:
            # Parse SSE format
            if line.startswith(b"data: "):
                data = line[6:]  # Remove "data: " prefix
                if data != b"[DONE]":
                    import json
                    chunk = json.loads(data)
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if delta:
                        print(delta, end="", flush=True)

# Example
stream_local_llm("Explain Docker in simple terms")
```

### Code Generation

```python
def generate_code(description, language="python"):
    """Generate code using local LLM"""

    prompt = f"""Generate {language} code for the following:

{description}

Provide only the code, no explanations.
"""

    code = query_local_llm(prompt, max_tokens=1000, temperature=0.3)
    return code

# Example
code = generate_code(
    description="Function to calculate Fibonacci sequence",
    language="python"
)
print(code)
```

### Code Review

```python
def review_code(code):
    """Review code using local LLM"""

    prompt = f"""Review this code and provide feedback on:
1. Bugs or errors
2. Performance issues
3. Best practices violations
4. Suggestions for improvement

Code:
```
{code}
```

Provide concise, actionable feedback.
"""

    review = query_local_llm(prompt, max_tokens=800, temperature=0.5)
    return review

# Example
code_to_review = """
def factorial(n):
    if n == 0:
        return 1
    return n * factorial(n-1)
"""

feedback = review_code(code_to_review)
print(feedback)
```

---

## Embeddings (Sentence Transformers)

### Generate Embeddings

```bash
# Embeddings are stored locally and used by AIDB.
ls ~/.cache/huggingface/sentence-transformers
```

### Python Usage

```python
def create_embedding(text):
    """Describe embedding flow (AIDB uses sentence-transformers)"""
    raise NotImplementedError("Use AIDB embedding pipeline or local sentence-transformers.")

# Example
text = "How to enable systemd service in NixOS"
embedding = create_embedding(text)

print(f"Dimensions: {len(embedding)}")  # 384
print(f"First 5 values: {embedding[:5]}")
```

### Batch Embeddings

```python
def batch_create_embeddings(texts):
    """Create embeddings for multiple texts efficiently"""

    embeddings = []

    for text in texts:
        response = ollama.embeddings(
            model="nomic-embed-text",
            prompt=text
        )
        embeddings.append(response["embedding"])

    return embeddings

# Example
texts = [
    "Enable Docker in NixOS",
    "Install packages in home-manager",
    "Configure GNOME desktop"
]

embeddings = batch_create_embeddings(texts)
print(f"Created {len(embeddings)} embeddings")
```

### Similarity Calculation

```python
import numpy as np

def cosine_similarity(embedding1, embedding2):
    """Calculate cosine similarity between two embeddings"""

    vec1 = np.array(embedding1)
    vec2 = np.array(embedding2)

    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)

    similarity = dot_product / (norm1 * norm2)
    return similarity

# Example
text1 = "Fix GNOME keyring error"
text2 = "Resolve OS keyring issue"
text3 = "Install Docker container"

emb1 = create_embedding(text1)
emb2 = create_embedding(text2)
emb3 = create_embedding(text3)

sim_1_2 = cosine_similarity(emb1, emb2)
sim_1_3 = cosine_similarity(emb1, emb3)

print(f"Similarity 1-2: {sim_1_2:.3f}")  # High (similar topics)
print(f"Similarity 1-3: {sim_1_3:.3f}")  # Low (different topics)
```

---

## Performance Optimization

### Model Selection

```python
# Use appropriate model for task
def choose_model(task_type):
    """Select best model for task"""

    models = {
        "code": "qwen-coder",      # Best for code generation
        "general": "qwen-general",  # General purpose
        "reasoning": "deepseek"     # Complex reasoning
    }

    return models.get(task_type, "qwen-coder")

# Example
model = choose_model("code")
```

### Context Length Management

```python
def truncate_context(text, max_tokens=2000):
    """Truncate text to fit context window"""

    # Rough estimation: 1 token ≈ 4 characters
    max_chars = max_tokens * 4

    if len(text) > max_chars:
        return text[:max_chars] + "... [truncated]"

    return text

# Example
long_code = "..." * 10000  # Very long code
truncated = truncate_context(long_code, max_tokens=1500)
```

### Temperature Tuning

```python
# Different temperatures for different tasks
TEMPERATURES = {
    "code_generation": 0.2,     # Low - deterministic
    "creative_writing": 0.9,    # High - creative
    "explanation": 0.5,         # Medium - balanced
    "code_review": 0.3,         # Low-medium - focused
    "brainstorming": 0.8        # High - diverse ideas
}

def query_with_task_temperature(prompt, task_type):
    temperature = TEMPERATURES.get(task_type, 0.7)

    return query_local_llm(
        prompt,
        temperature=temperature
    )
```

---

## Common Use Cases

### Use Case 1: Code Explanation

```python
def explain_code(code):
    """Explain what code does"""

    prompt = f"""Explain what this code does in simple terms:

```
{code}
```

Provide a concise explanation suitable for someone learning to code.
"""

    explanation = query_local_llm(prompt, max_tokens=300)
    return explanation
```

### Use Case 2: Syntax Checking

```python
def check_syntax(code, language="python"):
    """Check for syntax errors"""

    prompt = f"""Check this {language} code for syntax errors:

```
{code}
```

List any syntax errors found. If no errors, respond "No syntax errors found."
"""

    result = query_local_llm(prompt, max_tokens=200, temperature=0.3)
    return result
```

### Use Case 3: Documentation Generation

```python
def generate_docstring(function_code):
    """Generate docstring for function"""

    prompt = f"""Generate a Python docstring for this function:

```python
{function_code}
```

Follow Google-style docstring format. Be concise.
"""

    docstring = query_local_llm(prompt, max_tokens=300, temperature=0.4)
    return docstring
```

### Use Case 4: Refactoring Suggestions

```python
def suggest_refactoring(code):
    """Suggest code improvements"""

    prompt = f"""Suggest refactoring improvements for this code:

```
{code}
```

Focus on:
1. Readability
2. Performance
3. Maintainability

Provide 2-3 specific suggestions.
"""

    suggestions = query_local_llm(prompt, max_tokens=500)
    return suggestions
```

---

## Integration with RAG

### RAG-Enhanced Query

```python
from qdrant_client import QdrantClient

def rag_query(question):
    """Query local LLM with RAG context"""

    # Step 1: Search for relevant context
    embedding = create_embedding(question)

    client = QdrantClient(url="http://localhost:6333")
    results = client.search(
        collection_name="codebase-context",
        query_vector=embedding,
        limit=3
    )

    # Step 2: Build context
    if results and results[0].score > 0.7:
        context = "\n\n".join([
            r.payload.get("text", "") for r in results
        ])

        prompt = f"""Context:
{context}

Question: {question}

Answer based on the context above.
"""
    else:
        prompt = question

    # Step 3: Query local LLM
    answer = query_local_llm(prompt, max_tokens=400)

    return {
        "answer": answer,
        "context_used": len(results) > 0,
        "relevance": results[0].score if results else 0
    }

# Example
result = rag_query("How to fix GNOME keyring error?")
print(result["answer"])
print(f"Context relevance: {result['relevance']:.2f}")
```

---

## Monitoring & Health

### Check Model Status

```bash
# List loaded models
curl http://localhost:8080/v1/models | jq

# Check health
curl http://localhost:8080/health

# Embedding models live in the Hugging Face cache.
ls ~/.cache/huggingface/sentence-transformers
```

### Performance Metrics

```python
import time

def measure_inference_time(prompt):
    """Measure local LLM inference time"""

    start = time.time()
    response = query_local_llm(prompt, max_tokens=100)
    elapsed = time.time() - start

    tokens = len(response.split())
    tokens_per_second = tokens / elapsed

    print(f"Time: {elapsed:.2f}s")
    print(f"Tokens: {tokens}")
    print(f"Speed: {tokens_per_second:.1f} tok/s")

    return tokens_per_second

# Typical: 10-30 tok/s on consumer GPUs
speed = measure_inference_time("Explain NixOS")
```

---

## Troubleshooting

### Model Not Loaded

```bash
# Check if llama.cpp is downloading model
podman logs local-ai-llama-cpp | grep -i download

# First time can take 10-45 minutes
# Check progress regularly
```

### Slow Inference

```python
# Reduce max_tokens
answer = query_local_llm(prompt, max_tokens=200)  # Instead of 1000

# Lower temperature (faster sampling)
answer = query_local_llm(prompt, temperature=0.3)  # Instead of 0.9
```

### Out of Memory

```bash
# Check GPU memory
nvidia-smi

# Use smaller model (configure in docker-compose.yml)
# Qwen 4B instead of Qwen 7B
```

---

## Best Practices

1. **Use for simple tasks**: Code explanation, syntax check, simple generation
2. **Add context when possible**: RAG improves quality significantly
3. **Tune temperature**: Low (0.2-0.4) for code, high (0.7-0.9) for creativity
4. **Limit max_tokens**: Faster response, lower resource usage
5. **Cache embeddings**: Reuse for similar queries
6. **Monitor performance**: Track tokens/second, adjust as needed

---

## Next Steps

- **RAG integration**: [RAG Context Guide](21-RAG-CONTEXT.md)
- **Hybrid workflow**: [Hybrid Workflow](40-HYBRID-WORKFLOW.md)
- **Continuous learning**: [Learning Workflow](22-CONTINUOUS-LEARNING.md)
- **Service status**: [Service Status](02-SERVICE-STATUS.md)
