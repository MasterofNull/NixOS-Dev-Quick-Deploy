# Monitoring Dashboard Guidance

This document provides guidance for using the Prometheus, Grafana, and Portainer dashboards in the NixOS AI Stack.

## Prometheus Configuration

### Service Discovery
Prometheus is configured to automatically discover and monitor all AI stack services:

- **Job Name**: `ai-stack`
- **Scrape Interval**: 15 seconds
- **Metrics Path**: `/metrics`

### Monitored Services
The following services expose metrics endpoints:
- AIDB: `aidb.ai-stack.svc.cluster.local:8091`
- Embeddings: `embeddings.ai-stack.svc.cluster.local:8081`
- Hybrid Coordinator: `hybrid-coordinator.ai-stack.svc.cluster.local:8092`
- NixOS Docs: `nixos-docs.ai-stack.svc.cluster.local:8094`
- Ralph Wiggum: `ralph-wiggum.ai-stack.svc.cluster.local:8098`

### Kubernetes Integration
Prometheus also monitors Kubernetes pods automatically through service discovery:
- Discovers pods with `prometheus.io/scrape: "true"` annotation
- Uses port from `prometheus.io/port` annotation
- Uses path from `prometheus.io/path` annotation

## Grafana Dashboards

### Access
- **URL**: `http://<your-host>:3002`
- **Credentials**: admin/change_me (or as configured in environment)

### Available Dashboards
1. **Comprehensive System Monitoring**
   - Service health status
   - Security & Hardening metrics
   - Garbage Collection statistics
   - Health checks
   - Backup status
   - System performance

2. **P1 Security & Hardening Monitoring**
   - Query validation success vs failures
   - Rate limiting enforcement
   - Malicious pattern detection
   - Storage utilization
   - TLS certificate expiry
   - Certificate renewal status

### Dashboard Features
- Auto-refresh every 30 seconds
- Time range selection (default: last 6 hours)
- Panel-specific filtering
- Alert thresholds
- Log aggregation

## Portainer Dashboard

### Access
- **URL**: `http://<your-host>:9000` (or as configured)
- **Credentials**: As configured during setup

### Features
- Kubernetes cluster management
- Namespace monitoring (ai-stack, backups)
- Pod lifecycle management
- Service status overview
- Deployment scaling
- Resource utilization

### Navigation
1. **Dashboard**: Overview of cluster status
2. **Kubernetes**: Cluster resources and workloads
3. **Applications**: Deployed services in ai-stack namespace
4. **Settings**: Configuration and access management

## Setting Up Alerts

### Prometheus Alerts
Alert rules are defined in the `prometheus-hipaa-alerts.yaml` file:
- High validation failure rates
- Rate limit threshold breaches
- Garbage collection issues
- TLS certificate expiry warnings

### Grafana Alerting
1. Navigate to Alerting → Alert Rules
2. Configure notification channels (email, webhook, etc.)
3. Set up contact points for alert delivery

## Troubleshooting

### Common Issues

#### Prometheus Targets Down
1. Check if services are running: `kubectl get pods -n ai-stack`
2. Verify annotations on deployments
3. Check network connectivity between Prometheus and targets

#### Grafana Not Loading
1. Verify credentials
2. Check if Grafana pod is running: `kubectl get pods -n monitoring`
3. Review Grafana logs: `kubectl logs -n monitoring deployment/grafana`

#### Missing Metrics
1. Confirm `/metrics` endpoint is accessible on services
2. Check Prometheus configuration: `kubectl get configmap -n ai-stack prometheus-cm0`
3. Verify service accounts have proper RBAC permissions

### Useful Queries

#### System Health
```
sum(rate(aidb_requests_total[5m]))
```

#### Service Availability
```
up{job="ai-stack"}
```

#### Error Rates
```
rate(aidb_query_validation_failures_total[5m])
```

## Best Practices

### Monitoring
- Regularly review dashboard panels for anomalies
- Set up alerts for critical thresholds
- Monitor resource utilization trends
- Check backup status regularly

### Security
- Secure Grafana and Portainer with strong passwords
- Use HTTPS for production deployments
- Regularly rotate API keys
- Monitor access logs

### Maintenance
- Clean up old metrics data periodically
- Update dashboard configurations as needed
- Review and tune alert thresholds
- Backup dashboard configurations