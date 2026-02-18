# P1 Production Hardening - Deployment Guide

**Date**: 2026-01-08
**Version**: 1.0
**Status**: Production Ready

## 🎯 Overview

This guide walks through deploying all P1 (High Priority) production hardening features to your NixOS-Dev-Quick-Deploy AI stack.

**P1 Features Included:**
1. **Query Validation & Rate Limiting** - Input sanitization and DoS protection
2. **Garbage Collection** - Automated storage management
3. **Let's Encrypt Automation** - Automatic TLS certificate renewal

---

## 📋 Prerequisites

Before deploying P1 features, ensure:

- ✅ All P0 fixes are deployed (TLS/HTTPS, API keys, connection pooling, monitoring)
- ✅ System has at least 4GB RAM available
- ✅ PostgreSQL database is running and accessible
- ✅ Qdrant vector database is running
- ✅ Nginx reverse proxy is configured
- ✅ Prometheus and Grafana are running for monitoring

**Check Prerequisites:**
```bash
# Verify P0 components
./scripts/verify-production-readiness.sh

# Check available resources
free -h
df -h

# Verify services
podman ps | grep -E 'aidb|qdrant|nginx|prometheus|grafana'
```

---

## 🚀 Deployment Steps

### Step 1: Update Configuration

The P1 features require new configuration settings in `config.yaml`.

**File**: `ai-stack/mcp-servers/config/config.yaml`

```yaml
# Garbage Collection Configuration
garbage_collection:
  enabled: true
  schedule: "0 2 * * *"  # Run at 2 AM daily
  max_solutions: 100000
  max_age_days: 30
  min_value_score: 0.5
  deduplicate_similarity: 0.95
  orphan_cleanup_enabled: true

# Query Validation Configuration
query_validation:
  enabled: true
  max_query_size: 10000  # 10KB
  max_results: 100
  max_offset: 10000
  rate_limit:
    requests_per_minute: 60
    requests_per_hour: 1000
  allowed_collections:
    - nixos_docs
    - solved_issues
    - skill_embeddings
    - telemetry_patterns
    - system_registry
    - tool_schemas
```

**Action**: Verify configuration is present
```bash
grep -A 10 "garbage_collection:" ai-stack/mcp-servers/config/config.yaml
grep -A 15 "query_validation:" ai-stack/mcp-servers/config/config.yaml
```

---

### Step 2: Deploy Query Validator

The query validator is already integrated into AIDB server.py. Restart the service to apply changes.

**Restart AIDB Service:**
```bash
# Stop existing container
podman stop aidb || true
podman rm aidb || true

# Restart via dashboard script
./scripts/setup-dashboard.sh

# Verify service is running
podman logs aidb --tail 50
```

**Verify Query Validation:**
```bash
# Test valid query
curl -X POST http://localhost:8091/vector/search \
  -H "Content-Type: application/json" \
  -d '{
    "collection": "nixos_docs",
    "query": "How do I configure networking?",
    "limit": 5
  }'

# Test invalid collection (should fail with 400)
curl -X POST http://localhost:8091/vector/search \
  -H "Content-Type: application/json" \
  -d '{
    "collection": "malicious_db",
    "query": "test",
    "limit": 5
  }'

# Test XSS attack (should fail with 400)
curl -X POST http://localhost:8091/vector/search \
  -H "Content-Type: application/json" \
  -d '{
    "collection": "nixos_docs",
    "query": "<script>alert(\"xss\")</script>",
    "limit": 5
  }'
```

**Expected Results:**
- Valid query: `200 OK` with results
- Invalid collection: `400 Bad Request` - "Unknown collection"
- XSS attack: `400 Bad Request` - "potentially malicious patterns"

---

### Step 3: Deploy Garbage Collection

Enable automated garbage collection for the Hybrid Coordinator.

**Integrate GC into Hybrid Coordinator:**

Edit `ai-stack/mcp-servers/hybrid-coordinator/server.py`:

```python
# Add import at top
from garbage_collector import GarbageCollector, run_gc_scheduler

# In your server initialization (around line 100)
async def start_gc_scheduler():
    """Start garbage collection scheduler"""
    if not hasattr(self, '_gc_task'):
        gc = GarbageCollector(
            db_pool=self.db_pool,
            qdrant_client=self.qdrant_client,
            max_solutions=100_000,
            max_age_days=30,
            min_value_score=0.5,
            deduplicate_similarity=0.95
        )
        self._gc_task = asyncio.create_task(
            run_gc_scheduler(gc, interval_seconds=3600)  # Run every hour
        )
        logger.info("Garbage collection scheduler started")

# Call during server startup
await start_gc_scheduler()
```

**Restart Hybrid Coordinator:**
```bash
podman restart hybrid-coordinator
podman logs hybrid-coordinator --tail 50 | grep -i "garbage"
```

**Manual GC Trigger (for testing):**
```python
# Create test script: test_gc.py
import asyncio
import asyncpg
from qdrant_client import QdrantClient
from garbage_collector import GarbageCollector

async def test_gc():
    db_pool = await asyncpg.create_pool(
        host="localhost",
        database="hybrid_coordinator",
        user="aidb",
        password="aidb_password"
    )

    qdrant = QdrantClient(host="localhost", port=6333)

    gc = GarbageCollector(
        db_pool=db_pool,
        qdrant_client=qdrant
    )

    results = await gc.run_full_gc()
    print(f"GC Results: {results}")

    await db_pool.close()

asyncio.run(test_gc())
```

```bash
python3 test_gc.py
```

**Monitor GC Metrics:**
```bash
# Check Prometheus metrics
curl http://localhost:9090/api/v1/query?query=hybrid_gc_solutions_deleted_total

# View in Grafana
# Navigate to: http://localhost:3000/d/hybrid-coordinator
# Panel: "Garbage Collection Operations"
```

---

### Step 4: Deploy Let's Encrypt Automation

Set up automatic TLS certificate renewal with Let's Encrypt.

**4.1. Install Certbot (if not already installed)**

On NixOS, add to your configuration:

```nix
# /etc/nixos/configuration.nix
environment.systemPackages = with pkgs; [
  certbot
];
```

```bash
sudo nixos-rebuild switch
```

**4.2. Configure Nginx for ACME Challenge**

The nginx configuration is already updated with ACME challenge support. Verify it:

```bash
podman exec local-ai-nginx cat /etc/nginx/nginx.conf | grep -A 5 "acme-challenge"
```

**Expected output:**
```nginx
location /.well-known/acme-challenge/ {
  root /var/www/letsencrypt;
  try_files $uri =404;
}
```

**4.3. Create Webroot Directory**

```bash
sudo mkdir -p /var/www/letsencrypt
sudo chown -R $(whoami):$(whoami) /var/www/letsencrypt
```

**4.4. Mount Webroot in Nginx Container**

Edit `ai-stack/compose/docker-compose.yml`:

```yaml
services:
  nginx:
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/certs:/etc/nginx/certs:ro
      - /var/www/letsencrypt:/var/www/letsencrypt:ro  # Add this line
```

Restart nginx:
```bash
podman-compose -f ai-stack/compose/docker-compose.yml down nginx
podman-compose -f ai-stack/compose/docker-compose.yml up -d nginx
```

**4.5. Test Renewal Script (Dry Run)**

```bash
./scripts/renew-tls-certificate.sh \
  --domain localhost \
  --email admin@localhost \
  --staging \
  --dry-run
```

**Expected output:**
```
🔐 Let's Encrypt Certificate Renewal
  Domain: localhost
  Email: admin@localhost
  Staging: true
  Dry Run: true

ℹ️  Running in DRY RUN mode (no actual renewal)
✅ Dry run complete. No changes made.
```

**4.6. Install Systemd Timer**

```bash
# Copy systemd files
sudo cp ai-stack/systemd/letsencrypt-renewal.service /etc/systemd/system/
sudo cp ai-stack/systemd/letsencrypt-renewal.timer /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start timer
sudo systemctl enable letsencrypt-renewal.timer
sudo systemctl start letsencrypt-renewal.timer

# Check timer status
sudo systemctl status letsencrypt-renewal.timer
sudo systemctl list-timers | grep letsencrypt
```

**4.7. Verify Automatic Renewal**

```bash
# Check timer logs
sudo journalctl -u letsencrypt-renewal.timer -f

# Manually trigger renewal (for testing)
sudo systemctl start letsencrypt-renewal.service

# Check renewal logs
sudo journalctl -u letsencrypt-renewal.service -n 100
```

---

### Step 5: Run Integration Tests

Validate all P1 features are working correctly.

```bash
# Install test dependencies
pip install pytest httpx asyncpg qdrant-client

# Run integration tests
python3 ai-stack/tests/test_p1_integration.py

# Or with pytest
pytest ai-stack/tests/test_p1_integration.py -v
```

**Expected Test Results:**
```
test_valid_query_accepted PASSED
test_invalid_collection_rejected PASSED
test_oversized_query_rejected PASSED
test_xss_patterns_blocked PASSED
test_sql_injection_blocked PASSED
test_path_traversal_blocked PASSED
test_rate_limiting_enforced PASSED
test_cleanup_old_solutions PASSED
test_prune_low_value_solutions PASSED
test_deduplicate_solutions PASSED
test_renewal_script_exists PASSED
test_systemd_timer_exists PASSED
test_nginx_acme_challenge_configured PASSED

========================= 13 passed in 5.23s =========================
```

---

## 📊 Monitoring & Verification

### Query Validation Metrics

**Prometheus Queries:**
```promql
# Rate of validation failures
rate(aidb_query_validation_failures_total[5m])

# Rate limit rejections
rate(aidb_rate_limit_rejections_total[5m])

# Query size distribution
histogram_quantile(0.95, aidb_query_size_bytes_bucket)
```

**Grafana Dashboard:**
- Navigate to: http://localhost:3000/d/aidb
- Panel: "Query Validation & Security"
- Metrics: Validation failures, rate limit hits, malicious pattern detections

### Garbage Collection Metrics

**Prometheus Queries:**
```promql
# Solutions deleted by reason
sum by (reason) (rate(hybrid_gc_solutions_deleted_total[1h]))

# Storage utilization
hybrid_gc_storage_bytes / (100000 * 1000)  # Assume 1KB avg per solution

# GC execution time
rate(hybrid_gc_execution_seconds_sum[1h]) / rate(hybrid_gc_execution_seconds_count[1h])
```

**Grafana Dashboard:**
- Navigate to: http://localhost:3000/d/hybrid-coordinator
- Panel: "Garbage Collection"
- Metrics: Deleted solutions, storage usage, execution time

### Certificate Renewal Metrics

**Check Certificate Expiry:**
```bash
# Via Prometheus metric
curl http://localhost:9100/metrics | grep tls_certificate_expiry_seconds

# Via openssl
openssl x509 -in ai-stack/compose/nginx/certs/localhost.crt -noout -enddate
```

**Alert Rules (already configured):**
```yaml
- alert: TLSCertificateExpiringWarning
  expr: (tls_certificate_expiry_seconds - time()) / 86400 < 14
  for: 1h
  annotations:
    summary: "TLS certificate expires in <14 days"
```

---

## 🔧 Troubleshooting

### Query Validation Issues

**Problem**: All queries are being rejected

**Solution:**
```bash
# Check if validation is enabled
grep "enabled: true" ai-stack/mcp-servers/config/config.yaml

# Check logs
podman logs aidb --tail 100 | grep -i validation

# Test with minimal query
curl -X POST http://localhost:8091/vector/search \
  -H "Content-Type: application/json" \
  -d '{"collection": "nixos_docs", "query": "test", "limit": 1}'
```

**Problem**: Rate limiting too aggressive

**Solution**: Adjust limits in config.yaml
```yaml
query_validation:
  rate_limit:
    requests_per_minute: 120  # Increase from 60
    requests_per_hour: 2000   # Increase from 1000
```

### Garbage Collection Issues

**Problem**: GC not running on schedule

**Solution:**
```bash
# Check if GC task is running
podman logs hybrid-coordinator | grep -i "gc scheduler"

# Manually trigger GC
python3 test_gc.py

# Check GC metrics
curl http://localhost:9090/api/v1/query?query=hybrid_gc_solutions_deleted_total
```

**Problem**: GC deleting too many solutions

**Solution**: Adjust GC thresholds
```yaml
garbage_collection:
  max_age_days: 60        # Increase from 30
  min_value_score: 0.3    # Lower from 0.5
```

### Let's Encrypt Issues

**Problem**: Certificate renewal fails

**Solution:**
```bash
# Check certbot logs
sudo journalctl -u letsencrypt-renewal.service -n 100

# Test ACME challenge manually
echo "test" > /var/www/letsencrypt/test.txt
curl http://localhost/.well-known/acme-challenge/test.txt

# Run renewal with verbose output
./scripts/renew-tls-certificate.sh \
  --domain localhost \
  --email admin@localhost \
  --staging \
  --dry-run
```

**Problem**: Nginx not reloading after renewal

**Solution:**
```bash
# Check nginx config syntax
podman exec local-ai-nginx nginx -t

# Manually reload nginx
podman exec local-ai-nginx nginx -s reload

# Check nginx logs
podman logs local-ai-nginx --tail 100
```

---

## 🎯 Production Checklist

Before going to production, verify:

- [ ] Query validation is enabled and rejecting malicious input
- [ ] Rate limiting is enforced (test with rapid requests)
- [ ] GC scheduler is running and creating metrics
- [ ] Let's Encrypt timer is enabled and scheduled
- [ ] All integration tests pass
- [ ] Prometheus metrics are being collected
- [ ] Grafana dashboards show P1 metrics
- [ ] Alerting rules are configured for:
  - TLS certificate expiry
  - High rate limit rejections
  - GC failures
  - Storage approaching limits

**Final Verification:**
```bash
# Run production readiness check
./scripts/verify-production-readiness.sh

# Check all P1 metrics
curl http://localhost:9090/api/v1/label/__name__/values | grep -E 'gc|validation|tls'

# Verify systemd timers
sudo systemctl list-timers | grep letsencrypt
```

---

## 📈 Performance Impact

**Expected Performance Impact:**

| Feature | CPU Impact | Memory Impact | Latency Impact |
|---------|-----------|---------------|----------------|
| Query Validation | +2-5% | +10MB | +5-10ms |
| Rate Limiting | +1-2% | +5MB (per 1000 clients) | +1-2ms |
| Garbage Collection | +5-10% (during GC) | +50MB | 0ms (runs async) |
| Let's Encrypt | 0% (runs daily) | 0MB | 0ms |

**Total**: ~5-10% CPU, +65MB RAM, +6-12ms latency

---

## 🔄 Rollback Plan

If P1 features cause issues, rollback steps:

**1. Disable Query Validation:**
```yaml
# config.yaml
query_validation:
  enabled: false
```

**2. Disable Garbage Collection:**
```yaml
# config.yaml
garbage_collection:
  enabled: false
```

**3. Stop Let's Encrypt Timer:**
```bash
sudo systemctl stop letsencrypt-renewal.timer
sudo systemctl disable letsencrypt-renewal.timer
```

**4. Restart Services:**
```bash
podman restart aidb hybrid-coordinator
```

**5. Verify Rollback:**
```bash
# Query should work without validation
curl -X POST http://localhost:8091/vector/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "limit": 1}'
```

---

## 📚 Additional Resources

- **P1 Implementation Documentation**: `docs/archive/P1-IMPLEMENTATION-COMPLETE.md`
- **P1 Roadmap**: `P1-HARDENING-ROADMAP.md`
- **Query Validator Source**: `ai-stack/mcp-servers/aidb/query_validator.py`
- **Garbage Collector Source**: `ai-stack/mcp-servers/hybrid-coordinator/garbage_collector.py`
- **Renewal Script**: `scripts/renew-tls-certificate.sh`
- **Integration Tests**: `ai-stack/tests/test_p1_integration.py`

---

## 🎉 Success Criteria

P1 deployment is successful when:

✅ All integration tests pass
✅ Query validation blocks malicious input
✅ Rate limiting prevents DoS attacks
✅ GC runs on schedule and manages storage
✅ Let's Encrypt renews certificates automatically
✅ Prometheus metrics are healthy
✅ No performance degradation >15%
✅ Production readiness score: **8/10 or higher**

---

**Deployment completed**: _____________
**Deployed by**: _____________
**Production ready**: ✅ Yes / ⏳ Pending / ❌ No

