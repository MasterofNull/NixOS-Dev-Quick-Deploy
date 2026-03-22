# Troubleshooting Runbooks

**Status:** Active
**Owner:** Operations Team
**Last Updated:** 2026-03-20
**Version:** 1.0

## Table of Contents

1. [Service Failures](#service-failures)
2. [Performance Issues](#performance-issues)
3. [Deployment Failures](#deployment-failures)
4. [Integration Issues](#integration-issues)
5. [Database Issues](#database-issues)
6. [Network and Connectivity](#network-and-connectivity)

---

## Service Failures

### AI Hybrid Coordinator Not Starting

**Symptom**: Service fails to start or crashes immediately after start attempt. Error message in logs: `failed to bind to port 8000` or `configuration validation failed`.

**Root Causes**:
- Port 8000 already in use by another process
- Configuration file syntax error
- Database connectivity issues
- Insufficient system resources (memory, file descriptors)
- Missing required dependencies

**Diagnosis**:

```bash
# Check service status and recent logs
sudo systemctl status ai-hybrid-coordinator
sudo journalctl -u ai-hybrid-coordinator -n 50 --no-pager

# Check if port is in use
sudo netstat -tuln | grep 8000
sudo lsof -i :8000

# Check configuration validity
python3 -m py_compile /etc/ai-stack/config.py

# Check database connectivity
psql -h localhost -U aistack -d aistack -c "SELECT 1"

# Check file descriptor limits
ulimit -n

# Check system resources
free -h
df -h
```

**Resolution**:

**Case 1: Port already in use**
```bash
# Identify process using port 8000
PID=$(sudo lsof -i :8000 | grep LISTEN | awk '{print $2}')

# Kill the process (if safe)
sudo kill -9 $PID

# Or, change port in configuration
sudo vim /etc/nixos/configuration.nix
# Set: services.ai-hybrid-coordinator.port = 8001;

# Redeploy
sudo nixos-rebuild switch
```

**Case 2: Configuration error**
```bash
# Validate and fix configuration
sudo cat /var/log/ai-hybrid-coordinator/config.log

# Common issues:
# - YAML/JSON formatting
# - Missing required fields
# - Invalid credential references

sudo vim /etc/ai-stack/config.yml
sudo systemctl restart ai-hybrid-coordinator
```

**Case 3: Database not ready**
```bash
# Check PostgreSQL status
sudo systemctl status postgresql
sudo systemctl restart postgresql
sleep 5

# Try coordinator again
sudo systemctl start ai-hybrid-coordinator
```

**Case 4: Insufficient resources**
```bash
# Increase file descriptor limits
sudo bash -c 'echo "* soft nofile 65536" >> /etc/security/limits.conf'
sudo bash -c 'echo "* hard nofile 65536" >> /etc/security/limits.conf'

# Restart systemd
sudo systemctl daemon-reexec

# Restart service
sudo systemctl start ai-hybrid-coordinator
```

**Prevention**:
- Use systemd socket activation to avoid port conflicts
- Implement configuration validation in CI/CD
- Monitor file descriptor usage
- Set resource limits in systemd service file

---

### AI Gap Import Service Failing

**Symptom**: The `ai-gap-import.service` systemd unit fails with exit code 127. Logs show `env: 'bash': No such file or directory`.

**Root Causes**:
- Systemd service PATH does not include `/run/current-system/sw/bin` where bash is located
- Script uses `#!/usr/bin/env bash` shebang which depends on PATH resolution
- Service runs in a restricted environment without standard NixOS PATH

**Diagnosis**:

```bash
# Check service status and logs
systemctl status ai-gap-import.service
journalctl -u ai-gap-import.service -n 50 --no-pager

# Verify error message shows bash not found
journalctl -u ai-gap-import.service | grep "No such file"

# Check if bash exists in NixOS
ls -la /run/current-system/sw/bin/bash
```

**Remediation**:

1. **Fix applied in nix/modules/roles/ai-stack.nix**: The service now uses:
   - `path = [ pkgs.bash pkgs.coreutils ... ]` to add tools to PATH
   - `ExecStart = "${pkgs.bash}/bin/bash ${script}"` for explicit bash path

2. **Rebuild NixOS to apply fix**:
   ```bash
   sudo nixos-rebuild switch
   ```

3. **Verify service works**:
   ```bash
   sudo systemctl start ai-gap-import.service
   systemctl status ai-gap-import.service
   ```

**Prevention**:
- Always use explicit Nix paths in systemd service ExecStart
- Use `path = [ ... ]` in NixOS systemd service definitions for script dependencies
- Test systemd services after NixOS module changes

---

### Dashboard API Not Responding

**Symptom**: Dashboard API service is running but responds with errors (500, connection refused, timeout). Requests to `http://localhost:8001/health` fail or timeout.

**Root Causes**:
- Service hanging due to database lock
- Memory exhaustion causing OOM killer
- Slow database queries causing request timeout
- Connection pool exhaustion
- Corrupted cache state

**Diagnosis**:

```bash
# Check if service is responding
curl -i http://localhost:8001/health
curl -v http://localhost:8001/health

# Check service status
sudo systemctl status dashboard-api
sudo journalctl -u dashboard-api -n 100 --no-pager

# Check process state
ps aux | grep dashboard-api
top -p $(pgrep -f dashboard-api)

# Check network connections
sudo netstat -tuln | grep 8001
sudo ss -tupn | grep 8001

# Check database load
psql -h localhost -U aistack -d aistack -c "SELECT * FROM pg_stat_activity;"

# Check memory usage
free -h
vmstat 1 5

# Check disk space
df -h
```

**Resolution**:

**Case 1: Service hanging**
```bash
# Check for long-running queries
psql -h localhost -U aistack -d aistack << 'EOF'
SELECT pid, usename, application_name, state, query, query_start
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY query_start;
EOF

# Kill long-running query if necessary
sudo -u postgres psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid <> pg_backend_pid() AND state = 'active' AND query_start < now() - interval '5 minutes';"

# Restart dashboard API
sudo systemctl restart dashboard-api
```

**Case 2: Memory exhaustion**
```bash
# Check memory usage
top -p $(pgrep -f dashboard-api)

# Check for memory leaks in logs
sudo journalctl -u dashboard-api | grep -i "memory\|oom\|heap"

# Increase memory limit (in /etc/nixos/configuration.nix)
# systemd.services.dashboard-api.serviceConfig.MemoryLimit = "2G";

# Restart with new limits
sudo systemctl daemon-reload
sudo systemctl restart dashboard-api

# Monitor memory over time
watch -n 2 'ps aux | grep dashboard-api'
```

**Case 3: Connection pool exhaustion**
```bash
# Check connection count
psql -h localhost -U aistack -d aistack -c "SELECT datname, count(*) FROM pg_stat_activity GROUP BY datname;"

# Check connection pool status
redis-cli INFO stats | grep connected_clients

# Increase pool size in configuration
sudo vim /etc/ai-stack/database-config.yml
# Set: max_pool_size: 50  (increase from default)

# Restart
sudo systemctl restart dashboard-api
```

**Case 4: Corrupted cache**
```bash
# Clear Redis cache
redis-cli FLUSHALL

# Restart services that depend on cache
sudo systemctl restart dashboard-api
sudo systemctl restart ai-hybrid-coordinator

# Verify operation
curl http://localhost:8001/health
```

**Prevention**:
- Set up connection pool monitoring
- Configure query timeouts
- Monitor memory usage with Prometheus
- Use connection pooler (pgBouncer)

---

### Qdrant Vector Database Connection Failures

**Symptom**: Vector database operations fail with connection errors. Errors like `Connection refused`, `ECONNREFUSED localhost:6333`, `vector index unavailable`.

**Root Causes**:
- Qdrant service not running
- Port 6333 blocked or in use
- Insufficient disk space for indexes
- Network connectivity issues
- Corrupted vector collections

**Diagnosis**:

```bash
# Check Qdrant service status
sudo systemctl status qdrant
sudo journalctl -u qdrant -n 50 --no-pager

# Test connectivity
curl http://localhost:6333/health
curl http://localhost:6333/collections

# Check port availability
sudo netstat -tuln | grep 6333
sudo lsof -i :6333

# Check disk space
df -h /var/lib/qdrant

# Check data directory
ls -lah /var/lib/qdrant/

# Monitor Qdrant metrics
curl http://localhost:6333/metrics | head -20
```

**Resolution**:

**Case 1: Service not running**
```bash
# Start Qdrant
sudo systemctl start qdrant

# Check status
sudo systemctl status qdrant

# Verify collections exist
curl http://localhost:6333/collections

# If collections missing, restore from backup
```

**Case 2: Port blocked**
```bash
# Check firewall rules
sudo firewall-cmd --list-all
sudo iptables -L -n | grep 6333

# Allow Qdrant port
sudo firewall-cmd --permanent --add-port=6333/tcp
sudo firewall-cmd --reload

# Verify
curl http://localhost:6333/health
```

**Case 3: Disk space issue**
```bash
# Check space
df -h /var/lib/qdrant

# If full, archive old data or expand volume
# Move old snapshots to archive
sudo mv /var/lib/qdrant/snapshots/2026-01-* /archive/qdrant-backups/

# Or expand disk
sudo lvextend -L +100G /dev/vg0/qdrant
sudo resize2fs /dev/vg0/qdrant

# Restart Qdrant
sudo systemctl restart qdrant
```

**Case 4: Corrupted collections**
```bash
# Check collection status
curl http://localhost:6333/collections | jq '.'

# Recreate collections
curl -X DELETE "http://localhost:6333/collections/workflow-embeddings"
curl -X DELETE "http://localhost:6333/collections/agent-patterns"

# Recreate
curl -X PUT "http://localhost:6333/collections/workflow-embeddings" \
  -H "Content-Type: application/json" \
  -d '{"vectors": {"size": 1536, "distance": "Cosine"}}'

curl -X PUT "http://localhost:6333/collections/agent-patterns" \
  -H "Content-Type: application/json" \
  -d '{"vectors": {"size": 1536, "distance": "Cosine"}}'

# Reseed data if available
# Run data migration from backup
```

**Prevention**:
- Monitor Qdrant disk usage
- Implement collection snapshots
- Set up health checks for vector database
- Monitor index size and rebuild frequency

---

### PostgreSQL Database Issues

**Symptom**: Database operations fail with connection errors, query timeouts, or "too many connections" errors.

**Root Causes**:
- Database service not running
- Connection pool exhausted
- Corrupted indexes or tables
- Disk space full
- High lock contention
- Memory pressure

**Diagnosis**:

```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Check for running processes
ps aux | grep postgres

# Test basic connectivity
psql -h localhost -U aistack -d aistack -c "SELECT 1"

# Check active connections
psql -h localhost -U aistack -d aistack << 'EOF'
SELECT datname, count(*) as connections
FROM pg_stat_activity
GROUP BY datname;
EOF

# Check for locks
psql -h localhost -U aistack -d aistack << 'EOF'
SELECT * FROM pg_locks
WHERE NOT granted;
EOF

# Check disk space
df -h /var/lib/postgresql

# Check WAL archiving status
psql -h localhost -U aistack -d aistack << 'EOF'
SELECT * FROM pg_stat_replication;
EOF
```

**Resolution**:

**Case 1: Connection pool exhaustion**
```bash
# Check current connections
psql -h localhost -U aistack -d aistack -c "SELECT count(*) FROM pg_stat_activity;"

# Identify long-running queries
psql -h localhost -U aistack -d aistack << 'EOF'
SELECT pid, usename, query_start, query
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY query_start;
EOF

# Kill idle connections (if safe)
psql -h localhost -U aistack -d aistack << 'EOF'
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'aistack'
  AND usename != 'postgres'
  AND pid <> pg_backend_pid()
  AND state = 'idle'
  AND idle_in_transaction_session_timeout > interval '10 minutes';
EOF

# Increase max connections
sudo vim /var/lib/postgresql/data/postgresql.conf
# Set: max_connections = 200  (increase from 100)

# Use pgBouncer for connection pooling
sudo apt-get install pgbouncer
```

**Case 2: Disk space full**
```bash
# Check space
df -h /var/lib/postgresql

# Expand volume
sudo lvextend -L +100G /dev/vg0/postgres
sudo resize2fs /dev/vg0/postgres

# Or, archive old data
# Partition tables by date and archive old partitions
```

**Case 3: Lock contention**
```bash
# Check for locks
psql -h localhost -U aistack -d aistack << 'EOF'
SELECT l.locktype, l.relation::regclass, l.page, l.tuple, l.virtualxid,
       l.transactionid, l.classid, l.objid, l.objsubid, a.usename, a.query,
       a.query_start
FROM pg_locks l
JOIN pg_stat_activity a ON l.pid = a.pid
WHERE NOT l.granted;
EOF

# Kill blocking queries
psql -h localhost -U aistack -d aistack << 'EOF'
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE pid <> pg_backend_pid()
  AND query LIKE '%UPDATE workflows%'
  AND query_start < now() - interval '5 minutes';
EOF
```

**Case 4: Corrupted tables/indexes**
```bash
# Run VACUUM to reclaim space
psql -h localhost -U aistack -d aistack -c "VACUUM ANALYZE workflows;"

# Reindex if needed
psql -h localhost -U aistack -d aistack -c "REINDEX TABLE CONCURRENTLY workflows;"

# Check for corruption
psql -h localhost -U aistack -d aistack -c "ANALYZE workflows;"

# If severe, restore from backup
sudo systemctl stop ai-hybrid-coordinator
sudo -u postgres pg_restore -d aistack /backups/aistack_*.dump
sudo systemctl start ai-hybrid-coordinator
```

**Prevention**:
- Monitor connection count
- Set up automated VACUUM
- Monitor disk space usage
- Implement query timeout limits

---

## Performance Issues

### Slow Route Search (p95 latency high)

**Symptom**: Route search operations are taking longer than expected. `aq-report` shows p95 latency > 1 second when target is 500ms.

**Root Causes**:
- Cache misses causing repeated calculations
- Inefficient query patterns
- Insufficient parallelization workers
- Database index missing
- Qdrant indexing lag

**Diagnosis**:

```bash
# Get performance metrics
aq-report --section=performance

# Check cache statistics
redis-cli INFO stats
redis-cli --stat

# Check database slow queries
psql -h localhost -U aistack -d aistack << 'EOF'
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
WHERE query LIKE '%route%'
ORDER BY mean_time DESC
LIMIT 10;
EOF

# Check Qdrant indexing lag
curl -s http://localhost:6333/metrics | grep qdrant_indexing_lag

# Monitor live latency
watch -n 1 'curl -s http://localhost:8000/metrics | grep request_duration_seconds'
```

**Resolution**:

**Case 1: Cache misses**
```bash
# Check cache hit rate
redis-cli INFO stats | grep hits

# Enable caching in config
sudo vim /etc/ai-stack/performance-config.yml
# Set:
# cache_enabled: true
# cache_ttl_seconds: 300
# cache_max_items: 10000

# Restart service
sudo systemctl restart ai-hybrid-coordinator

# Monitor improvement
aq-report --section=cache
```

**Case 2: Insufficient parallelization**
```bash
# Check CPU cores
nproc

# Increase parallel workers
sudo vim /etc/ai-stack/performance-config.yml
# Set: parallel_workers: 8  (if 8+ cores available)

# Restart
sudo systemctl restart ai-hybrid-coordinator

# Verify improvement
aq-report --section=performance
```

**Case 3: Missing database indexes**
```bash
# Identify slow queries
EXPLAIN ANALYZE SELECT * FROM workflows WHERE status = 'pending' LIMIT 100;

# Create indexes for common filters
psql -h localhost -U aistack -d aistack << 'EOF'
CREATE INDEX idx_workflows_status ON workflows(status);
CREATE INDEX idx_workflows_created ON workflows(created_at DESC);
ANALYZE workflows;
EOF

# Verify improvement
EXPLAIN SELECT * FROM workflows WHERE status = 'pending';
```

**Case 4: Qdrant indexing lag**
```bash
# Check Qdrant indexing status
curl -s http://localhost:6333/collections | jq '.result[] | {name, vectors_count, indexed_vectors_count}'

# Check if background indexing is enabled
curl -s http://localhost:6333/config | jq '.optimizer'

# Reduce batch size to allow faster indexing
# Or, increase Qdrant indexing priority
```

**Prevention**:
- Monitor cache hit rates
- Monitor query execution plans
- Set up automated index maintenance
- Monitor Qdrant indexing queue

---

### Cache Misses and Low Hit Rate

**Symptom**: Cache hit rate below 80% (target 85%+). High cache miss latency impacting user experience.

**Root Causes**:
- Cache TTL too short
- Cache capacity exceeded
- Query patterns not optimized for caching
- Cache invalidation too aggressive
- Memory pressure forcing eviction

**Diagnosis**:

```bash
# Check cache statistics
redis-cli INFO stats

# Sample output should show:
# hits: high number
# misses: low number
# hit_rate = hits / (hits + misses)

# Check memory usage
redis-cli INFO memory

# Check eviction stats
redis-cli INFO stats | grep evicted

# Check key distribution
redis-cli --scan | head -100
redis-cli DBSIZE
```

**Resolution**:

**Case 1: TTL too short**
```bash
# Check current TTL settings
sudo cat /etc/ai-stack/performance-config.yml | grep cache_ttl

# Increase TTL for stable data
sudo vim /etc/ai-stack/performance-config.yml
# Change: cache_ttl_seconds: 600  (from 300)

# Restart
sudo systemctl restart ai-hybrid-coordinator

# Rerun tests to measure improvement
```

**Case 2: Cache capacity exceeded**
```bash
# Check memory usage
redis-cli INFO memory | grep used_memory

# Increase Redis maxmemory
sudo vim /etc/redis/redis.conf
# Set: maxmemory 4gb

# Or, reduce cache items size
sudo vim /etc/ai-stack/performance-config.yml
# Set: cache_max_items: 5000

# Restart
sudo systemctl restart redis
```

**Case 3: Query patterns not optimized**
```bash
# Analyze cache misses
redis-cli MONITOR | head -100

# Identify patterns in misses
# - If similar queries with slight variations: normalize queries
# - If random keys: caching strategy not aligned with actual usage

# Optimize query patterns
# Ensure consistent query format for cache keys
# Add batch operations to reduce per-item lookups
```

**Prevention**:
- Monitor cache hit rate continuously
- Set up alerts for hit rate < 80%
- Implement cache warming for popular queries
- Profile query patterns before caching strategy

---

## Deployment Failures

### Deployment Stuck in Pending State

**Symptom**: Deployment initiated but stuck in "pending" state. No progress for 15+ minutes. No error messages visible.

**Root Causes**:
- Service health checks hanging
- Database migrations blocked
- Deadlock in configuration loading
- Resource contention
- Network connectivity issue

**Diagnosis**:

```bash
# Check deployment status
workflow/run/exec_*/status

# Check service health checks
sudo systemctl status ai-hybrid-coordinator
sudo journalctl -u ai-hybrid-coordinator -f

# Check for hanging processes
ps aux | grep deployment
ps aux | grep nixos-rebuild

# Check system resources
free -h
df -h
top -n 1

# Check network connectivity
ping 8.8.8.8
traceroute github.com
```

**Resolution**:

**Case 1: Health checks hanging**
```bash
# Check what health check is running
sudo cat /proc/$(pgrep -f health-check)/cmdline

# Manually test health endpoint
curl -m 5 http://localhost:8000/health

# If timeout, the health check itself is broken
# Increase health check timeout
sudo vim /etc/nixos/configuration.nix
# systemd.services.ai-hybrid-coordinator.serviceConfig.TimeoutStartSec = "2min";

# Redeploy
sudo nixos-rebuild switch
```

**Case 2: Database migrations blocked**
```bash
# Check for running migrations
psql -h localhost -U aistack -d aistack << 'EOF'
SELECT * FROM pg_stat_activity WHERE state != 'idle';
EOF

# Kill blocking migration if necessary
sudo -u postgres psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE query LIKE '%migration%';"

# Manually complete migration
psql -h localhost -U aistack -d aistack << 'EOF'
BEGIN;
-- Run migration statements
COMMIT;
EOF

# Resume deployment
```

**Case 3: Configuration deadlock**
```bash
# Check if process is stuck in config loading
strace -p $(pgrep -f deployment)

# If in infinite loop, kill and restart
pkill -9 deployment
pkill -9 nixos-rebuild

# Clear deployment state
sudo rm -f /var/run/deployment.lock

# Retry deployment
deploy
```

**Prevention**:
- Set deployment timeout limits
- Implement deployment status polling
- Add verbose logging to deployment steps
- Monitor deployment duration metrics

---

### Service Dependencies Not Met

**Symptom**: Deployment succeeds but services fail to start. Error: `Dependency failed for X service`.

**Root Causes**:
- Dependency service not starting first
- Database not initialized before app startup
- Cache not available
- Network port not available

**Diagnosis**:

```bash
# Check service dependencies
systemctl list-dependencies ai-hybrid-coordinator

# Check which dependency failed
journalctl -u ai-hybrid-coordinator -n 30 --no-pager

# Check all service statuses
sudo systemctl status

# Check prerequisite services
sudo systemctl status postgresql
sudo systemctl status redis
sudo systemctl status qdrant
```

**Resolution**:

**Case 1: Dependency service not started**
```bash
# Start dependencies in order
sudo systemctl start postgresql
sleep 5

sudo systemctl start redis
sleep 3

sudo systemctl start qdrant
sleep 5

# Start dependent service
sudo systemctl start ai-hybrid-coordinator

# Verify
sudo systemctl status ai-hybrid-coordinator
```

**Case 2: Database not initialized**
```bash
# Check if database exists
psql -h localhost -U postgres -c "SELECT datname FROM pg_database WHERE datname = 'aistack';"

# If not, create it
sudo -u postgres createdb aistack

# Initialize schema
psql -h localhost -U aistack -d aistack -f /etc/ai-stack/schema.sql

# Try service again
sudo systemctl start ai-hybrid-coordinator
```

**Case 3: Fix dependency ordering in systemd**
```bash
# Edit service file
sudo vim /etc/systemd/system/ai-hybrid-coordinator.service

# Ensure correct order:
# [Unit]
# After=postgresql.service redis.service qdrant.service
# Wants=postgresql.service redis.service qdrant.service

# [Service]
# Restart=on-failure
# RestartSec=5

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart ai-hybrid-coordinator
```

**Prevention**:
- Define explicit service dependencies
- Implement health check retries
- Add startup delay to dependent services
- Monitor service startup order in tests

---

## Integration Issues

### Workflow Orchestration Failures

**Symptom**: Workflows fail during execution. Error: `Orchestration failed` or `Agent communication timeout`.

**Root Causes**:
- AI Coordinator unable to reach agent endpoints
- Agent evaluation registry desynchronized
- Workflow state corrupted
- Agent timeout too short
- Insufficient workflow execution slots

**Diagnosis**:

```bash
# Check workflow status
workflow/run/exec_*/status

# Get runtime hints
workflow/run/exec_*/hints

# Check coordinator logs
sudo journalctl -u ai-hybrid-coordinator -f

# Check if coordinator can reach agents
curl -i http://localhost:8000/agents/list

# Check evaluation registry
curl -i http://localhost:8000/evaluations/current

# Check workflow queue depth
curl -i http://localhost:8000/workflows/queue
```

**Resolution**:

**Case 1: Agent communication timeout**
```bash
# Increase agent timeout
sudo vim /etc/ai-stack/orchestration-config.yml
# Set: agent_timeout_seconds: 60  (from 30)

# Or check if agents are available
curl http://localhost:8000/agents/list | jq '.agents[] | {name, status}'

# If agents unhealthy, restart them
sudo systemctl restart qwen-agent claude-agent codex-agent

# Retry workflow
workflow/run/start --plan-id "previous_failed_plan"
```

**Case 2: Evaluation registry desynchronized**
```bash
# Rebuild evaluation registry
curl -X POST http://localhost:8000/evaluations/rebuild

# Monitor rebuild progress
watch -n 2 'curl -s http://localhost:8000/evaluations/status | jq ".progress"'

# Once complete, retry workflow
```

**Case 3: Workflow state corrupted**
```bash
# Check workflow state
psql -h localhost -U aistack -d aistack -c "SELECT id, status, error_msg FROM workflows WHERE id = 'exec_0892';"

# Reset workflow state if recoverable
psql -h localhost -U aistack -d aistack << 'EOF'
UPDATE workflows
SET status = 'pending', error_msg = NULL
WHERE id = 'exec_0892' AND status = 'failed';
EOF

# Restart workflow
workflow/run/start --plan-id "exec_0892"
```

**Prevention**:
- Monitor agent availability
- Set reasonable timeout values
- Implement workflow state validation
- Monitor evaluation registry synchronization

---

### Multi-Agent Coordination Problems

**Symptom**: Agents not coordinating correctly. Workflows select wrong agent or fail to delegate tasks.

**Root Causes**:
- Agent evaluation scores not updated
- Agent availability not current
- Coordination algorithm mismatch
- Agent capability registry outdated

**Diagnosis**:

```bash
# Check agent availability
curl http://localhost:8000/agents/list

# Check evaluation scores
curl http://localhost:8000/evaluations/current | jq '.agents[] | {name, score}'

# Check agent specializations
curl http://localhost:8000/agents/capabilities

# Check recent agent assignments
psql -h localhost -U aistack -d aistack << 'EOF'
SELECT agent_id, task_type, success_rate, last_used
FROM agent_evaluations
ORDER BY last_used DESC
LIMIT 20;
EOF
```

**Resolution**:

**Case 1: Evaluation scores outdated**
```bash
# Force evaluation update
curl -X POST http://localhost:8000/evaluations/update

# Check updated scores
curl http://localhost:8000/evaluations/current

# Retry failed tasks with new evaluation
```

**Case 2: Agent not available**
```bash
# Check agent status
curl http://localhost:8000/agents/list

# If agent unhealthy, restart
sudo systemctl restart qwen-agent

# Update agent availability
curl -X POST http://localhost:8000/agents/qwen-agent/status -d '{"available": true}'

# Retry task delegation
```

**Case 3: Agent capability mismatch**
```bash
# Update agent capabilities registry
curl -X POST http://localhost:8000/agents/qwen-agent/capabilities \
  -d '{
    "specializations": ["code", "testing", "documentation"],
    "max_parallel_tasks": 5
  }'

# Re-evaluate task routing
curl -X POST http://localhost:8000/evaluations/rebuild
```

**Prevention**:
- Monitor agent evaluation updates
- Maintain up-to-date capability registry
- Log agent selection decisions
- Implement evaluation confidence thresholds

---

## Database Issues

### Connection Pool Exhaustion

**Symptom**: New connections fail with "too many connections" error. Application can't create new database connections.

**Root Causes**:
- Connections not being released properly
- Connection leak in application code
- High concurrent load
- Connection timeout too long

**Diagnosis**:

```bash
# Count active connections
psql -h localhost -U aistack -d aistack << 'EOF'
SELECT datname, count(*) as connections, max_conn
FROM pg_stat_activity
JOIN (SELECT setting::int as max_conn FROM pg_settings WHERE name='max_connections')
ON true
GROUP BY datname, max_conn;
EOF

# Check connection idle time
psql -h localhost -U aistack -d aistack << 'EOF'
SELECT usename, state, count(*),
       min(state_change), max(state_change)
FROM pg_stat_activity
GROUP BY usename, state;
EOF
```

**Resolution**:

**Case 1: Close idle connections**
```bash
# Close idle connections older than 10 minutes
psql -h localhost -U aistack -d aistack << 'EOF'
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'aistack'
  AND state = 'idle'
  AND state_change < now() - interval '10 minutes'
  AND pid <> pg_backend_pid();
EOF
```

**Case 2: Increase pool size**
```bash
# In /var/lib/postgresql/data/postgresql.conf
max_connections = 200  # increase from 100

# Restart PostgreSQL
sudo systemctl restart postgresql
```

**Case 3: Implement pgBouncer connection pooling**
```bash
# Install pgBouncer
sudo apt-get install pgbouncer

# Configure /etc/pgbouncer/pgbouncer.ini
[databases]
aistack = host=localhost port=5432 dbname=aistack

[pgbouncer]
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
reserve_pool_size = 5

# Start pgBouncer
sudo systemctl start pgbouncer
sudo systemctl enable pgbouncer

# Update application connection string to use pgBouncer (localhost:6432)
```

**Prevention**:
- Monitor connection count
- Set reasonable connection timeouts
- Use connection pooling (pgBouncer)
- Set up alerts for high connection count

---

### Slow Queries

**Symptom**: Database queries are slow, causing timeouts. `aq-report` shows high database latency.

**Root Causes**:
- Missing indexes
- Inefficient query plan
- Table statistics stale
- High lock contention
- Insufficient disk I/O

**Diagnosis**:

```bash
# Enable query logging for slow queries
psql -h localhost -U aistack -d aistack << 'EOF'
ALTER SYSTEM SET log_min_duration_statement = 1000;  -- log queries > 1 second
EOF

# Analyze specific slow query
EXPLAIN ANALYZE SELECT * FROM workflows WHERE status = 'pending' AND created_at > now() - interval '7 days';

# Check table statistics
ANALYZE workflows;
SELECT * FROM pg_stat_user_tables WHERE relname = 'workflows';
```

**Resolution**:

**Case 1: Create missing indexes**
```bash
# Identify slow queries from logs
grep "duration:" /var/log/postgresql/postgresql.log | sort -t: -k3 -rn | head

# Analyze slow query
EXPLAIN ANALYZE SELECT ...

# If using full table scan, create index
CREATE INDEX idx_workflows_status_created
ON workflows(status, created_at DESC)
WHERE status IN ('pending', 'running');

# Verify improvement
EXPLAIN SELECT ... (should use index)
```

**Case 2: Update table statistics**
```bash
# Analyze all tables
ANALYZE;

# Or specific table
ANALYZE workflows;

# Re-run slow query to see if plan improved
EXPLAIN SELECT ...
```

**Case 3: Optimize query**
```bash
# Current slow query:
SELECT * FROM workflows
WHERE status = 'pending'
AND created_at > now() - interval '7 days'
ORDER BY created_at DESC;

# Optimized query:
SELECT id, status, created_at FROM workflows
WHERE status = 'pending'
AND created_at > now() - interval '7 days'
ORDER BY created_at DESC
LIMIT 1000;

-- Only select needed columns (reduce data transfer)
-- Add LIMIT to reduce result set
-- Use indexed columns in WHERE clause
```

**Prevention**:
- Monitor query execution plans
- Set up slow query logging
- Regularly run ANALYZE
- Index columns used in WHERE/JOIN clauses

---

## Network and Connectivity

### Port Conflicts

**Symptom**: Service fails to start with "Address already in use" or "bind failed" error.

**Root Causes**:
- Another process using the port
- Service restart too quick (socket in TIME_WAIT)
- Multiple instances of same service

**Diagnosis**:

```bash
# Find process using port 8000
sudo lsof -i :8000
sudo netstat -tuln | grep 8000

# Check all services on relevant ports
sudo netstat -tuln | grep -E "8000|8001|3000|5432"

# Check for zombie processes
ps aux | grep -i defunct
```

**Resolution**:

**Case 1: Kill process using port**
```bash
# Get PID of process using port
PID=$(sudo lsof -i :8000 | grep LISTEN | awk '{print $2}')

# Kill process
sudo kill -9 $PID

# Restart service
sudo systemctl start ai-hybrid-coordinator
```

**Case 2: Change service port**
```bash
# Edit configuration
sudo vim /etc/nixos/configuration.nix
# Change: services.ai-hybrid-coordinator.port = 8010;

# Redeploy
sudo nixos-rebuild switch
```

**Case 3: Reduce TIME_WAIT**
```bash
# Configure TCP socket reuse
sudo sysctl -w net.ipv4.tcp_tw_reuse=1

# Make permanent
echo "net.ipv4.tcp_tw_reuse=1" | sudo tee -a /etc/sysctl.conf
```

**Prevention**:
- Use systemd socket activation
- Document port assignments
- Implement port conflict detection in deployment

---

### Firewall Blocking Requests

**Symptom**: Remote clients can't connect to services. Services respond locally but not from other machines.

**Root Causes**:
- Firewall rules blocking port
- SELinux denying connections
- Service not binding to correct interface
- Network ACLs blocking traffic

**Diagnosis**:

```bash
# Check firewall status
sudo firewall-cmd --list-all
sudo iptables -L -n

# Check service binding
sudo netstat -tuln | grep 8000
sudo ss -tupn | grep 8000

# Test local connectivity
curl http://localhost:8000/health

# Test remote connectivity
curl http://10.0.1.10:8000/health

# Check SELinux context
sudo getenforce
sudo semanage port -l | grep 8000
```

**Resolution**:

**Case 1: Add firewall rule**
```bash
# Add port to firewall
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --permanent --add-port=8001/tcp
sudo firewall-cmd --permanent --add-port=3000/tcp

# Reload firewall
sudo firewall-cmd --reload

# Verify
sudo firewall-cmd --list-ports
```

**Case 2: Add rich rule for source IP**
```bash
# Allow traffic from specific subnet
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="10.0.0.0/8" port protocol="tcp" port="8000" accept'

# Reload
sudo firewall-cmd --reload
```

**Case 3: Fix SELinux context**
```bash
# Check if SELinux is blocking
sudo sealert -a /var/log/audit/audit.log

# Allow application access if needed
sudo semanage port -a -t http_port_t -p tcp 8000

# Or disable SELinux for troubleshooting
sudo setenforce 0  # temporary
```

**Prevention**:
- Document all open ports
- Use source IP restrictions
- Monitor firewall rule changes
- Test connectivity post-deployment

---

### SSL/TLS Certificate Errors

**Symptom**: HTTPS requests fail with certificate validation errors. Error messages like "certificate verify failed" or "ERR_CERT_AUTHORITY_INVALID".

**Root Causes**:
- Certificate expired
- Certificate not in trust store
- Hostname mismatch
- Self-signed certificate without CA cert installed

**Diagnosis**:

```bash
# Check certificate expiration
openssl x509 -in /etc/ssl/certs/api.example.com.crt -noout -dates

# Check certificate validity
openssl verify /etc/ssl/certs/api.example.com.crt

# Test HTTPS connection
curl -v https://localhost:8000/health

# Check certificate chain
openssl s_client -connect localhost:8000 -showcerts
```

**Resolution**:

**Case 1: Renew expired certificate**
```bash
# Using Let's Encrypt
sudo certbot renew --force-renewal

# Verify renewal
openssl x509 -in /etc/letsencrypt/live/api.example.com/cert.pem -noout -dates

# Restart service
sudo systemctl restart ai-hybrid-coordinator
```

**Case 2: Install self-signed certificate in trust store**
```bash
# For Linux clients
sudo cp /etc/ssl/certs/selfsigned.crt /usr/local/share/ca-certificates/
sudo update-ca-certificates

# Verify
curl https://localhost:8000/health
```

**Case 3: Fix hostname mismatch**
```bash
# Check certificate CN
openssl x509 -in /etc/ssl/certs/cert.crt -noout -subject
# Should match your hostname

# Regenerate certificate with correct hostname
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/api.example.com.key \
  -out /etc/ssl/certs/api.example.com.crt \
  -subj "/CN=api.example.com"

# Update configuration
sudo vim /etc/nixos/configuration.nix
# Set correct certificate paths

# Redeploy
sudo nixos-rebuild switch
```

**Prevention**:
- Set up certificate renewal reminders
- Monitor certificate expiration dates
- Use Let's Encrypt for automated renewal
- Test SSL/TLS after certificate updates

---

**Document Version History**:
- v1.0 (2026-03-20): Initial troubleshooting runbooks

**Related Documentation**:
- [Production Deployment Guide](../operations/production-deployment-guide.md)
- [CLI Reference](../development/cli-reference.md)
- [Architecture Decisions](../architecture/architecture-decisions.md)
