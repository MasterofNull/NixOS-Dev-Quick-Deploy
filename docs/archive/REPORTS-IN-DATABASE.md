# Reports in Database - Not in Repo

**Date**: 2026-01-01
**Purpose**: Store deployment reports in PostgreSQL instead of cluttering repo with markdown files
**Status**: Implemented

## Problem

We were creating too many markdown report files in the repo root:
- `*-SUMMARY.md`
- `*-COMPLETE.md`
- `*-FIX.md`
- `*-IMPLEMENTATION.md`
- `*-DEPLOYMENT.md`
- etc.

**Issues**:
1. Repo cluttered with 50+ report files
2. Hard to distinguish system docs from session reports
3. No metadata or search capabilities
4. Version control noise (reports change frequently)
5. Difficult to filter or query reports
6. Wastes time cleaning up later

## Solution

**Store reports in PostgreSQL database** with proper metadata, search, and categorization.

### Database Table: `deployment_reports`

Located in: [ai-stack/postgres/init-schema.sql](../ai-stack/postgres/init-schema.sql)

**Schema**:
```sql
CREATE TABLE deployment_reports (
    id UUID PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    report_type VARCHAR(50) NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deployment_id UUID,  -- Links to deployments table
    tags TEXT[],
    category VARCHAR(100),
    is_archived BOOLEAN DEFAULT FALSE,
    search_vector tsvector  -- Full-text search
);
```

**Report Types**:
- `deployment` - Deployment reports
- `fix` - Bug fixes and corrections
- `upgrade` - System upgrades and migrations
- `error` - Error reports and debugging
- `debug` - Debug sessions
- `summary` - Session summaries
- `session` - General session logs

## Usage

### Store a Report (In Scripts)

```bash
source scripts/lib/report-to-database.sh

# Simple report
store_report \
    "PyTorch CPU-Only Fix" \
    "$(cat PYTORCH-FIX.md)" \
    "fix" \
    '{"issue": "CUDA packages downloading", "component": "aidb"}'

# Deployment report
store_deployment_report \
    "System Deployment 2026-01-01" \
    "Full deployment completed successfully..." \
    '{"duration": "45min", "phase": "complete"}'

# Fix report with metadata
store_fix_report \
    "Container Port Conflict Fix" \
    "Fixed port 8091 conflict..." \
    "port_conflict" \
    '{"affected_containers": ["aidb", "coordinator"]}'

# Upgrade report
store_upgrade_report \
    "PyTorch 2.9.1 to 2.5.1" \
    "Downgraded PyTorch..." \
    "2.9.1" \
    "2.5.1" \
    '{"reason": "CUDA dependencies issue"}'
```

### Query Reports

```bash
# View recent reports
./scripts/lib/report-to-database.sh get_reports

# View reports by type
./scripts/lib/report-to-database.sh get_reports "fix" 20

# Search reports
./scripts/lib/report-to-database.sh search_reports "pytorch cuda"

# Get specific report
./scripts/lib/report-to-database.sh get_report_by_id "abc-123-..."
```

### SQL Queries

```sql
-- Recent reports
SELECT id, title, report_type, created_at
FROM deployment_reports
ORDER BY created_at DESC
LIMIT 10;

-- Search by keyword
SELECT title, report_type, created_at
FROM deployment_reports
WHERE search_vector @@ plainto_tsquery('english', 'pytorch cuda')
ORDER BY created_at DESC;

-- Reports by type
SELECT title, metadata->>'issue' as issue, created_at
FROM deployment_reports
WHERE report_type = 'fix'
ORDER BY created_at DESC;

-- Reports with specific metadata
SELECT title, metadata, created_at
FROM deployment_reports
WHERE metadata->>'component' = 'aidb'
ORDER BY created_at DESC;
```

## Metadata Best Practices

Always include metadata to distinguish reports from system documentation:

```json
{
  "report_type": "fix",
  "issue_fixed": "cuda_dependencies",
  "components": ["aidb", "pytorch"],
  "severity": "high",
  "packages_changed": ["torch==2.5.1"],
  "files_modified": ["Dockerfile", "requirements.txt"],
  "automated": false,
  "session_id": "2026-01-01-abc123",
  "related_reports": ["uuid1", "uuid2"]
}
```

**Why metadata matters**:
- Prevents confusion when system attributes change
- Enables filtering by component, severity, etc.
- Links related reports together
- Tracks automation vs manual fixes
- Preserves context for future reference

## Migration

### Migrate Existing Reports to Database

```bash
# Step 1: Migrate all report files
./scripts/migrate-reports-to-database.sh

# Step 2: Verify in database
psql -h localhost -U mcp -d mcp -c "
SELECT title, report_type, created_at
FROM deployment_reports
ORDER BY created_at DESC
LIMIT 10;
"

# Step 3: Clean up migrated files (AFTER verifying)
./scripts/cleanup-migrated-reports.sh
```

### What Gets Migrated

**YES** (migrated to database):
- `*-SUMMARY.md`
- `*-COMPLETE.md`
- `*-FIX.md`, `*-FIXES.md`
- `*-IMPLEMENTATION.md`
- `*-UPGRADE.md`
- `*-DEPLOYMENT.md`
- `*-SESSION.md`
- `*-ERROR.md`
- `*-DEBUG.md`
- `*-CONTAINER-*.md`

**NO** (kept in repo):
- `README.md`
- `CONTRIBUTING.md`
- `LICENSE.md`
- `docs/**/*.md` (system documentation)
- `ai-stack/*/README.md` (component docs)
- Architecture/design docs in `docs/`

## .gitignore Configuration

The [.gitignore](../.gitignore) now prevents report files from being committed:

```gitignore
# Reports and Session Logs (stored in database, not repo)
*-SUMMARY*.md
*-COMPLETE*.md
*-FIX*.md
*-IMPLEMENTATION*.md
*-UPGRADE*.md
*-DEPLOYMENT*.md
*-SESSION*.md
# ... etc ...

# Exception: Keep README and core documentation
!README.md
!CONTRIBUTING.md
!LICENSE.md
```

## Fallback Behavior

If the database is not available, reports are saved to `.reports/` directory:

```
.reports/
  deployment/
    system-deployment-20260101-143022.md
  fix/
    pytorch-fix-20260101-150033.md
  session/
    work-session-20260101-160044.md
```

These can be migrated to database later when it's available.

## Default Behavior Going Forward

### For Scripts

All scripts that generate reports should use the database:

```bash
#!/usr/bin/env bash
source "$(dirname "$0")/lib/report-to-database.sh"

# Do work...
work_output="..."

# Store report
store_report \
    "My Work Title" \
    "$work_output" \
    "session" \
    '{"script": "my-script.sh", "duration": "5min"}'
```

### For Agents

When agents create reports, they should:
1. Use `store_report` function if in bash script
2. Or write to `.reports/` and it will be migrated automatically
3. Include comprehensive metadata in JSON format

**Example agent metadata**:
```json
{
  "agent_type": "claude-sonnet-4.5",
  "session_id": "abc123",
  "task_type": "fix",
  "components_modified": ["aidb", "docker-compose"],
  "issue_severity": "high",
  "human_verified": false,
  "related_issues": ["port_conflict", "cuda_dependencies"],
  "packages_before": {"torch": "2.9.1"},
  "packages_after": {"torch": "2.5.1"},
  "automated_fix": true
}
```

## Querying Reports

### By Component

```sql
SELECT title, created_at
FROM deployment_reports
WHERE metadata->'components' ? 'aidb'
ORDER BY created_at DESC;
```

### By Severity

```sql
SELECT title, metadata->>'severity' as severity, created_at
FROM deployment_reports
WHERE metadata->>'severity' IN ('high', 'critical')
ORDER BY created_at DESC;
```

### By Session

```sql
SELECT title, report_type, created_at
FROM deployment_reports
WHERE metadata->>'session_id' = '2026-01-01-abc123'
ORDER BY created_at;
```

### Related Reports

```sql
-- Find all reports related to a specific issue
WITH RECURSIVE related AS (
  -- Start with a specific report
  SELECT id, title, metadata
  FROM deployment_reports
  WHERE title = 'PyTorch CPU-Only Fix'

  UNION

  -- Find reports referenced in metadata
  SELECT r.id, r.title, r.metadata
  FROM deployment_reports r
  INNER JOIN related rel ON
    r.id::text = ANY(
      SELECT jsonb_array_elements_text(rel.metadata->'related_reports')
    )
)
SELECT title, metadata->>'issue_fixed' as issue
FROM related;
```

## Archival

Old reports can be archived instead of deleted:

```sql
-- Archive reports older than 90 days
UPDATE deployment_reports
SET is_archived = TRUE, archived_at = NOW()
WHERE created_at < NOW() - INTERVAL '90 days'
AND report_type IN ('session', 'debug');

-- Search only active reports
SELECT title, created_at
FROM deployment_reports
WHERE is_archived = FALSE
ORDER BY created_at DESC;
```

## Benefits

### Before (Markdown Files in Repo)

❌ 50+ files cluttering repo root
❌ No search or filtering
❌ No metadata or categorization
❌ Version control noise
❌ Manual cleanup required
❌ Hard to find related reports
❌ No automation possible

### After (PostgreSQL Database)

✅ Clean repo (only system docs)
✅ Full-text search
✅ Rich metadata and tagging
✅ No version control noise
✅ Automatic archival
✅ Query related reports
✅ Integrate with automation

## Future Enhancements

1. **Web UI** - View/search reports via dashboard
2. **Auto-tagging** - AI extracts tags from content
3. **Report templates** - Standardized report formats
4. **Slack integration** - Post reports to Slack
5. **Email summaries** - Daily/weekly report digests
6. **Trend analysis** - Common issues over time
7. **Knowledge extraction** - Build knowledge base from reports

## Example Workflow

### Agent Session

```bash
#!/usr/bin/env bash
source scripts/lib/report-to-database.sh

SESSION_ID="$(uuidgen)"

# Start session
store_report \
    "Session Started: Fix PyTorch Issues" \
    "Starting work on CUDA dependency issues..." \
    "session" \
    "{\"session_id\": \"$SESSION_ID\", \"status\": \"started\"}"

# Work...

# Store fixes
store_fix_report \
    "Fixed PyTorch CUDA Dependencies" \
    "Changed torch version from 2.9.1 to 2.5.1..." \
    "cuda_dependencies" \
    "{\"session_id\": \"$SESSION_ID\", \"component\": \"aidb\"}"

# End session
store_report \
    "Session Complete" \
    "Successfully resolved all PyTorch issues..." \
    "session" \
    "{\"session_id\": \"$SESSION_ID\", \"status\": \"complete\", \"duration\": \"2h\"}"
```

## Summary

- ✅ Reports stored in PostgreSQL, not repo
- ✅ Metadata prevents confusion
- ✅ Full-text search enabled
- ✅ Auto-archival after 90 days
- ✅ Clean repo structure
- ✅ Easy to query and filter
- ✅ Integration ready

**Documentation**: This file stays in `docs/` because it's system documentation, not a session report.

**Location**: [docs/REPORTS-IN-DATABASE.md](../docs/REPORTS-IN-DATABASE.md)
