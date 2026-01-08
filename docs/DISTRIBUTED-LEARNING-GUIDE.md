### Distribution & Federation Guide

Complete guide for deploying the hybrid learning system across multiple nodes with automatic synchronization and knowledge sharing.

> **📊 System Dashboard**: Monitor federation status, connected nodes, and sync progress at [ai-stack/dashboard/index.html](/ai-stack/dashboard/index.html)

---

## Table of Contents

1. [Overview](#overview)
2. [Persistence in NixOS](#persistence-in-nixos)
3. [Data Modularity & Portability](#data-modularity--portability)
4. [Multi-Node Architecture](#multi-node-architecture)
5. [Setup Instructions](#setup-instructions)
6. [Federation Modes](#federation-modes)
7. [Conflict Resolution](#conflict-resolution)
8. [Data Transfer](#data-transfer)
9. [Troubleshooting](#troubleshooting)

---

## Overview

### Three Key Features

1. **Persistent in NixOS** ✅
   - Declarative configuration via NixOS module
   - Automatic service management
   - Data survives system rebuilds
   - Backed up regularly

2. **Modular & Portable** ✅
   - Export/import data snapshots
   - Transfer between systems
   - Version-controlled configurations
   - Reproducible deployments

3. **Distributed & Federated** ✅
   - Multi-node synchronization
   - Automatic knowledge aggregation
   - Conflict resolution
   - Central hub or peer-to-peer

---

## Persistence in NixOS

### Declarative Configuration

Add to your `configuration.nix`:

```nix
{
  # Import the hybrid learning module
  imports = [
    ./nixos-improvements/hybrid-learning.nix
  ];

  # Enable hybrid learning system
  services.hybridLearning = {
    enable = true;

    # Paths (persistent across rebuilds)
    paths = {
      dataDir = "/var/lib/hybrid-learning";
      modelsDir = "/var/lib/hybrid-learning/models";
      finetuneData = "/var/lib/hybrid-learning/fine-tuning/dataset.jsonl";
      exportDir = "/var/lib/hybrid-learning/exports";
    };

    # Qdrant configuration
    qdrant = {
      url = "http://localhost:6333";
    };

    # llama.cpp configuration
    llama-cpp = {
      baseUrl = "http://localhost:8080";
    };

    # Learning thresholds
    learning = {
      localConfidenceThreshold = 0.7;
      highValueThreshold = 0.7;
      patternExtractionEnabled = true;
      autoFinetuneEnabled = false;  # Enable when GPU available
    };

    # Automatic backups
    backup = {
      enable = true;
      schedule = "daily";
      destination = "/var/backups/hybrid-learning";
      retention = 30;  # days
    };

    # Monitoring
    monitoring = {
      enable = true;
      port = 9200;
    };
  };
}
```

### What's Persisted

| Data Type | Location | Persistence |
|-----------|----------|-------------|
| **Qdrant Collections** | `/var/lib/qdrant` | Permanent |
| **GGUF Models** | `/var/lib/hybrid-learning/models` | Permanent |
| **Fine-tuning Datasets** | `/var/lib/hybrid-learning/fine-tuning` | Permanent |
| **Exports/Snapshots** | `/var/lib/hybrid-learning/exports` | Permanent |
| **Backups** | `/var/backups/hybrid-learning` | Permanent |
| **Service State** | `/var/lib/hybrid-learning` | Permanent |

### Automatic Services

After `nixos-rebuild switch`:

```bash
# Services automatically start
systemctl status hybrid-coordinator        # MCP server
systemctl status hybrid-learning-backup    # Daily backups
systemctl status hybrid-learning-exporter  # Metrics

# View logs
journalctl -u hybrid-coordinator -f

# Manual backup
systemctl start hybrid-learning-backup
```

---

## Data Modularity & Portability

### Export Data Snapshot

**Full Export** (all collections + models):

```bash
# Automated export
python3 -m federation_sync --export /tmp/my-learning-data.json

# Or via systemd
systemctl start hybrid-learning-export
```

**Export Contents**:
```json
{
  "manifest": {
    "node_id": "my-workstation",
    "timestamp": "2025-12-19T10:30:00",
    "collections": {
      "skills-patterns": {"count": 150, "high_value_count": 120},
      "error-solutions": {"count": 80, "high_value_count": 75},
      "best-practices": {"count": 50, "high_value_count": 50}
    }
  },
  "collections": {
    "skills-patterns": [...],  // Full data
    "error-solutions": [...],
    "best-practices": [...]
  }
}
```

### Import Data Snapshot

**On New System**:

```bash
# Import exported snapshot
python3 -m federation_sync --import /path/to/my-learning-data.json

# Verify import
curl http://localhost:6333/collections | jq '.result.collections[] | {name, points_count}'
```

### Modular Components

Each component is independently portable:

1. **Qdrant Collections**
   ```bash
   # Export single collection
   curl -X POST "http://localhost:6333/collections/skills-patterns/snapshots/create" \
     > skills-patterns.snapshot

   # Import on another system
   curl -X PUT "http://localhost:6333/collections/skills-patterns/snapshots/upload" \
     --data-binary @skills-patterns.snapshot
   ```

2. **Fine-tuned Models**
   ```bash
   # Copy GGUF models
   rsync -av /var/lib/hybrid-learning/models/ user@remote:/var/lib/hybrid-learning/models/
   ```

3. **Configuration**
   ```bash
   # NixOS configuration is in version control
   git clone your-nixos-config
   # Contains: nixos-improvements/hybrid-learning.nix
   ```

---

## Multi-Node Architecture

### Three Federation Modes

#### 1. **Peer-to-Peer** (Equal Nodes)

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Node A     │◄───►│   Node B     │◄───►│   Node C     │
│  (Peer)      │     │  (Peer)      │     │  (Peer)      │
└──────────────┘     └──────────────┘     └──────────────┘
       │                     │                     │
       └─────────────────────┴─────────────────────┘
              All nodes share equally
```

**Use case**: Multiple development machines, equal importance

**Configuration**:
```nix
services.hybridLearning.federation = {
  enable = true;
  mode = "peer";
  nodes = [
    "http://node-b.local:8092"
    "http://node-c.local:8092"
  ];
  syncInterval = 3600;  # hourly
};
```

#### 2. **Hub-and-Spoke** (Central Aggregation)

```
                 ┌──────────────┐
                 │   Hub Node   │
                 │  (Aggregator)│
                 └──────────────┘
                        △
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
 ┌──────────┐    ┌──────────┐    ┌──────────┐
 │ Spoke 1  │    │ Spoke 2  │    │ Spoke 3  │
 │  (Edge)  │    │  (Edge)  │    │  (Edge)  │
 └──────────┘    └──────────┘    └──────────┘
```

**Use case**: Central server with multiple edge deployments

**Hub Configuration**:
```nix
services.hybridLearning.federation = {
  enable = true;
  mode = "hub";
  # Hub doesn't need to list spokes
  syncInterval = 1800;  # 30 min
};
```

**Spoke Configuration**:
```nix
services.hybridLearning.federation = {
  enable = true;
  mode = "spoke";
  nodes = [
    "http://hub.example.com:8092"
  ];
  syncInterval = 3600;  # hourly
};
```

#### 3. **Hybrid** (Hub + P2P)

```
        ┌──────────────┐
        │     Hub      │
        │ (Aggregator) │
        └──────────────┘
               △
               │
    ┌──────────┼──────────┐
    │          │          │
    ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐
│Peer A  │◄─►Peer B  │◄─►Peer C  │
│(Spoke) │ │(Spoke) │ │(Spoke) │
└────────┘ └────────┘ └────────┘
```

**Use case**: Central aggregation + local peer sharing

---

## Setup Instructions

### Single Node (Standalone)

```bash
# 1. Add module to configuration.nix
imports = [ ./nixos-improvements/hybrid-learning.nix ];

# 2. Configure
services.hybridLearning.enable = true;

# 3. Rebuild
sudo nixos-rebuild switch

# 4. Verify
systemctl status hybrid-coordinator
curl http://localhost:6333/collections
```

### Multi-Node (Peer-to-Peer)

**On Each Node**:

```nix
# configuration.nix
services.hybridLearning = {
  enable = true;

  federation = {
    enable = true;
    mode = "peer";
    nodeId = "node-1";  # Unique per node
    nodes = [
      "http://node-2.local:8092"
      "http://node-3.local:8092"
    ];
    syncInterval = 3600;
    conflictResolution = "highest-value";
  };
};
```

```bash
# Deploy on all nodes
sudo nixos-rebuild switch

# Check sync status
journalctl -u hybrid-learning-sync -f

# Manual sync trigger
systemctl start hybrid-learning-sync
```

### Multi-Node (Hub-and-Spoke)

**Hub Server**:

```nix
services.hybridLearning = {
  enable = true;

  federation = {
    enable = true;
    mode = "hub";
    nodeId = "hub-central";
    syncInterval = 1800;
  };

  # Open firewall
  networking.firewall.allowedTCPPorts = [ 8092 ];
};
```

**Edge Nodes**:

```nix
services.hybridLearning = {
  enable = true;

  federation = {
    enable = true;
    mode = "spoke";
    nodeId = "edge-01";
    nodes = [
      "http://hub.company.com:8092"
    ];
    syncInterval = 3600;
  };
};
```

---

## Conflict Resolution

When the same data exists on multiple nodes, conflicts are resolved using configured strategy:

### 1. **Latest** (Timestamp-based)

```nix
conflictResolution = "latest";
```

- Most recently updated data wins
- Good for: frequently changing data
- Risk: may lose older high-quality data

### 2. **Highest-Value** (Quality-based) ✅ Recommended

```nix
conflictResolution = "highest-value";
```

- Data with highest `value_score` wins
- Good for: learning data (patterns, skills)
- Ensures best quality data propagates

### 3. **Merge** (Intelligent Combination)

```nix
conflictResolution = "merge";
```

- Combines data from both sources
- Good for: complementary information
- More complex, requires careful design

### 4. **Manual** (Human Review)

```nix
conflictResolution = "manual";
```

- Conflicts logged for manual resolution
- Good for: critical data
- Requires human intervention

### Conflict Example

**Node A has**:
```json
{
  "id": "skill-123",
  "skill_name": "NixOS module creation",
  "value_score": 0.85,
  "success_examples": ["example1", "example2"]
}
```

**Node B has**:
```json
{
  "id": "skill-123",
  "skill_name": "NixOS module creation",
  "value_score": 0.92,
  "success_examples": ["example3", "example4", "example5"]
}
```

**Resolution** (highest-value):
- Node B wins (0.92 > 0.85)
- Node A imports from Node B
- Result: All nodes have the better version

---

## Data Transfer

### Scenario 1: New Deployment

You have an existing system with valuable learning data and want to deploy to a new machine.

**Export from existing system**:

```bash
# On existing system
sudo python3 /var/lib/hybrid-learning/coordinator/federation_sync.py \
  --export /tmp/my-learning-snapshot.json

# Copy to new system
scp /tmp/my-learning-snapshot.json newmachine:/tmp/
```

**Import on new system**:

```bash
# On new system (after NixOS deployment)
sudo python3 /var/lib/hybrid-learning/coordinator/federation_sync.py \
  --import /tmp/my-learning-snapshot.json

# Verify
curl http://localhost:6333/collections | jq
```

### Scenario 2: Team Sharing

Multiple team members want to share their learning data.

**Setup Central Hub**:

```nix
# hub.company.com
services.hybridLearning.federation = {
  enable = true;
  mode = "hub";
  nodeId = "team-hub";
};
```

**Connect Team Members**:

```nix
# Each developer's machine
services.hybridLearning.federation = {
  enable = true;
  mode = "spoke";
  nodeId = "dev-alice";  # or dev-bob, dev-carol, etc.
  nodes = [ "http://hub.company.com:8092" ];
  syncInterval = 7200;  # sync every 2 hours
};
```

**Result**:
- Alice solves a problem → pattern extracted → synced to hub → distributed to Bob & Carol
- Bob finds an error solution → synced to hub → available to everyone
- Carol fine-tunes a model → shared via hub → team benefits

### Scenario 3: Offline Transfer

Air-gapped systems that can't connect directly.

**Export**:

```bash
# On source system
sudo systemctl start hybrid-learning-export
# Creates: /var/lib/hybrid-learning/exports/snapshot-YYYYMMDD-HHMMSS.json

# Copy to USB drive
cp /var/lib/hybrid-learning/exports/snapshot-*.json /media/usb/
```

**Import**:

```bash
# On destination system
cp /media/usb/snapshot-*.json /tmp/
sudo python3 -m federation_sync --import /tmp/snapshot-*.json
```

---

## Federation API

Each node exposes an HTTP API on port 8092:

### Endpoints

#### GET /manifest

Returns current data manifest.

```bash
curl http://localhost:8092/manifest | jq
```

**Response**:
```json
{
  "node_id": "my-workstation",
  "timestamp": "2025-12-19T10:30:00",
  "collections": {
    "skills-patterns": {
      "count": 150,
      "high_value_count": 120,
      "checksum": "a1b2c3d4e5f6"
    }
  }
}
```

#### GET /export/{collection}

Export collection data.

```bash
curl http://localhost:8092/export/skills-patterns | jq > skills.json
```

#### POST /import/{collection}

Import collection data.

```bash
curl -X POST http://localhost:8092/import/skills-patterns \
  -H "Content-Type: application/json" \
  -d @skills.json
```

#### POST /sync

Manually trigger synchronization.

```bash
curl -X POST http://localhost:8092/sync
```

---

## Monitoring & Observability

### Metrics

Prometheus metrics on port 9200:

```bash
curl http://localhost:9200/metrics
```

**Key Metrics**:
- `hybrid_learning_interactions_total` - Total interactions
- `hybrid_learning_high_value_count` - High-value interactions
- `hybrid_learning_sync_success_total` - Successful syncs
- `hybrid_learning_sync_failure_total` - Failed syncs
- `hybrid_learning_collections_size` - Collection sizes

### Grafana Dashboard

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'hybrid-learning'
    static_configs:
      - targets:
        - 'node-1:9200'
        - 'node-2:9200'
        - 'node-3:9200'
```

**Dashboard Panels**:
1. Total interactions across all nodes
2. High-value data growth trend
3. Sync status matrix
4. Collection sizes by node
5. Conflict resolution outcomes

---

## Advanced Scenarios

### Global Team Distribution

**Scenario**: Development teams in US, Europe, Asia

**Architecture**:
```
      [US Hub]
         △
         │
    ┌────┼────┐
    │    │    │
   US1  US2  US3

      [EU Hub]
         △
         │
    ┌────┼────┐
    │    │    │
   EU1  EU2  EU3

      [Asia Hub]
         △
         │
    ┌────┼────┐
    │    │    │
   AS1  AS2  AS3

  [Global Aggregator]
         △
         │
    ┌────┼────┐
    │    │    │
 US-Hub EU-Hub AS-Hub
```

**Configuration**:

Regional hubs sync with global aggregator:

```nix
# US Hub
services.hybridLearning.federation = {
  mode = "hub";
  nodes = [ "http://global.company.com:8092" ];  # Sync with global
};

# Global Aggregator
services.hybridLearning.federation = {
  mode = "hub";
  # Receives from all regional hubs
};
```

### CI/CD Integration

```yaml
# .github/workflows/learning-sync.yml
name: Sync Learning Data

on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours

jobs:
  sync:
    runs-on: self-hosted
    steps:
      - name: Export learning data
        run: |
          python3 -m federation_sync --export /tmp/ci-learning.json

      - name: Upload to S3
        run: |
          aws s3 cp /tmp/ci-learning.json s3://company-learning-data/$(date +%Y%m%d)/

      - name: Distribute to nodes
        run: |
          for node in node1 node2 node3; do
            scp /tmp/ci-learning.json $node:/tmp/
            ssh $node "python3 -m federation_sync --import /tmp/ci-learning.json"
          done
```

---

## Troubleshooting

### Sync Not Working

```bash
# Check service status
systemctl status hybrid-learning-sync

# Check logs
journalctl -u hybrid-learning-sync -f

# Test connectivity
curl http://remote-node:8092/manifest

# Manual sync
systemctl start hybrid-learning-sync
```

### Data Not Syncing

```bash
# Check manifests
curl http://localhost:8092/manifest | jq '.collections'
curl http://remote:8092/manifest | jq '.collections'

# Compare checksums
# If different, sync should occur

# Check conflict resolution
# View logs for rejected imports
journalctl -u hybrid-learning-sync | grep conflict
```

### Port Already in Use

```nix
# Change federation port
services.hybridLearning.federation.port = 8093;  # Default: 8092
```

### Backup Not Running

```bash
# Check timer
systemctl list-timers | grep hybrid-learning

# Manual backup
systemctl start hybrid-learning-backup

# Check backup location
ls -lh /var/backups/hybrid-learning/
```

---

## Security Considerations

### Authentication

For production deployments, add authentication:

```nix
services.hybridLearning.federation = {
  # Add nginx reverse proxy with auth
  authentication = {
    enable = true;
    type = "basic";  # or "oauth", "mtls"
  };
};
```

### Encryption

Use TLS for inter-node communication:

```nix
services.hybridLearning.federation = {
  tls = {
    enable = true;
    certFile = "/path/to/cert.pem";
    keyFile = "/path/to/key.pem";
  };
};
```

### Firewall

Restrict federation to trusted networks:

```nix
networking.firewall.extraCommands = ''
  # Allow federation only from trusted IPs
  iptables -A INPUT -p tcp --dport 8092 -s 10.0.0.0/8 -j ACCEPT
  iptables -A INPUT -p tcp --dport 8092 -j DROP
'';
```

---

## Summary

### Answers to Your Questions

1. **Is it automatically setup and persistent in NixOS?**
   - ✅ YES - Declarative NixOS module
   - ✅ Automatic service management
   - ✅ Data survives rebuilds
   - ✅ Backed up automatically

2. **Are refinements transferable and modular?**
   - ✅ YES - Export/import snapshots
   - ✅ Modular components (collections, models, configs)
   - ✅ Version-controlled configuration
   - ✅ Reproducible across machines

3. **How to aggregate and distribute across nodes?**
   - ✅ YES - Federation service included
   - ✅ Three modes: Peer, Hub-Spoke, Hybrid
   - ✅ Automatic synchronization
   - ✅ Conflict resolution strategies
   - ✅ HTTP API for data exchange

### Key Files

- **NixOS Module**: `templates/nixos-improvements/hybrid-learning.nix`
- **Federation Service**: `ai-stack/mcp-servers/hybrid-coordinator/federation_sync.py`
- **This Guide**: `DISTRIBUTED-LEARNING-GUIDE.md`

### Quick Start

```bash
# 1. Enable in configuration.nix
services.hybridLearning.enable = true;
services.hybridLearning.federation.enable = true;

# 2. Rebuild
sudo nixos-rebuild switch

# 3. Verify
systemctl status hybrid-coordinator
systemctl status hybrid-learning-sync
```

---

**Everything is persistent, modular, and distributed!** 🎉
