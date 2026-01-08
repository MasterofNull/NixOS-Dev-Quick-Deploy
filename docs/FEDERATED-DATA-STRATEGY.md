# Federated Continuous Learning Data Strategy

**Date**: 2025-12-21
**Issue**: Critical data (telemetry, fine-tuning, learned patterns) stored outside repo
**Impact**: Data loss, no federation, violates continuous learning framework
**Priority**: Critical

---

## Problem Statement

### Current Issues

1. **Data Outside Repo**:
   - Telemetry: `~/.local/share/nixos-ai-stack/telemetry/*.jsonl` (NOT in git)
   - Fine-tuning: `~/.local/share/nixos-ai-stack/fine-tuning/*.jsonl` (NOT in git)
   - Dashboard: `~/.local/share/nixos-system-dashboard/*.json` (NOT in git)
   - Skills: `.claude/skills/` → symlink to `~/.agent/skills` (NOT in git)

2. **Federation Failure**:
   - Learned patterns not shared across systems
   - Fine-tuning datasets not distributed
   - System-specific knowledge isolated
   - No collective intelligence

3. **Data Loss Risk**:
   - System reinstall = all learning lost
   - No backup strategy
   - No version control for learned data

4. **Violates Framework Principles**:
   - "Persistent and distributed AI stack"
   - "Continuous learning framework"
   - "Federation sync" (mentioned in hybrid coordinator)

---

## Proposed Solution: Federated Data Repository

### Architecture

```
NixOS-Dev-Quick-Deploy/
├── data/                           # NEW: Version-controlled learning data
│   ├── telemetry/                  # Aggregated telemetry (anonymized)
│   │   ├── .gitkeep
│   │   ├── README.md
│   │   └── snapshots/              # Periodic telemetry snapshots
│   │       ├── 2025-12-21.jsonl
│   │       └── latest.jsonl -> 2025-12-21.jsonl
│   ├── patterns/                   # Extracted high-value patterns
│   │   ├── .gitkeep
│   │   ├── README.md
│   │   ├── skills-patterns.jsonl  # Value score >= 0.7
│   │   ├── error-solutions.jsonl  # Proven solutions
│   │   └── best-practices.jsonl   # Endorsed practices
│   ├── fine-tuning/                # Fine-tuning datasets
│   │   ├── .gitkeep
│   │   ├── README.md
│   │   ├── dataset.jsonl          # Master dataset
│   │   └── snapshots/              # Versioned snapshots
│   │       ├── v1.0.0.jsonl
│   │       └── latest.jsonl -> v1.0.0.jsonl
│   ├── collections/                # Qdrant collection exports
│   │   ├── .gitkeep
│   │   ├── README.md
│   │   └── snapshots/
│   │       ├── codebase-context-2025-12-21.json
│   │       ├── skills-patterns-2025-12-21.json
│   │       └── ...
│   └── metrics/                    # Historical metrics for trend analysis
│       ├── .gitkeep
│       ├── README.md
│       └── monthly/
│           └── 2025-12.json
│
├── .gitignore                      # MODIFIED: Exclude raw telemetry, keep patterns
└── scripts/
    ├── sync-learning-data.sh       # NEW: Sync runtime → repo
    ├── export-collections.sh       # NEW: Export Qdrant → repo
    ├── import-collections.sh       # NEW: Import repo → Qdrant
    └── federate-sync.sh            # NEW: Sync across systems
```

---

## Implementation Plan

### Phase 1: Create Data Repository Structure

```bash
# Create versioned data directories in repo
mkdir -p data/{telemetry/snapshots,patterns,fine-tuning/snapshots,collections/snapshots,metrics/monthly}
```

### Phase 2: Data Sync Scripts

#### A. `sync-learning-data.sh` - Sync Runtime Data to Repo

**Purpose**: Copy high-value learning data from runtime locations to repo

```bash
#!/usr/bin/env bash
# Sync learning data from runtime to repo
# Filters for high-value patterns only

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DATA="${AI_STACK_DATA:-$HOME/.local/share/nixos-ai-stack}"
REPO_DATA="$REPO_ROOT/data"

# Extract high-value patterns (score >= 0.7)
extract_patterns() {
    local source="$RUNTIME_DATA/telemetry/hybrid-events.jsonl"
    local dest="$REPO_DATA/patterns/skills-patterns.jsonl"

    if [[ -f "$source" ]]; then
        # Extract only high-value interactions
        jq -c 'select(.value_score >= 0.7)' "$source" >> "$dest"
        # Deduplicate
        sort -u "$dest" -o "$dest"
    fi
}

# Sync fine-tuning dataset
sync_finetuning() {
    local source="$RUNTIME_DATA/fine-tuning/dataset.jsonl"
    local dest="$REPO_DATA/fine-tuning/dataset.jsonl"

    if [[ -f "$source" ]]; then
        cp "$source" "$dest"
        # Create versioned snapshot
        local version=$(date +%Y-%m-%d)
        cp "$source" "$REPO_DATA/fine-tuning/snapshots/${version}.jsonl"
    fi
}

# Create telemetry snapshot (last 1000 high-value events)
snapshot_telemetry() {
    local source="$RUNTIME_DATA/telemetry/hybrid-events.jsonl"
    local dest="$REPO_DATA/telemetry/snapshots/$(date +%Y-%m-%d).jsonl"

    if [[ -f "$source" ]]; then
        # Last 1000 high-value events only
        jq -c 'select(.value_score >= 0.7)' "$source" | tail -1000 > "$dest"
    fi
}

extract_patterns
sync_finetuning
snapshot_telemetry
```

#### B. `export-collections.sh` - Export Qdrant Collections

**Purpose**: Export learned patterns from Qdrant to repo

```bash
#!/usr/bin/env bash
# Export Qdrant collections to JSON for version control

QDRANT_URL="http://localhost:6333"
REPO_DATA="data/collections/snapshots"
DATE=$(date +%Y-%m-%d)

export_collection() {
    local collection=$1
    local output="$REPO_DATA/${collection}-${DATE}.json"

    # Export collection points
    curl -s "$QDRANT_URL/collections/$collection/points/scroll" \
        -H "Content-Type: application/json" \
        -d '{"limit": 10000, "with_payload": true, "with_vector": false}' \
        > "$output"

    echo "Exported $collection to $output"
}

# Export high-value collections only
export_collection "skills-patterns"
export_collection "error-solutions"
export_collection "best-practices"
```

#### C. `import-collections.sh` - Import Collections to Qdrant

**Purpose**: Restore learned patterns to new Qdrant instance

```bash
#!/usr/bin/env bash
# Import collection exports into Qdrant

QDRANT_URL="http://localhost:6333"
REPO_DATA="data/collections/snapshots"

import_collection() {
    local collection=$1
    local snapshot=$(ls -t $REPO_DATA/${collection}-*.json 2>/dev/null | head -1)

    if [[ -f "$snapshot" ]]; then
        echo "Importing $collection from $snapshot"

        # Extract points and upload
        jq -c '.result.points[]' "$snapshot" | while read point; do
            curl -s -X PUT "$QDRANT_URL/collections/$collection/points" \
                -H "Content-Type: application/json" \
                -d "{\"points\": [$point]}"
        done
    fi
}

import_collection "skills-patterns"
import_collection "error-solutions"
import_collection "best-practices"
```

### Phase 3: Federated Sync Script

#### `federate-sync.sh` - Sync Across Systems

**Purpose**: Pull learned patterns from other systems, merge, and push

```bash
#!/usr/bin/env bash
# Federated learning data sync across systems

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_REPOS=(
    # Add other system repo URLs here
    # "git@github.com:user/other-system-learning.git"
)

# Pull latest from origin
git pull origin main

# Merge patterns from other systems (if configured)
for remote in "${REMOTE_REPOS[@]}"; do
    echo "Syncing from $remote"
    # Implementation for cross-system sync
done

# Commit new learnings
if [[ -n $(git status --porcelain data/) ]]; then
    git add data/
    git commit -m "Sync learned patterns $(date +%Y-%m-%d)"
    git push origin main
fi
```

---

## Data Privacy & Size Management

### What to Store in Git

✅ **DO Store**:
- High-value patterns (value_score >= 0.7)
- Anonymized error solutions
- Best practices (no system-specific data)
- Fine-tuning datasets (reviewed for sensitivity)
- Collection exports (excluding raw telemetry)
- Aggregated metrics (no PII)

❌ **DON'T Store**:
- Raw telemetry (too large, may contain PII)
- System-specific configurations
- API keys or secrets
- Full conversation logs
- Dashboard JSON snapshots (regenerate on each system)

### Size Limits

- **Telemetry Snapshots**: Last 1000 high-value events only
- **Patterns**: Deduplicated, max 10MB per file
- **Fine-tuning**: Versioned snapshots, keep last 5 versions
- **Collections**: Vector-less exports (payloads only)

### .gitignore Updates

```gitignore
# Runtime data (not for federation)
.local/
**/telemetry/aidb-events.jsonl
**/telemetry/hybrid-events.jsonl

# Keep pattern extracts
!data/patterns/
!data/fine-tuning/
!data/collections/

# Dashboard data (regenerate on each system)
**/.local/share/nixos-system-dashboard/

# Large files
*.jsonl.bak
*.jsonl.tmp
```

---

## Integration with Existing System

### Modified docker-compose.yml

```yaml
hybrid-coordinator:
  volumes:
    # Runtime data
    - ${AI_STACK_DATA:-~/.local/share/nixos-ai-stack}/hybrid-coordinator:/data:Z
    - ${AI_STACK_DATA:-~/.local/share/nixos-ai-stack}/telemetry:/data/telemetry:Z
    - ${AI_STACK_DATA:-~/.local/share/nixos-ai-stack}/fine-tuning:/data/fine-tuning:Z

    # Federated learning data (in repo)
    - ${PROJECT_ROOT}/data/patterns:/data/patterns:ro  # Read-only access to shared patterns
    - ${PROJECT_ROOT}/data/collections:/data/collections:ro
```

### Modified Hybrid Coordinator

Add federation sync capability:

```python
# In hybrid coordinator
def sync_federated_patterns():
    """Load shared patterns from repo into Qdrant"""
    patterns_dir = Path("/data/patterns")

    for pattern_file in patterns_dir.glob("*.jsonl"):
        with open(pattern_file) as f:
            for line in f:
                pattern = json.loads(line)
                if pattern.get("value_score", 0) >= 0.7:
                    # Insert into Qdrant
                    qdrant_client.upsert(
                        collection_name="skills-patterns",
                        points=[pattern]
                    )
```

---

## Deployment Workflow

### Initial Setup (New System)

```bash
# 1. Clone repo with learning data
git clone <repo-url>
cd NixOS-Dev-Quick-Deploy

# 2. Initialize AI stack
bash scripts/initialize-ai-stack.sh

# 3. Import federated patterns
bash scripts/import-collections.sh

# 4. System now has collective intelligence from all federated systems
```

### Daily Operations

```bash
# 1. System learns during operation (telemetry logged)

# 2. Periodic sync (cron job)
0 */6 * * * bash /path/to/scripts/sync-learning-data.sh

# 3. Weekly export to repo
0 0 * * 0 bash /path/to/scripts/export-collections.sh

# 4. Monthly federation sync
0 0 1 * * bash /path/to/scripts/federate-sync.sh
```

### Before System Reinstall

```bash
# Export all learned data
bash scripts/export-collections.sh
bash scripts/sync-learning-data.sh

# Commit to repo
git add data/
git commit -m "Backup learned data before reinstall"
git push
```

### After System Reinstall

```bash
# Restore learned data
git pull
bash scripts/import-collections.sh
# All learning restored!
```

---

## Benefits

### ✅ Federation Achieved

- Learned patterns shared across ALL systems
- Collective intelligence grows
- Error solutions benefit everyone
- Best practices propagate automatically

### ✅ Data Persistence

- Learning survives system reinstalls
- Version-controlled knowledge base
- Historical trend analysis possible
- Disaster recovery built-in

### ✅ Continuous Improvement

- Patterns refined across systems
- Fine-tuning datasets grow collectively
- System gets smarter over time
- Knowledge compounds

---

## Metrics to Track

### Federation Health

```json
{
  "federation_sync_last": "2025-12-21T20:00:00Z",
  "total_systems": 3,
  "patterns_federated": 1234,
  "fine_tuning_samples": 5678,
  "collective_learning_rate": 0.15
}
```

### Data Growth

- Patterns per week
- Fine-tuning dataset size
- Cross-system pattern adoption rate
- Value score distribution

---

## Next Steps

1. **Create data/ directory structure**
2. **Implement sync-learning-data.sh**
3. **Implement export-collections.sh**
4. **Implement import-collections.sh**
5. **Update .gitignore**
6. **Test full cycle**
7. **Document federation protocol**
8. **Set up cron jobs**

---

## Security Considerations

### Data Sanitization

Before committing to git:
- Remove API keys
- Remove system-specific paths
- Remove PII
- Anonymize hostnames/IPs
- Review error messages for secrets

### Access Control

- Private repo for organization learning
- Public repo for community patterns (reviewed)
- Separate repos for sensitive vs. public data

---

This strategy transforms isolated system learning into true federated continuous learning!
