# 43: Federated Learning Deployment

**Category**: Deployment & Operations
**Prerequisites**: [00-SYSTEM-OVERVIEW](00-SYSTEM-OVERVIEW.md), [22-CONTINUOUS-LEARNING](22-CONTINUOUS-LEARNING.md)
**Related**: [40-HYBRID-WORKFLOW](40-HYBRID-WORKFLOW.md), [41-VALUE-SCORING](41-VALUE-SCORING.md), [42-PATTERN-EXTRACTION](42-PATTERN-EXTRACTION.md)

---

## Overview

This guide explains how to deploy, operate, and maintain the federated continuous learning framework across multiple NixOS systems. The framework enables collective intelligence by sharing high-value learned patterns via git.

### What is Federated Learning?

In this system, "federated learning" means:
- **Multiple systems** run the same AI stack independently
- **High-value patterns** (value_score >= 0.7) are extracted locally
- **Patterns are shared** via git repository (`data/` directory)
- **All systems benefit** from collective knowledge
- **Privacy preserved** through anonymization and filtering

---

## Architecture

### Data Storage Model

```
┌─────────────────────────────────────────────────────────────┐
│                    LOCAL SYSTEM                             │
│                                                             │
│  Runtime Data (NOT in git):                                 │
│  ~/.local/share/nixos-ai-stack/                             │
│  ├── telemetry/                                             │
│  │   ├── aidb-events.jsonl        (all events)             │
│  │   └── hybrid-events.jsonl      (all events)             │
│  ├── fine-tuning/                                           │
│  │   └── dataset.jsonl            (all patterns)           │
│  └── dashboard/                                             │
│                                                             │
│  Federated Data (IN git):                                   │
│  data/                                                      │
│  ├── patterns/                    (value_score >= 0.7)     │
│  │   ├── skills-patterns.jsonl                             │
│  │   ├── error-solutions.jsonl                             │
│  │   └── best-practices.jsonl                              │
│  ├── fine-tuning/                                           │
│  │   └── snapshots/               (last 5 versions)        │
│  ├── collections/                                           │
│  │   └── snapshots/               (Qdrant exports)         │
│  ├── telemetry/                                             │
│  │   └── snapshots/               (last 1000 high-value)   │
│  └── metrics/                                               │
│      └── monthly/                 (aggregated stats)       │
└─────────────────────────────────────────────────────────────┘
```

### Federation Workflow

```
System A                    GitHub                    System B
--------                    ------                    --------
Runtime Data                                          Runtime Data
    ↓                                                      ↑
sync-learning-data.sh                          import-collections.sh
    ↓                                                      ↑
data/ directory  ----→  git push  ----→  git pull  ----→ data/ directory
```

---

## Core Commands

### Sync Learning Data

**Purpose**: Extract high-value patterns from runtime to git repo

```bash
bash scripts/sync-learning-data.sh
```

**What it does**:
1. Reads `~/.local/share/nixos-ai-stack/telemetry/hybrid-events.jsonl`
2. Filters events with `value_score >= 0.7`
3. Extracts patterns by category (skills, errors, best practices)
4. Deduplicates and sorts
5. Writes to `data/patterns/*.jsonl`
6. Creates versioned snapshot of fine-tuning dataset
7. Snapshots last 1000 high-value telemetry events

**When to run**: Hourly (cron) or after significant usage

**Output**:
```
🔄 Syncing federated learning data...
✓ Extracted 42 skills patterns (value_score >= 0.7)
✓ Extracted 18 error solutions
✓ Extracted 7 best practices
✓ Synced fine-tuning dataset (v12, 234 total patterns)
✓ Created telemetry snapshot (1000 events)
📊 Federation metrics updated
```

### Export Collections

**Purpose**: Export Qdrant collection contents to JSON

```bash
bash scripts/export-collections.sh
```

**What it does**:
1. Connects to Qdrant (http://localhost:6333)
2. Exports 3 federated collections:
   - `skills-patterns`
   - `error-solutions`
   - `best-practices`
3. Exports **payloads only** (no vectors to save space)
4. Creates timestamped snapshots in `data/collections/snapshots/`
5. Limits to 10,000 points per collection

**When to run**: Weekly (cron) or before major deployments

**Output**:
```
📦 Exporting Qdrant collections...
✓ Exported skills-patterns (42 points) → skills-patterns-20251221-203000.json
✓ Exported error-solutions (18 points) → error-solutions-20251221-203001.json
✓ Exported best-practices (7 points) → best-practices-20251221-203002.json
```

### Import Collections

**Purpose**: Import collection snapshots into Qdrant on new system

```bash
bash scripts/import-collections.sh
```

**What it does**:
1. Finds latest snapshot for each collection in `data/collections/snapshots/`
2. Ensures collection exists in Qdrant (creates if needed)
3. Imports points in batches of 100
4. Skips duplicates based on point ID

**When to run**:
- Automatically during `initialize-ai-stack.sh` (Step 10)
- Manually after pulling new federated data

**Output**:
```
📥 Importing Qdrant collections...
ℹ Found snapshot: data/collections/snapshots/skills-patterns-20251221-203000.json
✓ Imported 42 points to skills-patterns
✓ Imported 18 points to error-solutions
✓ Imported 7 points to best-practices
✓ Collection import complete
```

---

## Deployment Scenarios

### Scenario 1: First Deployment (System A)

**Situation**: You're setting up the AI stack for the first time.

#### Steps

1. **Clone repository**
```bash
git clone https://github.com/yourusername/NixOS-Dev-Quick-Deploy.git
cd NixOS-Dev-Quick-Deploy
```

2. **Run NixOS Quick Deploy**
```bash
sudo bash nixos-quick-deploy.sh
```

3. **Initialize AI Stack**
```bash
bash scripts/initialize-ai-stack.sh
```

Expected output at Step 10:
```
Step 10: Importing federated learning data
ℹ No federated snapshots found (this is normal for first deployment)
ℹ Future deployments will restore learned patterns from git
```

4. **Use the system**
- Interact with Open WebUI: http://localhost:3001
- Query AIDB endpoints
- Let hybrid coordinator capture telemetry

5. **After accumulating patterns** (hours to days of usage)
```bash
# Sync patterns to repo
bash scripts/sync-learning-data.sh

# Export collections
bash scripts/export-collections.sh

# Review what was federated
ls -lh data/patterns/
git diff data/
```

6. **Commit and share**
```bash
git add data/
git commit -m "Add initial federated patterns from System A

- 42 skills patterns (RAG queries, error handling)
- 18 error solutions (Qdrant, Podman issues)
- 7 best practices (deployment, monitoring)

Value score range: 0.72 - 0.94
Collection: $(date +%Y-%m-%d)"

git push origin main
```

**Result**: System A's learned patterns are now available for other systems! 🎉

---

### Scenario 2: Subsequent Deployment (System B)

**Situation**: You're deploying on a new machine, and System A has already contributed patterns.

#### Steps

1. **Clone repository** (includes System A's patterns!)
```bash
git clone https://github.com/yourusername/NixOS-Dev-Quick-Deploy.git
cd NixOS-Dev-Quick-Deploy

# Check federated data exists
ls -lh data/patterns/
# skills-patterns.jsonl (42 patterns from System A)
```

2. **Run NixOS Quick Deploy**
```bash
sudo bash nixos-quick-deploy.sh
```

3. **Initialize AI Stack**
```bash
bash scripts/initialize-ai-stack.sh
```

Expected output at Step 10:
```
Step 10: Importing federated learning data
ℹ Found 3 collection snapshot(s), importing...
✓ Imported 42 points to skills-patterns
✓ Imported 18 points to error-solutions
✓ Imported 7 points to best-practices
✓ Federated learning data imported
```

4. **Verify federation**
```bash
# Check Qdrant has points from System A
curl http://localhost:6333/collections/skills-patterns | jq '.result.points_count'
# Output: 42

# Query a pattern from System A
curl -X POST http://localhost:6333/collections/skills-patterns/points/scroll \
  -H "Content-Type: application/json" \
  -d '{"limit": 1, "with_payload": true, "with_vector": false}' | jq '.result.points[0]'
```

**Result**: System B starts with System A's collective knowledge! ✨

5. **Contribute back**

As System B accumulates its own patterns:
```bash
# Sync System B's new patterns
bash scripts/sync-learning-data.sh
bash scripts/export-collections.sh

# Commit
git add data/
git commit -m "Add patterns from System B - $(date +%Y-%m-%d)"
git push origin main
```

6. **Update System A with System B's patterns**

On System A:
```bash
git pull origin main
bash scripts/import-collections.sh
```

**Result**: Bidirectional federation! 🔄 Both systems now share each other's learned patterns.

---

### Scenario 3: Reinstallation (System A Redeployed)

**Situation**: You're reinstalling System A after hardware failure or OS reinstall.

#### Steps

1. **Clone repository**
```bash
git clone https://github.com/yourusername/NixOS-Dev-Quick-Deploy.git
cd NixOS-Dev-Quick-Deploy

# Pull latest (includes System A's old patterns + System B's contributions)
git pull origin main
```

2. **Redeploy**
```bash
sudo bash nixos-quick-deploy.sh
bash scripts/initialize-ai-stack.sh
```

Expected output:
```
Step 10: Importing federated learning data
ℹ Found 3 collection snapshot(s), importing...
✓ Imported 67 points to skills-patterns (42 from old System A + 25 from System B)
✓ Imported 31 points to error-solutions
✓ Imported 12 points to best-practices
✓ Federated learning data imported
```

**Result**: System A's old knowledge + System B's contributions restored! No data loss! 🛡️

---

## Automation

### Cron Jobs (Recommended)

Use templates from [scripts/cron-templates.sh](../../scripts/cron-templates.sh):

```bash
crontab -e
```

**Conservative schedule** (recommended for most users):
```cron
# Hourly: Sync patterns
0 * * * * bash /home/$USER/Documents/try/NixOS-Dev-Quick-Deploy/scripts/sync-learning-data.sh >> /var/log/federated-sync.log 2>&1

# Weekly (Sunday 2 AM): Export collections
0 2 * * 0 bash /home/$USER/Documents/try/NixOS-Dev-Quick-Deploy/scripts/export-collections.sh >> /var/log/federated-export.log 2>&1

# Every 5 minutes: Dashboard metrics
*/5 * * * * bash /home/$USER/Documents/try/NixOS-Dev-Quick-Deploy/scripts/generate-dashboard-data.sh >> /var/log/dashboard-metrics.log 2>&1
```

**Aggressive schedule** (active development):
```cron
# Every 15 minutes: Sync patterns
*/15 * * * * bash /path/to/scripts/sync-learning-data.sh

# Daily (3 AM): Export collections
0 3 * * * bash /path/to/scripts/export-collections.sh
```

**Automated git commits** (optional, use with caution):
```cron
# Every 6 hours: Auto-commit and push
0 */6 * * * cd /path/to/repo && bash scripts/sync-learning-data.sh && git add data/ && git commit -m "Auto-sync $(date +\%Y-\%m-\%d\ \%H:\%M)" && git push origin main
```

### Systemd Timers (Advanced)

See [scripts/cron-templates.sh](../../scripts/cron-templates.sh) for systemd unit file examples.

---

## Monitoring

### Check Federation Status

```bash
# Last sync timestamp
cat data/patterns/skills-patterns.jsonl | jq -r '.timestamp' | tail -1

# Pattern count by category
echo "Skills: $(wc -l < data/patterns/skills-patterns.jsonl)"
echo "Errors: $(wc -l < data/patterns/error-solutions.jsonl)"
echo "Best Practices: $(wc -l < data/patterns/best-practices.jsonl)"

# Average value score
cat data/patterns/skills-patterns.jsonl | jq -r '.value_score' | \
  awk '{sum+=$1; count++} END {printf "%.3f\n", sum/count}'

# data/ directory size
du -sh data/

# Collection point counts
curl -s http://localhost:6333/collections/skills-patterns | jq '.result.points_count'
curl -s http://localhost:6333/collections/error-solutions | jq '.result.points_count'
curl -s http://localhost:6333/collections/best-practices | jq '.result.points_count'
```

### View Sync Logs

```bash
# Real-time sync log
tail -f /var/log/federated-sync.log

# Recent sync history
tail -50 /var/log/federated-sync.log

# Export log
tail -f /var/log/federated-export.log
```

### Health Checks

```bash
# Check if patterns are accumulating
watch -n 60 'wc -l data/patterns/*.jsonl'

# Check if collections are growing
watch -n 300 'curl -s http://localhost:6333/collections | jq -r ".result.collections[] | select(.name | startswith(\"skills\")) | .points_count"'

# Check telemetry generation
tail -f ~/.local/share/nixos-ai-stack/telemetry/hybrid-events.jsonl
```

---

## Troubleshooting

### No Patterns Being Federated

**Symptoms**: `data/patterns/` is empty after running sync script

**Diagnosis**:
```bash
# Check if telemetry exists
ls -lh ~/.local/share/nixos-ai-stack/telemetry/hybrid-events.jsonl

# Check value scores
tail -100 ~/.local/share/nixos-ai-stack/telemetry/hybrid-events.jsonl | jq '.value_score'

# Count high-value events
tail -1000 ~/.local/share/nixos-ai-stack/telemetry/hybrid-events.jsonl | \
  jq -r '.value_score' | awk '$1 >= 0.7 {count++} END {print count}'

# Check pattern extraction
grep -c "pattern_extracted.*true" ~/.local/share/nixos-ai-stack/telemetry/hybrid-events.jsonl
```

**Solutions**:
1. **Not enough high-value interactions yet**
   - Use the system more
   - Wait for value_score >= 0.7 events

2. **Hybrid coordinator not running**
   ```bash
   cd ai-stack/compose
   podman-compose up -d hybrid-coordinator
   ```

3. **Pattern extraction disabled**
   - Check `PATTERN_EXTRACTION_ENABLED=true` in docker-compose.yml
   - Restart coordinator: `podman-compose restart hybrid-coordinator`

### Import Fails on New System

**Symptoms**: `import-collections.sh` reports errors

**Diagnosis**:
```bash
# Check Qdrant is running
curl http://localhost:6333/healthz

# Check snapshots exist
ls -lh data/collections/snapshots/

# Validate snapshot JSON
jq . data/collections/snapshots/skills-patterns-*.json | head -20
```

**Solutions**:
1. **Qdrant not running**
   ```bash
   cd ai-stack/compose
   podman-compose up -d qdrant
   ```

2. **Collections don't exist**
   ```bash
   bash scripts/initialize-qdrant-collections.sh
   ```

3. **Corrupt snapshots**
   - Delete corrupt file
   - Re-export from source system

### Data Directory Too Large

**Symptoms**: `data/` > 100MB, slow git operations

**Diagnosis**:
```bash
du -sh data/*
du -sh data/collections/snapshots/*
```

**Solutions**:
```bash
# Clean old snapshots (keep last 5 per collection)
cd data/fine-tuning/snapshots/
ls -t *.jsonl | tail -n +6 | xargs rm -f

cd data/collections/snapshots/
# 3 collections × 5 versions = keep last 15 files
ls -t *.json | tail -n +16 | xargs rm -f

# Verify vectors weren't exported (they shouldn't be)
grep -l '"vector":\s*\[' data/collections/snapshots/*.json
# Should return nothing

# Commit cleanup
git add data/
git commit -m "Clean old federation snapshots"
git push origin main
```

---

## Best Practices

### 1. Review Before Committing

Always inspect federated data before pushing:

```bash
git status
git diff data/

# Review new patterns
tail -20 data/patterns/skills-patterns.jsonl | jq .

# Check for sensitive data
grep -riE "api.*key|password|secret|token|192\.168\.|10\." data/
# Should return nothing
```

### 2. Document High-Value Commits

```bash
git commit -m "Add error-solution patterns for Qdrant issues

Patterns include:
- Connection refused errors (5 solutions)
- Port binding conflicts (3 solutions)
- Container network issues (4 solutions)

Source: System A production incidents
Value score range: 0.78 - 0.94
Date range: 2025-12-15 to 2025-12-21"
```

### 3. Monitor Data Quality

```bash
# Average value score should be >= 0.7
cat data/patterns/*.jsonl | jq -r '.value_score' | \
  awk '{sum+=$1; count++} END {printf "Average: %.3f\n", sum/count}'

# Check for duplicates
cat data/patterns/skills-patterns.jsonl | jq -r '.pattern_id' | \
  sort | uniq -d
# Should return nothing
```

### 4. Set Retention Policies

```bash
# Add to monthly cron job
# Keep last 90 days of telemetry snapshots
find data/telemetry/snapshots/ -name "*.jsonl" -mtime +90 -delete

# Keep last 10 fine-tuning snapshots
cd data/fine-tuning/snapshots/
ls -t *.jsonl | tail -n +11 | xargs rm -f

# Keep last 20 collection snapshots
cd data/collections/snapshots/
ls -t *.json | tail -n +21 | xargs rm -f
```

### 5. Use Branches for Experimentation

```bash
# Test new sync schedules on branch
git checkout -b experiment/hourly-sync

# Make changes, test thoroughly

# Merge if successful
git checkout main
git merge experiment/hourly-sync
```

### 6. Backup Before Major Operations

```bash
# Backup runtime data
tar -czf ~/backup-ai-stack-$(date +%Y%m%d).tar.gz \
  ~/.local/share/nixos-ai-stack/

# Backup federated data
cp -r data/ ~/backup-federated-$(date +%Y%m%d)/
```

---

## Integration with Existing Workflows

### With Dashboard Generation

Dashboard metrics include federation stats:

```bash
bash scripts/generate-dashboard-data.sh

# View federation metrics
cat ~/.local/share/nixos-system-dashboard/config.json | jq '.federation'
```

### With Health Monitoring

Use health-monitor MCP server to track federation:

```python
# Via MCP
result = mcp_client.call_tool(
    server="health-monitor",
    tool="get_dashboard_metrics",
    arguments={"filename": "config.json"}
)

federation_stats = result["federation"]
```

### With System Analysis

system-analysis skill includes federation checks:

```bash
# System analysis automatically reports:
# - Federated pattern counts
# - Last sync timestamp
# - Data directory size
# - Collection import status
```

---

## Advanced Topics

### Multi-Team Federation

For organizations with multiple teams:

```bash
# Separate federation repos per team
git submodule add https://github.com/team-a/federated-data data/team-a
git submodule add https://github.com/team-b/federated-data data/team-b

# Import from both
bash scripts/import-collections.sh data/team-a/collections/snapshots/
bash scripts/import-collections.sh data/team-b/collections/snapshots/
```

### Selective Federation

Filter what gets federated:

Edit `scripts/sync-learning-data.sh`:
```bash
# Only federate specific categories
jq -c 'select(.value_score >= 0.7 and .category == "error-solutions")' \
    "$source" >> "$dest"

# Only federate from specific agents
jq -c 'select(.value_score >= 0.7 and .agent_type == "coding-assistant")' \
    "$source" >> "$dest"
```

### Cross-Organization Federation

For public pattern sharing:

1. Create separate public federation repo
2. Export anonymized patterns (remove org-specific data)
3. Security review (no proprietary info)
4. Use as submodule

```bash
git submodule add https://github.com/public/nixos-patterns data/public
bash scripts/import-collections.sh data/public/collections/snapshots/
```

---

## Security Considerations

### Data Sanitization

Before committing, ensure:

```bash
# No API keys
grep -riE "api.*key|sk-[a-zA-Z0-9]{48}" data/

# No passwords
grep -riE "password|passwd|pwd" data/

# No private IPs
grep -riE "192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[0-1])\." data/

# No hostnames
grep -riE "$(hostname)" data/
```

### .gitignore Enforcement

Verify exclusions work:

```bash
# Runtime data should NOT be tracked
git status | grep ".local/share"
# Should return nothing

# Federated data SHOULD be tracked
git status | grep "data/"
# Should show modified files
```

### Access Control

For private federation repos:

```bash
# Use SSH keys (not HTTPS passwords)
git remote set-url origin git@github.com:yourusername/NixOS-Dev-Quick-Deploy.git

# Verify
git remote -v
```

---

## Summary

### Federation Checklist

**Initial Setup**:
- [x] Deploy AI stack with `initialize-ai-stack.sh`
- [x] Verify `data/` directory exists
- [x] Set up cron jobs for automation
- [x] Test manual sync: `bash scripts/sync-learning-data.sh`

**Daily Operations**:
- [x] System accumulates telemetry
- [x] High-value patterns extracted (value_score >= 0.7)
- [x] Sync script runs (manually or cron)
- [x] Review and commit federated data

**Weekly Operations**:
- [x] Export Qdrant collections
- [x] Review data/ size (should be < 50MB)
- [x] Push to remote
- [x] Pull on other systems

**Monthly Operations**:
- [x] Clean old snapshots
- [x] Audit for PII/secrets
- [x] Review data quality
- [x] Document high-value patterns

---

## Related Documentation

- [FEDERATED-DATA-STRATEGY.md](../../FEDERATED-DATA-STRATEGY.md) - Architecture decisions
- [22-CONTINUOUS-LEARNING.md](22-CONTINUOUS-LEARNING.md) - Value scoring algorithm
- [40-HYBRID-WORKFLOW.md](40-HYBRID-WORKFLOW.md) - Pattern extraction workflow
- [41-VALUE-SCORING.md](41-VALUE-SCORING.md) - How patterns are valued
- [42-PATTERN-EXTRACTION.md](42-PATTERN-EXTRACTION.md) - Pattern extraction details
- [scripts/cron-templates.sh](../../scripts/cron-templates.sh) - Automation examples

---

**Next Steps**: [90-COMPREHENSIVE-ANALYSIS.md](90-COMPREHENSIVE-ANALYSIS.md) - System health monitoring
