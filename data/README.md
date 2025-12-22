# Federated Learning Data Repository

This directory contains version-controlled learning data for the NixOS Hybrid AI Learning Stack's federated continuous learning framework.

## Purpose

**Problem**: Learning data stored in `~/.local/share/` is:
- Not backed up
- Not shared across systems
- Lost on reinstall
- Violates federation principles

**Solution**: Store high-value learned patterns here for:
- Version control (git)
- Federation (shared across systems)
- Persistence (survives reinstalls)
- Collective intelligence

## Directory Structure

### `patterns/`
High-value patterns extracted from telemetry (value_score >= 0.7)
- `skills-patterns.jsonl` - Reusable skills and solutions
- `error-solutions.jsonl` - Proven error fixes
- `best-practices.jsonl` - Endorsed practices

### `fine-tuning/`
Fine-tuning datasets for local model improvement
- `dataset.jsonl` - Master fine-tuning dataset
- `snapshots/` - Versioned snapshots

### `telemetry/`
Periodic snapshots of high-value telemetry (NOT raw logs)
- `snapshots/YYYY-MM-DD.jsonl` - Last 1000 high-value events

### `collections/`
Qdrant collection exports (payloads only, no vectors)
- `snapshots/COLLECTION-DATE.json` - Collection point exports

### `metrics/`
Historical metrics for trend analysis
- `monthly/YYYY-MM.json` - Monthly aggregated metrics

## Data Privacy

### ✅ Store in Git
- Anonymized patterns
- Generalized solutions
- Reviewed fine-tuning data
- Aggregated metrics

### ❌ Never Store in Git
- Raw telemetry (use snapshots)
- API keys or secrets
- System-specific configs
- PII or sensitive data

## Sync Scripts

Located in `scripts/`:
- `sync-learning-data.sh` - Sync runtime → repo
- `export-collections.sh` - Export Qdrant → repo
- `import-collections.sh` - Import repo → Qdrant
- `federate-sync.sh` - Sync across systems

## Usage

### New System Setup
```bash
# Clone repo (gets all federated learning)
git clone <repo-url>

# Import learned patterns
bash scripts/import-collections.sh
```

### Daily Operations
```bash
# Periodic sync (automated via cron)
bash scripts/sync-learning-data.sh
```

### Before Reinstall
```bash
# Backup all learning
bash scripts/export-collections.sh
git add data/
git commit -m "Backup learned data"
git push
```

## Federation

This data is designed to be:
1. **Shared** across multiple systems
2. **Merged** with patterns from other instances
3. **Refined** through collective learning
4. **Distributed** to benefit all systems

Every system contributes patterns, every system benefits from all patterns.

## File Formats

### Patterns (JSONL)
```json
{"pattern_id": "uuid", "value_score": 0.85, "content": "...", "metadata": {...}}
```

### Fine-tuning (JSONL)
```json
{"prompt": "...", "completion": "...", "metadata": {...}}
```

### Collection Exports (JSON)
```json
{"result": {"points": [{"id": "...", "payload": {...}}]}}
```

## Size Limits

- Patterns: ~10MB max per file
- Snapshots: Last 1000 events
- Collections: Payloads only (no vectors)
- Total: ~100MB for full federation data

## Maintenance

- **Weekly**: Export collections
- **Monthly**: Create metric snapshots
- **Quarterly**: Review and deduplicate patterns
- **Annually**: Archive old snapshots

Last updated: 2025-12-21
