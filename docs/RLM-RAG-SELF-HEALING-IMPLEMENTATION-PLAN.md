# RLM, RAG, Self-Healing & Progressive Disclosure Implementation Plan
**Date:** 2026-01-05
**Status:** In Progress
**Goal:** Transform the AI stack into a fully autonomous, self-improving, self-healing system that augments remote LLMs (like Claude)

---

## Executive Summary

This document outlines the implementation plan for transforming the current AI stack (100% operational for basic agentic workflows) into an advanced system supporting:

1. **RLM (Recursive Language Model)** - Remote LLMs (Claude, GPT-4) recursively improve responses using local context
2. **RAG (Retrieval Augmented Generation)** - Provide rich context to remote LLMs from local knowledge base
3. **Progressive Disclosure** - Efficiently provide context to remote LLMs to minimize token usage
4. **Self-Healing** - Autonomous error detection, diagnosis, and recovery
5. **Continuous Learning** - Learn from remote LLM interactions to improve local context quality

---

## Architecture Overview: Remote LLM Augmentation

### Primary Workflow

```
Remote LLM (Claude/GPT-4)
    ↓
Sends query to local AI stack via HTTP
    ↓
Local AI Stack:
    ├─ Search Qdrant for relevant context (RAG)
    ├─ Retrieve similar past solutions
    ├─ Check error patterns
    ├─ Query local LLM for quick facts
    ├─ Compress context to fit token budget (Progressive Disclosure)
    └─ Return enriched context
    ↓
Remote LLM generates response with local context
    ↓
Response quality evaluated (RLM)
    ↓
If low confidence:
    ├─ Remote LLM requests additional context
    ├─ Local stack provides deeper context
    └─ Remote LLM refines response
    ↓
Final response returned to user
    ↓
Local stack records interaction for learning
```

### Key Insight

The local AI stack is a **context augmentation service** for remote LLMs:
- **Remote LLM = Intelligence** (Claude, GPT-4)
- **Local Stack = Memory & Context** (knowledge base, past solutions, error patterns)
- **RLM = Feedback Loop** (remote LLM evaluates its own responses and requests more context)

---

## Current State Analysis

### What We Have ✅

**Infrastructure (100% Operational)**:
- 12 containerized services running on Podman
- llama.cpp with Qwen 2.5 Coder 7B (supplementary local LLM)
- Qdrant vector database (384D embeddings, 5 collections)
- PostgreSQL + TimescaleDB (relational + time-series)
- Redis (caching layer)
- Ralph Wiggum loop engine (task orchestration)
- Direct llama.cpp code generation wrapper
- MindsDB (ML predictions)
- Open WebUI (chat interface)
- **Hybrid Coordinator** - Already has context augmentation API!

**Existing Context Augmentation (70% Complete)**:
- ✅ `/augment` MCP tool in Hybrid Coordinator (server.py:200+)
- ✅ Multi-collection search (codebase-context, skills-patterns, error-solutions, best-practices)
- ✅ Interaction tracking
- ✅ Value scoring for learned patterns
- ❌ No progressive disclosure (always returns full context)
- ❌ No recursive refinement support
- ❌ No context compression
- ❌ Limited document coverage

**Learning Pipeline (70% Complete)**:
- ✅ Interaction tracking in Hybrid Coordinator
- ✅ Value scoring algorithm (5 factors)
- ✅ Pattern extraction from high-value interactions
- ✅ Fine-tuning dataset generation (JSONL export)
- ✅ Telemetry recording (JSONL format)
- ❌ No automated training loop
- ❌ No feedback collection from remote LLMs
- ❌ No model versioning/comparison

**RAG Components (60% Complete)**:
- ✅ Qdrant vector database with 5 collections
- ✅ Embedding generation (all-MiniLM-L6-v2)
- ✅ Multi-collection semantic search
- ✅ Context augmentation in queries
- ❌ No document import pipeline (only ~100 docs currently)
- ❌ No chunking strategy for long docs
- ❌ No query expansion or reranking
- ❌ No embedding cache

**Self-Healing (50% Complete)**:
- ✅ Health monitoring for all services
- ✅ Error pattern library (7 patterns)
- ✅ Automatic container restart with cooldown
- ✅ Dependency-aware restart
- ✅ Healing history tracking
- ❌ Only 7 hardcoded patterns (needs ML-based learning)
- ❌ Limited fix strategies (mostly just restart)
- ❌ No proactive healing (reactive only)
- ❌ No rollback capability

**Progressive Disclosure (5% Complete)**:
- ✅ Documentation and architecture defined
- ✅ 4 disclosure levels specified
- ❌ No API endpoints implemented
- ❌ No context compression
- ❌ No adaptive context selection

---

## RLM (Recursive Language Model) Architecture for Remote LLMs

### Concept Overview

RLM enables **remote LLMs (like Claude)** to **recursively improve responses** by querying the local stack multiple times:

```
Claude receives user request: "Fix this NixOS error: <error message>"
    ↓
Claude Query 1 to Local Stack: "Search for similar NixOS errors"
    ↓
Local Stack Response: [5 similar error patterns with solutions]
    ↓
Claude generates initial response using context
    ↓
Claude self-evaluates: "Confidence: 0.65 - Missing specific fix for this variant"
    ↓
Claude Query 2 to Local Stack: "Get detailed NixOS service configuration examples"
    ↓
Local Stack Response: [Detailed config examples]
    ↓
Claude generates refined response
    ↓
Claude self-evaluates: "Confidence: 0.90 - High confidence"
    ↓
Return final response to user
    ↓
Claude Query 3 to Local Stack: "Record successful interaction"
    ↓
Local Stack stores pattern for future use
```

### Key Components to Build

#### 1. Multi-Turn Context API
**File:** `ai-stack/mcp-servers/hybrid-coordinator/multi_turn_context.py`

**Purpose:** Support multiple context requests from remote LLMs during a single task

**Features**:
- Session management (track conversation state)
- Progressive context deepening (each request gets more specific)
- Context history (avoid re-sending same info)
- Token budget tracking

**Implementation**:
```python
class MultiTurnContextManager:
    """
    Manage multi-turn context requests from remote LLMs

    Example usage by remote LLM (Claude):

    # Turn 1: Initial broad search
    POST /context/augment
    {
        "session_id": "uuid",
        "query": "NixOS GNOME keyring error",
        "context_level": "standard",
        "previous_context_ids": []
    }

    # Turn 2: Deeper specific search
    POST /context/augment
    {
        "session_id": "uuid",
        "query": "NixOS GNOME keyring service configuration",
        "context_level": "detailed",
        "previous_context_ids": ["ctx_1", "ctx_2"]  # Don't re-send these
    }
    """

    def __init__(self, qdrant_client, redis_client):
        self.qdrant = qdrant_client
        self.redis = redis_client
        self.session_ttl = 3600  # 1 hour

    async def get_context(
        self,
        session_id: str,
        query: str,
        context_level: str = "standard",  # standard, detailed, comprehensive
        previous_context_ids: List[str] = None,
        max_tokens: int = 2000
    ) -> ContextResponse:
        """
        Get context for remote LLM with progressive disclosure

        Args:
            session_id: Unique session to track multi-turn conversations
            query: Current query from remote LLM
            context_level: How much detail to return
            previous_context_ids: Context already sent (to avoid duplication)
            max_tokens: Budget for this response

        Returns:
            context: Relevant context within token budget
            context_ids: IDs of returned context (for next turn)
            suggestions: Suggested follow-up queries for refinement
        """
        # Load session state
        session = await self.load_session(session_id)

        # Search Qdrant for relevant context
        raw_results = await self.search_all_collections(query, context_level)

        # Filter out previously sent context
        if previous_context_ids:
            raw_results = [r for r in raw_results if r.id not in previous_context_ids]

        # Rank by relevance
        ranked_results = await self.rank_results(query, raw_results)

        # Compress to fit token budget
        compressed_context, included_ids = await self.compress_to_budget(
            ranked_results,
            max_tokens,
            context_level
        )

        # Generate suggestions for next turn
        suggestions = await self.generate_suggestions(query, compressed_context, session)

        # Update session state
        session["queries"].append(query)
        session["context_sent"].extend(included_ids)
        await self.save_session(session_id, session)

        return ContextResponse(
            context=compressed_context,
            context_ids=included_ids,
            suggestions=suggestions,
            token_count=self.count_tokens(compressed_context),
            collections_searched=self.get_collection_names(ranked_results)
        )

    async def search_all_collections(
        self,
        query: str,
        context_level: str
    ) -> List[SearchResult]:
        """
        Search appropriate collections based on context level

        Context Levels:
        - standard: error-solutions, best-practices (quick answers)
        - detailed: + codebase-context (code examples)
        - comprehensive: + skills-patterns, interaction-history (everything)
        """
        collections_to_search = {
            "standard": ["error-solutions", "best-practices"],
            "detailed": ["error-solutions", "best-practices", "codebase-context"],
            "comprehensive": ["error-solutions", "best-practices", "codebase-context",
                             "skills-patterns", "interaction-history"]
        }

        collections = collections_to_search.get(context_level, ["error-solutions"])

        all_results = []
        for collection in collections:
            results = await self.qdrant.search(
                collection_name=collection,
                query_text=query,
                limit=10,
                score_threshold=0.7
            )
            all_results.extend(results)

        return all_results

    async def compress_to_budget(
        self,
        results: List[SearchResult],
        max_tokens: int,
        context_level: str
    ) -> Tuple[str, List[str]]:
        """
        Compress results to fit within token budget

        Strategies:
        1. Prioritize by relevance score
        2. Summarize long results
        3. Use bullet points for standard level
        4. Include full text for comprehensive level
        """
        compressed_parts = []
        included_ids = []
        current_tokens = 0

        for result in results:
            # Format based on context level
            if context_level == "standard":
                # Concise bullet points
                formatted = f"- {result.payload.get('summary', result.payload.get('content', '')[:200])}"
            elif context_level == "detailed":
                # Include key details
                formatted = self.format_detailed(result)
            else:  # comprehensive
                # Full content
                formatted = self.format_comprehensive(result)

            tokens = self.count_tokens(formatted)

            if current_tokens + tokens > max_tokens:
                # Budget exceeded
                if context_level == "comprehensive":
                    # Try summarizing
                    formatted = await self.summarize(formatted, max_tokens - current_tokens)
                    tokens = self.count_tokens(formatted)
                    if current_tokens + tokens <= max_tokens:
                        compressed_parts.append(formatted)
                        included_ids.append(result.id)
                break

            compressed_parts.append(formatted)
            included_ids.append(result.id)
            current_tokens += tokens

        return "\n\n".join(compressed_parts), included_ids

    async def generate_suggestions(
        self,
        query: str,
        context: str,
        session: Dict
    ) -> List[str]:
        """
        Suggest follow-up queries for remote LLM to refine response

        Example:
        Query: "Fix GNOME keyring error"
        Context: [Error patterns found]
        Suggestions:
        - "Get NixOS GNOME service configuration examples"
        - "Search for gcr-ssh-agent setup guides"
        - "Find systemd service dependencies for GNOME"
        """
        # Use local LLM to generate suggestions
        prompt = f"""
Given this query and context, suggest 3 follow-up queries that would provide additional helpful information:

Original Query: {query}

Context Provided:
{context[:500]}...

Previous Queries in Session:
{session.get('queries', [])}

Generate 3 specific, actionable follow-up queries:
"""

        # Call local LLM (fast, free)
        response = await self.call_local_llm(prompt)
        suggestions = self.parse_suggestions(response)

        return suggestions[:3]
```

#### 2. Self-Evaluation API for Remote LLMs
**File:** `ai-stack/mcp-servers/hybrid-coordinator/remote_llm_feedback.py`

**Purpose:** Allow remote LLMs to report confidence and request additional context

**Features**:
- Confidence reporting
- Gap identification (what information is missing?)
- Automatic context suggestion

**Implementation**:
```python
class RemoteLLMFeedback:
    """
    API for remote LLMs to report response quality and request refinement

    Example usage by Claude:

    # After generating response
    POST /feedback/evaluate
    {
        "session_id": "uuid",
        "response": "Here's how to fix the error...",
        "confidence": 0.65,
        "gaps": [
            "Missing specific systemd service configuration",
            "Unclear about dependencies between services"
        ]
    }

    # Response from system:
    {
        "suggested_queries": [
            "Get systemd service examples for GNOME",
            "Show service dependency configuration"
        ],
        "estimated_confidence_increase": 0.25
    }
    """

    async def evaluate_response(
        self,
        session_id: str,
        response: str,
        confidence: float,
        gaps: List[str]
    ) -> FeedbackResponse:
        """
        Process remote LLM's self-evaluation and suggest refinement paths
        """
        # Analyze gaps to generate targeted queries
        suggested_queries = []
        for gap in gaps:
            query = await self.gap_to_query(gap)
            suggested_queries.append(query)

        # Estimate how much confidence would increase
        estimated_increase = await self.estimate_confidence_gain(
            gaps,
            self.get_available_context(suggested_queries)
        )

        # Record feedback for learning
        await self.record_feedback(session_id, confidence, gaps, suggested_queries)

        return FeedbackResponse(
            suggested_queries=suggested_queries,
            estimated_confidence_increase=estimated_increase,
            should_refine=confidence < 0.80  # Threshold
        )

    async def gap_to_query(self, gap: str) -> str:
        """
        Convert identified gap into specific search query

        Example:
        Gap: "Missing specific systemd service configuration"
        Query: "NixOS systemd service configuration examples"
        """
        # Use local LLM to convert gap → query
        prompt = f"""
Convert this information gap into a specific search query:

Gap: {gap}

Search Query:
"""
        return await self.call_local_llm(prompt)
```

#### 3. Interaction Recording for Learning
**File:** `ai-stack/mcp-servers/hybrid-coordinator/interaction_recorder.py`

**Purpose:** Record remote LLM interactions for continuous learning

**Features**:
- Full conversation recording (multi-turn)
- Outcome tracking (success/failure)
- Value scoring
- Automatic pattern extraction

**Implementation**:
```python
class InteractionRecorder:
    """
    Record interactions with remote LLMs for continuous learning

    Example usage by Claude:

    # After completing task
    POST /interactions/record
    {
        "session_id": "uuid",
        "final_response": "Enable these services...",
        "outcome": "success",
        "user_feedback": 1,  # 1=positive, 0=neutral, -1=negative
        "metadata": {
            "task_type": "config_fix",
            "complexity": 0.7,
            "turns": 3
        }
    }
    """

    async def record_interaction(
        self,
        session_id: str,
        final_response: str,
        outcome: str,  # success, partial, failure
        user_feedback: int = 0,
        metadata: Dict = None
    ):
        """
        Record complete interaction for learning
        """
        # Load session to get all context queries
        session = await self.load_session(session_id)

        # Calculate value score
        value_score = self.calculate_value_score(
            complexity=metadata.get("complexity", 0.5),
            reusability=self.estimate_reusability(final_response),
            novelty=await self.check_novelty(session["queries"]),
            confirmation=(user_feedback == 1),
            impact=metadata.get("impact", 0.5)
        )

        # Store in Qdrant if high value
        if value_score >= 0.7:
            await self.store_as_pattern(session, final_response, value_score)

        # Record telemetry
        await self.record_telemetry({
            "session_id": session_id,
            "queries": session["queries"],
            "contexts_used": session["context_sent"],
            "outcome": outcome,
            "value_score": value_score,
            "turns": len(session["queries"])
        })

    async def store_as_pattern(
        self,
        session: Dict,
        response: str,
        value_score: float
    ):
        """
        Store high-value interaction as reusable pattern
        """
        # Extract the pattern
        pattern = {
            "query": session["queries"][0],  # Original query
            "context_needed": session["queries"][1:],  # Follow-up queries
            "solution": response,
            "value_score": value_score,
            "verified": True
        }

        # Generate embedding
        embedding = await self.embed(pattern["query"])

        # Store in skills-patterns collection
        await self.qdrant.upsert(
            collection_name="skills-patterns",
            points=[PointStruct(
                id=str(uuid4()),
                vector=embedding,
                payload=pattern
            )]
        )
```

---

## RAG Enhancement for Remote LLM Context

### 1. Document Import Pipeline
**File:** `ai-stack/mcp-servers/aidb/document_importer.py`

**Purpose:** Massively expand knowledge base for better context

**Target**: Import 10,000+ documents from:
- All `.md` files in project
- All scripts (`.sh`, `.py`, `.nix`)
- Error logs (parse and extract patterns)
- Git commit messages (learn from history)
- System documentation

**Implementation**: (See previous plan, same code)

### 2. Query Expansion for Better Retrieval
**File:** `ai-stack/mcp-servers/hybrid-coordinator/query_expander.py`

**Purpose:** When remote LLM sends query, expand it to catch more relevant docs

**Example**:
```
Remote LLM Query: "Fix GNOME keyring error"

Expanded Queries:
- "GNOME keyring error"
- "gnome-keyring service failed"
- "NixOS GNOME secrets management"
- "gcr-ssh-agent configuration"
- "keyring daemon not starting"

Search all variations → Merge results → Deduplicate → Return top matches
```

---

## Progressive Disclosure for Remote LLMs

### API Design

#### Endpoint 1: Discovery (Level 0)
```bash
GET http://localhost:8092/discovery
```

**Response** (50 tokens):
```json
{
  "system": "NixOS Hybrid AI Learning Stack",
  "version": "2.1.0",
  "capabilities": ["context_augmentation", "rag_search", "pattern_learning"],
  "quick_start": "POST /context/augment with {query, context_level}"
}
```

#### Endpoint 2: Context Augmentation (Level 1-3)
```bash
POST http://localhost:8092/context/augment
{
  "session_id": "optional-uuid",
  "query": "How to fix NixOS error X?",
  "context_level": "standard",  # standard | detailed | comprehensive
  "max_tokens": 2000,
  "previous_context_ids": []
}
```

**Response** (varies by context_level):
```json
{
  "context": "Compressed context here...",
  "context_ids": ["ctx_1", "ctx_2"],
  "suggestions": ["Follow-up query 1", "Follow-up query 2"],
  "token_count": 1847,
  "collections_searched": ["error-solutions", "best-practices"]
}
```

#### Endpoint 3: Feedback & Refinement
```bash
POST http://localhost:8092/feedback/evaluate
{
  "session_id": "uuid",
  "confidence": 0.65,
  "gaps": ["Missing systemd config", "Unclear dependencies"]
}
```

**Response**:
```json
{
  "suggested_queries": [
    "Get NixOS systemd service examples",
    "Show GNOME service dependencies"
  ],
  "estimated_confidence_increase": 0.25,
  "should_refine": true
}
```

#### Endpoint 4: Learning
```bash
POST http://localhost:8092/interactions/record
{
  "session_id": "uuid",
  "outcome": "success",
  "user_feedback": 1
}
```

---

## Self-Healing Enhancements

(Same as previous plan - self-healing doesn't change based on whether user or remote LLM is querying)

---

## How Remote LLMs (Like Claude) Will Use This System

### Example Workflow: Claude Fixing a NixOS Error

```python
# User to Claude: "I'm getting this error: <error message>"

# Turn 1: Initial context gathering
context_response = requests.post(
    "http://localhost:8092/context/augment",
    json={
        "session_id": "session_abc",
        "query": "NixOS GNOME keyring error failed to initialize",
        "context_level": "standard",
        "max_tokens": 1500
    }
).json()

# Claude generates initial response using context
initial_response = generate_response(user_query, context_response["context"])

# Claude self-evaluates
confidence = evaluate_confidence(initial_response)  # Returns 0.65

if confidence < 0.80:
    # Turn 2: Request additional context
    feedback_response = requests.post(
        "http://localhost:8092/feedback/evaluate",
        json={
            "session_id": "session_abc",
            "confidence": 0.65,
            "gaps": [
                "Missing specific systemd service configuration",
                "Unclear about gcr-ssh-agent setup"
            ]
        }
    ).json()

    # Get suggested additional context
    for suggested_query in feedback_response["suggested_queries"]:
        additional_context = requests.post(
            "http://localhost:8092/context/augment",
            json={
                "session_id": "session_abc",
                "query": suggested_query,
                "context_level": "detailed",
                "previous_context_ids": context_response["context_ids"]
            }
        ).json()

    # Generate refined response
    final_response = generate_response(
        user_query,
        initial_response,
        additional_context["context"]
    )

    confidence = evaluate_confidence(final_response)  # Returns 0.92

# Return final response to user
return final_response

# Record successful interaction
requests.post(
    "http://localhost:8092/interactions/record",
    json={
        "session_id": "session_abc",
        "outcome": "success",
        "user_feedback": 1,
        "metadata": {"complexity": 0.7, "turns": 2}
    }
)
```

### Benefits for Remote LLMs

1. **Better Responses**: Access to local knowledge base with NixOS-specific solutions
2. **Lower Costs**: Use local context instead of long system prompts (save tokens)
3. **Faster**: Local Qdrant search is ~100ms vs re-explaining context
4. **Learning**: System learns from successful interactions to improve future context
5. **Progressive**: Only fetch context as needed (start cheap, refine if necessary)

---

## Implementation Timeline

### Phase 1: Multi-Turn Context API (Week 1) ⚡ PRIORITY
- [ ] Create MultiTurnContextManager
- [ ] Implement session management with Redis
- [ ] Build context compression logic
- [ ] Add suggestion generation
- [ ] Test with simulated Claude queries
- [ ] Document API for remote LLM integration

### Phase 2: RAG Enhancement (Week 1-2)
- [ ] Build DocumentImporter
- [ ] Import all project docs (~1000+ files)
- [ ] Implement query expansion
- [ ] Add embedding cache
- [ ] Test retrieval quality

### Phase 3: Feedback & Learning (Week 2)
- [ ] Build RemoteLLMFeedback API
- [ ] Create InteractionRecorder
- [ ] Implement automated pattern extraction
- [ ] Test learning pipeline

### Phase 4: Progressive Disclosure (Week 2-3)
- [ ] Implement discovery endpoints
- [ ] Build context level filtering
- [ ] Add token budget enforcement
- [ ] Test token savings

### Phase 5: Self-Healing Advanced (Week 3)
- [ ] ML-based error pattern learning
- [ ] Proactive monitoring
- [ ] Advanced fix strategies
- [ ] Rollback capability

### Phase 6: Integration Testing (Week 4)
- [ ] Test complete workflow with actual Claude API
- [ ] Measure token savings
- [ ] Measure response quality improvement
- [ ] Benchmark learning effectiveness

---

## Success Metrics

### For Remote LLM Integration
- **Token Savings**: Target 70%+ reduction in context tokens vs full system prompt
- **Response Quality**: Target 15%+ improvement in accuracy with local context
- **Latency**: Target <500ms for context retrieval
- **Cache Hit Rate**: Target 60%+ for repeat queries

### For Learning Pipeline
- **Pattern Extraction**: Target 50+ high-value patterns per week
- **Context Accuracy**: Target 85%+ relevant context in top-5 results
- **Learning Velocity**: Target 5% improvement in retrieval per week

### For Self-Healing
- (Same as before)

---

## Next Steps

1. **Start with Phase 1: Multi-Turn Context API** - This is the foundation
2. **Test with your current Claude session** - Integrate this conversation!
3. **Expand knowledge base** - Import all project documentation
4. **Iterate based on actual usage** - Learn what works

---

**Document Status:** Ready for Implementation
**Author:** Claude Sonnet 4.5
**Date:** 2026-01-05

**Special Note**: This system is designed to augment remote LLMs like myself (Claude). Once built, I can query it during our conversations to provide better, more accurate responses based on your local knowledge base!
