# RAG & Context Augmentation - Reduce Token Usage

**Purpose**: Learn how to use local context to reduce remote API costs

---

## Core Concept

**RAG (Retrieval Augmented Generation)**:
1. Search local knowledge base for relevant context
2. Augment your query with that context
3. Send enriched query to LLM (local or remote)
4. Get better answer with less tokens

---

## Token Savings Example

### Without RAG
```
User: "How do I fix the keyring error in NixOS?"
→ Load full NixOS docs (15,000 tokens)
→ Load gnome-keyring docs (8,000 tokens)
→ Load PAM docs (5,000 tokens)
Total: 28,000 tokens
```

### With RAG
```
User: "How do I fix the keyring error in NixOS?"
→ Search Qdrant: "keyring error nixos"
→ Found: Past solution (200 tokens of relevant context)
→ Query: "How to fix keyring? Context: [libsecret needed, PAM integration...]"
Total: 500 tokens
```

**Savings**: 97% reduction!

---

## How to Use RAG (Python)

### Step 1: Create Embedding
```python
import ollama

# Convert query to vector
response = ollama.embeddings(
    model="nomic-embed-text",
    prompt="fix gnome keyring error"
)
embedding = response["embedding"]
```

### Step 2: Search Qdrant
```python
from qdrant_client import QdrantClient

client = QdrantClient(url="http://localhost:6333")

# Search relevant collections
results = client.search(
    collection_name="error-solutions",
    query_vector=embedding,
    limit=3  # Top 3 most relevant
)
```

### Step 3: Extract Context
```python
context = []
for result in results:
    if result.score > 0.75:  # Only high-relevance matches
        context.append(result.payload["solution"])

combined_context = "\n\n".join(context)
```

### Step 4: Augmented Query
```python
augmented_prompt = f"""
Context from past solutions:
{combined_context}

User Question: {original_question}

Based on the context above, provide a solution.
"""

# Now send this to local LLM or remote API
# Much smaller token count!
```

---

## Collections to Search

### By Task Type

| Task | Search Collection | Typical Tokens Saved |
|------|------------------|----------------------|
| Debugging | `error-solutions` | 80-90% |
| Implementation | `skills-patterns` | 60-70% |
| Configuration | `best-practices` + `codebase-context` | 70-80% |
| Understanding Code | `codebase-context` | 50-60% |

---

## Advanced RAG Strategies

### Strategy 1: Multi-Collection Search
```python
# Search multiple collections for comprehensive context
def search_all_relevant(query_embedding):
    collections = [
        "error-solutions",
        "skills-patterns",
        "best-practices"
    ]

    all_results = []
    for collection in collections:
        results = client.search(
            collection_name=collection,
            query_vector=query_embedding,
            limit=2
        )
        all_results.extend([r for r in results if r.score > 0.7])

    # Sort by relevance
    all_results.sort(key=lambda x: x.score, reverse=True)
    return all_results[:5]  # Top 5 overall
```

### Strategy 2: Hybrid Search (Semantic + Keyword)
```python
# Combine vector similarity with keyword matching
results = client.search(
    collection_name="codebase-context",
    query_vector=embedding,
    query_filter={
        "must": [
            {"key": "file_type", "match": {"value": "nix"}}
        ]
    },
    limit=5
)
```

### Strategy 3: Re-Ranking
```python
# Use local LLM to re-rank results by relevance
def rerank_results(query, results):
    scored_results = []
    for result in results:
        prompt = f"Rate relevance 0-1: Query: {query}, Context: {result.payload}"
        score = local_llm_score(prompt)
        scored_results.append((result, score))

    return sorted(scored_results, key=lambda x: x[1], reverse=True)
```

---

## When to Use Local vs Remote

### Use Local LLM (Lemonade) When:
✅ Query has high-relevance local context (score > 0.85)
✅ Task is simple (code explanation, syntax check)
✅ Speed matters more than perfection
✅ Budget is limited

### Use Remote API When:
✅ No relevant local context (score < 0.6)
✅ Complex reasoning required
✅ Novel problem not seen before
✅ Quality matters more than cost

### Decision Function
```python
def choose_llm(query_embedding, task_complexity):
    # Search for context
    results = search_qdrant(query_embedding)
    best_score = results[0].score if results else 0

    # Decision tree
    if best_score > 0.85 and task_complexity < 5:
        return "local"  # High context, simple task
    elif best_score > 0.7 and task_complexity < 3:
        return "local"  # Medium context, very simple
    else:
        return "remote"  # Use remote API
```

---

## Measuring Effectiveness

### Track Your Savings
```python
# Store usage stats
stats = {
    "query": query,
    "context_used": len(context),
    "context_score": best_score,
    "llm_used": "local" | "remote",
    "tokens_with_rag": count_tokens(augmented_prompt),
    "estimated_tokens_without": 15000,  # Average full doc load
    "savings_pct": ((15000 - tokens_with_rag) / 15000) * 100
}
```

### Monitor Collection Quality
```python
# Check average relevance scores
avg_scores = []
for query in recent_queries:
    results = search_qdrant(query)
    avg_scores.append(results[0].score if results else 0)

print(f"Average relevance: {sum(avg_scores)/len(avg_scores)}")
# Target: > 0.75 for good RAG performance
```

---

## Common Patterns

### Pattern 1: Error Debugging
```python
# 1. Search error-solutions
error_results = search_collection("error-solutions", error_embedding)

# 2. If found (score > 0.8), apply directly
if error_results[0].score > 0.8:
    return error_results[0].payload["solution"]

# 3. Otherwise, use context to augment remote query
context = extract_context(error_results)
remote_query = augment_query(original_error, context)
return remote_api_call(remote_query)
```

### Pattern 2: Code Implementation
```python
# 1. Search skills-patterns AND best-practices
patterns = search_collection("skills-patterns", task_embedding)
practices = search_collection("best-practices", task_embedding)

# 2. Combine context
combined = merge_contexts(patterns, practices)

# 3. Use local LLM with context
solution = local_llm_generate(task, context=combined)

# 4. Store if successful
if validate_solution(solution):
    store_pattern(task, solution, value_score=0.85)
```

---

## Configuration

### Embedding Model Settings
```bash
# In Ollama
# Default: nomic-embed-text (384 dimensions)
# Fast, good quality for code/text

# To change:
export EMBEDDING_MODEL="nomic-embed-text"
export EMBEDDING_DIMENSIONS=384
```

### Search Parameters
```python
# Tune these based on your needs
SEARCH_CONFIG = {
    "limit": 5,              # Top N results
    "score_threshold": 0.7,  # Minimum relevance
    "max_context_tokens": 2000,  # Max context size
    "timeout_ms": 100        # Search timeout
}
```

---

## Best Practices

1. **Always embed queries before searching** - Don't skip this step
2. **Filter by score threshold** - Irrelevant context hurts more than helps
3. **Limit context size** - More context ≠ better results
4. **Cache embeddings** - Reuse for similar queries
5. **Monitor token usage** - Track actual savings
6. **Update collections regularly** - Fresh context = better results

---

## Troubleshooting

### Low Relevance Scores
- **Problem**: Results always < 0.6
- **Solution**: Collection may be empty or need better data
- **Fix**: Populate collections with more examples

### Slow Search
- **Problem**: Qdrant queries > 1s
- **Solution**: Too many vectors or no indexes
- **Fix**: Enable HNSW indexing, reduce collection size

### Irrelevant Context
- **Problem**: High score but wrong context
- **Solution**: Embedding model mismatch
- **Fix**: Use same model for storage and retrieval

---

## Next Steps

- Learn: [Continuous Learning Workflow](22-CONTINUOUS-LEARNING.md)
- See: [Qdrant Operations](30-QDRANT-OPERATIONS.md)
- Try: [Hybrid Workflow Guide](40-HYBRID-WORKFLOW.md)
