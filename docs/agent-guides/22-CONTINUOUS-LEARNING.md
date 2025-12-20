# Continuous Learning Workflow

**Purpose**: Store learnings, improve over time, reduce future costs

---

## Core Principle

**Every interaction is a learning opportunity.**

- ✅ Solution worked? → Store it
- ❌ Solution failed? → Store the failure AND the fix
- 🔄 Pattern emerged? → Extract and reuse
- 📊 High value? → Add to fine-tuning dataset

---

## The Learning Cycle

```
┌──────────────┐
│ Receive Task │
└──────┬───────┘
       │
       ▼
┌──────────────────────┐
│ Search Local Context │ ← Qdrant vector search
└──────┬───────────────┘
       │
       ▼
┌────────────────────┐
│ Execute Solution   │ ← Local LLM or Remote API
└──────┬─────────────┘
       │
       ▼
┌──────────────────┐
│ Store Outcome    │ ← ALWAYS store (success or failure)
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Calculate Value  │ ← 5-factor scoring
└──────┬───────────┘
       │
       ▼
┌──────────────────────┐
│ Extract Pattern?     │ ← If value score > 0.7
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ Next Task Benefits   │ ← Improved local context
└──────────────────────┘
```

---

## Step 1: Store Successful Solutions

### When to Store

**ALWAYS** store when:
- Solution works correctly
- Error is fixed
- Configuration succeeds
- Pattern is identified
- User explicitly confirms success

### How to Store (Python)

```python
import ollama
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
import uuid
from datetime import datetime

def store_solution(query, solution, category="skills-patterns", metadata=None):
    """Store successful solution for future reference"""

    # Step 1: Create embedding
    response = ollama.embeddings(
        model="nomic-embed-text",
        prompt=query
    )
    embedding = response["embedding"]

    # Step 2: Prepare payload
    payload = {
        "query": query,
        "solution": solution,
        "category": category,
        "timestamp": datetime.utcnow().isoformat(),
        "source": "human-interaction",
        **(metadata or {})
    }

    # Step 3: Store in Qdrant
    client = QdrantClient(url="http://localhost:6333")

    point_id = str(uuid.uuid4())
    client.upsert(
        collection_name=category,
        points=[
            PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload
            )
        ]
    )

    print(f"✓ Stored solution: {point_id}")
    return point_id

# Example usage
store_solution(
    query="How to fix GNOME keyring error in NixOS",
    solution="""
    Add to home.nix:
    - libsecret
    - gcr

    Add to configuration.nix:
    security.pam.services.login.enableGnomeKeyring = true;
    security.pam.services.passwd.enableGnomeKeyring = true;
    """,
    category="error-solutions",
    metadata={
        "error_type": "gnome-keyring",
        "os": "nixos",
        "severity": "medium"
    }
)
```

---

## Step 2: Store Failures and Fixes

### When to Store Failures

**ALWAYS** store when:
- Error encountered
- Solution attempted but failed
- Correct solution found after failure
- Root cause identified

### How to Store Failures

```python
def store_error_and_fix(error, attempted_solution, correct_solution, root_cause):
    """Store error with attempted and correct solutions"""

    # Create embedding from error message
    response = ollama.embeddings(
        model="nomic-embed-text",
        prompt=error
    )
    embedding = response["embedding"]

    # Comprehensive error record
    payload = {
        "error": error,
        "attempted_solution": attempted_solution,
        "correct_solution": correct_solution,
        "root_cause": root_cause,
        "timestamp": datetime.utcnow().isoformat(),
        "outcome": "resolved"
    }

    client = QdrantClient(url="http://localhost:6333")
    client.upsert(
        collection_name="error-solutions",
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload=payload
            )
        ]
    )

    print("✓ Error and fix stored for future reference")

# Example usage
store_error_and_fix(
    error="OSError: [Errno 30] Read-only file system: '/nix/store/.../site-packages'",
    attempted_solution="pip install --user qdrant-client",
    correct_solution="""
    python3 -m venv venv
    source venv/bin/activate
    pip install qdrant-client
    """,
    root_cause="NixOS /nix/store is immutable, cannot modify system Python packages"
)
```

---

## Step 3: Calculate Value Score

### 5-Factor Value Algorithm

```python
def calculate_value_score(interaction):
    """Calculate 0-1 value score based on 5 factors"""

    # Factor 1: Complexity (0-1)
    # More complex = higher value
    complexity_score = min(1.0, interaction.get("lines_of_code", 0) / 100)

    # Factor 2: Reusability (0-1)
    # Generic patterns = higher value
    reusability_score = 0.8 if interaction.get("is_generic", False) else 0.3

    # Factor 3: Novelty (0-1)
    # First occurrence = higher value
    novelty_score = 1.0 if interaction.get("is_novel", True) else 0.2

    # Factor 4: User Confirmation (0-1)
    # Explicit success = higher value
    confirmation_score = 1.0 if interaction.get("user_confirmed", False) else 0.5

    # Factor 5: Impact (0-1)
    # Fixes critical issue = higher value
    impact_map = {
        "critical": 1.0,
        "high": 0.8,
        "medium": 0.5,
        "low": 0.3
    }
    impact_score = impact_map.get(interaction.get("severity", "medium"), 0.5)

    # Weighted average
    weights = {
        "complexity": 0.2,
        "reusability": 0.3,
        "novelty": 0.2,
        "confirmation": 0.15,
        "impact": 0.15
    }

    value_score = (
        complexity_score * weights["complexity"] +
        reusability_score * weights["reusability"] +
        novelty_score * weights["novelty"] +
        confirmation_score * weights["confirmation"] +
        impact_score * weights["impact"]
    )

    return round(value_score, 2)

# Example
interaction = {
    "lines_of_code": 50,
    "is_generic": True,
    "is_novel": True,
    "user_confirmed": True,
    "severity": "high"
}

score = calculate_value_score(interaction)
print(f"Value Score: {score}")  # Output: 0.77
```

---

## Step 4: Extract Patterns

### When to Extract Patterns

Extract when:
- Value score > 0.7 (high value)
- Pattern appears 3+ times
- User explicitly marks as important
- Solution is broadly applicable

### Pattern Extraction

```python
def extract_pattern(interactions):
    """Extract reusable pattern from similar interactions"""

    # Group similar solutions
    pattern_template = {
        "problem_type": identify_problem_type(interactions),
        "solution_template": generalize_solution(interactions),
        "prerequisites": extract_prerequisites(interactions),
        "variations": extract_variations(interactions),
        "success_rate": calculate_success_rate(interactions)
    }

    # Store as high-value pattern
    store_solution(
        query=pattern_template["problem_type"],
        solution=pattern_template["solution_template"],
        category="skills-patterns",
        metadata={
            "pattern_type": "extracted",
            "occurrence_count": len(interactions),
            "success_rate": pattern_template["success_rate"],
            "prerequisites": pattern_template["prerequisites"]
        }
    )

    return pattern_template

# Example: After fixing 3 similar NixOS config errors
pattern = extract_pattern([
    {"error": "service X not starting", "fix": "enable service in configuration.nix"},
    {"error": "service Y not starting", "fix": "enable service in configuration.nix"},
    {"error": "service Z not starting", "fix": "enable service in configuration.nix"}
])

# Result: Generic pattern stored
# "NixOS service not starting → Check services.X.enable = true in configuration.nix"
```

---

## Step 5: Update Interaction History

### Complete Interaction Record

```python
def log_interaction(query, response, outcome, context_used, llm_used):
    """Log complete interaction for analysis"""

    # Create embedding
    response_obj = ollama.embeddings(
        model="nomic-embed-text",
        prompt=query
    )
    embedding = response_obj["embedding"]

    # Comprehensive record
    payload = {
        "query": query,
        "response": response,
        "outcome": outcome,  # "success" | "failure" | "partial"
        "context_used": context_used,  # What local context was retrieved
        "llm_used": llm_used,  # "local" | "remote"
        "timestamp": datetime.utcnow().isoformat(),
        "tokens_saved": estimate_tokens_saved(context_used),
        "value_score": calculate_value_score({
            # ... factors from response
        })
    }

    client = QdrantClient(url="http://localhost:6333")
    client.upsert(
        collection_name="interaction-history",
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload=payload
            )
        ]
    )

    # Also store in PostgreSQL for structured queries
    store_in_postgres(payload)

    print(f"✓ Interaction logged")

def estimate_tokens_saved(context_used):
    """Estimate how many tokens were saved by using local context"""
    if not context_used:
        return 0

    # Assume full docs would be 15,000 tokens
    # Context-augmented query uses ~500 tokens
    return 15000 - 500
```

---

## Step 6: Fine-Tuning Dataset Generation

### Generate Training Data

```python
def generate_fine_tuning_dataset(min_value_score=0.7):
    """Generate fine-tuning dataset from high-value interactions"""

    client = QdrantClient(url="http://localhost:6333")

    # Search for high-value interactions
    results = client.scroll(
        collection_name="interaction-history",
        limit=1000,
        with_payload=True
    )

    dataset = []
    for point in results[0]:
        if point.payload.get("value_score", 0) >= min_value_score:
            dataset.append({
                "instruction": point.payload["query"],
                "output": point.payload["response"],
                "context": point.payload.get("context_used", "")
            })

    # Save in format for fine-tuning
    import json
    output_path = "~/.local/share/nixos-ai-stack/fine-tuning/dataset.jsonl"

    with open(output_path, "w") as f:
        for item in dataset:
            f.write(json.dumps(item) + "\n")

    print(f"✓ Generated {len(dataset)} training examples")
    return output_path
```

---

## Continuous Learning Best Practices

### 1. Always Store Outcomes

```python
# GOOD: Store success
if solution_works():
    store_solution(query, solution)

# GOOD: Store failure AND fix
if solution_fails():
    store_error_and_fix(error, attempted, correct, root_cause)

# BAD: Don't store anything
if solution_works():
    pass  # ❌ Lost learning opportunity!
```

### 2. Search Before Executing

```python
# GOOD: Check local context first
results = search_qdrant(query)
if results[0].score > 0.8:
    use_cached_solution(results[0])
else:
    execute_new_solution()

# BAD: Always use remote API
response = call_remote_api(query)  # ❌ Wasted tokens!
```

### 3. Update Context Regularly

```bash
# Weekly: Review high-value interactions
python3 scripts/review-high-value-interactions.py

# Monthly: Extract patterns
python3 scripts/extract-patterns.py

# Quarterly: Generate fine-tuning dataset
python3 scripts/generate-fine-tuning-data.py
```

### 4. Monitor Quality

```python
def check_learning_quality():
    """Monitor continuous learning effectiveness"""

    client = QdrantClient(url="http://localhost:6333")

    # Check average relevance scores
    recent_queries = get_recent_queries(days=7)

    avg_scores = []
    for query in recent_queries:
        results = search_qdrant(query)
        if results:
            avg_scores.append(results[0].score)

    avg_relevance = sum(avg_scores) / len(avg_scores)

    print(f"Average relevance: {avg_relevance:.2f}")
    print(f"Target: > 0.75 for good performance")

    if avg_relevance < 0.6:
        print("⚠️  Low relevance - need more diverse examples")
    elif avg_relevance > 0.85:
        print("✓ Excellent learning performance")
```

---

## Integration with Remote Agents

### Agent Workflow

```python
class ContinuousLearningAgent:
    """Remote agent with local context awareness"""

    def __init__(self):
        self.qdrant = QdrantClient(url="http://localhost:6333")
        self.local_llm_url = "http://localhost:8080/v1/chat/completions"
        self.remote_api_url = "https://api.anthropic.com/v1/messages"

    def execute_task(self, query):
        # Step 1: Search local context
        context = self.search_local_context(query)

        # Step 2: Decide LLM
        llm = self.choose_llm(context, query_complexity)

        # Step 3: Execute
        if llm == "local":
            response = self.call_local_llm(query, context)
        else:
            response = self.call_remote_api(query, context)

        # Step 4: Store outcome (ALWAYS)
        self.store_outcome(query, response, context, llm)

        return response

    def search_local_context(self, query):
        """Search Qdrant for relevant context"""
        embedding = ollama.embeddings(model="nomic-embed-text", prompt=query)
        results = self.qdrant.search(
            collection_name="skills-patterns",
            query_vector=embedding["embedding"],
            limit=3
        )
        return results

    def choose_llm(self, context, complexity):
        """Decide local vs remote"""
        best_score = context[0].score if context else 0

        if best_score > 0.85 and complexity < 5:
            return "local"
        else:
            return "remote"

    def store_outcome(self, query, response, context, llm):
        """Always store learning"""
        log_interaction(query, response, "success", context, llm)
```

---

## Next Steps

- **Implement RAG**: [RAG & Context Guide](21-RAG-CONTEXT.md)
- **Qdrant operations**: [Qdrant Guide](30-QDRANT-OPERATIONS.md)
- **Value scoring details**: [Value Scoring Guide](41-VALUE-SCORING.md)
- **Pattern extraction**: [Pattern Extraction Guide](42-PATTERN-EXTRACTION.md)
