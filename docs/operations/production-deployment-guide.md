# Production Deployment Guide

**Status:** Active
**Owner:** Platform Engineering Team
**Last Updated:** 2026-03-20
**Version:** 1.0

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial Deployment](#initial-deployment)
3. [Service Management](#service-management)
4. [Scaling](#scaling)
5. [Security Hardening](#security-hardening)
6. [Backup and Recovery](#backup-and-recovery)
7. [Performance Tuning](#performance-tuning)
8. [Monitoring and Alerting](#monitoring-and-alerting)

## Prerequisites

### System Requirements

- **NixOS**: 24.05 or later
- **CPU**: Minimum 8 cores (16+ cores recommended for production)
- **Memory**: Minimum 32 GB RAM (64 GB+ recommended)
- **Storage**:
  - Root filesystem: 100 GB (SSD recommended)
  - Data filesystem: 500 GB+ (SSD required for databases)
  - Log filesystem: 100 GB (for long-term audit logs)
- **Network**: 1 Gbps or higher connectivity
- **Time Synchronization**: NTP configured and running

### Dependencies

```bash
# All dependencies are managed through Nix
# Verify system has latest Nix channels
nix-channel --update

# Key managed components
# - systemd (init system)
# - PostgreSQL 15+
# - Redis 7+
# - Qdrant vector database
# - Python 3.11+
# - Node.js 20+
```

### Network Configuration

**Required Ports**:

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| AI Hybrid Coordinator | 8000 | TCP/HTTP | API and workflow management |
| Dashboard API | 8001 | TCP/HTTP | Dashboard backend |
| Dashboard Frontend | 3000 | TCP/HTTP | Web UI |
| PostgreSQL | 5432 | TCP | Database |
| Redis | 6379 | TCP | Cache and session store |
| Qdrant | 6333 | TCP | Vector database |
| Prometheus | 9090 | TCP | Metrics |
| Grafana | 3001 | TCP | Dashboards |

**Firewall Rules**:

```bash
# Allow SSH access
firewall-cmd --permanent --add-service=ssh
firewall-cmd --permanent --add-port=22/tcp

# Allow API access from trusted networks
firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="10.0.0.0/8" port protocol="tcp" port="8000" accept'

# Allow dashboard from trusted networks
firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="10.0.0.0/8" port protocol="tcp" port="3000" accept'

# Allow monitoring (internal only)
firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="127.0.0.1" port protocol="tcp" port="9090" accept'

# Reload firewall
firewall-cmd --reload
```

### SSL/TLS Certificates

Prepare certificates before deployment:

```bash
# Option 1: Use Let's Encrypt
certbot certonly --standalone -d api.example.com -d dashboard.example.com

# Option 2: Use self-signed certificates (development only)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/selfsigned.key \
  -out /etc/ssl/certs/selfsigned.crt

# Copy to expected locations
sudo mkdir -p /etc/ssl/certs
sudo cp /path/to/cert.pem /etc/ssl/certs/
sudo cp /path/to/key.pem /etc/ssl/private/
sudo chmod 600 /etc/ssl/private/key.pem
```

## Initial Deployment

### Step 1: System Configuration

Create NixOS configuration file `/etc/nixos/configuration.nix`:

```nix
{ config, lib, pkgs, ... }:

{
  # System identification
  networking.hostName = "nix-ai-prod-01";
  time.timeZone = "UTC";

  # Enable required services
  services.openssh.enable = true;
  services.openssh.permitRootLogin = "no";

  # NixOS AI Stack modules
  imports = [
    ./hardware-configuration.nix
    ../../nix/modules/ai-hybrid-coordinator.nix
    ../../nix/modules/dashboard.nix
    ../../nix/modules/qdrant-vector-db.nix
    ../../nix/modules/postgresql-db.nix
    ../../nix/modules/redis-cache.nix
    ../../nix/modules/monitoring.nix
  ];

  # Network configuration
  networking.interfaces.eth0.ipv4.addresses = [
    { address = "10.0.1.10"; prefixLength = 24; }
  ];
  networking.defaultGateway = "10.0.1.1";
  networking.nameservers = [ "8.8.8.8" "8.8.4.4" ];

  # System packages
  environment.systemPackages = with pkgs; [
    curl
    wget
    git
    htop
    iotop
    iftop
    jq
    sqlite
  ];

  # Allow unfree packages if needed
  nixpkgs.config.allowUnfree = true;

  # System optimization
  boot.loader.timeout = 10;
  boot.cleanTmpDir = true;

  system.stateVersion = "24.05";
}
```

### Step 2: Deploy NixOS Configuration

```bash
# Validate configuration
sudo nixos-rebuild dry-build

# Build and activate new configuration
sudo nixos-rebuild switch

# Check deployment status
systemctl status
systemctl list-units --type=service --all
```

### Step 2.1: Runtime Deployment Control Plane

For bounded repo-native runtime deployment exercises after the system is up, use the dashboard deployment control plane instead of ad hoc shell execution.

Operator workflow:

```bash
# Inspect recent runtime deployment history
curl http://127.0.0.1:8889/api/deployments/history?limit=12

# Start a bounded dry-run deployment through the dashboard API
curl -X POST http://127.0.0.1:8889/api/deployments/execute \
  -H "Content-Type: application/json" \
  -d '{
    "deployment_id": "runtime-dry-run",
    "strategy": "blue_green",
    "dry_run": true,
    "confirm": true,
    "user": "operator"
  }'

# Review pending approvals when require_approval=true
curl http://127.0.0.1:8889/api/deployments/approvals/pending
```

What operators should verify in the dashboard deployment inspector:
- `runtime plan`: selected strategy, dry-run/live mode, approval state
- `planned stages`: expected stage sequence for blue-green, canary, rolling, or immediate
- `executed stages`: actual recorded stage logs emitted by the runtime deployer
- `metrics`: rollout percentage and other bounded execution metrics
- rollback affordance: available before attempting a live deployment

Rollback path:

```bash
curl -X POST http://127.0.0.1:8889/api/deployments/runtime-dry-run/rollback \
  -H "Content-Type: application/json" \
  -d '{
    "confirm": true,
    "execute": false,
    "reason": "Operator reviewed rollout summary"
  }'
```

### Step 3: Initialize Database

```bash
# Wait for PostgreSQL to be ready
sudo systemctl wait postgresql

# Initialize database schema
sudo -u postgres psql -f /etc/ai-stack/schema.sql

# Create database user
sudo -u postgres psql -c "CREATE USER aistack WITH PASSWORD 'secure-password';"
sudo -u postgres psql -c "ALTER USER aistack CREATEDB;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE aistack TO aistack;"

# Test connection
psql -h localhost -U aistack -d aistack -c "SELECT version();"
```

### Step 4: Initialize Vector Database

```bash
# Start Qdrant service
sudo systemctl start qdrant

# Wait for Qdrant to be ready
sleep 5

# Create collections via API
curl -X PUT "http://localhost:6333/collections/workflow-embeddings" \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 1536,
      "distance": "Cosine"
    }
  }'

curl -X PUT "http://localhost:6333/collections/agent-patterns" \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 1536,
      "distance": "Cosine"
    }
  }'
```

### Step 5: Start AI Stack Services

```bash
# Start all services
sudo systemctl start redis
sudo systemctl start qdrant
sudo systemctl start postgresql
sudo systemctl start ai-hybrid-coordinator
sudo systemctl start dashboard-api
sudo systemctl start dashboard-frontend

# Verify all services are running
sudo systemctl status ai-hybrid-coordinator
sudo systemctl status dashboard-api
sudo systemctl status dashboard-frontend

# Check logs for errors
journalctl -u ai-hybrid-coordinator -n 100
journalctl -u dashboard-api -n 100
journalctl -u dashboard-frontend -n 100
```

### Step 6: Verify Deployment

```bash
# Test API endpoint
curl http://localhost:8000/health

# Test dashboard
curl http://localhost:3000/health

# Check database connectivity
psql -h localhost -U aistack -d aistack -c "\dt"

# Verify Qdrant collections
curl http://localhost:6333/collections
```

## Service Management

### Starting Services

```bash
# Start all services at once
sudo systemctl start ai-hybrid-coordinator dashboard-api dashboard-frontend redis qdrant postgresql

# Start individual service
sudo systemctl start ai-hybrid-coordinator

# Enable service to start on boot
sudo systemctl enable ai-hybrid-coordinator
```

### Stopping Services

```bash
# Graceful shutdown
sudo systemctl stop ai-hybrid-coordinator

# Stop all services (in reverse dependency order)
sudo systemctl stop dashboard-api dashboard-frontend ai-hybrid-coordinator qdrant redis postgresql
```

### Restarting Services

```bash
# Restart specific service
sudo systemctl restart ai-hybrid-coordinator

# Restart and check status
sudo systemctl restart ai-hybrid-coordinator && systemctl status ai-hybrid-coordinator
```

### Health Checks and Monitoring

```bash
# Check service status
sudo systemctl status ai-hybrid-coordinator

# View recent logs
journalctl -u ai-hybrid-coordinator -n 50 -f

# Check service dependencies
systemctl list-dependencies ai-hybrid-coordinator

# Monitor service resource usage
ps aux | grep ai-hybrid-coordinator
top -p $(pgrep -f ai-hybrid-coordinator)
```

### Log Locations

| Service | Log Location | Access |
|---------|--------------|--------|
| AI Coordinator | `/var/log/ai-hybrid-coordinator.log` | journalctl -u ai-hybrid-coordinator |
| Dashboard API | `/var/log/dashboard-api.log` | journalctl -u dashboard-api |
| Dashboard Frontend | `/var/log/dashboard-frontend.log` | journalctl -u dashboard-frontend |
| PostgreSQL | `/var/log/postgresql/` | journalctl -u postgresql |
| Redis | `/var/log/redis.log` | journalctl -u redis |
| Qdrant | `/var/log/qdrant.log` | journalctl -u qdrant |

## Scaling

### Horizontal Scaling

**Multi-Node Deployment**:

```bash
# Node 1: Primary services
# /etc/nixos/configuration.nix
services.ai-hybrid-coordinator = {
  enable = true;
  bind = "10.0.1.10";
  port = 8000;
};

# Node 2: Secondary services
# /etc/nixos/configuration.nix
services.ai-hybrid-coordinator = {
  enable = true;
  bind = "10.0.1.11";
  port = 8000;
  primaryNode = "10.0.1.10";
};

# Load Balancer (HAProxy)
services.haproxy = {
  enable = true;
  config = ''
    frontend ai_coordinator
      bind 10.0.1.5:8000
      default_backend coordinator_nodes

    backend coordinator_nodes
      mode http
      balance roundrobin
      server node1 10.0.1.10:8000 check
      server node2 10.0.1.11:8000 check
  '';
};
```

### Vertical Scaling

Increase resource allocation:

```nix
# In configuration.nix
boot.kernel.sysctl = {
  # Increase file descriptors
  "fs.file-max" = 2097152;
  # Increase network connections
  "net.core.somaxconn" = 65535;
  "net.ipv4.tcp_max_syn_backlog" = 65535;
};

# Database connection pooling
services.ai-hybrid-coordinator = {
  databaseConfig = {
    maxConnections = 100;
    connectionTimeout = 30;
    idleTimeout = 600;
  };
};

# Memory allocation
services.redis.configs = {
  maxmemory = "16gb";
  maxmemory-policy = "allkeys-lru";
};
```

### Database Replication

```bash
# Primary node setup
sudo -u postgres psql -c "CREATE ROLE replication_user LOGIN REPLICATION ENCRYPTED PASSWORD 'secure-password';"

# Configure pg_hba.conf
echo "host    replication     replication_user    10.0.1.11/32    md5" | \
  sudo tee -a /var/lib/postgresql/data/pg_hba.conf

# Restart PostgreSQL
sudo systemctl restart postgresql

# Standby node setup
sudo -u postgres bash << 'EOF'
pg_basebackup -h 10.0.1.10 -U replication_user -D /var/lib/postgresql/data -P -W
touch /var/lib/postgresql/data/standby.signal
EOF

# Start standby
sudo systemctl start postgresql
```

## Security Hardening

### Authentication and Authorization

```bash
# Configure AI Coordinator authentication
cat > /etc/ai-stack/auth-config.yml << 'EOF'
authentication:
  provider: "oauth2"
  oauth2:
    issuer: "https://auth.example.com"
    client_id: "${CLIENT_ID}"
    client_secret: "${CLIENT_SECRET}"
    scopes: ["openid", "profile", "email"]

authorization:
  rbac:
    enabled: true
    default_role: "viewer"
    roles:
      - name: "admin"
        permissions: ["*"]
      - name: "operator"
        permissions: ["workflow:*", "metrics:read"]
      - name: "viewer"
        permissions: ["metrics:read", "logs:read"]
EOF

# Restrict service account permissions
sudo useradd -r -s /bin/false ai-coordinator
sudo chown -R ai-coordinator:ai-coordinator /opt/ai-coordinator
```

### Network Segmentation

```bash
# Create network namespaces for isolation
sudo ip netns add ai-coordinator
sudo ip netns add dashboard
sudo ip netns add database

# Configure firewall zones
sudo firewall-cmd --permanent --new-zone=ai-services
sudo firewall-cmd --permanent --zone=ai-services --add-port=8000/tcp
sudo firewall-cmd --permanent --zone=ai-services --add-source=10.0.2.0/24
sudo firewall-cmd --reload

# Use SELinux contexts
sudo semanage fcontext -a -t var_log_t "/var/log/ai-coordinator(/.*)?"
sudo restorecon -Rv /var/log/
```

### Secrets Management

```bash
# Use encrypted configuration
sudo apt-get install sops

# Create secrets file
cat > /etc/ai-stack/secrets.yml << 'EOF'
postgresql_password: "secure-password"
api_key: "secret-api-key"
jwt_secret: "jwt-signing-secret"
EOF

# Encrypt with sops
sops -e -k "arn:aws:kms:region:account:key/id" /etc/ai-stack/secrets.yml

# Load encrypted secrets in systemd
# Use ExecStart with sops decryption
```

### Audit Logging

```bash
# Enable auditd
sudo systemctl enable auditd

# Configure audit rules
sudo cat > /etc/audit/rules.d/ai-stack.rules << 'EOF'
# Monitor AI service executable
-w /opt/ai-coordinator/ -p wa -k ai_coordinator_changes

# Monitor configuration changes
-w /etc/ai-stack/ -p wa -k ai_config_changes

# Monitor database access
-a always,exit -F arch=b64 -S connect -F dir=/var/lib/postgresql/ -k db_access
EOF

# Reload audit rules
sudo service auditd restart

# Review audit logs
sudo ausearch -k ai_coordinator_changes
```

## Backup and Recovery

### Database Backups

```bash
# Daily full backup
sudo cat > /usr/local/bin/backup-db.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backups/postgresql"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Full backup
sudo -u postgres pg_dump -d aistack \
  | gzip > $BACKUP_DIR/aistack_full_$TIMESTAMP.sql.gz

# Keep only 30 days of backups
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_DIR/aistack_full_$TIMESTAMP.sql.gz"
EOF

chmod +x /usr/local/bin/backup-db.sh

# Schedule daily backups
sudo crontab -e
# Add: 2 2 * * * /usr/local/bin/backup-db.sh
```

### Configuration Backups

```bash
# Backup configuration
sudo tar czf /backups/config_$(date +%Y%m%d_%H%M%S).tar.gz \
  /etc/nixos/ \
  /etc/ai-stack/ \
  /etc/ssl/certs/ \
  /etc/ssl/private/

# Verify backup integrity
tar tzf /backups/config_*.tar.gz | head -20
```

### Recovery Procedures

```bash
# Restore from database backup
sudo systemctl stop ai-hybrid-coordinator
sudo systemctl stop postgresql

# Restore backup
sudo -u postgres psql -d aistack < /backups/postgresql/aistack_full_*.sql

# Restart services
sudo systemctl start postgresql
sudo systemctl start ai-hybrid-coordinator

# Verify recovery
psql -h localhost -U aistack -d aistack -c "SELECT COUNT(*) FROM workflows;"
```

### Point-in-Time Recovery

```bash
# Enable WAL archiving in postgresql.nix
services.postgresql.settings = {
  wal_level = "replica";
  archive_mode = "on";
  archive_command = "cp %p /backups/wal_archive/%f";
};

# Perform PITR
sudo systemctl stop postgresql

# Find target time in WAL archives
ls -la /backups/wal_archive/ | grep -A5 -B5 "2026-03-20 14:30"

# Restore to point in time
sudo -u postgres pg_basebackup -D /var/lib/postgresql/data
# Edit recovery.conf with recovery_target_time
sudo systemctl start postgresql
```

## Performance Tuning

### Resource Allocation

```nix
# In configuration.nix
systemd.services.ai-hybrid-coordinator = {
  serviceConfig = {
    # CPU limits
    CPUQuota = "75%";
    CPUAccounting = true;

    # Memory limits
    MemoryLimit = "16G";
    MemoryAccounting = true;

    # IO limits
    IOWeight = 500;
    IOAccounting = true;
  };
};
```

### Caching Configuration

```bash
# Configure Redis for optimal cache performance
cat > /etc/redis/redis.conf << 'EOF'
maxmemory 16gb
maxmemory-policy allkeys-lru

# Persistence
save 900 1
save 300 10
save 60 10000

# AOF for durability
appendonly yes
appendfsync everysec

# Replication
repl-diskless-sync yes
repl-diskless-sync-delay 5
EOF

# Apply settings
sudo systemctl restart redis
```

### Database Optimization

```sql
-- Analyze query performance
EXPLAIN ANALYZE SELECT * FROM workflows WHERE status = 'completed';

-- Create indexes for common queries
CREATE INDEX idx_workflows_status ON workflows(status);
CREATE INDEX idx_workflows_created_at ON workflows(created_at DESC);

-- Autovacuum configuration
ALTER DATABASE aistack SET autovacuum_vacuum_scale_factor = 0.05;
ALTER DATABASE aistack SET autovacuum_analyze_scale_factor = 0.02;

-- Connection pooling (pgBouncer)
-- Configure /etc/pgbouncer/pgbouncer.ini
```

### Route Search Optimization

Configure parallel execution and caching:

```bash
cat > /etc/ai-stack/performance-config.yml << 'EOF'
route_search:
  # Enable parallelization
  parallel_workers: 8
  max_concurrent_searches: 16

  # Caching strategy
  cache_enabled: true
  cache_ttl_seconds: 300
  cache_max_items: 10000

  # Timeout guards
  search_timeout_ms: 5000
  execution_timeout_ms: 30000

  # Batch processing
  batch_size: 100
  prefetch_enabled: true
EOF
```

## Monitoring and Alerting

### Metrics Collection

```bash
# Enable Prometheus monitoring
cat > /etc/prometheus/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['localhost:9093']

rule_files:
  - '/etc/prometheus/rules/*.yml'

scrape_configs:
  - job_name: 'ai-coordinator'
    static_configs:
      - targets: ['localhost:8000']

  - job_name: 'dashboard-api'
    static_configs:
      - targets: ['localhost:8001']

  - job_name: 'postgresql'
    static_configs:
      - targets: ['localhost:9187']

  - job_name: 'redis'
    static_configs:
      - targets: ['localhost:9121']

  - job_name: 'qdrant'
    static_configs:
      - targets: ['localhost:8222']
EOF

sudo systemctl restart prometheus
```

### Dashboard Setup

Access Grafana at `http://localhost:3001`:

```bash
# Default credentials
# Username: admin
# Password: admin (change on first login)

# Import dashboards
curl -X POST http://localhost:3001/api/dashboards/db \
  -H "Authorization: Bearer $GRAFANA_API_TOKEN" \
  -d @dashboard-config.json
```

### Alert Configuration

```yaml
# /etc/prometheus/rules/ai-stack-alerts.yml
groups:
  - name: ai-stack
    interval: 30s
    rules:
      - alert: AICoordinatorDown
        expr: up{job="ai-coordinator"} == 0
        for: 5m
        annotations:
          summary: "AI Coordinator is down"

      - alert: HighAPILatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1
        for: 5m
        annotations:
          summary: "API p95 latency > 1s"

      - alert: DatabaseConnectionPoolExhausted
        expr: pg_stat_activity_count > 95
        for: 5m
        annotations:
          summary: "Database connection pool nearly exhausted"

      - alert: RedisMemoryUsageHigh
        expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.85
        for: 5m
        annotations:
          summary: "Redis memory usage > 85%"

      - alert: QdrantIndexingLag
        expr: qdrant_indexing_lag_seconds > 300
        for: 10m
        annotations:
          summary: "Vector database indexing lag > 5 minutes"
```

### Alert Routing

```bash
# Configure Alertmanager routes
cat > /etc/alertmanager/config.yml << 'EOF'
global:
  slack_api_url: '${SLACK_WEBHOOK_URL}'

route:
  receiver: 'default'
  group_by: ['alertname', 'cluster']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h

  routes:
    - match:
        severity: critical
      receiver: 'pagerduty'
      repeat_interval: 5m

    - match:
        severity: warning
      receiver: 'slack'
      repeat_interval: 1h

receivers:
  - name: 'default'
    slack_configs:
      - channel: '#ai-stack-alerts'
        title: 'Alert: {{ .GroupLabels.alertname }}'

  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: '${PAGERDUTY_SERVICE_KEY}'
EOF

sudo systemctl restart alertmanager
```

---

**Document Version History**:
- v1.0 (2026-03-20): Initial comprehensive production deployment guide

**Related Documentation**:
- [CLI Reference](../development/cli-reference.md)
- [Troubleshooting Runbooks](../operations/troubleshooting-runbooks.md)
- [Architecture Decisions](../architecture/architecture-decisions.md)
