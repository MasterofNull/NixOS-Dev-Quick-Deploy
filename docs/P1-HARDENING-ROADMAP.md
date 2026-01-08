# P1 Production Hardening Roadmap
**Date:** 2026-01-09
**Priority:** High (Complete within 30 days)
**Dependencies:** P0 fixes completed

---

## Overview

This document outlines the P1 (High Priority) production hardening tasks identified in the critical system review. These are non-blocking but important improvements that should be completed before scaling to production load.

---

## Table of Contents

1. [Query Validation](#1-query-validation)
2. [Garbage Collection](#2-garbage-collection)
3. [Let's Encrypt Automation](#3-lets-encrypt-automation)
4. [Implementation Plan](#implementation-plan)
5. [Testing Strategy](#testing-strategy)

---

## 1. Query Validation

### Current Issues

**Problem:** No validation on vector search queries
```python
# Current code (UNSAFE)
@app.post("/vector/search")
async def search(query: str, limit: int):
    # ❌ No size limits
    # ❌ No pagination
    # ❌ No collection name validation
    # ❌ No injection protection

    results = await qdrant.search(
        collection_name=query.collection,  # User-controlled!
        query_vector=embed(query.text),    # Unbounded size!
        limit=limit                         # No max limit!
    )
    return results
```

**Attack Scenarios:**
1. **Resource Exhaustion:** Query 1GB of text → OOM
2. **Collection Enumeration:** Try random collection names → leak data
3. **Result Flooding:** Set limit=1000000 → DoS
4. **Injection:** Malicious collection names → QDRANT exploits

---

### Solution Design

#### 1.1 Query Size Limits

```python
from pydantic import BaseModel, Field, validator

class VectorSearchRequest(BaseModel):
    collection: str = Field(..., min_length=1, max_length=64)
    query: str = Field(..., min_length=1, max_length=10_000)  # 10KB max
    limit: int = Field(default=10, ge=1, le=100)  # Max 100 results
    offset: int = Field(default=0, ge=0, le=10_000)  # Pagination support

    @validator('collection')
    def validate_collection(cls, v):
        # Whitelist allowed collections
        ALLOWED_COLLECTIONS = {
            'nixos_docs',
            'solved_issues',
            'skill_embeddings',
            'telemetry_patterns'
        }

        if v not in ALLOWED_COLLECTIONS:
            raise ValueError(f"Unknown collection: {v}")

        return v

    @validator('query')
    def validate_query_content(cls, v):
        # Basic injection protection
        dangerous_patterns = [
            '<script',  # XSS
            'DROP ',    # SQL-ish
            '../',      # Path traversal
        ]

        v_lower = v.lower()
        for pattern in dangerous_patterns:
            if pattern.lower() in v_lower:
                raise ValueError(f"Potentially malicious query detected")

        return v
```

#### 1.2 Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/vector/search")
@limiter.limit("60/minute")  # 60 requests per minute per IP
@limiter.limit("1000/hour")  # 1000 requests per hour per IP
async def search(request: VectorSearchRequest, req: Request):
    # Validated request
    results = await vector_search_service.search(request)
    return results
```

#### 1.3 Pagination

```python
class PaginatedResponse(BaseModel):
    results: list
    total: int
    offset: int
    limit: int
    has_more: bool

@app.post("/vector/search")
async def search(request: VectorSearchRequest):
    # Get total count (cached)
    total = await qdrant.count(collection_name=request.collection)

    # Fetch with pagination
    results = await qdrant.search(
        collection_name=request.collection,
        query_vector=embed(request.query),
        limit=request.limit,
        offset=request.offset
    )

    return PaginatedResponse(
        results=results,
        total=total,
        offset=request.offset,
        limit=request.limit,
        has_more=(request.offset + request.limit) < total
    )
```

---

### Implementation Steps

**File:** `ai-stack/mcp-servers/aidb/query_validator.py` (NEW)

**Tasks:**
1. Create `VectorSearchRequest` Pydantic model
2. Add collection name whitelist
3. Implement content validation
4. Add rate limiting middleware
5. Add pagination support
6. Update API routes to use validator
7. Add Prometheus metrics for rejected queries

**Metrics:**
```python
QUERY_VALIDATION_FAILURES = Counter(
    "aidb_query_validation_failures_total",
    "Query validation failures by reason",
    ["reason"]
)

QUERY_SIZE_HISTOGRAM = Histogram(
    "aidb_query_size_bytes",
    "Distribution of query sizes",
    buckets=[100, 500, 1000, 5000, 10000]
)
```

---

## 2. Garbage Collection

### Current Issues

**Problem:** Continuous learning fills database infinitely
```python
# Current code (NO CLEANUP)
@app.post("/hybrid/learn")
async def store_solution(solution: Solution):
    # ✅ Stores solution
    # ❌ NEVER deletes old solutions
    # ❌ NEVER deduplicates
    # ❌ NO expiration

    await db.execute(
        "INSERT INTO solved_issues (query, solution, value_score, created_at) "
        "VALUES ($1, $2, $3, NOW())",
        solution.query, solution.text, solution.score
    )
```

**Growth Rate (Estimated):**
- 100 agents × 20 queries/day = 2,000 queries/day
- Avg solution size: 2KB
- Daily growth: 4MB
- **30-day growth: 120MB**
- **1-year growth: 1.46GB**

**Vector Database:**
- 2,000 vectors/day × 384 dimensions × 4 bytes = 3MB/day
- **30-day growth: 90MB vectors**
- **1-year growth: 1.1GB vectors**

Plus metadata, duplicates, low-value entries → **2-3x actual growth**

---

### Solution Design

#### 2.1 Time-Based Expiration

```python
# Automated cleanup job (runs daily)
async def cleanup_old_solutions():
    """Delete solutions older than 30 days with low value scores"""

    deleted = await db.execute("""
        DELETE FROM solved_issues
        WHERE value_score < 0.5
        AND created_at < NOW() - INTERVAL '30 days'
        RETURNING id
    """)

    logger.info(f"Garbage collection: Deleted {len(deleted)} old low-value solutions")

    # Update metrics
    GC_SOLUTIONS_DELETED.inc(len(deleted))
```

#### 2.2 Value-Based Pruning

```python
async def prune_low_value_solutions():
    """Keep only high-value solutions when storage is high"""

    # Check current storage usage
    count = await db.fetchval("SELECT COUNT(*) FROM solved_issues")

    if count > MAX_SOLUTIONS:  # e.g., 100,000
        # Delete bottom 20% by value score
        threshold = await db.fetchval("""
            SELECT value_score
            FROM solved_issues
            ORDER BY value_score ASC
            LIMIT 1 OFFSET (SELECT COUNT(*) FROM solved_issues) * 0.2
        """)

        deleted = await db.execute("""
            DELETE FROM solved_issues
            WHERE value_score < $1
            RETURNING id
        """, threshold)

        logger.warning(f"Pruned {len(deleted)} low-value solutions (storage limit reached)")
```

#### 2.3 Deduplication

```python
async def deduplicate_solutions():
    """Remove near-duplicate solutions"""

    # Find duplicate embeddings (cosine similarity > 0.95)
    duplicates = await qdrant.search_duplicates(
        collection_name="solved_issues",
        similarity_threshold=0.95
    )

    for dup_group in duplicates:
        # Keep highest value score
        keeper = max(dup_group, key=lambda x: x.value_score)
        to_delete = [d.id for d in dup_group if d.id != keeper.id]

        await db.execute("""
            DELETE FROM solved_issues
            WHERE id = ANY($1)
        """, to_delete)

        logger.info(f"Deduplicated {len(to_delete)} similar solutions, kept {keeper.id}")
```

#### 2.4 Vector Database Cleanup

```python
async def cleanup_qdrant_orphans():
    """Remove vectors with no corresponding database entry"""

    # Get all vector IDs from Qdrant
    qdrant_ids = await qdrant.list_all_ids(collection_name="solved_issues")

    # Get all IDs from PostgreSQL
    db_ids = await db.fetch("SELECT id FROM solved_issues")
    db_id_set = set(row['id'] for row in db_ids)

    # Find orphaned vectors
    orphans = [vid for vid in qdrant_ids if vid not in db_id_set]

    if orphans:
        await qdrant.delete(
            collection_name="solved_issues",
            points_selector=orphans
        )
        logger.info(f"Cleaned {len(orphans)} orphaned vectors from Qdrant")
```

---

### Implementation Steps

**File:** `ai-stack/mcp-servers/hybrid-coordinator/garbage_collector.py` (NEW)

**Tasks:**
1. Create `GarbageCollector` class
2. Implement time-based expiration
3. Implement value-based pruning
4. Implement deduplication
5. Implement vector cleanup
6. Add configuration for thresholds
7. Create systemd timer or cron job
8. Add Prometheus metrics

**Configuration:**
```yaml
# ai-stack/mcp-servers/config/config.yaml
garbage_collection:
  enabled: true
  schedule: "0 2 * * *"  # Daily at 2 AM
  max_solutions: 100000
  max_age_days: 30
  min_value_score: 0.5
  deduplicate_similarity: 0.95
  orphan_cleanup_enabled: true
```

**Metrics:**
```python
GC_SOLUTIONS_DELETED = Counter(
    "hybrid_gc_solutions_deleted_total",
    "Solutions deleted by garbage collection",
    ["reason"]
)

GC_VECTORS_CLEANED = Counter(
    "hybrid_gc_vectors_cleaned_total",
    "Orphaned vectors cleaned from Qdrant"
)

GC_STORAGE_BYTES = Gauge(
    "hybrid_gc_storage_bytes",
    "Estimated storage used by solutions"
)
```

---

## 3. Let's Encrypt Automation

### Current Issues

**Problem:** Manual TLS certificate renewal
```bash
# Current workflow (MANUAL)
1. Certificate expires in 7 days
2. Alert fires (if configured)
3. Human logs in
4. Runs: openssl req -x509 -newkey rsa:4096 ...
5. Copies cert to nginx/certs/
6. Restarts nginx
7. Forgets to update calendar reminder
8. Certificate expires unexpectedly 365 days later
```

**Risk:** Production outage due to expired certificate

---

### Solution Design

#### 3.1 Certbot Integration

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Or with Nix
nix-shell -p certbot
```

#### 3.2 Automated Renewal Script

**File:** `scripts/renew-tls-certificate.sh` (NEW)

```bash
#!/usr/bin/env bash
set -euo pipefail

# Automated TLS certificate renewal with Let's Encrypt
# Usage: ./scripts/renew-tls-certificate.sh --domain example.com

DOMAIN=""
EMAIL=""
WEBROOT="/var/www/letsencrypt"
CERT_DIR="ai-stack/compose/nginx/certs"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)
      DOMAIN="$2"
      shift 2
      ;;
    --email)
      EMAIL="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "${DOMAIN}" ]]; then
  echo "❌ Error: --domain required" >&2
  exit 1
fi

if [[ -z "${EMAIL}" ]]; then
  echo "❌ Error: --email required (for Let's Encrypt notifications)" >&2
  exit 1
fi

# Create webroot for ACME challenge
mkdir -p "${WEBROOT}"

# Request certificate
certbot certonly \
  --webroot \
  --webroot-path "${WEBROOT}" \
  --domain "${DOMAIN}" \
  --email "${EMAIL}" \
  --agree-tos \
  --non-interactive \
  --quiet

# Copy to nginx certs directory
cp "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" "${CERT_DIR}/${DOMAIN}.crt"
cp "/etc/letsencrypt/live/${DOMAIN}/privkey.pem" "${CERT_DIR}/${DOMAIN}.key"

# Fix permissions
chmod 644 "${CERT_DIR}/${DOMAIN}.crt"
chmod 600 "${CERT_DIR}/${DOMAIN}.key"

# Reload nginx
podman exec local-ai-nginx nginx -s reload

echo "✅ Certificate renewed for ${DOMAIN}"
echo "   Expires: $(openssl x509 -in "${CERT_DIR}/${DOMAIN}.crt" -noout -enddate | cut -d= -f2)"
```

#### 3.3 Nginx Configuration for ACME Challenge

**File:** `ai-stack/compose/nginx/nginx.conf`

```nginx
# Add HTTP server for ACME challenges
server {
    listen 80;
    server_name your-domain.com;

    # ACME challenge location
    location /.well-known/acme-challenge/ {
        root /var/www/letsencrypt;
    }

    # Redirect everything else to HTTPS
    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/nginx/certs/your-domain.com.crt;
    ssl_certificate_key /etc/nginx/certs/your-domain.com.key;

    # ... rest of config
}
```

#### 3.4 Automated Renewal Cron Job

**File:** `ai-stack/cron/letsencrypt-renewal`

```cron
# Let's Encrypt certificate renewal
# Runs daily at 3 AM, certbot only renews if <30 days until expiry

0 3 * * * root /home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/scripts/renew-tls-certificate.sh --domain your-domain.com --email admin@your-domain.com >> /var/log/letsencrypt-renewal.log 2>&1
```

#### 3.5 Systemd Timer (Alternative)

**File:** `ai-stack/systemd/letsencrypt-renewal.service`

```ini
[Unit]
Description=Let's Encrypt Certificate Renewal
After=network.target

[Service]
Type=oneshot
ExecStart=/home/hyperd/Documents/try/NixOS-Dev-Quick-Deploy/scripts/renew-tls-certificate.sh --domain your-domain.com --email admin@your-domain.com
```

**File:** `ai-stack/systemd/letsencrypt-renewal.timer`

```ini
[Unit]
Description=Let's Encrypt Certificate Renewal Timer
Requires=letsencrypt-renewal.service

[Timer]
OnCalendar=daily
RandomizedDelaySec=1h
Persistent=true

[Install]
WantedBy=timers.target
```

---

### Implementation Steps

**Tasks:**
1. Create renewal script
2. Update nginx config for ACME
3. Test manual renewal
4. Set up cron job or systemd timer
5. Test automated renewal
6. Update monitoring to check renewal status
7. Document process

**Testing:**
```bash
# Test with Let's Encrypt staging (avoid rate limits)
certbot certonly \
  --staging \
  --webroot \
  --webroot-path /var/www/letsencrypt \
  --domain test.example.com \
  --email test@example.com \
  --agree-tos \
  --non-interactive

# Verify renewal works
certbot renew --dry-run
```

---

## Implementation Plan

### Week 1: Query Validation

**Day 1-2:**
- Design validation models
- Implement Pydantic validators
- Add collection whitelist

**Day 3-4:**
- Add rate limiting
- Implement pagination
- Add metrics

**Day 5:**
- Testing and documentation
- Deploy to staging

### Week 2: Garbage Collection

**Day 1-2:**
- Implement time-based expiration
- Implement value-based pruning

**Day 3-4:**
- Implement deduplication
- Implement vector cleanup
- Add configuration

**Day 5:**
- Testing and validation
- Set up cron job

### Week 3: Let's Encrypt

**Day 1-2:**
- Create renewal script
- Update nginx configuration

**Day 3-4:**
- Test with staging
- Set up automation

**Day 5:**
- Production testing
- Documentation

### Week 4: Integration & Testing

**Day 1-3:**
- End-to-end testing
- Load testing
- Performance validation

**Day 4-5:**
- Documentation updates
- Production deployment

---

## Testing Strategy

### Query Validation Tests

```python
# Test 1: Size limits
def test_query_too_large():
    query = "x" * 11_000  # 11KB (over limit)
    response = client.post("/vector/search", json={"query": query})
    assert response.status_code == 422
    assert "max_length" in response.json()["detail"]

# Test 2: Invalid collection
def test_invalid_collection():
    response = client.post("/vector/search", json={
        "collection": "evil_collection",
        "query": "test"
    })
    assert response.status_code == 422
    assert "Unknown collection" in response.json()["detail"]

# Test 3: Pagination
def test_pagination():
    response = client.post("/vector/search", json={
        "collection": "nixos_docs",
        "query": "install",
        "limit": 10,
        "offset": 20
    })
    assert response.status_code == 200
    data = response.json()
    assert data["offset"] == 20
    assert len(data["results"]) <= 10
    assert data["has_more"] in [True, False]
```

### Garbage Collection Tests

```python
# Test 1: Old solution cleanup
async def test_cleanup_old_solutions():
    # Create old low-value solution
    old_date = datetime.now() - timedelta(days=40)
    await db.execute(
        "INSERT INTO solved_issues (query, solution, value_score, created_at) "
        "VALUES ($1, $2, $3, $4)",
        "test", "test solution", 0.3, old_date
    )

    # Run GC
    gc = GarbageCollector()
    await gc.cleanup_old_solutions()

    # Verify deletion
    count = await db.fetchval(
        "SELECT COUNT(*) FROM solved_issues WHERE created_at < NOW() - INTERVAL '30 days'"
    )
    assert count == 0

# Test 2: Deduplication
async def test_deduplication():
    # Create near-duplicates
    text = "How to install vim"
    for i in range(5):
        await store_solution(Solution(
            query=text,
            solution=f"Solution {i}",
            value_score=0.5 + (i * 0.1)
        ))

    # Run deduplication
    gc = GarbageCollector()
    await gc.deduplicate_solutions()

    # Should keep only highest score (0.9)
    remaining = await db.fetch(
        "SELECT * FROM solved_issues WHERE query = $1", text
    )
    assert len(remaining) == 1
    assert remaining[0]['value_score'] == 0.9
```

### Let's Encrypt Tests

```bash
# Test 1: Staging renewal
./scripts/renew-tls-certificate.sh \
  --domain test.example.com \
  --email test@example.com \
  --staging

# Test 2: Dry run
certbot renew --dry-run

# Test 3: Certificate validity
openssl x509 -in /etc/letsencrypt/live/example.com/fullchain.pem -noout -dates
```

---

## Success Criteria

### Query Validation
- [ ] All queries validated before processing
- [ ] Rate limits enforced (60/min, 1000/hour)
- [ ] Pagination working for all endpoints
- [ ] Zero injection vulnerabilities
- [ ] Metrics tracking rejection reasons

### Garbage Collection
- [ ] Daily cleanup job running
- [ ] Database growth stabilized (<100MB/month)
- [ ] Vector storage growth stabilized (<50MB/month)
- [ ] No orphaned vectors
- [ ] Deduplication reducing storage by 20%+

### Let's Encrypt
- [ ] Automated renewal working
- [ ] Certificate renewed before expiry
- [ ] Zero manual intervention required
- [ ] Monitoring alerts on renewal failures
- [ ] Documentation complete

---

## Rollback Plan

If any P1 feature causes issues:

1. **Query Validation Issues**
   - Rollback to validation-free endpoint
   - Adjust limits based on real usage
   - Deploy fixes incrementally

2. **Garbage Collection Issues**
   - Disable automated cleanup
   - Restore from backup if data lost
   - Audit deletion logic

3. **Let's Encrypt Issues**
   - Revert to self-signed certificates
   - Manual renewal as backup
   - Debug ACME challenge issues

---

**End of Roadmap**
