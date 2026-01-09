# Issue Tracking System - User Guide

**Purpose**: Track production errors, analyze patterns, and identify system improvements to prevent recurring issues.

---

## 🎯 Quick Start

### Record an Issue

```bash
# Basic issue
./scripts/record-issue.py \
  "Integration tests failed" \
  "P1 integration tests failed during deployment" \
  --severity high \
  --category integration \
  --component p1-integration

# With error details and suggested fixes
./scripts/record-issue.py \
  "Database connection timeout" \
  "PostgreSQL connection timed out after 30 seconds" \
  --severity critical \
  --category reliability \
  --component aidb \
  --error "connection timeout after 30s" \
  --error-type "ConnectionTimeout" \
  --fix "Increase connection pool size" \
  --fix "Add connection retry logic" \
  --change "Implement connection health checks" \
  --tag database --tag timeout
```

### List Issues

```bash
# List open issues
./scripts/list-issues.py

# List all issues (including resolved)
./scripts/list-issues.py --all

# List critical issues only
./scripts/list-issues.py --severity critical

# List security issues
./scripts/list-issues.py --category security

# List issues for specific component
./scripts/list-issues.py --component aidb
```

### Analyze Patterns

```bash
# Analyze issue patterns and get improvement suggestions
./scripts/analyze-issues.py
```

---

## 📊 Features

### 1. Issue Tracking
- **Severity Levels**: critical, high, medium, low, info
- **Categories**: security, performance, reliability, data_integrity, configuration, deployment, integration, validation, monitoring, other
- **Status Tracking**: open, investigating, in_progress, resolved, wont_fix, duplicate
- **Deduplication**: Automatically groups duplicate errors
- **Occurrence Counting**: Tracks how many times each issue occurs

### 2. Pattern Analysis
- Identifies most common errors
- Finds most affected components
- Breaks down issues by category
- Tracks trends over time (7-day window)

### 3. System Improvement Suggestions
- Analyzes patterns to suggest fixes
- Prioritizes suggestions (high/medium/low)
- Recommends system changes to prevent recurrence

### 4. Prometheus Metrics
- `aidb_issues_created_total` - Issues created by severity/category/component
- `aidb_issues_resolved_total` - Issues resolved by severity/category
- `aidb_issue_resolution_seconds` - Time to resolve issues
- `aidb_active_issues` - Current active issues by severity/category

---

## 📋 Issue Severities

| Severity | Description | Examples |
|----------|-------------|----------|
| **Critical** | System down, data loss | Database corruption, service crash |
| **High** | Major functionality broken | Authentication failure, API timeout |
| **Medium** | Minor functionality broken | Validation error, logging failure |
| **Low** | Cosmetic, documentation | UI glitch, typo in docs |
| **Info** | Informational | Configuration change, deployment note |

---

## 📂 Issue Categories

| Category | Description | Examples |
|----------|-------------|----------|
| **Security** | Security vulnerabilities | XSS, SQL injection, auth bypass |
| **Performance** | Performance degradation | Slow queries, high CPU |
| **Reliability** | Crashes, timeouts, errors | Service crash, timeout |
| **Data Integrity** | Data corruption, inconsistency | Orphaned records, duplicate data |
| **Configuration** | Configuration errors | Invalid config, missing env var |
| **Deployment** | Deployment failures | Build failure, rollout error |
| **Integration** | Integration failures | API integration broken, test failure |
| **Validation** | Input validation failures | Invalid input accepted |
| **Monitoring** | Monitoring/alerting issues | Metric not collected, alert not firing |
| **Other** | Uncategorized | Misc issues |

---

## 🔧 CLI Reference

### record-issue.py

**Required Arguments:**
- `title` - Short issue summary
- `description` - Detailed description
- `--component` - Component where issue occurred

**Optional Arguments:**
- `--severity` - critical, high, medium, low, info (default: medium)
- `--category` - Category (default: other)
- `--error` - Error message
- `--error-type` - Error type (e.g., ValueError)
- `--stack-trace` - Full stack trace
- `--fix` - Suggested fix (can use multiple times)
- `--change` - System change needed (can use multiple times)
- `--tag` - Tag for categorization (can use multiple times)
- `--context` - Additional context (JSON string)

**Database Options:**
- `--db-host` - Database host (default: localhost)
- `--db-port` - Database port (default: 5432)
- `--db-name` - Database name (default: aidb)
- `--db-user` - Database user (default: aidb)
- `--db-password` - Database password

### list-issues.py

**Options:**
- `--all` - List all issues (including resolved)
- `--status` - Filter by status (open, investigating, in_progress, resolved, wont_fix, duplicate)
- `--severity` - Filter by severity
- `--category` - Filter by category
- `--component` - Filter by component
- `--limit` - Limit results (default: 50)

### analyze-issues.py

**Options:**
- (Same database options as above)

**Output:**
- Statistics (total, open, critical issues)
- Most common errors
- Most affected components
- Category breakdown
- System improvement suggestions

---

## 💡 Examples

### Example 1: Record P1 Integration Failure

```bash
./scripts/record-issue.py \
  "P1 integration tests failed during deployment" \
  "Multiple integration tests failed when deploying P1 features. Tests for query validation, GC, and Let's Encrypt all failed." \
  --severity high \
  --category integration \
  --component p1-integration \
  --error "Integration tests returned non-zero exit code" \
  --error-type "TestFailure" \
  --fix "Verify database is running and accessible" \
  --fix "Check that all required services are started" \
  --fix "Review test environment configuration" \
  --change "Add pre-deployment validation" \
  --change "Improve test environment setup automation" \
  --change "Add integration test monitoring to CI/CD" \
  --tag deployment --tag p1 --tag tests
```

### Example 2: Record Database Connection Issue

```bash
./scripts/record-issue.py \
  "AIDB failed to connect to PostgreSQL" \
  "AIDB server could not establish connection to PostgreSQL database. Service started but all queries failed." \
  --severity critical \
  --category reliability \
  --component aidb \
  --error "could not connect to server: Connection refused" \
  --error-type "ConnectionRefusedError" \
  --fix "Verify PostgreSQL is running" \
  --fix "Check connection pool configuration" \
  --fix "Verify database credentials" \
  --change "Add database connection health checks on startup" \
  --change "Implement exponential backoff retry logic" \
  --change "Add connection pool monitoring"
```

### Example 3: Record Certificate Renewal Failure

```bash
./scripts/record-issue.py \
  "Let's Encrypt certificate renewal failed" \
  "Systemd timer triggered renewal but certbot failed with ACME challenge error" \
  --severity high \
  --category security \
  --component letsencrypt \
  --error "ACME challenge failed: Connection refused" \
  --error-type "ACMEChallengeError" \
  --fix "Verify nginx is serving /.well-known/acme-challenge/" \
  --fix "Check that port 80 is accessible" \
  --fix "Verify webroot directory exists and is mounted" \
  --change "Add ACME challenge validation before renewal" \
  --change "Implement alerting for renewal failures" \
  --tag tls --tag certificate --tag renewal
```

---

## 🔍 Pattern Analysis Example

After recording several issues, run analysis:

```bash
./scripts/analyze-issues.py
```

**Example Output:**

```
📊 ISSUE PATTERN ANALYSIS (Last 7 Days)

📈 Statistics:
   Total issues: 15
   Open issues: 12
   Critical issues: 3
   High priority issues: 5
   Total occurrences: 47

🔥 Most Common Errors:
   1. ConnectionTimeout in aidb
      Count: 5 issues, 23 occurrences
   2. ValidationError in query_validator
      Count: 3 issues, 12 occurrences

🎯 Most Affected Components:
   1. aidb
      Issues: 8, Occurrences: 30
   2. p1-integration
      Issues: 4, Occurrences: 10

💡 SYSTEM IMPROVEMENT SUGGESTIONS

🔴 HIGH PRIORITY:
   1. High frequency of ConnectionTimeout in aidb
      → Add specific error handling for ConnectionTimeout in aidb
      Occurrences: 23

🟡 MEDIUM PRIORITY:
   1. Component aidb has 8 different issues
      → Review aidb for reliability improvements
      Issues: 8
```

---

## 🗃️ Database Schema

Issues are stored in PostgreSQL with the following schema:

```sql
CREATE TABLE issues (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    severity TEXT NOT NULL,
    category TEXT NOT NULL,
    component TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    error_type TEXT,
    stack_trace TEXT,
    error_hash TEXT,              -- For deduplication
    context JSONB,
    affected_users INTEGER,
    occurrence_count INTEGER,
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    resolution TEXT,
    resolved_at TIMESTAMPTZ,
    resolved_by TEXT,
    related_issues JSONB,
    tags JSONB,
    suggested_fixes JSONB,
    system_changes_needed JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);
```

---

## 🔗 Integration with Monitoring

The issue tracker exports Prometheus metrics that can be visualized in Grafana:

**Grafana Dashboard Queries:**

```promql
# Active issues by severity
sum by (severity) (aidb_active_issues)

# Issue creation rate
rate(aidb_issues_created_total[5m])

# Average resolution time
rate(aidb_issue_resolution_seconds_sum[1h]) / rate(aidb_issue_resolution_seconds_count[1h])
```

---

## 🎯 Best Practices

### When to Record Issues

**DO record:**
- ✅ Production errors and exceptions
- ✅ Deployment failures
- ✅ Integration test failures
- ✅ Security incidents
- ✅ Performance degradations
- ✅ Data integrity issues

**DON'T record:**
- ❌ Expected user errors (e.g., invalid login)
- ❌ Transient network blips
- ❌ Normal operational events
- ❌ Development/testing issues (unless systemic)

### Writing Good Issue Descriptions

**Good:**
```
Title: "Integration tests failed during P1 deployment"
Description: "When deploying P1 features, 5 out of 22 integration tests
failed with database connection errors. The aidb service was running but
could not connect to PostgreSQL. This blocked the deployment."
```

**Bad:**
```
Title: "Tests failed"
Description: "Some tests didn't work"
```

### Suggesting Fixes

Be specific and actionable:

**Good:**
- ✅ "Increase PostgreSQL connection pool size from 10 to 20"
- ✅ "Add connection retry logic with exponential backoff"
- ✅ "Implement health check endpoint for database connectivity"

**Bad:**
- ❌ "Fix the database"
- ❌ "Make it work better"
- ❌ "Investigate later"

---

## 📚 Related Documentation

- **P1 Integration**: [P1-INTEGRATION-COMPLETE.md](../P1-INTEGRATION-COMPLETE.md)
- **Deployment Guide**: [P1-DEPLOYMENT-GUIDE.md](P1-DEPLOYMENT-GUIDE.md)
- **Issue Tracker Source**: [../ai-stack/mcp-servers/aidb/issue_tracker.py](../ai-stack/mcp-servers/aidb/issue_tracker.py)

---

## 🆘 Troubleshooting

### "Failed to connect to database"

**Solution**: Verify PostgreSQL is running and credentials are correct:

```bash
# Check PostgreSQL is running
podman ps | grep postgres

# Test connection
psql -h localhost -U aidb -d aidb -c "SELECT 1"

# Use custom credentials
./scripts/record-issue.py "Title" "Description" \
  --db-host your-host \
  --db-user your-user \
  --db-password your-password
```

### "Table 'issues' does not exist"

**Solution**: The schema is created automatically on first run. If it fails:

```bash
# Manually create schema
psql -h localhost -U aidb -d aidb -f ai-stack/mcp-servers/aidb/issue_tracker_schema.sql
```

---

**Created**: 2026-01-08
**Last Updated**: 2026-01-08
**Version**: 1.0
