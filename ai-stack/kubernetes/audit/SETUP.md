# Kubernetes Audit Logging Setup for HIPAA Compliance

This directory contains the audit policy configuration required for HIPAA compliance.

## Why Audit Logging?

HIPAA Security Rule §164.312(b) requires:
- **Audit Controls**: Hardware, software, and procedural mechanisms to record and examine activity in systems containing ePHI
- **Information System Activity Review**: Regular review of audit logs, access reports, and security incident tracking

## Installation

### Step 1: Copy Audit Policy

```bash
sudo cp audit-policy.yaml /etc/rancher/k3s/audit-policy.yaml
```

### Step 2: Create Log Directory

```bash
sudo mkdir -p /var/log/kubernetes
sudo chown root:root /var/log/kubernetes
sudo chmod 750 /var/log/kubernetes
```

### Step 3: Update K3s Configuration

```bash
# Backup existing config
sudo cp /etc/rancher/k3s/config.yaml /etc/rancher/k3s/config.yaml.bak

# Apply audit configuration
sudo cp k3s-audit-config.yaml /etc/rancher/k3s/config.yaml
```

### Step 4: Restart K3s

```bash
sudo systemctl restart k3s
```

### Step 5: Verify Audit Logging

```bash
# Wait for K3s to start
sleep 30

# Check for audit log
sudo ls -la /var/log/kubernetes/audit.log

# View recent audit events
sudo tail -f /var/log/kubernetes/audit.log | jq '.'
```

## Log Rotation and Archival

The K3s configuration keeps:
- 10 backup files
- 100MB max per file
- 90 days of logs

For HIPAA compliance (6-year retention), set up log archival:

```bash
# Example: Archive to encrypted backup
sudo tar -czf /backup/audit-$(date +%Y%m%d).tar.gz /var/log/kubernetes/
```

## Audit Log Format

Logs are in JSON format with fields:
- `level`: None, Metadata, Request, RequestResponse
- `stage`: RequestReceived, ResponseStarted, ResponseComplete, Panic
- `requestURI`: API path accessed
- `verb`: get, list, create, update, delete, etc.
- `user`: Who made the request
- `sourceIPs`: Client IP addresses
- `objectRef`: Resource being accessed

## Monitored Resources (HIPAA Critical)

1. **Secrets** (RequestResponse) - May contain PHI credentials
2. **ConfigMaps** (RequestResponse) - May contain connection strings
3. **Pod Exec/Attach** (RequestResponse) - Direct container access
4. **RBAC Changes** (RequestResponse) - Permission modifications
5. **Network Policies** (RequestResponse) - Network isolation changes
6. **Deployments** (Metadata) - Service configuration changes

## Integration with Loki

Send audit logs to Loki for centralized logging:

```yaml
# Add to promtail config
scrape_configs:
  - job_name: kubernetes-audit
    static_configs:
      - targets:
          - localhost
        labels:
          job: kubernetes-audit
          __path__: /var/log/kubernetes/audit.log
```
