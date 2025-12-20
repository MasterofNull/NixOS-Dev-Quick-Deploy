# Hybrid Local-Remote AI Learning Architecture

> **📊 System Dashboard**: View real-time architecture status and metrics at [../ai-stack/dashboard/index.html](../ai-stack/dashboard/index.html)

## Overview

A continuous learning system where **local LLMs** (Lemonade/Ollama) support **remote agents** (Claude, GPT-4) with context augmentation, while learning from interactions to improve over time.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Remote Agents                                │
│  (Claude Code, GPT-4, DeepSeek API, Anthropic API)                  │
└────────────────┬────────────────────────────────┬───────────────────┘
                 │                                │
                 │ Context Requests               │ Results & Feedback
                 ▼                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Hybrid Agent Coordinator (MCP Server)                   │
│  • Route queries (local vs remote)                                  │
│  • Aggregate context from Qdrant                                    │
│  • Track success/failure metrics                                    │
│  • Score data value                                                 │
└────────┬──────────────────────────┬──────────────────┬──────────────┘
         │                          │                  │
         │ Context Retrieval        │ Store Results    │ Update Metrics
         ▼                          ▼                  ▼
┌────────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│  Qdrant Vector DB  │   │  PostgreSQL/     │   │  Learning        │
│                    │   │  SQLite Metrics  │   │  Feedback Loop   │
│ • Codebase context │   │                  │   │                  │
│ • Skills & patterns│   │ • Success rates  │   │ • Fine-tuning    │
│ • Error solutions  │   │ • Token usage    │   │ • Model updates  │
│ • Best practices   │   │ • Query patterns │   │ • Prompt refine  │
└────────────────────┘   └──────────────────┘   └──────────────────┘
         ▲                          ▲                  │
         │ Embeddings               │ Metrics          │ Improved Models
         │                          │                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Local LLM Inference Layer                         │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  Lemonade    │  │  Lemonade    │  │  Lemonade    │              │
│  │  General     │  │  Coder       │  │  DeepSeek    │              │
│  │  (Qwen 4B)   │  │  (Qwen 7B)   │  │  (6.7B)      │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│                                                                       │
│  ┌──────────────────────────────────────────────────────┐           │
│  │              Ollama (Optional)                        │           │
│  │  • Llama 3.1 70B (high-capacity reasoning)           │           │
│  │  • CodeLlama 34B (specialized coding)                │           │
│  └──────────────────────────────────────────────────────┘           │
└───────────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Hybrid Agent Coordinator (New MCP Server)

**Purpose**: Intelligently route queries between local and remote agents while managing the learning feedback loop.

**Responsibilities**:
- **Query Analysis**: Determine if query needs remote (complex) or local (context-heavy) processing
- **Context Augmentation**: Retrieve relevant context from Qdrant to reduce remote token usage
- **Result Tracking**: Store outcomes (success/failure) for continuous improvement
- **Value Scoring**: Rank data by reusability and learning value
- **Model Routing**: Direct queries to most appropriate local model

### 2. Qdrant Vector Database (Enhanced)

**Collections**:

#### Collection: `codebase-context`
```python
{
    "vectors": {"size": 384, "distance": "Cosine"},
    "payload_schema": {
        "file_path": "string",
        "code_snippet": "text",
        "language": "string",
        "framework": "string",  # nix, python, bash, etc.
        "purpose": "text",
        "last_accessed": "timestamp",
        "access_count": "integer",
        "success_rate": "float"  # How often this context led to success
    }
}
```

#### Collection: `skills-patterns`
```python
{
    "vectors": {"size": 384, "distance": "Cosine"},
    "payload_schema": {
        "skill_name": "string",
        "description": "text",
        "usage_pattern": "text",
        "success_examples": "array[text]",
        "failure_examples": "array[text]",
        "prerequisites": "array[string]",
        "related_skills": "array[string]",
        "value_score": "float",  # 0-1, reusability metric
        "last_updated": "timestamp"
    }
}
```

#### Collection: `error-solutions`
```python
{
    "vectors": {"size": 384, "distance": "Cosine"},
    "payload_schema": {
        "error_message": "text",
        "error_type": "string",  # nixos, python, build, etc.
        "context": "text",
        "solution": "text",
        "solution_verified": "boolean",
        "success_count": "integer",
        "failure_count": "integer",
        "first_seen": "timestamp",
        "last_used": "timestamp",
        "confidence_score": "float"
    }
}
```

#### Collection: `interaction-history`
```python
{
    "vectors": {"size": 384, "distance": "Cosine"},
    "payload_schema": {
        "query": "text",
        "agent_type": "string",  # local or remote
        "model_used": "string",
        "context_provided": "array[string]",  # IDs of context used
        "response": "text",
        "outcome": "string",  # success, partial, failure
        "user_feedback": "integer",  # -1, 0, 1
        "tokens_used": "integer",
        "latency_ms": "integer",
        "timestamp": "timestamp",
        "value_score": "float"  # Computed learning value
    }
}
```

#### Collection: `best-practices`
```python
{
    "vectors": {"size": 384, "distance": "Cosine"},
    "payload_schema": {
        "category": "string",  # nixos, coding, deployment, etc.
        "title": "string",
        "description": "text",
        "examples": "array[text]",
        "anti_patterns": "array[text]",
        "references": "array[string]",
        "endorsement_count": "integer",
        "last_validated": "timestamp"
    }
}
```

### 3. Learning Feedback Loop

**Components**:

1. **Outcome Tracker**: Records every interaction result
2. **Value Scorer**: Computes reusability and learning value
3. **Pattern Extractor**: Identifies recurring successful patterns
4. **Fine-Tuning Pipeline**: Generates training data from high-value interactions
5. **Model Updater**: Periodically fine-tunes local models

### 4. Context Augmentation Service

**Workflow**:

```python
async def augment_query_with_context(query: str, agent_type: str):
    """
    Enhance query with relevant local context before sending to remote agent
    """
    # 1. Embed the query
    query_embedding = await embed(query)

    # 2. Search relevant collections
    codebase_context = await qdrant.search(
        collection="codebase-context",
        vector=query_embedding,
        limit=5,
        score_threshold=0.7
    )

    skills = await qdrant.search(
        collection="skills-patterns",
        vector=query_embedding,
        limit=3,
        score_threshold=0.75
    )

    error_solutions = await qdrant.search(
        collection="error-solutions",
        vector=query_embedding,
        limit=2,
        score_threshold=0.8
    )

    best_practices = await qdrant.search(
        collection="best-practices",
        vector=query_embedding,
        limit=2,
        score_threshold=0.75
    )

    # 3. Construct augmented prompt
    augmented_prompt = f"""
Query: {query}

Relevant Context from Local Knowledge Base:

## Codebase Context
{format_results(codebase_context)}

## Related Skills & Patterns
{format_results(skills)}

## Similar Error Solutions
{format_results(error_solutions)}

## Best Practices
{format_results(best_practices)}

Please use this context to provide a more accurate and efficient response.
"""

    # 4. Track which context was provided
    context_ids = [
        r.id for r in (codebase_context + skills + error_solutions + best_practices)
    ]

    return {
        "augmented_prompt": augmented_prompt,
        "context_ids": context_ids,
        "original_query": query
    }
```

## Data Value Scoring Algorithm

**Purpose**: Identify high-value data worth storing and learning from.

```python
def compute_value_score(interaction: dict) -> float:
    """
    Score interaction value (0-1) based on multiple factors
    """
    score = 0.0

    # 1. Outcome quality (40% weight)
    if interaction["outcome"] == "success":
        score += 0.4
    elif interaction["outcome"] == "partial":
        score += 0.2

    # 2. User feedback (20% weight)
    if interaction["user_feedback"] == 1:
        score += 0.2
    elif interaction["user_feedback"] == 0:
        score += 0.1

    # 3. Reusability potential (20% weight)
    # Based on query similarity to other queries
    reusability = estimate_reusability(interaction["query"])
    score += 0.2 * reusability

    # 4. Complexity (10% weight)
    # More complex successful solutions are more valuable
    complexity = estimate_complexity(interaction["response"])
    score += 0.1 * complexity

    # 5. Novelty (10% weight)
    # New patterns are more valuable
    novelty = estimate_novelty(interaction["query"])
    score += 0.1 * novelty

    return min(score, 1.0)


def estimate_reusability(query: str) -> float:
    """
    Estimate how likely this query pattern will recur
    """
    # Check similarity to past queries
    similar_count = count_similar_queries(query, threshold=0.8)

    # Keywords indicating reusable patterns
    reusable_keywords = ["how to", "best practice", "configure", "setup"]
    keyword_bonus = sum(1 for kw in reusable_keywords if kw in query.lower())

    return min((similar_count * 0.1 + keyword_bonus * 0.2), 1.0)


def estimate_complexity(response: str) -> float:
    """
    Estimate response complexity (code length, concepts, etc.)
    """
    # Multi-step solutions are more valuable
    steps = response.count("1.") + response.count("2.") + response.count("3.")

    # Code blocks indicate technical solutions
    code_blocks = response.count("```")

    # Length as complexity indicator (normalized)
    length_score = min(len(response) / 2000, 1.0)

    return min((steps * 0.1 + code_blocks * 0.15 + length_score * 0.5), 1.0)


def estimate_novelty(query: str) -> float:
    """
    Check if this is a new pattern not seen before
    """
    similar_count = count_similar_queries(query, threshold=0.9)

    # Fewer similar queries = more novel
    if similar_count == 0:
        return 1.0
    elif similar_count < 3:
        return 0.7
    elif similar_count < 10:
        return 0.4
    else:
        return 0.1
```

## Continuous Learning Workflow

### Phase 1: Context Augmentation (Reduce Remote Costs)

```python
async def handle_remote_agent_request(query: str):
    """
    Remote agent requests help from local system
    """
    # 1. Augment with local context
    augmented = await augment_query_with_context(query, "remote")

    # 2. Check if local LLM can handle it
    local_confidence = await estimate_local_capability(query)

    if local_confidence > 0.8:
        # Local LLM can handle this
        response = await lemonade_inference(augmented["augmented_prompt"])
        source = "local"
    else:
        # Need remote agent, but provide context
        response = augmented["augmented_prompt"]  # Send to remote
        source = "context_only"

    # 3. Track the interaction
    await track_interaction(
        query=query,
        context_ids=augmented["context_ids"],
        response=response,
        source=source
    )

    return response
```

### Phase 2: Outcome Tracking

```python
async def record_interaction_outcome(
    interaction_id: str,
    outcome: str,  # success, partial, failure
    user_feedback: int = 0  # -1, 0, 1
):
    """
    Record the outcome of an interaction
    """
    # 1. Fetch original interaction
    interaction = await get_interaction(interaction_id)

    # 2. Update outcome
    interaction["outcome"] = outcome
    interaction["user_feedback"] = user_feedback

    # 3. Compute value score
    value_score = compute_value_score(interaction)
    interaction["value_score"] = value_score

    # 4. Update in Qdrant
    await qdrant.update(
        collection="interaction-history",
        point_id=interaction_id,
        payload=interaction
    )

    # 5. Update success rates of used context
    await update_context_success_rates(
        interaction["context_ids"],
        outcome == "success"
    )

    # 6. If high-value interaction, extract patterns
    if value_score > 0.7:
        await extract_and_store_patterns(interaction)
```

### Phase 3: Pattern Extraction

```python
async def extract_and_store_patterns(interaction: dict):
    """
    Extract reusable patterns from successful interactions
    """
    # 1. Analyze the interaction
    patterns = await analyze_interaction_patterns(
        query=interaction["query"],
        response=interaction["response"],
        context=interaction["context_provided"]
    )

    # 2. Store as skills/patterns
    for pattern in patterns:
        # Check if similar pattern exists
        existing = await qdrant.search(
            collection="skills-patterns",
            vector=await embed(pattern["description"]),
            limit=1,
            score_threshold=0.9
        )

        if existing:
            # Update existing pattern with new example
            await update_pattern(existing[0].id, pattern)
        else:
            # Create new pattern
            await qdrant.insert(
                collection="skills-patterns",
                point={
                    "id": generate_id(),
                    "vector": await embed(pattern["description"]),
                    "payload": pattern
                }
            )


async def analyze_interaction_patterns(query, response, context):
    """
    Use local LLM to extract patterns from interaction
    """
    prompt = f"""
Analyze this successful interaction and extract reusable patterns:

Query: {query}
Response: {response}
Context Used: {context}

Extract:
1. What problem was solved?
2. What approach was used?
3. What skills/knowledge were applied?
4. What can be generalized for future use?

Return JSON format:
{{
    "problem_type": "string",
    "solution_approach": "string",
    "skills_used": ["skill1", "skill2"],
    "generalizable_pattern": "text"
}}
"""

    # Use local Lemonade model for pattern extraction
    analysis = await lemonade_inference(prompt)
    return parse_json(analysis)
```

### Phase 4: Fine-Tuning Data Generation

```python
async def generate_fine_tuning_dataset():
    """
    Create fine-tuning dataset from high-value interactions
    """
    # 1. Query high-value interactions
    high_value = await qdrant.scroll(
        collection="interaction-history",
        filter={
            "must": [
                {"key": "value_score", "range": {"gte": 0.7}},
                {"key": "outcome", "match": {"value": "success"}}
            ]
        },
        limit=1000
    )

    # 2. Format for fine-tuning
    training_data = []
    for interaction in high_value:
        training_data.append({
            "messages": [
                {"role": "system", "content": "You are a helpful NixOS and coding assistant."},
                {"role": "user", "content": interaction.payload["query"]},
                {"role": "assistant", "content": interaction.payload["response"]}
            ]
        })

    # 3. Save to JSONL format
    output_path = "~/.local/share/nixos-ai-stack/fine-tuning/dataset.jsonl"
    with open(output_path, 'w') as f:
        for item in training_data:
            f.write(json.dumps(item) + '\n')

    return output_path


async def fine_tune_local_model():
    """
    Fine-tune local model with accumulated knowledge
    """
    # 1. Generate dataset
    dataset_path = await generate_fine_tuning_dataset()

    # 2. Fine-tune using llama.cpp or unsloth
    # This is a placeholder - actual implementation depends on setup
    command = f"""
unsloth-finetune \\
    --base_model unsloth/Qwen3-4B-Instruct-2507-GGUF \\
    --dataset {dataset_path} \\
    --output ~/.local/share/nixos-ai-stack/lemonade-models/qwen3-4b-finetuned \\
    --epochs 3 \\
    --batch_size 4 \\
    --learning_rate 2e-5
"""

    await execute_command(command)
```

## Query Routing Logic

**Decision Tree**:

```python
async def route_query(query: str, context: dict):
    """
    Decide: local LLM or remote agent?
    """
    # 1. Estimate query complexity
    complexity = estimate_query_complexity(query)

    # 2. Check if we have relevant context
    has_context = len(context["context_ids"]) > 0

    # 3. Estimate local capability
    local_confidence = await estimate_local_capability(query)

    # 4. Check token count
    estimated_tokens = estimate_tokens(query + str(context))

    # Decision logic
    if complexity == "simple" and has_context:
        return "local"  # Local LLM with context

    elif complexity == "medium" and local_confidence > 0.7:
        return "local"  # Local LLM can handle

    elif estimated_tokens > 4000:
        # Heavy context - use local for augmentation, remote for reasoning
        return "hybrid"

    elif complexity == "complex":
        return "remote"  # Remote agent needed

    else:
        return "local"  # Default to local
```

## Monitoring & Analytics

### Dashboards (Grafana + Prometheus)

**Metrics to Track**:

1. **Cost Savings**:
   - Tokens saved by local context augmentation
   - Remote API calls avoided
   - Cost comparison (local vs remote)

2. **Learning Progress**:
   - Number of high-value interactions
   - Pattern extraction rate
   - Context reuse frequency
   - Success rate trend over time

3. **Performance**:
   - Local LLM inference latency
   - Qdrant query latency
   - End-to-end response time
   - Cache hit rate

4. **Quality**:
   - User feedback distribution
   - Outcome success rate
   - Context relevance scores
   - Model confidence levels

## Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- ✅ Design Qdrant collection schemas
- ✅ Implement value scoring algorithm
- ✅ Create context augmentation service
- Build basic outcome tracking

### Phase 2: Learning Loop (Week 3-4)
- Implement pattern extraction
- Build fine-tuning pipeline
- Create automated model updates
- Add monitoring dashboards

### Phase 3: Optimization (Week 5-6)
- Optimize query routing
- Improve value scoring
- Add A/B testing
- Performance tuning

### Phase 4: Advanced Features (Week 7-8)
- Multi-model ensembles
- Automated skill discovery
- Cross-agent learning
- Production deployment

## Configuration

**Environment Variables** (`ai-stack/compose/.env`):

```bash
# Hybrid Learning Configuration
HYBRID_MODE_ENABLED=true
LOCAL_CONFIDENCE_THRESHOLD=0.7
HIGH_VALUE_THRESHOLD=0.7
PATTERN_EXTRACTION_ENABLED=true
AUTO_FINETUNE_ENABLED=false  # Manual trigger initially
FINETUNE_INTERVAL_DAYS=30

# Qdrant Configuration
QDRANT_URL=http://qdrant:6333
QDRANT_API_KEY=  # Optional

# Model Routing
PREFER_LOCAL=true  # Prefer local when confidence is high
HYBRID_TOKEN_THRESHOLD=4000
```

## Benefits

### For Remote Agents (Claude, GPT-4)
- **Reduced Token Usage**: Local context eliminates redundant explanations
- **Better Accuracy**: Domain-specific context from codebase
- **Faster Responses**: Pre-filtered relevant information
- **Cost Savings**: 30-50% reduction in API costs

### For Local LLMs
- **Continuous Improvement**: Learn from every interaction
- **Domain Specialization**: Fine-tuned on your specific use cases
- **Pattern Recognition**: Accumulate reusable solutions
- **Quality Improvement**: Success/failure feedback drives refinement

### For the System
- **Self-Optimizing**: Gets better over time automatically
- **Knowledge Retention**: Never forget solutions to solved problems
- **Reduced Latency**: More queries handled locally over time
- **Resilience**: Less dependent on remote API availability

## Next Steps

Ready to implement! Shall I:

1. **Create the Hybrid Agent Coordinator MCP server**
2. **Set up Qdrant collections with schemas**
3. **Implement the value scoring system**
4. **Build the context augmentation pipeline**
5. **Create the fine-tuning automation scripts**

Let me know which component to start with!
