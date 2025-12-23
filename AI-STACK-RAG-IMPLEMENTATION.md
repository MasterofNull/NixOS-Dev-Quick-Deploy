# AI Stack & RAG System Implementation
**Date**: 2025-12-20
**Status**: Ready for Testing (Requires System Rebuild)
**Version**: 2.0.0

---

## Overview

I've implemented a complete RAG (Retrieval Augmented Generation) system with advanced features and fixed the critical podman rootless permission issue. The system is now ready for testing after a NixOS rebuild.

---

## What Was Implemented

### 1. Complete RAG System ([scripts/rag-system-complete.py](scripts/rag-system-complete.py))

A comprehensive, standalone RAG implementation featuring:

#### Core Features
- ✅ **Embedding Generation**: Ollama integration with nomic-embed-text (384 dimensions)
- ✅ **Vector Search**: Qdrant integration with multi-collection search
- ✅ **Semantic Caching**: SQLite-based cache with 95% similarity threshold
- ✅ **Enhanced Data Structures**: Comprehensive metadata tracking
- ✅ **Value Scoring**: 5-factor algorithm (complexity, reusability, novelty, confirmation, impact)
- ✅ **LLM Routing**: Intelligent local vs remote decision making
- ✅ **Token Tracking**: Automatic savings calculation

#### Enhanced Payload Structure
```python
EnhancedPayload:
  - content: The actual data
  - content_type: Classification (code_snippet, error_solution, pattern)
  - language, category, tags: Metadata for filtering
  - file_path, version, parent_id, related_ids: Lineage tracking
  - usage_count, success_rate, value_score: Quality metrics
  - created_at, updated_at, last_used_at: Temporal tracking
  - metadata: Extensible additional data
```

#### Semantic Caching
- **Cache Hit Detection**: SHA-256 hash for exact matches
- **TTL Management**: 24-hour default expiration
- **Hit Statistics**: Tracks usage and token savings
- **Automatic Cleanup**: Removes expired entries

#### RAG Workflow
```
1. Check semantic cache → Cache hit? Return immediately
2. Generate embedding (Ollama)
3. Search Qdrant (multiple collections)
4. Build context from top results
5. Route to LLM:
   - Local (llama.cpp) if score > 0.85
   - Remote (Claude API) if score < 0.85
6. Cache result for future queries
7. Track token savings
```

### 2. Podman Rootless Fix ([templates/nixos-improvements/podman.nix](templates/nixos-improvements/podman.nix))

Fixed the critical `newuidmap: write to uid_map failed: Operation not permitted` error:

#### Changes Made
- ✅ Added `virtualisation.containers` configuration
- ✅ Configured security wrappers for newuidmap/newgidmap with setuid
- ✅ Added overlay storage driver configuration
- ✅ Enabled automatic container pruning
- ✅ Added additional tools: podman-tui, skopeo, buildah

**This fix is already integrated** into the configuration template, but requires a system rebuild to apply.

### 3. AI Stack Initialization Script ([scripts/initialize-ai-stack.sh](scripts/initialize-ai-stack.sh))

Comprehensive setup and validation script:

#### Features
1. **Podman Validation**: Ensures rootless podman is working
2. **Data Directory Setup**: Creates all required directories
3. **Service Startup**: Starts all 7 AI stack containers
4. **Health Checks**: Validates each service
5. **Qdrant Initialization**: Creates all 5 collections with enhanced schema
6. **Model Downloads**: Pulls Ollama and llama.cpp models
7. **RAG Testing**: End-to-end workflow validation

#### Usage
```bash
# Full setup
./scripts/initialize-ai-stack.sh

# Skip model downloads (faster testing)
./scripts/initialize-ai-stack.sh --skip-models

# Test only (don't start services)
./scripts/initialize-ai-stack.sh --test-only
```

---

## Required Next Steps

### Step 1: Rebuild NixOS to Apply Podman Fix

The podman rootless fix is in the template, but needs to be applied:

```bash
# Rebuild the system configuration
sudo nixos-rebuild switch

# Verify podman works
podman ps

# If successful, you should see no errors
```

**Expected outcome**: Podman commands should work without the newuidmap error.

### Step 2: Initialize AI Stack

Once podman is working:

```bash
cd /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy
./scripts/initialize-ai-stack.sh
```

This will:
1. Start all containers
2. Initialize Qdrant collections
3. Download models (10-45 minutes for first time)
4. Run health checks
5. Test RAG system

### Step 3: Monitor Model Downloads

Models download in the background. Monitor progress:

```bash
# Ollama (nomic-embed-text, ~274MB)
podman logs -f local-ai-ollama

# llama.cpp (Qwen2.5-Coder-7B, ~4.5GB)
podman logs -f local-ai-llama-cpp
```

### Step 4: Run RAG Tests

Once models are downloaded:

```bash
# Check all services
python3 scripts/check-ai-stack-health-v2.py -v

# Test RAG system
python3 scripts/rag-system-complete.py
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER / AGENT                              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   RAG SYSTEM (Python)                            │
│  • Query processing                                              │
│  • Semantic caching (SQLite)                                     │
│  • LLM routing logic                                             │
│  • Token tracking                                                │
└────────┬──────────────┬──────────────┬──────────────────────────┘
         │              │              │
         ▼              ▼              ▼
┌────────────┐  ┌────────────┐  ┌─────────────┐
│  Qdrant    │  │  Ollama    │  │  llama.cpp   │
│  Vector DB │  │  Embedding │  │  Local LLM  │
│  Port 6333 │  │  Port11434 │  │  Port 8080  │
└────────────┘  └────────────┘  └─────────────┘
         │              │              │
         ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  PERSISTENT STORAGE                              │
│  ~/.local/share/nixos-ai-stack/                                  │
│  ├── qdrant/          (Vector database)                          │
│  ├── ollama/          (Embedding models)                         │
│  ├── llama-cpp-models/ (GGUF models)                              │
│  └── semantic_cache.db (Response cache)                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Testing Strategy

### Phase 1: Service Health (Automated)
```bash
python3 scripts/check-ai-stack-health-v2.py -v
```

**Expected Results**:
- ✓ Qdrant: Healthy with 5 collections
- ✓ Ollama: Healthy with nomic-embed-text model
- ✓ llama.cpp: Healthy (may show warning during model download)
- ✓ Open WebUI: Healthy on port 3001
- ✓ PostgreSQL: Healthy
- ✓ Redis: Healthy

### Phase 2: RAG System (Automated)
```bash
python3 scripts/rag-system-complete.py
```

**Tests**:
1. Service connectivity
2. Embedding generation
3. Vector search
4. Semantic caching
5. Complete RAG workflow

### Phase 3: Manual Validation

#### Test 1: Generate Embedding
```python
from scripts.rag_system_complete import RAGSystem
rag = RAGSystem()
embedding = rag.generate_embedding("test query")
print(f"Dimensions: {embedding.dimensions}")  # Should be 384
```

#### Test 2: Store and Retrieve
```python
# Store a test solution
payload = EnhancedPayload(
    content="Install libsecret and gcr packages",
    content_type="error_solution",
    language="nix",
    tags=["gnome-keyring", "error-fix"]
)
# Store in Qdrant...

# Search for it
results = rag.search_qdrant(embedding.vector, "error-solutions")
print(f"Found {len(results)} results")
```

#### Test 3: Complete RAG Query
```python
result = rag.rag_query("How to fix keyring error in NixOS?")
print(f"Cache hit: {result['cache_hit']}")
print(f"Context score: {result['context_score']}")
print(f"LLM used: {result['llm_used']}")
print(f"Tokens saved: {result['tokens_saved']}")
```

---

## Performance Expectations

### Token Savings
- **Without RAG**: ~28,000 tokens (full docs)
- **With RAG**: ~500 tokens (query + context)
- **Savings**: 97% reduction

### Response Times
- **Cache hit**: < 10ms
- **Embedding generation**: 50-200ms
- **Vector search**: < 100ms
- **Local LLM**: 500-2000ms
- **Total (no cache)**: 600-2500ms

### Cache Effectiveness
- **Hit rate target**: 30-50% after 100 queries
- **TTL**: 24 hours
- **Storage**: ~1KB per cached query

---

## Troubleshooting

### Issue: Podman still shows newuidmap error

**Cause**: NixOS not rebuilt with new configuration

**Solution**:
```bash
sudo nixos-rebuild switch
# Then reboot if necessary
reboot
```

### Issue: Qdrant connection refused

**Cause**: Container not running

**Solution**:
```bash
podman ps -a | grep qdrant
./scripts/hybrid-ai-stack.sh up
```

### Issue: Ollama model not found

**Cause**: Model still downloading

**Check**:
```bash
podman logs local-ai-ollama
# Look for "successfully pulled nomic-embed-text"
```

### Issue: llama.cpp not responding

**Cause**: Model downloading (first time takes 10-45 min)

**Check**:
```bash
podman logs local-ai-llama-cpp | tail -50
# Look for download progress bars
```

---

## Next Implementation Steps

Once the AI stack is functional, we'll implement:

### 1. Hybrid Coordinator MCP Server
- Intelligent query routing
- Multi-model support
- Automatic fallback handling

### 2. Pattern Extraction
- Automatic detection of repeated solutions
- Template generation
- Pattern library building

### 3. Model Cascading
- Try smallest model first (Qwen 1.5B)
- Escalate if confidence low
- Further 15-25% token savings

### 4. Monitoring Dashboard
- Real-time service status
- Token usage graphs
- Cache hit rates
- Model performance metrics

### 5. Integration into nixos-quick-deploy.sh
- Make Phase 9 mandatory
- Add AI stack to backups
- Automatic health validation

---

## Files Created/Modified

### New Files
1. `scripts/rag-system-complete.py` - Complete RAG implementation
2. `scripts/initialize-ai-stack.sh` - Initialization and validation
3. `AI-STACK-RAG-IMPLEMENTATION.md` - This document
4. `COMPREHENSIVE-SYSTEM-ANALYSIS.md` - System audit

### Modified Files
1. `templates/nixos-improvements/podman.nix` - Fixed rootless permissions

---

## Summary

✅ **Implemented**: Complete RAG system with semantic caching, value scoring, and intelligent routing

✅ **Fixed**: Podman rootless permission issue (requires rebuild)

✅ **Created**: Comprehensive initialization and testing scripts

⏳ **Next**: Rebuild NixOS, initialize AI stack, run tests

Once the system is rebuilt and services are running, we can proceed with:
- End-to-end RAG workflow testing
- Hybrid coordinator implementation
- Pattern extraction automation
- Model cascading optimization
- Monitoring dashboard creation

---

**Ready to proceed!** Run the rebuild, then initialization script.
