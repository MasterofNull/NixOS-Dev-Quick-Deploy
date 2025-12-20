# Hybrid Agent Coordinator MCP Server

Intelligently coordinates between local LLMs and remote AI agents while implementing continuous learning through interaction tracking and pattern extraction.

## Features

### 1. Context Augmentation
- Retrieves relevant context from Qdrant vector database
- Reduces remote agent token usage by 30-50%
- Provides domain-specific knowledge from local codebase

### 2. Query Routing
- Automatically determines local vs remote processing
- Routes to specialized models (general, coding, analysis)
- Optimizes for cost and latency

### 3. Continuous Learning
- Tracks all interactions with outcome and feedback
- Computes value scores for learning prioritization
- Extracts reusable patterns from successful interactions
- Generates fine-tuning datasets automatically

### 4. Knowledge Management
- Stores high-value data in Qdrant collections
- Updates success rates for context items
- Maintains best practices and error solutions
- Builds reusable skill library

## Installation

```bash
cd ai-stack/mcp-servers/hybrid-coordinator
pip install -r requirements.txt
```

## Usage

### As MCP Server

Add to your MCP configuration:

```json
{
  "mcpServers": {
    "hybrid-coordinator": {
      "command": "python",
      "args": ["/path/to/hybrid-coordinator/server.py"],
      "env": {
        "QDRANT_URL": "http://localhost:6333",
        "LEMONADE_BASE_URL": "http://localhost:8000/api/v1",
        "LOCAL_CONFIDENCE_THRESHOLD": "0.7",
        "HIGH_VALUE_THRESHOLD": "0.7",
        "PATTERN_EXTRACTION_ENABLED": "true"
      }
    }
  }
}
```

### Available Tools

#### 1. `augment_query`
Augment a query with relevant context from local knowledge base.

```python
result = await mcp.call_tool("augment_query", {
    "query": "How do I configure Nginx in NixOS?",
    "agent_type": "remote"
})
```

**Returns**:
```json
{
  "augmented_prompt": "Query: How do I configure Nginx in NixOS?\n\nRelevant Context...",
  "context_ids": ["uuid1", "uuid2", "uuid3"],
  "original_query": "How do I configure Nginx in NixOS?",
  "context_count": 3
}
```

#### 2. `track_interaction`
Record an interaction for learning and analysis.

```python
interaction_id = await mcp.call_tool("track_interaction", {
    "query": "How do I configure Nginx in NixOS?",
    "response": "To configure Nginx in NixOS...",
    "agent_type": "remote",
    "model_used": "claude-sonnet-4",
    "context_ids": ["uuid1", "uuid2"],
    "tokens_used": 1500,
    "latency_ms": 2300
})
```

**Returns**:
```json
{
  "interaction_id": "uuid-of-interaction"
}
```

#### 3. `update_outcome`
Update interaction outcome and trigger learning.

```python
await mcp.call_tool("update_outcome", {
    "interaction_id": "uuid-of-interaction",
    "outcome": "success",  # or "partial", "failure"
    "user_feedback": 1  # -1 (bad), 0 (neutral), 1 (good)
})
```

This automatically:
- Computes value score
- Updates context success rates
- Extracts patterns if high-value
- Triggers fine-tuning data generation

#### 4. `generate_training_data`
Generate fine-tuning dataset from high-value interactions.

```python
result = await mcp.call_tool("generate_training_data", {})
```

**Returns**:
```json
{
  "dataset_path": "~/.local/share/nixos-ai-stack/fine-tuning/dataset.jsonl"
}
```

#### 5. `search_context`
Search specific collection for relevant context.

```python
results = await mcp.call_tool("search_context", {
    "query": "nixos module configuration",
    "collection": "codebase-context",
    "limit": 5
})
```

## Qdrant Collections

The server manages 5 collections:

### 1. `codebase-context`
Stores code snippets and their context from your codebase.

**Fields**:
- `file_path`: Source file path
- `code_snippet`: Code content
- `language`: Programming language
- `framework`: Framework/tool (nix, python, bash)
- `purpose`: What this code does
- `access_count`: How many times retrieved
- `success_rate`: Success rate when used as context

### 2. `skills-patterns`
Reusable patterns extracted from successful interactions.

**Fields**:
- `skill_name`: Name of the skill/pattern
- `description`: What it does
- `usage_pattern`: How to apply it
- `success_examples`: Examples of successful usage
- `failure_examples`: Common mistakes
- `prerequisites`: Required knowledge
- `related_skills`: Connected patterns
- `value_score`: Reusability score (0-1)

### 3. `error-solutions`
Known errors and their solutions.

**Fields**:
- `error_message`: Error text
- `error_type`: Category (nixos, python, build, etc.)
- `context`: When this error occurs
- `solution`: How to fix it
- `solution_verified`: Confirmed to work
- `success_count`: Times successfully applied
- `failure_count`: Times it didn't work
- `confidence_score`: Solution reliability (0-1)

### 4. `interaction-history`
Complete history of all interactions.

**Fields**:
- `query`: Original question
- `response`: Answer provided
- `agent_type`: local or remote
- `model_used`: Which model answered
- `context_provided`: Context IDs used
- `outcome`: success, partial, or failure
- `user_feedback`: -1, 0, or 1
- `tokens_used`: Token count
- `latency_ms`: Response time
- `value_score`: Learning value (0-1)

### 5. `best-practices`
Curated best practices and guidelines.

**Fields**:
- `category`: Domain (nixos, coding, deployment)
- `title`: Practice name
- `description`: What and why
- `examples`: Good examples
- `anti_patterns`: What to avoid
- `references`: Documentation links
- `endorsement_count`: Community validation

## Value Scoring

The system computes a value score (0-1) for each interaction based on:

1. **Outcome Quality (40%)**:
   - Success: +0.4
   - Partial: +0.2
   - Failure: +0.0

2. **User Feedback (20%)**:
   - Positive: +0.2
   - Neutral: +0.1
   - Negative: +0.0

3. **Reusability (20%)**:
   - Based on query pattern frequency
   - Keywords like "how to", "configure", "setup"

4. **Complexity (10%)**:
   - Multi-step solutions
   - Code blocks included
   - Response length

5. **Novelty (10%)**:
   - New patterns not seen before
   - Unique problem-solving approaches

**High-value threshold**: Interactions scoring ≥0.7 trigger pattern extraction and fine-tuning data generation.

## Continuous Learning Workflow

```
┌─────────────────┐
│ Remote Agent    │
│ Sends Query     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│ 1. Augment with Context │
│    (Search Qdrant)      │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 2. Provide Augmented    │
│    Query to Agent       │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 3. Track Interaction    │
│    (Store in Qdrant)    │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 4. Collect Outcome      │
│    (User Feedback)      │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 5. Compute Value Score  │
│    (Learning Priority)  │
└────────┬────────────────┘
         │
         ▼
    ┌───┴───┐
    │ Score │
    │ ≥0.7? │
    └───┬───┘
        │ Yes
        ▼
┌─────────────────────────┐
│ 6. Extract Patterns     │
│    (Using Local LLM)    │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 7. Store New Patterns   │
│    (skills-patterns)    │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 8. Update Context Metrics│
│    (Success Rates)      │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 9. Generate Training Data│
│    (For Fine-Tuning)    │
└─────────────────────────┘
```

## Environment Variables

```bash
# Qdrant Configuration
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=  # Optional

# Lemonade Configuration
LEMONADE_BASE_URL=http://localhost:8000/api/v1
LEMONADE_CODER_URL=http://localhost:8001/api/v1
LEMONADE_DEEPSEEK_URL=http://localhost:8003/api/v1

# Learning Configuration
LOCAL_CONFIDENCE_THRESHOLD=0.7
HIGH_VALUE_THRESHOLD=0.7
PATTERN_EXTRACTION_ENABLED=true

# Paths
FINETUNE_DATA_PATH=~/.local/share/nixos-ai-stack/fine-tuning/dataset.jsonl
```

## Integration Examples

### With Claude Code

```python
# In your Claude Code workflow
from mcp import ClientSession

async with ClientSession() as session:
    # 1. Augment query with local context
    context = await session.call_tool("augment_query", {
        "query": user_query,
        "agent_type": "remote"
    })

    # 2. Send augmented query to Claude
    response = await claude_api.complete(context["augmented_prompt"])

    # 3. Track the interaction
    interaction = await session.call_tool("track_interaction", {
        "query": user_query,
        "response": response,
        "agent_type": "remote",
        "model_used": "claude-sonnet-4",
        "context_ids": context["context_ids"],
        "tokens_used": response.usage.total_tokens
    })

    # 4. After user confirms it worked
    await session.call_tool("update_outcome", {
        "interaction_id": interaction["interaction_id"],
        "outcome": "success",
        "user_feedback": 1
    })
```

### With Local LLM Only

```python
async with ClientSession() as session:
    # 1. Augment with context
    context = await session.call_tool("augment_query", {
        "query": user_query,
        "agent_type": "local"
    })

    # 2. Use local Lemonade model
    response = await lemonade_inference(context["augmented_prompt"])

    # 3. Track for learning
    await session.call_tool("track_interaction", {
        "query": user_query,
        "response": response,
        "agent_type": "local",
        "model_used": "qwen-coder-7b",
        "context_ids": context["context_ids"]
    })
```

## Monitoring

### Check Collection Stats

```python
from qdrant_client import QdrantClient

client = QdrantClient("http://localhost:6333")

# Get collection info
info = client.get_collection("interaction-history")
print(f"Total interactions: {info.points_count}")

# Get high-value interactions count
results = client.scroll(
    collection_name="interaction-history",
    scroll_filter={"must": [{"key": "value_score", "range": {"gte": 0.7}}]},
    limit=1
)
print(f"High-value interactions: {results[1]}")
```

### Generate Training Dataset

```bash
# Via MCP tool
python -c "
from mcp import ClientSession
import asyncio

async def generate():
    async with ClientSession() as session:
        result = await session.call_tool('generate_training_data', {})
        print(result['dataset_path'])

asyncio.run(generate())
"
```

## Fine-Tuning Workflow

1. **Accumulate interactions** (recommended: 500+ high-value examples)
2. **Generate dataset**: Use `generate_training_data` tool
3. **Review dataset**: Check quality of examples
4. **Fine-tune model**: Use unsloth or llama.cpp
5. **Deploy updated model**: Replace in Lemonade container
6. **Monitor improvement**: Track success rates

## Troubleshooting

### Collections not initialized
```bash
# Check Qdrant is running
curl http://localhost:6333/health

# Restart MCP server to reinitialize
pkill -f hybrid-coordinator/server.py
python ai-stack/mcp-servers/hybrid-coordinator/server.py
```

### Pattern extraction slow
- Pattern extraction uses local LLM (Lemonade)
- Check Lemonade is running: `curl http://localhost:8000/health`
- Reduce `HIGH_VALUE_THRESHOLD` to extract less frequently
- Set `PATTERN_EXTRACTION_ENABLED=false` to disable

### Fine-tuning dataset empty
- Ensure interactions have `outcome="success"` and `value_score≥0.7`
- Check: `qdrant_client.scroll(collection_name="interaction-history", ...)`
- May need to accumulate more interactions first

## License

Part of NixOS-Dev-Quick-Deploy project.
