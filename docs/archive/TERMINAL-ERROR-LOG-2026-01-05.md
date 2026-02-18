# Terminal & API Error Log
**Started:** 2026-01-05
**Purpose:** Track API connection errors and terminal issues during Claude sessions

---

## How to Use This Log

### Automatic Logging
Every time an API error occurs in the terminal, log it here with:
- Timestamp
- Error message
- Command that caused it
- Context (what we were trying to do)
- Resolution (if fixed)

### Format
```markdown
### ERROR-TERM-XXX: [Short Description]
**Time:** HH:MM PST
**Command:** `command that failed`
**Error:**
```
[error output]
```
**Context:** What we were trying to accomplish
**Status:** [OPEN|INVESTIGATING|FIXED]
**Resolution:** How it was fixed (if applicable)
```

---

## Current Session Errors (2026-01-05)

### ERROR-TERM-001: Embeddings API Returns 501
**Time:** 18:28 PST
**Command:**
```bash
curl -s -X POST http://localhost:8080/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"input": "test embedding"}'
```

**Error:**
```json
{
  "error": {
    "code": 501,
    "message": "This server does not support embeddings. Start it with '--embeddings'",
    "type": "not_supported_error"
  }
}
```

**Context:** Testing if llama.cpp embeddings service was working after initial import

**Status:** ✅ PARTIALLY FIXED

**Resolution:**
1. Added `--embeddings` flag to docker-compose.yml:126
2. Recreated container with `podman-compose down` + `up`
3. New error emerged: Model doesn't support embeddings (pooling type 'none')

**Follow-up Required:**
- Need embedding-capable model OR
- Deploy separate embedding service (sentence-transformers)

---

### ERROR-TERM-002: Embeddings API Returns 400 (Model Incompatible)
**Time:** 18:30 PST
**Command:**
```bash
curl -s -X POST http://localhost:8080/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"input": "test"}'
```

**Error:**
```json
{
  "error": {
    "code": 400,
    "message": "Pooling type 'none' is not OAI compatible. Please use a different pooling type",
    "type": "invalid_request_error"
  }
}
```

**Context:** After adding `--embeddings` flag, testing if it works

**Status:** ⚠️ OPEN - Model Limitation

**Root Cause:** Qwen2.5-Coder-7B model doesn't have embedding capabilities built-in (pooling type is 'none')

**Options:**
1. Switch to embedding-capable model (e.g., nomic-embed-text)
2. Run separate embedding service alongside llama.cpp
3. Use external embedding API

**Impact:**
- All document embeddings are zero vectors
- Semantic search non-functional
- Fallback to payload-based search only

---

### ERROR-TERM-003: Progressive Disclosure Returns NoneType Error
**Time:** 18:22 PST
**Command:**
```bash
curl -s -X POST http://localhost:8092/discovery/capabilities \
  -H 'Content-Type: application/json' \
  -d '{"level": "overview"}'
```

**Error:**
```json
{
  "error": "'NoneType' object has no attribute 'discover'"
}
```

**Context:** Testing progressive disclosure endpoint after initial container rebuild

**Status:** ✅ FIXED

**Root Cause:** Global variable `progressive_disclosure` not declared in `initialize_server()` function

**Resolution:**
1. Updated server.py:1012 to include `progressive_disclosure` in global declaration
2. Rebuilt container
3. Restarted service
4. Verified with test - now returns proper JSON response

**Time to Fix:** ~15 minutes

---

### ERROR-TERM-004: Container Name Conflicts During Rebuild
**Time:** 18:25 PST
**Command:**
```bash
podman-compose up -d hybrid-coordinator
```

**Error:**
```
Error: creating container storage: the container name "local-ai-hybrid-coordinator"
is already in use by 00d0c26828db. You have to remove that container to be able to
reuse that name
```

**Context:** Trying to start container after rebuild

**Status:** ✅ FIXED

**Root Cause:** `podman-compose up` doesn't remove old containers automatically

**Resolution:** Use proper workflow:
```bash
podman-compose stop hybrid-coordinator
podman-compose build hybrid-coordinator
podman-compose up -d hybrid-coordinator
```

Or better:
```bash
podman-compose down hybrid-coordinator
podman-compose up -d hybrid-coordinator
```

**Prevention:** Document proper rebuild procedure

---

### ERROR-TERM-005: Import Script Shows No Embeddings Available
**Time:** 14:47 PST
**Command:**
```bash
python3 scripts/import-documents.py --directory . --extensions .md
```

**Error (repeated in logs):**
```
WARNING - Embedding service unavailable, using zero vector
```

**Context:** Importing 132 markdown files into knowledge base

**Status:** ✅ EXPECTED BEHAVIOR (before embeddings fix)

**Impact:** All 739 chunks stored with zero embeddings

**Resolution:**
- Graceful fallback working as designed
- Will need to re-import after fixing embeddings service
- Or implement batch update of existing documents

---

## API Connection Error Patterns

### Common Causes

1. **Service Not Running**
   - Symptom: Connection refused
   - Check: `curl http://localhost:PORT/health`
   - Fix: `podman ps` then `podman-compose up -d SERVICE`

2. **Wrong Port**
   - Symptom: Connection refused on expected port
   - Check: `podman ps | grep PORT` or `podman port CONTAINER`
   - Fix: Update URL to correct port

3. **Service Starting**
   - Symptom: Connection refused temporarily
   - Check: `podman logs CONTAINER`
   - Fix: Wait 10-30 seconds for startup

4. **Configuration Error**
   - Symptom: 500 errors or unexpected responses
   - Check: `podman logs CONTAINER --tail 50`
   - Fix: Review logs for initialization errors

5. **Model/Feature Not Supported**
   - Symptom: 501 "Not Supported" or 400 "Invalid Request"
   - Check: Model capabilities, server flags
   - Fix: Enable feature flag or use compatible model

---

## Quick Diagnostic Commands

```bash
# Check all services
podman ps | grep local-ai

# Check specific service health
curl http://localhost:8092/health | jq .
curl http://localhost:8080/v1/models | jq .
curl http://localhost:6333/collections | jq .

# Check service logs
podman logs local-ai-hybrid-coordinator --tail 50
podman logs local-ai-llama-cpp --tail 50
podman logs local-ai-qdrant --tail 20

# Check if port is listening
ss -tlnp | grep :8092
ss -tlnp | grep :8080
ss -tlnp | grep :6333

# Restart services
podman-compose restart SERVICE_NAME
# Or full restart
podman-compose down && podman-compose up -d
```

---

## Session Statistics

### Errors by Category
- **API Connection**: 2 errors (1 fixed, 1 model limitation)
- **Container Management**: 1 error (fixed)
- **Service Initialization**: 1 error (fixed)
- **Expected Warnings**: 1 (graceful degradation)

### Resolution Time
- **Total errors**: 5
- **Fixed immediately**: 3
- **Partial fix**: 1
- **Expected behavior**: 1
- **Average resolution time**: ~10 minutes

### Most Common Error Types
1. Missing global variable declarations (Python)
2. Model capability mismatches
3. Container name conflicts
4. Service startup timing

---

## Improvement Recommendations

### For Future Error Prevention

1. **Pre-flight Checks**
   ```python
   async def check_embedding_service():
       """Verify embeddings work before importing"""
       try:
           response = await client.post("/v1/embeddings", json={"input": "test"})
           if response.status_code == 501:
               logger.warning("Embeddings not supported - imports will use zero vectors")
               return False
       except:
           return False
       return True
   ```

2. **Better Error Messages**
   ```python
   # Instead of:
   {"error": "'NoneType' object has no attribute 'discover'"}

   # Provide:
   {
       "error": "Progressive disclosure not initialized",
       "hint": "Check server.py global variable declarations",
       "docs": "https://docs/troubleshooting#global-vars"
   }
   ```

3. **Health Check Enhancements**
   ```bash
   GET /health
   {
       "status": "healthy",
       "services": {
           "qdrant": "ok",
           "redis": "ok",
           "embeddings": "degraded - model incompatible",
           "progressive_disclosure": "ok"
       },
       "warnings": ["Embedding service using zero vectors"]
   }
   ```

4. **Automated Error Reporting**
   - Log all 500 errors to dedicated file
   - Include stack traces
   - Auto-create GitHub issues for new error patterns

---

## Next Error to Log

When you see an error in the terminal, add it here with this template:

```markdown
### ERROR-TERM-XXX: [Brief Description]
**Time:** HH:MM PST
**Command:** `command`
**Error:**
```
error output
```
**Context:** What we were doing
**Status:** OPEN
```

---

**Last Updated:** 2026-01-05 19:20 PST
**Total Errors Logged:** 5
**Errors Resolved:** 3
**Errors Pending:** 1 (embedding model compatibility)
