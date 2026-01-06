# Error and Issue Log - RLM Implementation
**Date:** January 5, 2026
**Session:** Week 1 RLM/RAG Implementation

## Purpose

This document logs all errors, issues, and problems encountered during the RLM (Recursive Language Model) implementation. The goal is to track problems over time to identify patterns, improve the system, and prevent recurring issues.

## Issue Categories

- **[BUILD]** - Build and compilation errors
- **[RUNTIME]** - Runtime execution errors
- **[CONFIG]** - Configuration issues
- **[INTEGRATION]** - Integration and API issues
- **[DATA]** - Data and knowledge base issues
- **[PERFORMANCE]** - Performance problems

---

## Session Issues (2026-01-05)

### ISSUE-001: Missing Global Variable Declaration
**Category:** [RUNTIME]
**Severity:** High
**Status:** ✅ FIXED

**Description:**
Progressive disclosure API was returning error: `'NoneType' object has no attribute 'discover'`

**Root Cause:**
The `progressive_disclosure` global variable was initialized in `initialize_server()` but not declared in the `global` statement, causing it to be assigned to a local variable instead of the global one.

**Error Details:**
```python
# File: ai-stack/mcp-servers/hybrid-coordinator/server.py
# Line 1012

async def initialize_server():
    global qdrant_client, llama_cpp_client, embedding_client, multi_turn_manager, feedback_api
    # Missing: progressive_disclosure
```

**Fix Applied:**
```python
async def initialize_server():
    global qdrant_client, llama_cpp_client, embedding_client, multi_turn_manager, feedback_api, progressive_disclosure
```

**Impact:**
- API endpoint `/discovery/capabilities` returned 500 errors
- Could not test progressive disclosure functionality
- Container rebuild required

**Prevention:**
- Add linting rule to check global variable declarations
- Add unit tests that verify all global variables are properly initialized
- Consider using dependency injection instead of global variables

**Files Modified:**
- [ai-stack/mcp-servers/hybrid-coordinator/server.py:1012](ai-stack/mcp-servers/hybrid-coordinator/server.py#L1012)

**Time to Fix:** ~15 minutes (diagnosis + fix + rebuild + test)

---

### ISSUE-002: Dockerfile Missing New Python Modules
**Category:** [BUILD]
**Severity:** High
**Status:** ✅ FIXED

**Description:**
Initial container rebuild completed successfully but new Python modules were not included in the container image.

**Root Cause:**
Dockerfile had hardcoded list of files to copy. New modules (`multi_turn_context.py`, `remote_llm_feedback.py`, `progressive_disclosure.py`, `context_compression.py`, `query_expansion.py`, `embedding_cache.py`) were not in the COPY list.

**Error Details:**
```dockerfile
# Only copied these files:
COPY hybrid-coordinator/server.py .
COPY hybrid-coordinator/coordinator.py .
COPY hybrid-coordinator/federation_sync.py .
COPY hybrid-coordinator/continuous_learning.py .
COPY hybrid-coordinator/continuous_learning_daemon.py .
COPY hybrid-coordinator/start_with_learning.sh .
# Missing: 6 new modules
```

**Fix Applied:**
Added all new modules to Dockerfile:
```dockerfile
COPY hybrid-coordinator/multi_turn_context.py .
COPY hybrid-coordinator/remote_llm_feedback.py .
COPY hybrid-coordinator/progressive_disclosure.py .
COPY hybrid-coordinator/context_compression.py .
COPY hybrid-coordinator/query_expansion.py .
COPY hybrid-coordinator/embedding_cache.py .
```

**Impact:**
- Import errors at runtime
- APIs would fail with ModuleNotFoundError
- Required second rebuild

**Prevention:**
- Use wildcard COPY: `COPY hybrid-coordinator/*.py .`
- Or copy entire directory: `COPY hybrid-coordinator/ /app/`
- Add CI check to verify all .py files are included
- Document file addition process

**Files Modified:**
- [ai-stack/mcp-servers/hybrid-coordinator/Dockerfile:55-67](ai-stack/mcp-servers/hybrid-coordinator/Dockerfile#L55-L67)

**Time to Fix:** ~10 minutes (update Dockerfile + rebuild)

---

### ISSUE-003: Embeddings Not Enabled in llama.cpp
**Category:** [CONFIG]
**Severity:** Medium
**Status:** ⚠️ PARTIALLY FIXED

**Description:**
Embedding API calls returned HTTP 501 error indicating embeddings not supported.

**Error Details:**
```json
{
  "error": {
    "code": 501,
    "message": "This server does not support embeddings. Start it with `--embeddings`",
    "type": "not_supported_error"
  }
}
```

**Root Cause:**
llama.cpp server was not started with `--embeddings` flag in docker-compose.yml.

**Fix Applied:**
Added `--embeddings` flag to command arguments:
```yaml
command:
  - "--metrics"
  - "--embeddings"  # Added this line
```

**Current Status:**
Flag added and container restarted, but now getting different error:

```json
{
  "error": {
    "code": 400,
    "message": "Pooling type 'none' is not OAI compatible. Please use a different pooling type",
    "type": "invalid_request_error"
  }
}
```

**New Issue:**
The model (Qwen2.5-Coder-7B) doesn't have embedding capabilities built-in. Need to either:
1. Use a different model with embedding support
2. Load a separate embedding model
3. Use external embedding service

**Impact:**
- Semantic search non-functional
- All embeddings in Qdrant are zero vectors
- RAG retrieval falls back to payload-based search only
- Quality of context retrieval is degraded

**Prevention:**
- Document model requirements (embedding pooling type)
- Add health check that verifies embedding functionality
- Consider bundled embedding model configuration

**Files Modified:**
- [ai-stack/compose/docker-compose.yml:126](ai-stack/compose/docker-compose.yml#L126)

**Time to Fix:** ~5 minutes (config change) + pending (model issue)

**Action Required:**
- [ ] Research embedding-capable models for llama.cpp
- [ ] Or add separate embedding service (sentence-transformers)
- [ ] Update documentation with embedding requirements

---

### ISSUE-004: Import Statement Had 744 Documents but Took 18 Seconds
**Category:** [PERFORMANCE]
**Severity:** Low
**Status:** ⚠️ MONITORING

**Description:**
Document import processed 132 files creating 739 chunks in approximately 18 seconds. Each embedding call made unnecessary HTTP request even though it would fail.

**Performance Metrics:**
```
Files imported:     132
Chunks created:     739
Time taken:         ~18 seconds
Average per file:   ~136ms
Average per chunk:  ~24ms
```

**Root Cause:**
Document importer makes HTTP request to embedding service for every chunk, even though embeddings are not available. Should detect failure once and skip subsequent calls.

**Impact:**
- Slower than necessary import process
- Unnecessary network overhead
- Repeated 501 errors in logs

**Optimization Opportunities:**
1. Check embedding availability once before batch import
2. Cache "embedding unavailable" status
3. Batch embedding requests instead of one-per-chunk
4. Use connection pooling for HTTP requests

**Prevention:**
- Add embedding availability pre-check
- Implement batch embedding API
- Add performance benchmarks to CI

**Files Affected:**
- [ai-stack/mcp-servers/aidb/document_importer.py](ai-stack/mcp-servers/aidb/document_importer.py)

**Time Lost:** ~13 seconds per import run

**Action Required:**
- [ ] Add embedding availability check
- [ ] Implement batch embedding
- [ ] Add performance tests

---

### ISSUE-005: Container Name Conflicts During Rebuild
**Category:** [BUILD]
**Severity:** Low
**Status:** ⚠️ WORKAROUND APPLIED

**Description:**
When running `podman-compose up -d` after rebuild, got errors about container names already in use.

**Error Details:**
```
Error: creating container storage: the container name "local-ai-hybrid-coordinator"
is already in use by 00d0c26828db. You have to remove that container to be able to
reuse that name: that name is already in use
```

**Root Cause:**
`podman-compose up -d hybrid-coordinator` tries to create dependent containers (qdrant, redis, postgres) but old containers with same names exist.

**Workaround:**
Use explicit stop + up sequence:
```bash
podman-compose stop hybrid-coordinator
podman-compose build hybrid-coordinator
podman-compose up -d hybrid-coordinator
```

**Better Solution:**
Use `podman-compose down` + `up` to properly clean up:
```bash
podman-compose down hybrid-coordinator
podman-compose up -d hybrid-coordinator
```

**Impact:**
- Confusing error messages
- Required manual intervention
- Slows development iteration

**Prevention:**
- Document proper rebuild procedure
- Create helper script for common operations
- Consider using `--replace` flag

**Files Affected:**
None (operational issue)

**Time Lost:** ~2 minutes per occurrence

---

## Historical Issues (For Reference)

### ISSUE-006: Knowledge Base Had Only 9 Documents Initially
**Category:** [DATA]
**Severity:** Medium
**Status:** ✅ FIXED

**Description:**
System started with only 9 documents in knowledge base (5 in codebase-context, 4 test entries), making RAG essentially useless.

**Fix Applied:**
- Created document import pipeline
- Populated from web searches (24 entries)
- Imported 132 markdown files (739 chunks)
- Total: 778 documents

**Prevention:**
- Automate knowledge base population on first run
- Add knowledge base health checks
- Document minimum viable knowledge base size

---

## Issue Statistics

### By Category
- **[RUNTIME]**: 1 issue
- **[BUILD]**: 2 issues
- **[CONFIG]**: 1 issue
- **[PERFORMANCE]**: 1 issue
- **[DATA]**: 1 issue

### By Severity
- **High**: 3 issues (2 fixed)
- **Medium**: 2 issues (1 fixed)
- **Low**: 2 issues

### By Status
- **✅ FIXED**: 3 issues
- **⚠️ PARTIALLY FIXED**: 1 issue
- **⚠️ MONITORING**: 1 issue
- **⚠️ WORKAROUND APPLIED**: 1 issue

### Time Impact
- **Total time lost to issues**: ~45 minutes
- **Average time per issue**: ~7.5 minutes
- **Build/rebuild time**: ~3 rebuilds × 2 minutes = 6 minutes
- **Diagnosis time**: ~25 minutes
- **Fix implementation time**: ~14 minutes

---

## Patterns and Insights

### Common Patterns Identified

1. **Global Variable Management**
   - Python global variables are error-prone
   - Easy to forget in global declarations
   - Consider dependency injection pattern

2. **Docker Build Process**
   - Manual file listing in Dockerfile causes omissions
   - Need automated file discovery or wildcards
   - Multi-stage builds working well

3. **Configuration Management**
   - docker-compose.yml changes require container recreation
   - `restart` doesn't pick up new configs
   - Need clear documentation on when to use `down`/`up` vs `restart`

4. **Embedding Service Architecture**
   - Tight coupling to llama.cpp model choice
   - Should support pluggable embedding backends
   - Need better error messages about model capabilities

### Recommendations for System Improvements

1. **Add Pre-Flight Checks**
   ```python
   async def preflight_check():
       """Verify system requirements before starting"""
       # Check embedding service availability
       # Verify minimum knowledge base size
       # Test all service connections
       # Validate configuration
   ```

2. **Improve Error Messages**
   - Add context about what failed and why
   - Suggest fixes in error messages
   - Include relevant documentation links

3. **Add Health Monitoring**
   - Track embedding service availability
   - Monitor knowledge base size
   - Alert on degraded functionality

4. **Development Tooling**
   - Create `scripts/dev-rebuild.sh` for common rebuild workflow
   - Add `scripts/verify-build.sh` to check container contents
   - Implement pre-commit hooks for common mistakes

5. **Documentation**
   - Document common error scenarios and fixes
   - Add troubleshooting guide
   - Create developer quickstart guide

---

## Action Items

### Immediate (This Session)
- [x] Fix global variable declaration
- [x] Update Dockerfile with all modules
- [x] Enable embeddings flag in docker-compose.yml
- [ ] Research embedding-capable models
- [ ] Create this error log document

### Short-term (Next Session)
- [ ] Implement embedding availability pre-check
- [ ] Add batch embedding support
- [ ] Create dev-rebuild helper script
- [ ] Add pre-flight checks to server startup
- [ ] Document rebuild procedures

### Long-term (Future)
- [ ] Replace global variables with dependency injection
- [ ] Implement pluggable embedding backend
- [ ] Add comprehensive health monitoring
- [ ] Create CI pipeline with build verification
- [ ] Add performance benchmarks

---

## Lessons Learned

1. **Test Early and Often**
   - Testing endpoints immediately after rebuild would have caught global variable issue faster
   - Should test each component as it's added

2. **Automation Over Documentation**
   - Dockerfile wildcards better than documenting "remember to add files"
   - Scripts better than instructions

3. **Fail Fast with Clear Errors**
   - Early checks prevent cascading failures
   - Good error messages save debugging time

4. **Know Your Dependencies**
   - Understanding model capabilities before integration
   - Check compatibility matrix upfront

5. **Version Everything**
   - Docker images
   - Python packages
   - Models
   - Configurations

---

## Future Error Reporting Template

For consistency, future errors should be logged with:

```markdown
### ISSUE-XXX: [Short Description]
**Category:** [BUILD|RUNTIME|CONFIG|INTEGRATION|DATA|PERFORMANCE]
**Severity:** [High|Medium|Low]
**Status:** [FIXED|PARTIAL|MONITORING|WORKAROUND|OPEN]

**Description:**
[What happened]

**Root Cause:**
[Why it happened]

**Error Details:**
[Code/logs/stack traces]

**Fix Applied:**
[What was done]

**Impact:**
[Consequences]

**Prevention:**
[How to avoid in future]

**Files Modified:**
[List with line numbers]

**Time to Fix:** [Duration]

**Action Required:**
- [ ] Item 1
- [ ] Item 2
```

---

## Contact and Updates

This document should be updated continuously as new issues are discovered. Each session should add new issues to the top of the "Session Issues" section.

**Last Updated:** 2026-01-05 18:45 PST
**Next Review:** After next implementation session
**Maintained By:** AI Stack Development Team
