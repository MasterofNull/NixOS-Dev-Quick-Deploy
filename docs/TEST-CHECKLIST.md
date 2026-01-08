# AI Stack Testing Checklist
**Date**: 2025-12-20
**Purpose**: Track testing progress and results

---

## Pre-Flight Checks

- [ ] **Deployment script run**: `./nixos-quick-deploy.sh --with-ai-stack`
- [ ] **NixOS dry-build validation**: `nix --extra-experimental-features 'nix-command flakes' build --print-out-paths '/home/$USER/.dotfiles/home-manager#nixosConfigurations.\"nixos\".config.system.build.toplevel' --dry-run`
- [ ] **NixOS rebuild completed**: No errors
- [ ] **Podman works**: `podman ps` (no newuidmap error)
- [ ] **AI stack initialized**: `./scripts/initialize-ai-stack.sh`
- [ ] **AI stack env sanity**: `grep -q '^GRAFANA_ADMIN_USER=' ~/.config/nixos-ai-stack/.env && grep -q '^GRAFANA_ADMIN_PASSWORD=' ~/.config/nixos-ai-stack/.env`
- [ ] **Hardware tier selected**: CPU-only / iGPU / GPU

### Hardware Tiers (Expected Defaults)

| Tier | Coder Default | Embedding Default | Expected Load Time |
|------|---------------|-------------------|--------------------|
| **CPU-only (< 24GB RAM)** | qwen3-4b | sentence-transformers/all-MiniLM-L6-v2 | Coder < 5 min, Embeddings < 2 min |
| **iGPU (>= 24GB RAM)** | qwen2.5-coder | sentence-transformers/all-MiniLM-L6-v2 | Coder < 5 min, Embeddings < 2 min |
| **GPU (>= 16GB VRAM)** | qwen2.5-coder | sentence-transformers/all-MiniLM-L6-v2 | Coder < 3 min, Embeddings < 2 min |
| **GPU (>= 24GB VRAM)** | qwen2.5-coder-14b | sentence-transformers/all-MiniLM-L6-v2 | Coder < 3 min, Embeddings < 2 min |

---

## Service Health Checks

Run: `python3 scripts/check-ai-stack-health-v2.py -v`

- [ ] **Qdrant**: ✓ Healthy with 5 collections
- [ ] **Ollama**: ✓ Healthy with nomic-embed-text model
- [ ] **llama.cpp**: ✓ Healthy with Qwen2.5-Coder-7B
- [ ] **Open WebUI**: ✓ Healthy on port 3001
- [ ] **PostgreSQL**: ✓ Healthy
- [ ] **Redis**: ✓ Healthy
- [ ] **MindsDB**: ○ Optional (can be stopped)

**Summary**: ___ / 6 core services healthy

---

## RAG System Tests

### Test 1: RAG System Initialization
Run: `python3 scripts/rag-system-complete.py`

- [ ] Service diagnostics show all available
- [ ] Test query executes without errors
- [ ] Cache statistics displayed
- [ ] Configuration loaded correctly

**Result**: ✅ Pass / ❌ Fail / ⚠️ Partial
**Notes**: ___________________________________________

### Test 2: Embedding Generation
- [ ] Embedding generated (384 dimensions)
- [ ] Model: nomic-embed-text
- [ ] Response time < 200ms

**Actual time**: _______ ms
**Result**: ✅ Pass / ❌ Fail

### Test 3: Vector Storage
- [ ] Solution stored in Qdrant
- [ ] Returned valid UUID
- [ ] No errors in logs

**Solution ID**: ______________________________
**Result**: ✅ Pass / ❌ Fail

### Test 4: Vector Retrieval
- [ ] Query found stored solution
- [ ] Confidence score > 0.5
- [ ] Context retrieved correctly

**Confidence**: _______ (target: > 0.7)
**Result**: ✅ Pass / ❌ Fail

### Test 5: Semantic Caching
- [ ] First query: Cache miss
- [ ] Second query (identical): Cache hit
- [ ] Tokens saved on cache hit
- [ ] Cache statistics updated

**1st query tokens saved**: _______
**2nd query tokens saved**: _______
**Result**: ✅ Pass / ❌ Fail

### Test 6: Value Scoring
- [ ] High-value score: 0.7-1.0
- [ ] Low-value score: 0.0-0.5
- [ ] Algorithm working correctly

**High-value actual**: _______
**Low-value actual**: _______
**Result**: ✅ Pass / ❌ Fail

---

## Hybrid Coordinator Tests

Run: `python3 ai-stack/mcp-servers/hybrid-coordinator/coordinator.py`

- [ ] Coordinator initializes without errors
- [ ] Test query executes
- [ ] Statistics tracking works
- [ ] Solution storage works
- [ ] Query routing logic executes

**LLM Used**: Local / Remote
**Confidence**: _______
**Tokens Saved**: _______
**Result**: ✅ Pass / ❌ Fail

---

## Performance Measurements

### Response Times (Target < 2.5s)
- Cache hit: _______ ms (target: < 10ms)
- Embedding: _______ ms (target: < 200ms)
- Vector search: _______ ms (target: < 100ms)
- Full RAG query: _______ s (target: < 2.5s)

### Token Savings
- Average per query: _______ tokens
- Percentage saved: _______% (target: 30-50%)
- Total queries tested: _______
- Cache hit rate: _______% (target: 25-50% after 20 queries)

### Cache Performance
- Total entries: _______
- Total hits: _______
- Average hits per entry: _______

---

## Integration Tests

### End-to-End Workflow
- [ ] Query → Embedding → Search → Context → LLM → Response
- [ ] Error handling works correctly
- [ ] Statistics tracked accurately
- [ ] Results cached for reuse

**Result**: ✅ Pass / ❌ Fail
**Notes**: ___________________________________________

### Multi-Query Test (20 queries)
- [ ] All queries complete successfully
- [ ] Cache hit rate increases over time
- [ ] Token savings accumulate
- [ ] No memory leaks or errors

**Final cache hit rate**: _______%
**Total tokens saved**: _______
**Result**: ✅ Pass / ❌ Fail

---

## Known Issues Log

| Issue | Severity | Status | Notes |
|-------|----------|--------|-------|
| | | | |
| | | | |
| | | | |

**Rule:** If the dry-build validation fails, log the error here before proceeding.

---

## Overall Test Results

### Summary
- **Total Tests**: 20
- **Passed**: ___ / 20
- **Failed**: ___ / 20
- **Warnings**: ___ / 20

### Critical Components
- [ ] Podman working (CRITICAL)
- [ ] All services healthy (CRITICAL)
- [ ] RAG workflow functional (CRITICAL)
- [ ] Token savings demonstrated (HIGH)
- [ ] Caching working (MEDIUM)

### Sign-Off
**Testing completed**: _____ (date/time)
**Tested by**: hyperd / Claude
**Overall status**: ✅ Ready for Production / ⚠️ Issues Found / ❌ Major Problems

---

## Release Acceptance (Team Rollout)

### Environment Cohesion
- [ ] `scripts/validate-ai-stack-env-drift.sh` passes on a clean install
- [ ] `.env` values match compose expectations (no hardcoded overrides)
- [ ] Model selection prompts reflect actual defaults in `.env`

### Model Operations
- [ ] `scripts/swap-llama-cpp-model.sh` swaps GGUF without redownloading
- [ ] `scripts/swap-embeddings-model.sh` swaps embeddings and restarts cleanly
- [ ] Cached + active models visible in `dashboard.html`

### Health & Reliability
- [ ] `scripts/system-health-check.sh --detailed` passes
- [ ] `scripts/check-ai-stack-health-v2.py -v` passes
- [ ] AI stack health gates enforce failure when unhealthy

### Performance Baselines
- [ ] CPU-only: llama.cpp model loads < 5 min, embeddings < 2 min
- [ ] iGPU: same as CPU-only
- [ ] GPU 16GB+: llama.cpp loads < 3 min, embeddings < 2 min

---

## Next Steps After Testing

Once all tests pass:

1. [ ] Document final performance metrics
2. [ ] Continue with system review improvements
3. [ ] Implement pattern extraction
4. [ ] Implement model cascading
5. [ ] Create monitoring dashboard
6. [ ] Integrate into Phase 9 deployment
7. [ ] Update all documentation with actual metrics

---

## Quick Commands Reference

```bash
# Health check
python3 scripts/check-ai-stack-health-v2.py -v

# RAG test
python3 scripts/rag-system-complete.py

# Coordinator test
python3 ai-stack/mcp-servers/hybrid-coordinator/coordinator.py

# Service logs
podman logs -f local-ai-qdrant
podman logs -f local-ai-ollama
podman logs -f local-ai-llama-cpp

# Service management
./scripts/hybrid-ai-stack.sh status
./scripts/hybrid-ai-stack.sh up
./scripts/hybrid-ai-stack.sh down
./scripts/hybrid-ai-stack.sh restart

# Cache stats
python3 -c "from pathlib import Path; from scripts.rag_system_complete import SemanticCache; cache = SemanticCache(Path.home() / '.local/share/nixos-ai-stack/semantic_cache.db'); print(cache.stats())"
```

---

**Ready to test!** Check off items as you complete them.
