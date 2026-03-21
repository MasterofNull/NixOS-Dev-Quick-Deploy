# CLI Reference Documentation

**Status:** Active
**Owner:** Developer Relations Team
**Last Updated:** 2026-03-20
**Version:** 1.0

## Overview

The NixOS-Dev-Quick-Deploy AI stack provides several command-line tools for system management, diagnostics, workflow orchestration, and deployment operations. This reference documents all available CLI commands, their options, and usage patterns.

## Table of Contents

1. [aq-report Command](#aq-report-command)
2. [aq-hints Command](#aq-hints-command)
3. [workflow Commands](#workflow-commands)
4. [Deployment Commands](#deployment-commands)
5. [Testing Commands](#testing-commands)
6. [Common Workflows](#common-workflows)

## aq-report Command

Generate comprehensive system status and diagnostic reports.

### Usage

```bash
aq-report [options]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--format=json\|text` | Output format | `text` |
| `--section=<section>` | Report section | `all` |
| `--verbose, -v` | Verbose output | off |
| `--quiet, -q` | Minimal output | off |
| `--output=<file>` | Write to file | stdout |

### Available Sections

- `services`: Service health and status
- `cache`: Cache performance and hit rates
- `evaluations`: Agent evaluation metrics
- `performance`: System performance metrics
- `deployments`: Recent deployment history
- `all`: Complete report (default)

### Examples

**Basic status report**:
```bash
$ aq-report
System Status Report - 2026-03-20 15:30:45

Services:
  ai-hybrid-coordinator: running (uptime: 4d 3h 22m)
  dashboard-api: running (uptime: 4d 3h 22m)
  dashboard-frontend: running (uptime: 4d 3h 22m)
  postgresql: running (uptime: 4d 3h 22m)
  redis: running (uptime: 4d 3h 22m)

Cache Statistics:
  Hit Rate: 87.3%
  Miss Rate: 12.7%
  Items Cached: 2,847
  Memory Used: 1.2 GB / 4.0 GB

Last Check: 2026-03-20 15:30:45
Status: HEALTHY
```

**Service section only, JSON format**:
```bash
$ aq-report --section=services --format=json
{
  "services": [
    {
      "name": "ai-hybrid-coordinator",
      "status": "running",
      "uptime_seconds": 366132,
      "memory_mb": 512,
      "cpu_percent": 2.1,
      "timestamp": "2026-03-20T15:30:45Z"
    },
    {
      "name": "dashboard-api",
      "status": "running",
      "uptime_seconds": 366132,
      "memory_mb": 384,
      "cpu_percent": 1.5,
      "timestamp": "2026-03-20T15:30:45Z"
    }
  ]
}
```

**Performance metrics report**:
```bash
$ aq-report --section=performance
Performance Report - 2026-03-20 15:30:45

CPU Metrics:
  Usage: 12.3%
  Load Average: 2.1 (1m), 1.9 (5m), 1.7 (15m)
  Context Switches: 145,232 / minute

Memory Metrics:
  Total: 64.0 GB
  Used: 34.2 GB (53.4%)
  Available: 29.8 GB
  Swap Used: 2.1 GB

Disk I/O:
  Read: 125 MB/s
  Write: 43 MB/s
  IOPS: 4,521

Network:
  eth0 RX: 2.1 Gbps
  eth0 TX: 1.8 Gbps
  Connections: 348 (established)
```

**Evaluation metrics report**:
```bash
$ aq-report --section=evaluations
Agent Evaluation Report - 2026-03-20 15:30:45

Top Performing Agents:
  1. qwen-coder: score=0.94, tasks=156, success_rate=98.1%
  2. claude-architect: score=0.91, tasks=89, success_rate=96.6%
  3. codex-validator: score=0.87, tasks=234, success_rate=93.2%

Recent Evaluations:
  - [14:32] qwen-coder: task_001 (workflow planning) -> SUCCESS
  - [14:28] claude-architect: task_002 (architecture review) -> SUCCESS
  - [14:15] codex-validator: task_003 (code review) -> SUCCESS

Learning Metrics:
  Total Tasks Evaluated: 652
  Average Success Rate: 94.2%
  Recommendation Updates: 12 (last 24h)
```

## aq-hints Command

Get contextual hints and recommendations for workflows and operations.

### Usage

```bash
aq-hints --query "<query>" [options]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--query=<query>` | Query string (required) | N/A |
| `--format=json\|text` | Output format | `text` |
| `--limit=<N>` | Number of hints | `5` |
| `--context=<type>` | Context type | `auto` |
| `--verbose, -v` | Verbose output | off |

### Context Types

- `auto`: Auto-detect based on query
- `workflow`: Workflow execution hints
- `deployment`: Deployment operation hints
- `troubleshooting`: Troubleshooting guidance
- `performance`: Performance optimization hints
- `security`: Security best practices hints

### Examples

**Basic workflow hint**:
```bash
$ aq-hints --query "deploy configuration change"
Recommended Hints for: deploy configuration change

1. Prepare Configuration
   - Review changes: nixos-rebuild dry-build
   - Test configuration syntax
   - Back up current configuration

2. Deploy with Caution
   - Use switch not boot for immediate activation
   - Monitor logs: journalctl -u ai-hybrid-coordinator -f
   - Have rollback plan ready

3. Health Checks
   - Run: aq-report --section=services
   - Test API: curl http://localhost:8000/health
   - Verify database: psql -c "SELECT 1"

4. Common Issues
   - Service dependency failures -> check systemd status
   - Configuration validation errors -> review Nix syntax
   - Database connection issues -> verify credentials

Success Rate for This Operation: 97.2%
Learning History: 143 successful deployments
Estimated Execution Time: 5-10 minutes
```

**Troubleshooting hint, JSON format**:
```bash
$ aq-hints --query "dashboard slow to load" --format=json
{
  "query": "dashboard slow to load",
  "context": "troubleshooting",
  "hints": [
    {
      "rank": 1,
      "title": "Check Dashboard API Performance",
      "steps": [
        "curl http://localhost:8001/health",
        "curl http://localhost:8001/metrics | grep request_duration"
      ],
      "confidence": 0.94,
      "success_rate": 0.93
    },
    {
      "rank": 2,
      "title": "Analyze Frontend Performance",
      "steps": [
        "Check browser console for errors",
        "Monitor network tab for slow requests",
        "Verify React component rendering"
      ],
      "confidence": 0.87,
      "success_rate": 0.88
    }
  ],
  "learning_metrics": {
    "total_queries_similar": 34,
    "avg_resolution_time_minutes": 12.3,
    "success_rate": 0.91
  }
}
```

**Performance optimization hint**:
```bash
$ aq-hints --query "improve route search performance" --limit=3
Recommended Hints for: improve route search performance

1. Enable Route Caching (HIGH IMPACT)
   Configuration: /etc/ai-stack/performance-config.yml
   cache_enabled: true
   cache_ttl_seconds: 300
   Expected Improvement: 35% latency reduction
   Implementation Time: 5 minutes

2. Increase Parallelization Workers (MEDIUM IMPACT)
   Current: parallel_workers: 4
   Recommended: parallel_workers: 8
   Expected Improvement: 25% throughput increase
   Prerequisites: 8+ CPU cores

3. Optimize Query Patterns (MEDIUM IMPACT)
   - Review slow queries: psql EXPLAIN ANALYZE
   - Add database indexes for common filters
   - Consider query result pagination
   Expected Improvement: 15% latency reduction

Recommendation Confidence: 0.93
Based on: 156 similar optimization attempts
Average Time to Implement: 2.5 hours
```

## workflow Commands

Manage and execute AI workflows.

### workflow/plan

Create a structured execution plan for a workflow.

**Usage**:
```bash
workflow/plan --objective "<objective>" [options]
```

**Options**:
```
--objective=<text>    Workflow objective (required)
--max-depth=<N>       Max planning depth (default: 5)
--parallel=<N>        Max parallel tasks (default: 3)
--format=json|text    Output format (default: text)
--save-to=<file>      Save plan to file
```

**Example**:
```bash
$ workflow/plan --objective "deploy security patches to production"
Workflow Execution Plan
======================
Objective: deploy security patches to production
Generated: 2026-03-20 15:32:00

Phase 1: Preparation (Est. 15 min)
  [1.1] Review security advisories
  [1.2] Assess compatibility impact
  [1.3] Plan rollback strategy
  [1.4] Schedule maintenance window

Phase 2: Staging (Est. 30 min)
  [2.1] Download patches
  [2.2] Verify signatures
  [2.3] Create staging environment
  [2.4] Test patches in staging

Phase 3: Production Deployment (Est. 45 min)
  [3.1] Notify stakeholders
  [3.2] Create pre-deployment backup
  [3.3] Deploy patches (rolling update)
  [3.4] Monitor service health

Phase 4: Validation (Est. 20 min)
  [4.1] Run smoke tests
  [4.2] Verify all services operational
  [4.3] Collect metrics (baseline vs new)

Total Estimated Time: 110 minutes
Confidence Level: 0.96
Risk Assessment: MEDIUM
```

### workflow/run/start

Start execution of a workflow.

**Usage**:
```bash
workflow/run/start --plan-id "<id>" [options]
```

**Example**:
```bash
$ workflow/run/start --plan-id "plan_001_deploy_patches"
Starting Workflow Execution
===========================
Plan ID: plan_001_deploy_patches
Start Time: 2026-03-20 15:35:00
Execution ID: exec_0892_202603201535

Executing Phase 1: Preparation...
[✓] Review security advisories (completed in 3m 22s)
[✓] Assess compatibility impact (completed in 2m 11s)
[→] Plan rollback strategy (in progress...)

Use 'workflow/run/exec_0892_202603201535/status' for status updates
Use 'workflow/run/exec_0892_202603201535/hints' for runtime guidance
```

### workflow/run/<id>/status

Check workflow execution status.

**Usage**:
```bash
workflow/run/<id>/status [options]
```

**Example**:
```bash
$ workflow/run/exec_0892_202603201535/status
Workflow Execution Status
=========================
Execution ID: exec_0892_202603201535
Plan: deploy security patches to production
Status: IN PROGRESS
Progress: 42% (2 of 5 phases complete)
Elapsed Time: 34 minutes 12 seconds
Estimated Remaining: 45 minutes

Phase Summary:
  [✓] Phase 1: Preparation (15 min 22 sec)
  [✓] Phase 2: Staging (18 min 50 sec)
  [→] Phase 3: Production Deployment (in progress)
      - [✓] Notify stakeholders (2 min 11 sec)
      - [✓] Create pre-deployment backup (8 min 33 sec)
      - [→] Deploy patches (rolling update) - 8% complete
  [ ] Phase 4: Validation (pending)

No Errors Detected
Next Checkpoint: 2026-03-20 15:50:00
```

### workflow/run/<id>/hints

Get runtime hints for an active workflow.

**Usage**:
```bash
workflow/run/<id>/hints [options]
```

**Example**:
```bash
$ workflow/run/exec_0892_202603201535/hints
Runtime Hints for Active Workflow
==================================
Execution ID: exec_0892_202603201535

Current Phase: Phase 3: Production Deployment

💡 Hint 1: Monitor Service Health
   During rolling updates, watch:
   - Health check success rates (target: >99%)
   - API response latencies (p95 should be <1000ms)
   - Database connection pool usage (keep <80%)

   Check with: aq-report --section=performance

💡 Hint 2: Watch Deployment Progress
   Current node: nix-ai-prod-02/3
   Deployed: 1 of 3 nodes
   Expected time for this node: 12 minutes

   Watch logs: journalctl -u ai-hybrid-coordinator -f

⚠️  Hint 3: Prepare for Phase 4
   Smoke tests will begin soon
   Required: All services must respond to /health endpoint
   Typical duration: 15-20 minutes

Success Probability (at current checkpoint): 96.2%
Rollback Difficulty (if needed): EASY
Recommendation: Continue deployment
```

## Deployment Commands

### deploy

Deploy system configuration changes.

**Usage**:
```bash
deploy [options]
```

**Options**:
```
--dry-run            Show what would be deployed without applying
--no-rollback        Skip rollback configuration backup
--monitor            Monitor deployment and services post-deploy
--timeout=<seconds>  Deployment timeout (default: 600)
```

**Example**:
```bash
$ deploy --dry-run
Deployment Dry Run
==================
Configuration: /etc/nixos/configuration.nix
Changes Detected:
  - Updated ai-hybrid-coordinator service
  - Updated redis configuration
  - Added new security audit rules

Impact Analysis:
  - Services affected: 3
  - Required restarts: 2
  - Expected downtime: ~2 minutes
  - Data loss risk: NONE

Would deploy without errors. Use 'deploy --monitor' to proceed.
```

### rollback

Rollback to previous deployment.

**Usage**:
```bash
rollback [options]
```

**Options**:
```
--generation=<N>     Generation to rollback to
--dry-run            Preview rollback without applying
--verify             Verify rollback success post-execution
```

**Example**:
```bash
$ rollback --generation=prev --verify
Rollback to Previous Generation
================================
Current Generation: 42
Target Generation: 41
Timestamp: 2026-03-20 14:22:00

Changes to Revert:
  - ai-hybrid-coordinator service (downgrade)
  - redis configuration (revert)
  - security audit rules (remove)

Executing rollback...
[✓] Configuration reverted
[✓] Services restarted
[✓] Health checks passed

Verification Results:
  - All services online: ✓
  - Database connectivity: ✓
  - API responding: ✓
  - Cache operational: ✓

Rollback Successful! Generation 41 now active.
```

### status

Check deployment status.

**Usage**:
```bash
status [options]
```

**Example**:
```bash
$ status
Deployment Status
=================
Current Generation: 42
Current Configuration: /etc/nixos/configuration.nix
Build Status: SUCCESS
Last Deployment: 2026-03-20 14:22:00
Time Since Deployment: 1 hour 8 minutes

Service Status:
  ai-hybrid-coordinator: running (healthy)
  dashboard-api: running (healthy)
  dashboard-frontend: running (healthy)
  postgresql: running (healthy)
  redis: running (healthy)

Recent Generations:
  Gen 42 (current): deployed 2026-03-20 14:22:00
  Gen 41: deployed 2026-03-20 12:15:00
  Gen 40: deployed 2026-03-19 18:30:00

Available Actions:
  - deploy (to apply pending changes)
  - rollback (to previous generation)
  - aq-report (for detailed diagnostics)
```

## Testing Commands

### pytest

Run test suites.

**Usage**:
```bash
pytest [options] [test_pattern]
```

**Options**:
```
--coverage           Generate coverage report
--verbose, -v        Verbose output
--junit-xml=<file>   Export results as JUnit XML
--slow               Run slow tests (normally skipped)
--markers=<list>     Run specific test markers
```

**Example**:
```bash
$ pytest --coverage --markers="integration"
Running Integration Tests
==========================
Markers: integration
Coverage Enabled: true

Test Results:
  Passed: 89
  Failed: 0
  Skipped: 2
  Duration: 4m 32s

Coverage Report:
  Overall: 92.3%
  ai_hybrid_coordinator: 94.1%
  dashboard_api: 88.7%
  dashboard_frontend: 91.2%
  vector_database: 89.3%

Status: ALL TESTS PASSED ✓
```

### smoke-test

Run smoke tests for quick validation.

**Usage**:
```bash
smoke-test [options]
```

**Example**:
```bash
$ smoke-test
Running Smoke Tests
===================
Test Suite: Core Services

[✓] API Health Check (25ms)
[✓] Database Connectivity (45ms)
[✓] Redis Cache (12ms)
[✓] Vector Database (38ms)
[✓] Dashboard API (52ms)
[✓] Dashboard Frontend (87ms)

Overall: PASS
Duration: 259ms
Status: Ready for deployment
```

## Common Workflows

### Deploying a Configuration Change

**Step 1: Review Changes**
```bash
# Check what's changed
cd /etc/nixos
git diff

# Validate Nix syntax
nix-build configuration.nix -L
```

**Step 2: Plan Deployment**
```bash
# Create execution plan
workflow/plan --objective "deploy configuration change"

# Review plan
cat plan_*.json | jq '.'
```

**Step 3: Deploy with Monitoring**
```bash
# Get hints before deployment
aq-hints --query "deploy configuration change" --limit=5

# Deploy with monitoring
deploy --dry-run --monitor
deploy --monitor
```

**Step 4: Validate**
```bash
# Check status
aq-report --section=services
smoke-test

# If successful
echo "Deployment complete"
```

### Investigating a Deployment Failure

**Step 1: Gather Diagnostics**
```bash
# Generate full report
aq-report --format=json --output=report_$(date +%s).json

# Check service logs
journalctl -u ai-hybrid-coordinator -n 100
journalctl -u dashboard-api -n 100

# Check system metrics
aq-report --section=performance
```

**Step 2: Get Troubleshooting Hints**
```bash
# Get troubleshooting guidance
aq-hints --query "deployment failure" --context=troubleshooting
```

**Step 3: Root Cause Analysis**
```bash
# Check database connectivity
psql -h localhost -U aistack -d aistack -c "SELECT 1"

# Check cache
redis-cli ping

# Check vector database
curl http://localhost:6333/health
```

**Step 4: Resolution**
```bash
# Option 1: Fix configuration and redeploy
vim /etc/nixos/configuration.nix
deploy --dry-run

# Option 2: Rollback if needed
rollback --verify
```

### Running Diagnostics

**Comprehensive System Diagnostics**:
```bash
#!/bin/bash
echo "=== System Diagnostics ==="
aq-report --section=all --output=diagnostics_$(date +%s).json

echo "=== Service Status ==="
systemctl status ai-hybrid-coordinator dashboard-api dashboard-frontend postgresql redis

echo "=== Performance Metrics ==="
aq-report --section=performance

echo "=== Database Status ==="
psql -h localhost -U aistack -d aistack -c "SELECT * FROM pg_stat_activity;" | head -20

echo "=== Cache Status ==="
redis-cli INFO stats

echo "=== Vector Database Status ==="
curl -s http://localhost:6333/health | jq '.'

echo "=== Recent Logs ==="
journalctl -n 50 --no-pager
```

### Generating Status Reports

**Automated Status Report**:
```bash
#!/bin/bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="status_report_${TIMESTAMP}.json"

aq-report --section=all --format=json --output="$REPORT_FILE"

echo "Report generated: $REPORT_FILE"
echo "Key Metrics:"
jq '.services[] | {name, status, uptime_seconds}' "$REPORT_FILE"
jq '.cache' "$REPORT_FILE"
jq '.performance' "$REPORT_FILE"
```

---

**Document Version History**:
- v1.0 (2026-03-20): Initial CLI reference documentation

**Related Documentation**:
- [Production Deployment Guide](../deployment/production-deployment-guide.md)
- [Troubleshooting Runbooks](../operations/troubleshooting-runbooks.md)
- [Architecture Decisions](../architecture/architecture-decisions.md)
