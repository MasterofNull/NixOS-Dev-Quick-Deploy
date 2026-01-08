# Hybrid Local-Remote AI Learning System - Complete Guide

> **📊 System Dashboard**: Monitor all services, metrics, and learning progress at [ai-stack/dashboard/index.html](/ai-stack/dashboard/index.html)

## Executive Summary

This system creates a **bidirectional learning loop** where:

1. **Local LLMs** (llama.cpp/Ollama) augment **remote agents** (Claude/GPT-4) with context
2. **Remote agents** benefit from reduced token costs and better accuracy
3. **Local LLMs** continuously learn from interactions and improve
4. **High-value data** is automatically identified and stored
5. **Patterns** are extracted and reused for future queries
6. **Fine-tuning datasets** are generated automatically from successful interactions

## Architecture Overview

```
┌───────────────────────────────────────────────────────────────────┐
│                    Remote AI Agents                                │
│  • Claude Code / Sonnet 4.5                                        │
│  • GPT-4 / DeepSeek                                                │
│  • Anthropic API / OpenAI API                                      │
└──────────────────┬──────────────────────────────┬─────────────────┘
                   │                              │
         Context   │                              │  Results +
         Requests  │                              │  Feedback
                   ▼                              ▼
┌───────────────────────────────────────────────────────────────────┐
│          Hybrid Agent Coordinator (MCP Server)                     │
│  • Query augmentation with local context                           │
│  • Intelligent routing (local vs remote)                           │
│  • Interaction tracking & outcome recording                        │
│  • Value scoring & pattern extraction                              │
│  • Fine-tuning dataset generation                                  │
└────┬──────────┬───────────┬──────────┬──────────┬──────────────┬──┘
     │          │           │          │          │              │
     ▼          ▼           ▼          ▼          ▼              ▼
┌─────────┐ ┌──────┐ ┌──────────┐ ┌──────┐ ┌──────────┐ ┌──────────┐
│Codebase │ │Skills│ │  Error   │ │ Best │ │Interaction│ │PostgreSQL│
│Context  │ │Patterns│ Solutions│ │Practices│ History │ │ Metrics  │
└─────────┘ └──────┘ └──────────┘ └──────┘ └──────────┘ └──────────┘
     │          │           │          │          │              │
     └──────────┴───────────┴──────────┴──────────┴──────────────┘
                              │
                    Qdrant Vector Database
                              │
                ┌─────────────┴─────────────┐
                │                           │
                ▼                           ▼
         ┌──────────────┐         ┌──────────────┐
         │ Embeddings   │         │  Learning    │
         │ (Ollama)     │         │  Pipeline    │
         └──────────────┘         └──────────────┘
                                         │
                                         ▼
                              ┌───────────────────┐
                              │  Local LLM Stack  │
                              │                   │
                              │ • llama.cpp (3x)   │
                              │ • Ollama          │
                              │ • Fine-tuned      │
                              └───────────────────┘
```

## Key Components

### 1. Hybrid Agent Coordinator MCP Server

**Location**: `ai-stack/mcp-servers/hybrid-coordinator/`

**Purpose**: Orchestrates all learning and coordination activities.

**Core Functions**:
- **Context Augmentation**: Retrieves relevant context from Qdrant before queries
- **Query Routing**: Decides local vs remote processing
- **Interaction Tracking**: Records every query/response pair
- **Value Scoring**: Ranks data by learning value (0-1 scale)
- **Pattern Extraction**: Uses local LLM to extract reusable patterns
- **Dataset Generation**: Creates fine-tuning data from high-value interactions

### 2. Qdrant Vector Database (Enhanced)

**5 Collections for Continuous Learning**:

| Collection | Purpose | Key Fields |
|------------|---------|------------|
| `codebase-context` | Code snippets & context | file_path, code_snippet, success_rate |
| `skills-patterns` | Reusable patterns | skill_name, usage_pattern, value_score |
| `error-solutions` | Known errors & fixes | error_message, solution, confidence_score |
| `interaction-history` | Complete interaction log | query, response, outcome, value_score |
| `best-practices` | Curated guidelines | category, description, endorsement_count |

### 3. Local LLM Stack

**llama.cpp Services**:
- **Port 8080**: General reasoning (Qwen3-4B)
- **Port 8001**: Code generation (Qwen2.5-Coder-7B)
- **Port 8003**: Code analysis (Deepseek-Coder-6.7B)

**Ollama (Optional)**:
- Embeddings generation
- High-capacity reasoning (Llama 3.1 70B)
- Code specialization (CodeLlama 34B)

### 4. Learning Feedback Loop

Automatic continuous improvement through:
1. Outcome tracking
2. Value scoring
3. Pattern extraction
4. Fine-tuning data generation
5. Periodic model updates

## How It Works

### Scenario 1: Remote Agent Requests Context

```python
# 1. User asks Claude Code a question
user_query = "How do I configure Nginx with SSL in NixOS?"

# 2. Hybrid Coordinator augments with local context
context = await hybrid_coordinator.augment_query(user_query, "remote")

# Context retrieved from Qdrant:
# - Similar code snippets from your NixOS configs
# - Related skills (nginx, ssl, nixos-modules)
# - Previous error solutions (SSL certificate issues)
# - Best practices (security configurations)

# 3. Augmented query sent to Claude
augmented_query = f"""
{user_query}

Relevant context from local knowledge base:
{context["codebase_context"]}
{context["skills_patterns"]}
{context["error_solutions"]}
{context["best_practices"]}
"""

# 4. Claude responds with context-aware answer
response = await claude_api.complete(augmented_query)

# 5. Track interaction
interaction_id = await hybrid_coordinator.track_interaction(
    query=user_query,
    response=response,
    agent_type="remote",
    model_used="claude-sonnet-4",
    context_ids=context["context_ids"],
    tokens_used=response.usage.total_tokens
)

# 6. User confirms it worked
await hybrid_coordinator.update_outcome(
    interaction_id=interaction_id,
    outcome="success",
    user_feedback=1  # positive
)

# 7. System learns automatically:
# - Computes value score (e.g., 0.85)
# - Updates context success rates
# - Extracts pattern: "nginx ssl configuration"
# - Adds to fine-tuning dataset
```

**Benefits**:
- **30-50% token reduction** for Claude
- **Better accuracy** from domain context
- **Faster responses** (pre-filtered info)
- **Learning capture** for future use

### Scenario 2: Local LLM Handles Query Directly

```python
# 1. User asks a question
user_query = "Fix this NixOS module syntax error"

# 2. Check if local LLM can handle
local_confidence = estimate_local_capability(user_query)  # 0.92

# 3. Augment with context
context = await hybrid_coordinator.augment_query(user_query, "local")

# 4. Use local llama.cpp model
response = await llama-cpp_coder.inference(context["augmented_prompt"])

# 5. Track for learning
await hybrid_coordinator.track_interaction(
    query=user_query,
    response=response,
    agent_type="local",
    model_used="qwen-coder-7b",
    context_ids=context["context_ids"]
)
```

**Benefits**:
- **Zero API costs**
- **Faster response** (local inference)
- **Privacy** (data never leaves system)
- **Continuous improvement** (local model learns)

### Scenario 3: Hybrid Approach (Heavy Context)

```python
# 1. Complex query with lots of context
user_query = "Analyze this entire codebase and suggest refactorings"

# 2. Estimated tokens > 4000 (too expensive for remote)

# 3. Local LLM performs initial analysis
local_analysis = await llama-cpp_deepseek.analyze(codebase)

# 4. Remote agent gets summarized context
summary = local_analysis["summary"]
response = await claude_api.complete(f"{user_query}\n\nLocal Analysis:\n{summary}")

# 5. Both interactions tracked for learning
```

**Benefits**:
- **Cost optimization** (local for heavy lifting)
- **Quality maintained** (remote for final polish)
- **Both models learn** from interaction

## Value Scoring Algorithm

Every interaction gets a value score (0-1) based on:

```python
def compute_value_score(interaction):
    score = 0.0

    # 1. Outcome Quality (40%)
    if outcome == "success": score += 0.4
    elif outcome == "partial": score += 0.2

    # 2. User Feedback (20%)
    if user_feedback == +1: score += 0.2
    elif user_feedback == 0: score += 0.1

    # 3. Reusability (20%)
    # Higher for "how to", "configure", etc.
    score += 0.2 * estimate_reusability(query)

    # 4. Complexity (10%)
    # Multi-step, code-heavy solutions
    score += 0.1 * estimate_complexity(response)

    # 5. Novelty (10%)
    # New patterns not seen before
    score += 0.1 * estimate_novelty(query)

    return min(score, 1.0)
```

**High-value threshold**: 0.7

**What happens when value ≥ 0.7?**
1. Pattern extraction triggered
2. Added to fine-tuning dataset
3. Context success rates boosted
4. Stored in `skills-patterns` collection

## Pattern Extraction Process

When a high-value interaction occurs:

```python
# 1. Local LLM analyzes the interaction
prompt = f"""
Analyze this successful interaction:

Query: {query}
Response: {response}

Extract:
1. Problem type
2. Solution approach
3. Skills used
4. Generalizable pattern

Return JSON.
"""

# 2. llama.cpp extracts patterns
analysis = await llama-cpp.inference(prompt)

# 3. Stored in Qdrant
pattern = {
    "skill_name": analysis["problem_type"],
    "description": analysis["generalizable_pattern"],
    "usage_pattern": analysis["solution_approach"],
    "success_examples": [response],
    "value_score": 0.85,
    ...
}

await qdrant.insert("skills-patterns", pattern)
```

**Result**: Pattern becomes reusable context for future queries!

## Fine-Tuning Workflow

### Step 1: Accumulate High-Value Interactions

Target: **500-1000 examples** with `value_score ≥ 0.7`

```bash
# Check current count
python -c "
from qdrant_client import QdrantClient
client = QdrantClient('http://localhost:6333')
result = client.scroll(
    collection_name='interaction-history',
    scroll_filter={'must': [
        {'key': 'value_score', 'range': {'gte': 0.7}},
        {'key': 'outcome', 'match': {'value': 'success'}}
    ]},
    limit=1
)
print(f'High-value interactions: {result[1]}')
"
```

### Step 2: Generate Fine-Tuning Dataset

```python
# Via MCP tool
await hybrid_coordinator.generate_training_data()

# Output: ~/.local/share/nixos-ai-stack/fine-tuning/dataset.jsonl
```

**Dataset Format** (OpenAI JSONL):
```json
{
  "messages": [
    {"role": "system", "content": "You are a helpful NixOS assistant..."},
    {"role": "user", "content": "How do I configure Nginx?"},
    {"role": "assistant", "content": "To configure Nginx in NixOS..."}
  ]
}
```

### Step 3: Fine-Tune Model

```bash
# Using unsloth (recommended)
unsloth-finetune \
    --base_model unsloth/Qwen2.5-Coder-7B-Instruct-GGUF \
    --dataset ~/.local/share/nixos-ai-stack/fine-tuning/dataset.jsonl \
    --output ~/.local/share/nixos-ai-stack/llama-cpp-models/qwen-coder-finetuned \
    --epochs 3 \
    --batch_size 4 \
    --learning_rate 2e-5

# Or using llama.cpp
llama-finetune \
    --model ~/.cache/huggingface/qwen2.5-coder-7b-instruct-q4_k_m.gguf \
    --train-data ~/.local/share/nixos-ai-stack/fine-tuning/dataset.jsonl \
    --output ~/.local/share/nixos-ai-stack/llama-cpp-models/qwen-coder-finetuned.gguf
```

### Step 4: Deploy Updated Model

```bash
# Update docker-compose.yml to use fine-tuned model
# Then restart llama.cpp containers
cd ai-stack/compose/
podman-compose down llama-cpp-coder
podman-compose up -d llama-cpp-coder
```

### Step 5: Monitor Improvement

Track metrics:
- Success rate trend
- User feedback distribution
- Context reuse frequency
- Token cost savings

## Setup Instructions

### 1. Install Hybrid Coordinator

```bash
cd /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator
pip install -r requirements.txt
```

### 2. Configure Environment

Edit `ai-stack/compose/.env`:

```bash
# Hybrid Learning Configuration
HYBRID_MODE_ENABLED=true
LOCAL_CONFIDENCE_THRESHOLD=0.7
HIGH_VALUE_THRESHOLD=0.7
PATTERN_EXTRACTION_ENABLED=true
AUTO_FINETUNE_ENABLED=false  # Manual initially

# Qdrant Configuration
QDRANT_URL=http://qdrant:6333
```

### 3. Start Services

```bash
cd ai-stack/compose/
podman-compose up -d
```

This starts:
- llama.cpp (3 containers)
- Qdrant vector database
- Ollama (embeddings)
- Hybrid Coordinator MCP server

### 4. Initialize Collections

Collections are created automatically on first run.

Verify:
```bash
curl http://localhost:6333/collections | jq '.result.collections[].name'
```

Should show:
- codebase-context
- skills-patterns
- error-solutions
- interaction-history
- best-practices

### 5. Seed Initial Data

Populate with your codebase:

```python
# seed_codebase.py
import asyncio
from hybrid_coordinator import embed_text
from qdrant_client import QdrantClient

async def seed():
    client = QdrantClient("http://localhost:6333")

    # Example: Add NixOS module
    code_snippet = """
    services.nginx = {
      enable = true;
      virtualHosts."example.com" = {
        enableACME = true;
        forceSSL = true;
        root = "/var/www/example.com";
      };
    };
    """

    embedding = await embed_text(code_snippet)

    client.upsert(
        collection_name="codebase-context",
        points=[{
            "id": "nixos-nginx-ssl-example",
            "vector": embedding,
            "payload": {
                "file_path": "examples/nginx-ssl.nix",
                "code_snippet": code_snippet,
                "language": "nix",
                "framework": "nixos",
                "purpose": "Configure Nginx with SSL and ACME",
                "access_count": 0,
                "success_rate": 0.5
            }
        }]
    )

asyncio.run(seed())
```

## Integration with Claude Code

Add to your Claude Code MCP configuration:

```json
{
  "mcpServers": {
    "hybrid-coordinator": {
      "command": "python",
      "args": [
        "/home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/ai-stack/mcp-servers/hybrid-coordinator/server.py"
      ],
      "env": {
        "QDRANT_URL": "http://localhost:6333",
        "LLAMA_CPP_BASE_URL": "http://localhost:8080",
        "LOCAL_CONFIDENCE_THRESHOLD": "0.7",
        "HIGH_VALUE_THRESHOLD": "0.7",
        "PATTERN_EXTRACTION_ENABLED": "true"
      }
    }
  }
}
```

**Usage in Conversation**:

```
User: How do I configure Postgres in NixOS?

Claude: Let me check our local knowledge base first...
[Calls hybrid-coordinator.augment_query]

Based on our codebase context, here's how to configure PostgreSQL:
[Provides answer using retrieved context]

[After successful outcome]
[Calls hybrid-coordinator.update_outcome with success=true]

This solution has been stored for future reference!
```

## Monitoring Dashboard

### Metrics to Track

1. **Cost Savings**:
   - Tokens saved by context augmentation
   - API calls avoided by local processing
   - Monthly cost comparison

2. **Learning Progress**:
   - High-value interactions accumulated
   - Patterns extracted
   - Fine-tuning datasets generated
   - Success rate improvements

3. **Performance**:
   - Query routing decisions (local vs remote)
   - Average response latency
   - Context retrieval time
   - Qdrant query performance

4. **Quality**:
   - User feedback distribution
   - Outcome success rates
   - Context relevance scores
   - Model confidence levels

### Grafana Dashboard Setup

```bash
# Add to docker-compose.yml
services:
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"
    volumes:
      - ./monitoring/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/datasources:/etc/grafana/provisioning/datasources
```

Dashboard queries:
- High-value interaction count: `SELECT COUNT(*) FROM interactions WHERE value_score >= 0.7`
- Success rate trend: `SELECT date, AVG(outcome='success') FROM interactions GROUP BY date`
- Token savings: `SELECT SUM(tokens_saved) FROM interactions WHERE agent_type='context_only'`

## Advanced Features

### Multi-Agent Collaboration

```python
# Parallel processing with local ensemble
async def ensemble_query(query):
    results = await asyncio.gather(
        llama-cpp_general.inference(query),
        llama-cpp_coder.inference(query),
        llama-cpp_deepseek.inference(query)
    )

    # Vote or combine results
    best_response = vote(results)

    return best_response
```

### Automated Skill Discovery

```python
# Periodically analyze interaction patterns
async def discover_new_skills():
    # Find frequently co-occurring patterns
    patterns = await analyze_pattern_clusters()

    for cluster in patterns:
        if cluster.frequency > threshold:
            await create_skill_from_cluster(cluster)
```

### Cross-Agent Learning

```python
# Share successful patterns between local and remote
async def share_learning():
    # Extract what worked for remote agent
    remote_patterns = extract_patterns(remote_successes)

    # Fine-tune local model with these patterns
    await fine_tune_local(remote_patterns)

    # Vice versa: share local discoveries with remote context
    local_discoveries = extract_patterns(local_successes)
    await update_remote_context(local_discoveries)
```

## Expected Outcomes

### Month 1
- **500+ interactions** tracked
- **50+ patterns** extracted
- **20% token savings** from context augmentation
- Collections populated with initial data

### Month 3
- **2000+ interactions** tracked
- **200+ patterns** extracted
- **40% token savings**
- First fine-tuned model deployed
- Measurable improvement in local LLM accuracy

### Month 6
- **5000+ interactions** tracked
- **500+ patterns** extracted
- **50% token savings**
- Multiple fine-tuned models
- Local LLM handles 60%+ of queries
- Significant quality improvements measured

### Long-term (1 year+)
- **10,000+ interactions**
- **1000+ patterns**
- **70% token savings**
- Highly specialized local models
- Local LLM handles 80%+ of queries
- Remote agents reserved for complex novel problems only

## Troubleshooting

### Collections not created
```bash
# Check Qdrant
curl http://localhost:6333/health

# Restart hybrid coordinator
pkill -f hybrid-coordinator
python ai-stack/mcp-servers/hybrid-coordinator/server.py
```

### Pattern extraction not working
```bash
# Check llama.cpp is running
curl http://localhost:8080/health

# Check logs
podman logs llama-cpp

# Disable temporarily
export PATTERN_EXTRACTION_ENABLED=false
```

### Fine-tuning dataset empty
```bash
# Check high-value count
python -c "from qdrant_client import QdrantClient; ..."

# Lower threshold temporarily
export HIGH_VALUE_THRESHOLD=0.6
```

## References

- **Architecture Document**: [ai-knowledge-base/HYBRID-LEARNING-ARCHITECTURE.md](ai-knowledge-base/HYBRID-LEARNING-ARCHITECTURE.md)
- **Hybrid Coordinator**: [ai-stack/mcp-servers/hybrid-coordinator/](/ai-stack/mcp-servers/hybrid-coordinator/)
- **llama.cpp API**: [ai-knowledge-base/reference/llama-cpp-api.md](ai-knowledge-base/reference/llama-cpp-api.md)
- **MCP Server Catalogs**: [ai-knowledge-base/mcp-servers/](ai-knowledge-base/mcp-servers/)

---

**Last Updated**: 2025-12-19
**Version**: 1.0.0
**Status**: Ready for Implementation
