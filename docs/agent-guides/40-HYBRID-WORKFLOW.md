# Hybrid Workflow - Local + Remote Coordination

**Purpose**: Optimize costs by using local LLM when possible, remote API when needed

---

## Core Concept

**Use the right tool for the job:**
- Local LLM (Lemonade): Fast, free, good for simple/repetitive tasks
- Remote API (Claude/GPT): Expensive, excellent for complex/novel tasks

**Goal**: 70%+ queries handled locally, 30-50% token reduction overall

---

## Decision Tree

```
New Query Received
    │
    ├─ Step 1: Search Local Context
    │       │
    │       ├─ High Relevance (> 0.85)
    │       │   └─> Use Local LLM with Context
    │       │
    │       ├─ Medium Relevance (0.6 - 0.85)
    │       │   └─> Check Task Complexity
    │       │           │
    │       │           ├─ Simple → Local LLM
    │       │           └─ Complex → Remote API
    │       │
    │       └─ Low Relevance (< 0.6)
    │           └─> Use Remote API
    │
    └─ Step 2: Execute & Store
            └─> Always store outcome for learning
```

---

## Implementation

### Complete Hybrid Workflow Class

```python
import ollama
import requests
from qdrant_client import QdrantClient
from datetime import datetime
import json

class HybridWorkflow:
    """Coordinate local and remote LLM usage"""

    def __init__(self):
        self.qdrant = QdrantClient(url="http://localhost:6333")
        self.local_llm_url = "http://localhost:8080/v1/chat/completions"
        self.remote_api_key = "your-api-key"  # From env
        self.stats = {
            "local_queries": 0,
            "remote_queries": 0,
            "tokens_saved": 0
        }

    def execute_query(self, query, user_context=None):
        """Main entry point for all queries"""

        # Step 1: Search local knowledge base
        context_results = self.search_local_context(query)

        # Step 2: Calculate relevance and complexity
        relevance_score = context_results[0].score if context_results else 0
        complexity = self.estimate_complexity(query)

        # Step 3: Decide which LLM to use
        use_local = self.should_use_local(relevance_score, complexity)

        # Step 4: Execute query
        if use_local:
            response = self.query_local_llm(query, context_results)
            llm_used = "local"
            self.stats["local_queries"] += 1
        else:
            response = self.query_remote_api(query, context_results)
            llm_used = "remote"
            self.stats["remote_queries"] += 1

        # Step 5: Store outcome for learning
        self.store_interaction(
            query=query,
            response=response,
            context=context_results,
            llm_used=llm_used,
            relevance_score=relevance_score
        )

        return {
            "response": response,
            "llm_used": llm_used,
            "relevance_score": relevance_score,
            "context_found": len(context_results) > 0
        }

    def search_local_context(self, query):
        """Search Qdrant for relevant context"""

        # Create embedding
        embedding_response = ollama.embeddings(
            model="nomic-embed-text",
            prompt=query
        )
        query_vector = embedding_response["embedding"]

        # Search multiple collections
        collections = [
            "error-solutions",
            "skills-patterns",
            "best-practices"
        ]

        all_results = []
        for collection in collections:
            try:
                results = self.qdrant.search(
                    collection_name=collection,
                    query_vector=query_vector,
                    limit=2,
                    score_threshold=0.6
                )
                all_results.extend(results)
            except Exception as e:
                print(f"Warning: Could not search {collection}: {e}")

        # Sort by relevance
        all_results.sort(key=lambda x: x.score, reverse=True)
        return all_results[:5]  # Top 5 overall

    def estimate_complexity(self, query):
        """Estimate query complexity (1-10 scale)"""

        complexity_indicators = {
            "simple": ["what is", "how to", "show me", "list"],
            "medium": ["explain", "why", "compare", "debug"],
            "complex": ["design", "architect", "implement", "refactor", "optimize"]
        }

        query_lower = query.lower()

        if any(keyword in query_lower for keyword in complexity_indicators["complex"]):
            return 8
        elif any(keyword in query_lower for keyword in complexity_indicators["medium"]):
            return 5
        else:
            return 2

    def should_use_local(self, relevance_score, complexity):
        """Decide whether to use local LLM"""

        # High relevance + simple → Always local
        if relevance_score > 0.85 and complexity < 6:
            return True

        # High relevance + medium complexity → Local
        if relevance_score > 0.8 and complexity < 4:
            return True

        # Medium relevance + very simple → Local
        if relevance_score > 0.7 and complexity < 3:
            return True

        # Everything else → Remote
        return False

    def query_local_llm(self, query, context):
        """Query Lemonade local LLM"""

        # Build context-augmented prompt
        if context:
            context_text = "\n\n".join([
                f"Relevant context (score: {r.score:.2f}):\n{r.payload.get('solution', r.payload.get('text', ''))}"
                for r in context[:3]
            ])
            prompt = f"{context_text}\n\nQuery: {query}\n\nProvide a concise answer based on the context above."
        else:
            prompt = query

        # Call local LLM
        payload = {
            "model": "qwen-coder",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500,
            "temperature": 0.7
        }

        response = requests.post(
            self.local_llm_url,
            json=payload,
            timeout=30
        )

        result = response.json()
        answer = result["choices"][0]["message"]["content"]

        # Track token savings
        estimated_saved = self.estimate_tokens_saved(context)
        self.stats["tokens_saved"] += estimated_saved

        return answer

    def query_remote_api(self, query, context):
        """Query remote API (Claude/GPT) with context augmentation"""

        # Even remote queries benefit from local context
        if context and context[0].score > 0.7:
            context_text = "\n\n".join([
                f"{r.payload.get('solution', r.payload.get('text', ''))}"
                for r in context[:2]
            ])
            augmented_query = f"Relevant context:\n{context_text}\n\nQuery: {query}"

            # Still saved tokens by not loading full docs
            estimated_saved = 10000  # Avoided loading 10k tokens of docs
            self.stats["tokens_saved"] += estimated_saved
        else:
            augmented_query = query

        # Call remote API (example with Claude)
        # Replace with actual API call
        # response = anthropic.messages.create(...)

        # Placeholder
        return f"[Remote API response to: {query}]"

    def estimate_tokens_saved(self, context):
        """Estimate tokens saved by using local context"""
        if not context:
            return 0

        # Assume without context we'd need to load:
        # - Full documentation: ~15,000 tokens
        # - Multiple files: ~5,000 tokens
        # Total: ~20,000 tokens

        # With context we use:
        # - Context snippets: ~500 tokens
        # - Query: ~100 tokens
        # Total: ~600 tokens

        # Savings: 19,400 tokens per query
        return 19400

    def store_interaction(self, query, response, context, llm_used, relevance_score):
        """Store interaction for continuous learning"""

        from qdrant_client.models import PointStruct
        import uuid

        # Create embedding
        embedding_response = ollama.embeddings(
            model="nomic-embed-text",
            prompt=query
        )

        # Prepare payload
        payload = {
            "query": query,
            "response": response,
            "llm_used": llm_used,
            "relevance_score": relevance_score,
            "context_count": len(context),
            "timestamp": datetime.utcnow().isoformat(),
            "outcome": "success"  # Update based on actual validation
        }

        # Store in interaction-history
        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding_response["embedding"],
            payload=payload
        )

        self.qdrant.upsert(
            collection_name="interaction-history",
            points=[point]
        )

    def get_statistics(self):
        """Get usage statistics"""

        total_queries = self.stats["local_queries"] + self.stats["remote_queries"]
        local_percentage = (self.stats["local_queries"] / total_queries * 100) if total_queries > 0 else 0

        return {
            "total_queries": total_queries,
            "local_queries": self.stats["local_queries"],
            "remote_queries": self.stats["remote_queries"],
            "local_percentage": f"{local_percentage:.1f}%",
            "tokens_saved": self.stats["tokens_saved"],
            "estimated_cost_saved": self.stats["tokens_saved"] * 0.00003  # Example: $0.03 per 1k tokens
        }

# Usage Example
workflow = HybridWorkflow()

# Execute query
result = workflow.execute_query("How to fix GNOME keyring error in NixOS?")

print(f"Response: {result['response']}")
print(f"LLM used: {result['llm_used']}")
print(f"Relevance: {result['relevance_score']:.2f}")

# Check stats
stats = workflow.get_statistics()
print(f"Local queries: {stats['local_percentage']}")
print(f"Tokens saved: {stats['tokens_saved']}")
print(f"Cost saved: ${stats['estimated_cost_saved']:.2f}")
```

---

## Usage Patterns

### Pattern 1: Error Debugging

```python
# Step 1: Check error-solutions first
error_msg = "OSError: Read-only file system /nix/store"

context = workflow.search_local_context(error_msg)

if context and context[0].score > 0.85:
    # High confidence - use cached solution
    print(f"Known solution: {context[0].payload['correct_solution']}")
else:
    # Unknown error - use remote API to debug
    result = workflow.execute_query(error_msg)
    # Store the solution for next time
```

### Pattern 2: Code Generation

```python
# Simple code generation → Local
task = "Write a Python function to calculate factorial"
result = workflow.execute_query(task)
# Likely uses local LLM (simple, may have pattern)

# Complex code generation → Remote
task = "Design a distributed caching system with Redis and PostgreSQL"
result = workflow.execute_query(task)
# Likely uses remote API (complex, novel architecture)
```

### Pattern 3: NixOS Configuration

```python
# Check for similar configs first
task = "Enable Docker in NixOS"

context = workflow.search_local_context(task)

if context and context[0].score > 0.9:
    # Exact match - use cached config
    config = context[0].payload['solution']
    print(config)
else:
    # New config - query with context
    result = workflow.execute_query(task)
    # Store working config for reuse
```

---

## Optimization Strategies

### Strategy 1: Prefetch Common Patterns

```python
# During idle time, pre-generate embeddings for common queries
common_queries = [
    "enable systemd service",
    "install nix package",
    "debug container",
    "fix permission error"
]

for query in common_queries:
    context = workflow.search_local_context(query)
    # Warms up cache, faster future searches
```

### Strategy 2: Batch Processing

```python
# Process multiple queries efficiently
queries = [
    "How to restart Qdrant?",
    "Check Ollama status",
    "View container logs"
]

results = []
for query in queries:
    # Search once, use for multiple
    context = workflow.search_local_context(query)

    # All likely use local LLM (simple ops)
    if context and context[0].score > 0.7:
        result = workflow.query_local_llm(query, context)
        results.append(result)

# Saved significant tokens vs individual remote queries
```

### Strategy 3: Confidence Thresholds

```python
# Adjust thresholds based on task criticality
class CriticalWorkflow(HybridWorkflow):
    def should_use_local(self, relevance_score, complexity):
        # For critical tasks, require higher confidence
        if relevance_score > 0.95 and complexity < 4:
            return True
        return False  # Default to remote for safety

# For non-critical tasks, more aggressive local usage
class CasualWorkflow(HybridWorkflow):
    def should_use_local(self, relevance_score, complexity):
        if relevance_score > 0.65 and complexity < 7:
            return True
        return False
```

---

## Monitoring & Analytics

### Track Performance

```python
def analyze_workflow_performance(days=7):
    """Analyze hybrid workflow effectiveness"""

    client = QdrantClient(url="http://localhost:6333")

    # Get recent interactions
    from datetime import timedelta
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

    results = client.scroll(
        collection_name="interaction-history",
        limit=1000,
        with_payload=True
    )

    interactions = [
        p.payload for p in results[0]
        if p.payload.get("timestamp", "") > cutoff
    ]

    # Calculate metrics
    total = len(interactions)
    local = len([i for i in interactions if i["llm_used"] == "local"])
    remote = total - local

    avg_relevance_local = sum([
        i["relevance_score"] for i in interactions if i["llm_used"] == "local"
    ]) / local if local > 0 else 0

    print(f"=== Workflow Performance ({days} days) ===")
    print(f"Total queries: {total}")
    print(f"Local: {local} ({local/total*100:.1f}%)")
    print(f"Remote: {remote} ({remote/total*100:.1f}%)")
    print(f"Avg relevance (local): {avg_relevance_local:.2f}")
    print(f"Target: 70%+ local, 0.75+ avg relevance")
```

---

## Best Practices

### 1. Always Search First
```python
# GOOD
context = search_local_context(query)
if context:
    use_local_with_context()
else:
    use_remote()

# BAD
use_remote()  # ❌ Wasted opportunity!
```

### 2. Store Everything
```python
# After every query (local or remote)
store_interaction(query, response, context, llm_used)
```

### 3. Measure Effectiveness
```python
# Weekly check
analyze_workflow_performance(days=7)

# Adjust thresholds if needed
if local_percentage < 60:
    lower_relevance_threshold()
```

### 4. Update Collections
```python
# Regularly add high-value patterns
if interaction.value_score > 0.8:
    extract_and_store_pattern(interaction)
```

---

## Troubleshooting

### Too Many Remote Queries

**Problem**: < 50% local usage

**Solutions**:
- Lower relevance threshold (0.85 → 0.75)
- Increase complexity tolerance (< 5 → < 7)
- Add more examples to collections
- Check if collections are populated

### Low Quality Local Responses

**Problem**: Local LLM gives incorrect answers

**Solutions**:
- Increase relevance threshold (0.75 → 0.85)
- Reduce complexity tolerance (< 7 → < 5)
- Verify context quality in collections
- Use larger GGUF model

### Context Not Found

**Problem**: Relevance scores always < 0.5

**Solutions**:
- Check Qdrant collections populated
- Verify embedding model consistency
- Add more diverse examples
- Review search query phrasing

---

## Next Steps

- **Implement value scoring**: [Value Scoring Guide](41-VALUE-SCORING.md)
- **Extract patterns**: [Pattern Extraction](42-PATTERN-EXTRACTION.md)
- **RAG details**: [RAG Context Guide](21-RAG-CONTEXT.md)
- **Continuous learning**: [Learning Workflow](22-CONTINUOUS-LEARNING.md)
