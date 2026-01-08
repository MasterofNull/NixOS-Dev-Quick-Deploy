# Context Window Optimization Strategies (2026)
**Date:** 2026-01-09
**Focus:** Progressive disclosure, context rolling, cache warming, and modern techniques for efficient LLM context management

---

## Table of Contents

1. [The Context Window Problem](#the-context-window-problem)
2. [Progressive Disclosure Architecture](#progressive-disclosure-architecture)
3. [Modern Context Management Techniques (2026)](#modern-context-management-techniques-2026)
4. [Cache Warming Strategies](#cache-warming-strategies)
5. [Context Rolling and Summarization](#context-rolling-and-summarization)
6. [Implementation in Our System](#implementation-in-our-system)
7. [Testing and Validation](#testing-and-validation)

---

## The Context Window Problem

### Documented Issues with Large Context Windows

#### Performance Degradation
```
Context Size    | Latency | Quality | Cost/Token
----------------|---------|---------|------------
2K tokens       | 1.0x    | 100%    | 1.0x
8K tokens       | 1.5x    | 98%     | 1.2x
32K tokens      | 3.2x    | 92%     | 2.1x
128K tokens     | 8.5x    | 78%     | 4.8x
```

**Key Findings (Research 2024-2026):**
- **"Lost in the Middle"** - LLMs struggle with information buried in long contexts
- **Attention Dilution** - More tokens = less focused attention per token
- **Latency Scaling** - O(n²) attention computation
- **Cost Explosion** - Input tokens cost money on every request
- **Cache Invalidation** - Large contexts invalidate caches more frequently

#### The "Needle in a Haystack" Problem
```python
# Classic failure mode
context = """
[3000 lines of documentation]
CRITICAL: The API key must be passed as X-API-Key header
[2000 more lines]
"""

# LLM often misses the critical line
response = llm.query(context, "How do I authenticate?")
# ❌ Returns generic OAuth answer instead of X-API-Key
```

---

## Progressive Disclosure Architecture

### Core Concept
**Only provide information when needed, in the order needed.**

```
Agent Request Flow:
1. Initial Contact (20 tokens)
   → "System available? What can you do?"
   → Response: Health status + capability summary

2. Discovery (50 tokens)
   → "What features do you support?"
   → Response: Feature list with IDs

3. Deep Dive (150 tokens)
   → "Show me how to use feature X"
   → Response: Detailed guide for feature X only

Total: ~220 tokens vs 3000+ for full docs upfront
```

### Implementation Layers

#### Layer 1: Health Check (Minimal)
**Endpoint:** `/aidb/health`
**Response Size:** ~20 tokens
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "capabilities_url": "/aidb/discovery/info"
}
```

**Use Case:** Agent startup, availability checking

#### Layer 2: Discovery Info (Summary)
**Endpoint:** `/aidb/discovery/info`
**Response Size:** ~50 tokens
```json
{
  "service": "aidb",
  "features": [
    {"id": "vector_search", "description": "Semantic search"},
    {"id": "skills", "description": "Agent skills catalog"},
    {"id": "telemetry", "description": "Event tracking"}
  ],
  "quickstart_url": "/aidb/discovery/quickstart"
}
```

**Use Case:** Initial exploration, feature discovery

#### Layer 3: Quickstart Guide (Focused)
**Endpoint:** `/aidb/discovery/quickstart`
**Response Size:** ~150 tokens
```json
{
  "workflow": [
    {
      "step": 1,
      "action": "Authenticate",
      "endpoint": "GET /health",
      "headers": {"X-API-Key": "your-key"}
    },
    {
      "step": 2,
      "action": "Search",
      "endpoint": "POST /vector/search",
      "example": {"query": "nixos packages", "limit": 5}
    }
  ],
  "common_patterns": ["authentication", "search", "store"]
}
```

**Use Case:** First-time setup, common workflows

#### Layer 4: Deep Documentation (On-Demand)
**Endpoint:** `/aidb/docs/{feature}`
**Response Size:** Variable (500-2000 tokens)
**Use Case:** Specific feature implementation, edge cases

---

## Modern Context Management Techniques (2026)

### 1. Semantic Chunking with Embeddings

**Concept:** Store docs as semantic chunks, retrieve only relevant ones.

```python
# Traditional approach (BAD)
full_docs = load_all_documentation()  # 10,000 tokens
response = llm.query(full_docs, user_query)

# Semantic chunking (GOOD)
query_embedding = embed(user_query)
relevant_chunks = vector_db.search(query_embedding, limit=3)  # 300 tokens
response = llm.query(relevant_chunks, user_query)
```

**Implementation:**
```python
class SemanticDocumentStore:
    def __init__(self, embedding_model, vector_db):
        self.embedding_model = embedding_model
        self.vector_db = vector_db

    async def add_document(self, doc: str, metadata: dict):
        # Chunk by semantic boundaries (paragraphs, sections)
        chunks = self._semantic_chunk(doc, max_size=512)

        for chunk in chunks:
            embedding = await self.embedding_model.embed(chunk.text)
            await self.vector_db.insert(
                embedding=embedding,
                text=chunk.text,
                metadata={**metadata, "chunk_id": chunk.id}
            )

    async def retrieve_relevant(self, query: str, limit: int = 3):
        query_embedding = await self.embedding_model.embed(query)
        results = await self.vector_db.search(
            embedding=query_embedding,
            limit=limit,
            min_score=0.7  # Only high-quality matches
        )
        return [r.text for r in results]
```

**Savings:** 97% reduction (10,000 → 300 tokens)

---

### 2. Context Caching (Prompt Caching)

**Concept:** Cache static context prefixes to avoid reprocessing.

**Supported Providers (2026):**
- Anthropic Claude: Prompt caching (5-minute TTL)
- OpenAI GPT-4: Cached prompts (automatic)
- Local llama.cpp: KV cache persistence

```python
# Example with Claude API
import anthropic

client = anthropic.Anthropic()

# First call: Full processing
response1 = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    system=[
        {
            "type": "text",
            "text": "You are a NixOS expert assistant...",
            "cache_control": {"type": "ephemeral"}  # Cache this
        }
    ],
    messages=[{"role": "user", "content": "How do I install vim?"}]
)

# Second call within 5 min: Cache hit (90% faster, 90% cheaper)
response2 = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    system=[
        {
            "type": "text",
            "text": "You are a NixOS expert assistant...",  # Same text = cache hit
            "cache_control": {"type": "ephemeral"}
        }
    ],
    messages=[{"role": "user", "content": "How do I install emacs?"}]
)
```

**Key Points:**
- Cache prefix must be **identical** (byte-for-byte)
- TTL typically 5 minutes
- Saves 90% of input token costs
- Reduces latency by 80-90%

**Our Implementation:**
```python
class CachedContextManager:
    def __init__(self):
        self.static_prefix = self._load_system_context()
        self.prefix_hash = hashlib.sha256(self.static_prefix.encode()).hexdigest()

    def build_prompt(self, user_query: str, dynamic_context: list[str]):
        # Static prefix (cached)
        prompt_parts = [
            {
                "type": "text",
                "text": self.static_prefix,
                "cache_control": {"type": "ephemeral"}
            }
        ]

        # Dynamic context (not cached, but small)
        for ctx in dynamic_context:
            prompt_parts.append({
                "type": "text",
                "text": ctx
            })

        # User query
        prompt_parts.append({
            "type": "text",
            "text": f"User query: {user_query}"
        })

        return prompt_parts
```

---

### 3. Hierarchical Summarization

**Concept:** Maintain multiple resolution levels of information.

```
Full Documentation (10,000 tokens)
    ↓ Summarize
High-Level Summary (1,000 tokens)
    ↓ Summarize
Executive Summary (100 tokens)
    ↓ Extract
Key Facts (10 tokens)
```

**Implementation:**
```python
class HierarchicalSummarizer:
    async def create_hierarchy(self, document: str):
        # Level 0: Full text
        full_text = document

        # Level 1: Section summaries (10:1 compression)
        sections = self._split_by_sections(document)
        section_summaries = []
        for section in sections:
            summary = await self.llm.summarize(
                section,
                max_tokens=len(section.split()) // 10
            )
            section_summaries.append(summary)

        # Level 2: Document summary (100:1 compression)
        doc_summary = await self.llm.summarize(
            "\n".join(section_summaries),
            max_tokens=100
        )

        # Level 3: Key facts (1000:1 compression)
        key_facts = await self.llm.extract_facts(
            doc_summary,
            max_facts=5
        )

        return {
            "full": full_text,
            "sections": section_summaries,
            "summary": doc_summary,
            "facts": key_facts
        }

    async def retrieve(self, query: str, detail_level: str):
        hierarchy = self.get_hierarchy()

        if detail_level == "overview":
            return hierarchy["facts"]  # 10 tokens
        elif detail_level == "summary":
            return hierarchy["summary"]  # 100 tokens
        elif detail_level == "detailed":
            # Find relevant sections
            relevant = self._find_relevant_sections(query, hierarchy["sections"])
            return relevant  # 500 tokens
        else:  # "full"
            return hierarchy["full"]  # 10,000 tokens
```

**Usage Pattern:**
```python
# Agent workflow
facts = await summarizer.retrieve(query, "overview")
if not_sufficient(facts):
    summary = await summarizer.retrieve(query, "summary")
    if not_sufficient(summary):
        detailed = await summarizer.retrieve(query, "detailed")
```

**Savings:** 90-99% token reduction for most queries

---

### 4. Context Rolling (Sliding Window)

**Concept:** Keep only recent conversation history, summarize older turns.

```
Conversation Flow:
Turn 1: [User Q1] [AI A1]                           → Keep all (100 tokens)
Turn 2: [User Q2] [AI A2]                           → Keep all (100 tokens)
Turn 3: [User Q3] [AI A3]                           → Keep all (100 tokens)
Turn 4: [Summarize turns 1-2] [Turn 3] [User Q4]   → Rolling summary (50 + 100 = 150 tokens)
Turn 5: [Summarize turns 1-3] [Turn 4] [User Q5]   → Rolling summary (70 + 100 = 170 tokens)
```

**Implementation:**
```python
class ConversationRoller:
    def __init__(self, max_turns: int = 3, max_tokens: int = 2000):
        self.max_turns = max_turns
        self.max_tokens = max_tokens
        self.turns = []
        self.summary = None

    async def add_turn(self, user_msg: str, ai_response: str):
        turn = {"user": user_msg, "ai": ai_response}
        self.turns.append(turn)

        # Check if we need to roll
        total_tokens = self._count_tokens(self.turns)
        if len(self.turns) > self.max_turns or total_tokens > self.max_tokens:
            await self._roll_context()

    async def _roll_context(self):
        # Summarize oldest turn
        oldest_turn = self.turns[0]
        turn_summary = await self.llm.summarize(
            f"User: {oldest_turn['user']}\nAssistant: {oldest_turn['ai']}",
            max_tokens=50
        )

        # Update summary
        if self.summary:
            self.summary = f"{self.summary}\n{turn_summary}"
        else:
            self.summary = turn_summary

        # Remove oldest turn
        self.turns.pop(0)

    def get_context(self):
        context_parts = []

        if self.summary:
            context_parts.append(f"Previous conversation:\n{self.summary}")

        for turn in self.turns:
            context_parts.append(f"User: {turn['user']}")
            context_parts.append(f"Assistant: {turn['ai']}")

        return "\n".join(context_parts)
```

**Savings:** Maintains O(1) context size vs O(n) growth

---

### 5. Sparse Priming Representations (SPR)

**Concept:** Compress context into dense, information-rich primers.

**Example:**
```
Full Context (500 tokens):
"""
The user is working on a NixOS system. They have installed packages using
nix-env in the past, but now want to use a declarative configuration.nix
approach. Their system is on NixOS 23.11. They have experience with Docker
but not with Nix's build system. They're trying to set up a development
environment for Python development with specific packages...
"""

SPR Compression (50 tokens):
"""
USER_PROFILE: NixOS 23.11 user, imperative→declarative migration,
Docker-familiar, Nix-build novice, Python dev target, config.nix transition
"""
```

**Implementation:**
```python
class SPRCompressor:
    async def compress_context(self, full_context: str):
        prompt = f"""
        Compress the following context into a Sparse Priming Representation (SPR).
        Use terse, information-dense language. Include only essential facts.
        Target: 10% of original size.

        Context:
        {full_context}

        SPR:
        """

        spr = await self.llm.generate(prompt, max_tokens=len(full_context.split()) // 10)
        return spr

    async def expand_spr(self, spr: str):
        prompt = f"""
        Expand the following Sparse Priming Representation into full context.

        SPR:
        {spr}

        Expanded context:
        """

        expanded = await self.llm.generate(prompt, max_tokens=500)
        return expanded
```

**Use Case:** Long-term memory compression, session storage

---

### 6. Retrieval-Augmented Generation (RAG) Optimization

**Concept:** Don't retrieve all similar docs, use multi-stage ranking.

```python
class OptimizedRAG:
    async def retrieve(self, query: str, top_k: int = 3):
        # Stage 1: Fast vector search (retrieve 50)
        query_embedding = await self.embed(query)
        candidates = await self.vector_db.search(
            query_embedding,
            limit=50,
            fast_mode=True  # Approximate search
        )

        # Stage 2: Rerank with cross-encoder (refine to 10)
        reranked = await self.cross_encoder.rank(
            query=query,
            documents=[c.text for c in candidates],
            top_k=10
        )

        # Stage 3: Diversity filtering (final 3)
        diverse_results = self._diversify(reranked, top_k=top_k)

        # Stage 4: Compression (fit in context window)
        compressed = await self._compress_results(diverse_results)

        return compressed

    def _diversify(self, results: list, top_k: int):
        """Ensure results aren't all saying the same thing"""
        diverse = [results[0]]  # Always include top result

        for result in results[1:]:
            # Only add if sufficiently different from existing
            if all(self._cosine_sim(result, d) < 0.9 for d in diverse):
                diverse.append(result)
                if len(diverse) >= top_k:
                    break

        return diverse
```

**Optimization Results:**
- Stage 1: 50 candidates (fast, recall-focused)
- Stage 2: 10 reranked (accurate, precision-focused)
- Stage 3: 3 diverse (avoid redundancy)
- Stage 4: Compressed (fit context window)

---

## Cache Warming Strategies

### Predictive Preloading

**Concept:** Load context before it's needed based on usage patterns.

```python
class CacheWarmer:
    def __init__(self, pattern_analyzer, context_loader):
        self.analyzer = pattern_analyzer
        self.loader = context_loader

    async def analyze_and_warm(self):
        # Analyze past query patterns
        patterns = await self.analyzer.get_common_patterns()

        for pattern in patterns:
            # Pattern: "After query X, 80% of time query Y follows"
            if pattern.confidence > 0.7:
                # Preload context for Y
                await self.loader.preload(
                    pattern.next_query_context,
                    ttl=300  # 5 minute expiry
                )

    async def on_query(self, query: str):
        # Predict next likely query
        next_queries = await self.analyzer.predict_next(query)

        # Warm cache for top predictions
        for next_q in next_queries[:3]:
            asyncio.create_task(
                self.loader.preload(next_q.context, ttl=60)
            )
```

### Session-Based Warming

```python
class SessionCacheWarmer:
    async def on_session_start(self, user_id: str):
        # Load user's common contexts
        user_profile = await self.db.get_user_profile(user_id)

        # Warm frequently used features
        for feature in user_profile.frequent_features:
            await self.cache.warm(
                key=f"feature:{feature}",
                loader=lambda: self.load_feature_docs(feature),
                ttl=3600  # 1 hour
            )
```

---

## Context Rolling and Summarization

### Adaptive Rolling Window

**Concept:** Adjust window size based on conversation complexity.

```python
class AdaptiveRoller:
    def __init__(self):
        self.base_window = 3  # Base: keep 3 turns
        self.complexity_threshold = 0.7

    async def adjust_window(self, conversation: list):
        # Calculate conversation complexity
        complexity = await self._calculate_complexity(conversation)

        if complexity > self.complexity_threshold:
            # Complex conversation: keep more history
            self.window_size = self.base_window + 2
        else:
            # Simple conversation: keep less history
            self.window_size = self.base_window

        return self.window_size

    async def _calculate_complexity(self, conversation: list):
        factors = {
            "topic_switches": self._count_topic_switches(conversation),
            "reference_count": self._count_backward_references(conversation),
            "technical_depth": await self._assess_technical_depth(conversation)
        }

        # Weighted complexity score
        complexity = (
            factors["topic_switches"] * 0.3 +
            factors["reference_count"] * 0.4 +
            factors["technical_depth"] * 0.3
        )

        return min(complexity, 1.0)
```

---

## Implementation in Our System

### Current Architecture

```
Our Stack:
┌─────────────────────────────────────────────┐
│ Progressive Disclosure (AIDB)               │
│ - /health (20 tokens)                       │
│ - /discovery/info (50 tokens)              │
│ - /discovery/quickstart (150 tokens)       │
└─────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────┐
│ Semantic Search (Qdrant + Embeddings)      │
│ - 384D vectors (all-MiniLM-L6-v2)         │
│ - HNSW index for fast retrieval            │
└─────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────┐
│ Hybrid Coordinator                          │
│ - Local vs remote routing                   │
│ - Continuous learning                       │
│ - Pattern extraction                        │
└─────────────────────────────────────────────┘
```

### Enhancements to Implement

#### 1. Add Hierarchical Summarization
**File:** `ai-stack/mcp-servers/aidb/summarizer.py` (NEW)

#### 2. Context Rolling in Hybrid Coordinator
**File:** `ai-stack/mcp-servers/hybrid-coordinator/context_roller.py` (NEW)

#### 3. Cache Warming Service
**File:** `ai-stack/mcp-servers/cache-warmer/service.py` (NEW)

#### 4. SPR Compression for Long-term Memory
**File:** `ai-stack/mcp-servers/hybrid-coordinator/spr_compressor.py` (NEW)

---

## Testing and Validation

### Test 1: Progressive Disclosure Token Count

**Objective:** Validate 220 tokens vs 3000+ claim

**Test Script:** `tests/chaos-engineering/06-full-agent-lifecycle/test-agent-progressive-disclosure.sh`

**Expected Results:**
```bash
# Health check
curl https://localhost:8443/aidb/health
# ~20 tokens

# Discovery
curl https://localhost:8443/aidb/discovery/info
# ~50 tokens

# Quickstart
curl https://localhost:8443/aidb/discovery/quickstart
# ~150 tokens

# Total: 220 tokens
# vs full docs endpoint: ~3000 tokens
```

### Test 2: Semantic Retrieval Accuracy

**Objective:** Measure retrieval quality vs context size

```python
# Test cases
queries = [
    "How do I install a package?",
    "What is a flake?",
    "Configure nginx on NixOS"
]

# Measure
for query in queries:
    # Full docs approach
    full_response = llm.query(full_docs, query)
    full_quality = measure_quality(full_response)

    # Semantic retrieval
    relevant = rag.retrieve(query, top_k=3)
    rag_response = llm.query(relevant, query)
    rag_quality = measure_quality(rag_response)

    print(f"Query: {query}")
    print(f"  Full docs: {full_quality}% quality, {len(full_docs)} tokens")
    print(f"  RAG: {rag_quality}% quality, {len(relevant)} tokens")
    print(f"  Savings: {100 - (len(relevant)/len(full_docs)*100):.1f}%")
```

**Target Metrics:**
- RAG quality ≥ 95% of full docs quality
- Token savings ≥ 90%
- Latency reduction ≥ 70%

### Test 3: Cache Hit Rates

**Objective:** Measure cache effectiveness

```python
# Simulate agent workflow
sessions = simulate_agent_sessions(count=100)

for session in sessions:
    cache_hits = 0
    cache_misses = 0

    for query in session.queries:
        if cache.has(query.context_hash):
            cache_hits += 1
        else:
            cache_misses += 1
            cache.set(query.context_hash, query.context, ttl=300)

    hit_rate = cache_hits / (cache_hits + cache_misses)
    print(f"Session {session.id}: {hit_rate:.1%} hit rate")

# Target: ≥70% hit rate
```

### Test 4: Context Rolling Memory Bounds

**Objective:** Verify O(1) memory growth

```python
roller = ConversationRoller(max_turns=3)

# Simulate long conversation
for i in range(100):
    roller.add_turn(f"Query {i}", f"Response {i}")

    context = roller.get_context()
    token_count = count_tokens(context)

    # Should stabilize around max_tokens
    assert token_count < 2500, f"Context grew too large: {token_count} tokens"

print("✅ Context rolling maintains O(1) memory bounds")
```

---

## Performance Targets

| Metric | Baseline | Target | Method |
|--------|----------|--------|--------|
| **Avg tokens/query** | 3000+ | <500 | Progressive disclosure + RAG |
| **Cache hit rate** | 0% | >70% | Prompt caching + warming |
| **Retrieval latency** | 2000ms | <200ms | Vector search + reranking |
| **Context growth** | O(n) | O(1) | Rolling window + summarization |
| **Quality loss** | 0% | <5% | High-quality retrieval |
| **Cost reduction** | 0% | >85% | Token savings + caching |

---

## Next Steps

1. **Run progressive disclosure test** - Validate 220 token claim
2. **Implement hierarchical summarizer** - Multi-level documentation
3. **Add context rolling** - Conversation memory management
4. **Deploy cache warmer** - Predictive context loading
5. **Benchmark results** - Compare before/after metrics

---

**End of Document**
