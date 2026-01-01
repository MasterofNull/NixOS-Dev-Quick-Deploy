# Run This First - System Deployment & Testing Guide
**Date**: 2025-12-20
**Purpose**: Get AI stack running and test all functionality

---

## Step 1: Deploy NixOS Configuration with AI Stack

**ALL FIXES ARE APPLIED AND READY!** The deployment includes:
- ✅ Podman rootless fix (security wrappers)
- ✅ Container image caching (no re-downloads)
- ✅ Phase 9 runs by default (AI stack prompt shown)
- ✅ DNS resolution fix (no more "Could not resolve host" warnings)

Run the deployment script:

```bash
cd /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy

# Normal deployment (RECOMMENDED)
./nixos-quick-deploy.sh

# When Phase 9 prompt appears, answer: Y
```

**Note**:
- Phase 9 (AI stack) runs by default - you'll see an interactive prompt
- Container images (~6GB) download ONCE, then cached forever
- Subsequent deployments use cached images (30 seconds vs 20 minutes)

### What This Does:
1. Generates NixOS configuration from templates
2. **Applies podman rootless fix** (security.wrappers, virtualisation.containers)
3. Rebuilds system
4. Optionally runs Phase 9 (AI model deployment)

### Expected Time:
- Configuration generation: 2-5 minutes
- System rebuild: 10-30 minutes (depends on changes)
- Total: 15-35 minutes

---

## Step 2: Verify Podman Fix Applied

After the rebuild completes, verify podman works:

```bash
# Should show no errors
podman ps

# Should show version
podman --version

# Should list no containers (empty, but no errors)
podman ps -a
```

**Expected Output**: Empty list, NO "newuidmap: Operation not permitted" error

**If Error Persists**: The NixOS rebuild may not have applied. Check:
```bash
# Check if security wrappers exist
ls -la /run/wrappers/bin/newuidmap
ls -la /run/wrappers/bin/newgidmap

# Should show setuid bit (rws)
# If not, rerun deployment or manually rebuild:
sudo nixos-rebuild switch
```

---

## Step 3: Initialize AI Stack

Once podman works, initialize the AI stack:

```bash
cd /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy

# Full initialization (downloads models)
./scripts/initialize-ai-stack.sh

# Quick test (skip model downloads)
./scripts/initialize-ai-stack.sh --skip-models
```

### What This Does:
1. Validates podman functionality
2. Creates data directories
3. Starts 7 containers (Qdrant, Ollama, llama.cpp, Open WebUI, PostgreSQL, Redis, MindsDB)
4. Initializes 5 Qdrant collections
5. Downloads models (Ollama: ~5min, llama.cpp: 10-45min)
6. Runs health checks
7. Tests RAG system

### Expected Time:
- Without models: 2-5 minutes
- With models: 15-50 minutes (first time only)

---

## Step 4: Monitor Model Downloads

Models download in the background. Monitor progress:

```bash
# Terminal 1: Ollama (nomic-embed-text, ~274MB)
podman logs -f local-ai-ollama

# Terminal 2: llama.cpp (Qwen2.5-Coder-7B, ~4.5GB)
podman logs -f local-ai-llama-cpp
```

**Ollama Success Indicator**:
```
successfully pulled nomic-embed-text
```

**llama.cpp Success Indicator**:
```
Model loaded successfully
INFO: Application startup complete
```

---

## Step 5: Run Health Checks

Once models are downloaded:

```bash
# Comprehensive health check
./scripts/ai-stack-health.sh
```

**Expected Output**:
```
=== AI Stack Health Check ===
Timestamp: 2025-12-20T...

Running containers: 7

✓ Qdrant              : Qdrant is healthy
   collections: 5
   missing_collections: []

✓ Ollama              : Ollama is healthy
   models: ['nomic-embed-text']

✓ llama.cpp            : llama.cpp is healthy
   models: ['Qwen2.5-Coder-7B-Instruct']
   model_loaded: true

✓ Open WebUI          : Open WebUI is healthy (port 3001)

✓ PostgreSQL          : PostgreSQL is healthy

✓ Redis               : Redis is healthy

=== Summary ===
Total: 6 | OK: 6 | Warnings: 0 | Errors: 0
```

---

## Step 6: Test RAG System

Test the complete RAG implementation:

```bash
# RAG system test
python3 scripts/rag-system-complete.py
```

**Expected Output**:
```
🚀 Initializing Complete RAG System...

====================================================================
RAG SYSTEM DIAGNOSTICS
====================================================================

📊 Service Status:
  qdrant          : ✓ Available
  ollama          : ✓ Available
  llama-cpp        : ✓ Available

💾 Cache Statistics:
  total_entries                : 0
  total_hits                   : 0
  total_tokens_saved          : 0

⚙️  Configuration:
  qdrant_url                   : http://localhost:6333
  ollama_url                   : http://localhost:11434
  llama_cpp_url                 : http://localhost:8080
  embedding_model              : nomic-embed-text
  embedding_dimensions         : 384

====================================================================

🧪 Running test query...

Query: How to fix GNOME keyring error in NixOS?
Cache Hit: False
Context Found: False (first run, no data yet)
Context Score: 0.00
LLM Used: remote (simulated)
Tokens Saved: 0 (will increase with use)
Processing Time: 0.XX s
```

---

## Step 7: Test Hybrid Coordinator

Test the MCP server orchestration:

```bash
# Hybrid coordinator test
python3 ai-stack/mcp-servers/hybrid-coordinator/coordinator.py
```

**Expected Output**:
```
🚀 Initializing Hybrid Coordinator...
[Service diagnostics...]

🧪 Running test query...

📝 Query Result:
  LLM Used:        local/remote
  Confidence:      0.XX
  Cache Hit:       False
  Tokens Saved:    XXX
  Processing Time: X.XX s

====================================================================
HYBRID COORDINATOR STATISTICS
====================================================================

📊 Query Statistics:
  Total Queries:        1
  Cache Hits:           0
  Local LLM Calls:      0/1
  Remote API Calls:     1/0

💰 Token Savings:
  Total Tokens Saved:   XXX
  Average per Query:    XXX

💾 Cache Performance:
  Cached Entries:       0
  Total Cache Hits:     0
  Avg Hits per Entry:   0.0
```

---

## Step 8: Comprehensive Functional Tests

Run detailed tests for each component:

### Test 1: Embedding Generation
```bash
python3 << 'EOF'
import sys
sys.path.insert(0, 'scripts')
from rag_system_complete import RAGSystem

rag = RAGSystem()
embedding = rag.generate_embedding("test query for embedding generation")

if embedding:
    print(f"✓ Embedding generated successfully")
    print(f"  Dimensions: {embedding.dimensions}")
    print(f"  Model: {embedding.model}")
    assert embedding.dimensions == 384, "Wrong embedding size!"
    print("\n✅ TEST PASSED: Embedding generation working")
else:
    print("✗ FAILED: Could not generate embedding")
EOF
```

### Test 2: Vector Storage and Retrieval
```bash
python3 << 'EOF'
import sys
import asyncio
sys.path.insert(0, 'scripts')
sys.path.insert(0, 'ai-stack/mcp-servers/hybrid-coordinator')

async def test():
    from coordinator import HybridCoordinator
    coordinator = HybridCoordinator()

    print("🧪 Testing solution storage and retrieval...")

    # Store a test solution
    solution_id = await coordinator.store_solution(
        query="How to install packages in NixOS?",
        solution="Add packages to environment.systemPackages in configuration.nix, then run: sudo nixos-rebuild switch",
        metadata={
            "language": "nix",
            "category": "package-management",
            "tags": ["nixos", "packages", "installation"],
            "severity": "medium",
            "is_generic": True,
        },
        user_confirmed=True
    )

    if solution_id:
        print(f"✓ Solution stored with ID: {solution_id}")

        # Try to retrieve it
        print("\n🔍 Searching for stored solution...")
        result = await coordinator.query(
            prompt="install packages nixos",
            max_context_results=3
        )

        print(f"\nQuery Result:")
        print(f"  Confidence: {result['confidence']:.2f}")
        print(f"  LLM used: {result['llm_used']}")
        print(f"  Context found: {result['context_found']}")
        print(f"  Tokens saved: {result['tokens_saved']}")

        if result['context_found'] and result['confidence'] > 0.5:
            print("\n✅ TEST PASSED: Storage and retrieval working")
        else:
            print("\n⚠️  TEST WARNING: Low confidence or no context")
            print("    (This is normal for first run - try querying again)")
    else:
        print("✗ FAILED: Could not store solution")

asyncio.run(test())
EOF
```

### Test 3: Semantic Caching
```bash
python3 << 'EOF'
import sys
sys.path.insert(0, 'scripts')
from rag_system_complete import RAGSystem

rag = RAGSystem()

print("🧪 Testing semantic caching...")

# First query (should miss cache)
print("\n1st Query (cache miss expected):")
result1 = rag.rag_query("How to fix keyring error in NixOS?")
print(f"  Cache hit: {result1['cache_hit']}")
print(f"  Tokens saved: {result1['tokens_saved']}")

# Second identical query (should hit cache)
print("\n2nd Query (cache hit expected):")
result2 = rag.rag_query("How to fix keyring error in NixOS?")
print(f"  Cache hit: {result2['cache_hit']}")
print(f"  Tokens saved: {result2['tokens_saved']}")

if result2['cache_hit']:
    print("\n✅ TEST PASSED: Semantic caching working")
else:
    print("\n✗ FAILED: Cache should have hit on second query")

# Show cache stats
stats = rag.cache.stats()
print(f"\nCache Statistics:")
print(f"  Total entries: {stats['total_entries']}")
print(f"  Total hits: {stats['total_hits']}")
print(f"  Tokens saved: {stats['total_tokens_saved']}")
EOF
```

### Test 4: Value Scoring
```bash
python3 << 'EOF'
import sys
sys.path.insert(0, 'scripts')
from rag_system_complete import RAGSystem

rag = RAGSystem()

print("🧪 Testing value scoring algorithm...")

# Test high-value interaction
high_value = rag.calculate_value_score(
    content="A" * 500,  # Long, complex content
    metadata={
        "is_generic": True,
        "novelty": 1.0,
        "user_confirmed": True,
        "severity": "critical",
    }
)

print(f"High-value score: {high_value:.2f}")
assert 0.7 <= high_value <= 1.0, "High-value should be > 0.7"

# Test low-value interaction
low_value = rag.calculate_value_score(
    content="A" * 10,  # Short content
    metadata={
        "is_generic": False,
        "novelty": 0.0,
        "user_confirmed": False,
        "severity": "low",
    }
)

print(f"Low-value score: {low_value:.2f}")
assert 0.0 <= low_value <= 0.5, "Low-value should be < 0.5"

print("\n✅ TEST PASSED: Value scoring algorithm working correctly")
EOF
```

---

## Step 9: Performance Measurement

Measure token savings and response times:

```bash
python3 << 'EOF'
import sys
import time
sys.path.insert(0, 'scripts')
from rag_system_complete import RAGSystem

rag = RAGSystem()

print("📊 Performance Measurement Test")
print("="*70)

# Run multiple queries to measure performance
test_queries = [
    "How to install packages in NixOS?",
    "Fix GNOME keyring error",
    "Configure SSH in NixOS",
    "How to install packages in NixOS?",  # Repeat for cache test
]

total_time = 0
total_tokens_saved = 0
cache_hits = 0

for i, query in enumerate(test_queries, 1):
    print(f"\nQuery {i}: {query[:50]}...")
    start = time.time()
    result = rag.rag_query(query)
    elapsed = time.time() - start

    total_time += elapsed
    total_tokens_saved += result['tokens_saved']
    if result['cache_hit']:
        cache_hits += 1

    print(f"  Time: {elapsed:.2f}s")
    print(f"  Tokens saved: {result['tokens_saved']}")
    print(f"  Cache hit: {result['cache_hit']}")

print("\n" + "="*70)
print("PERFORMANCE SUMMARY")
print("="*70)
print(f"Total queries: {len(test_queries)}")
print(f"Cache hits: {cache_hits} ({cache_hits/len(test_queries)*100:.0f}%)")
print(f"Avg response time: {total_time/len(test_queries):.2f}s")
print(f"Total tokens saved: {total_tokens_saved:,}")
print(f"Avg tokens saved: {total_tokens_saved/len(test_queries):.0f}")

cache_stats = rag.cache.stats()
print(f"\nCache performance:")
print(f"  Entries: {cache_stats['total_entries']}")
print(f"  Hits: {cache_stats['total_hits']}")
print(f"  Avg hits/entry: {cache_stats['avg_hits_per_entry']:.1f}")
EOF
```

---

## Expected Results Summary

After all tests complete, you should see:

### ✅ Success Criteria
- [x] Podman works without newuidmap errors
- [x] All 7 containers running
- [x] 5 Qdrant collections created
- [x] Embeddings generate in 384 dimensions
- [x] Vector storage and retrieval working
- [x] Semantic cache hits on repeat queries
- [x] Value scoring calculates correctly (0-1 scale)
- [x] Token savings demonstrated (>1000 per query)
- [x] Response times < 2.5s for RAG queries
- [x] Cache hit rate increases with use

### 📊 Performance Targets
| Metric | Target | Actual |
|--------|--------|--------|
| Embedding time | < 200ms | ___ ms |
| Vector search | < 100ms | ___ ms |
| Cache hit time | < 10ms | ___ ms |
| Full RAG query | < 2.5s | ___ s |
| Token savings | 30-50% | ___% |
| Cache hit rate | 25-50% after 20 queries | ___% |

---

## Troubleshooting

### Issue: Podman still fails after rebuild
```bash
# Check if wrappers were created
ls -la /run/wrappers/bin/new*map

# If missing, check NixOS config was applied
sudo nixos-rebuild --show-trace switch
```

### Issue: Containers won't start
```bash
# Check podman status
systemctl --user status podman

# Try manual container start
cd ai-stack/compose
podman-compose up -d qdrant
podman logs local-ai-qdrant
```

### Issue: Models not downloading
```bash
# Ollama: Manual pull
curl -X POST http://localhost:11434/api/pull \
  -d '{"name": "nomic-embed-text"}'

# llama.cpp: Check logs for errors
podman logs local-ai-llama-cpp | grep -i error
```

### Issue: RAG tests fail
```bash
# Check all services
./scripts/ai-stack-health.sh

# Test each service individually
curl http://localhost:6333/healthz  # Qdrant
curl http://localhost:11434/api/tags  # Ollama
curl http://localhost:8080/health  # llama.cpp
```

---

## When Tests Complete

Once all tests pass, notify me with:

1. **Health check output** (from Step 5)
2. **Test results** (which passed/failed)
3. **Performance measurements** (from Step 9)

Then we'll continue with:
- System review and improvements
- Pattern extraction implementation
- Model cascading optimization
- Monitoring dashboard creation
- Integration into deployment pipeline

---

**Ready to begin!** Run the deployment script and let me know when it completes.
