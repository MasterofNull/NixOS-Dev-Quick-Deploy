# Security → Audit → Compliance Integration

Phase 4.3 implementation providing comprehensive security scanning, audit logging, and compliance checking.

## Quick Start

### 1. Run Security Scan

```bash
# Set repository root
export REPO_ROOT=/home/hyperd/Documents/NixOS-Dev-Quick-Deploy

# Source the scanner
source lib/security/scanner.sh

# Run full deployment scan
scan_deployment "deployment_$(date +%s)" "$REPO_ROOT"
```

### 2. Log Audit Events

```bash
# Log deployment event
python3 lib/security/audit-logger.py \
  --action log \
  --event-type deployment \
  --event-action started \
  --actor system \
  --resource "deployment:123"

# Query events
python3 lib/security/audit-logger.py --action query --limit 10

# Get statistics
python3 lib/security/audit-logger.py --action stats
```

### 3. Check Compliance

```bash
# Source compliance checker
source lib/security/compliance-checker.sh

# Run SOC2 compliance check
check_soc2_compliance "deployment_123"

# Run ISO 27001 check
check_iso27001_compliance "deployment_123"

# Run CIS benchmarks
check_cis_benchmarks "deployment_123" "L1"
```

### 4. Execute Security Workflow

```bash
# Source workflow validator
source lib/security/security-workflow-validator.sh

# Run complete security workflow
run_security_workflow "deployment_123"

# Or run individual stages
run_pre_deployment_security_gate "deployment_123"
run_post_deployment_security_verification "deployment_123"
```

### 5. Use Deployment Hooks

```bash
# Source hooks system
source lib/deploy/deployment-hooks.sh

# Register built-in security hooks
register_builtin_security_hooks

# Execute hooks
execute_hooks "pre_deployment" "deployment_123"
```

## Components

| Component | File | Purpose |
|-----------|------|---------|
| Security Scanner | `scanner.sh` | Vulnerability scanning, secret detection |
| Audit Logger | `audit-logger.py` | Tamper-evident audit logging |
| Compliance Checker | `compliance-checker.sh` | SOC2, ISO27001, CIS compliance |
| Workflow Validator | `security-workflow-validator.sh` | End-to-end workflow orchestration |
| Deployment Hooks | `../deploy/deployment-hooks.sh` | Hook registration and execution |

## Testing

```bash
# Run integration tests
python3 scripts/testing/test-security-workflow-integration.py --verbose

# Or run with unittest
python3 -m unittest scripts/testing/test-security-workflow-integration.py
```

## API Endpoints

Start the dashboard and access security endpoints:

```bash
# Get security summary
curl http://localhost:8889/api/security/summary

# Get scan results
curl http://localhost:8889/api/security/scan/deployment_123

# Trigger security scan
curl -X POST http://localhost:8889/api/security/scan/trigger?deployment_id=deploy_123

# Get audit events
curl http://localhost:8889/api/security/audit/events?limit=100

# Get compliance status
curl http://localhost:8889/api/security/compliance/status

# Get vulnerabilities
curl http://localhost:8889/api/security/vulnerabilities?severity=high
```

## Documentation

- **Integration Guide**: `docs/operations/security-audit-compliance-integration.md`
- **Hardening Guide**: `docs/security/security-hardening-guide.md`

## Configuration

### Environment Variables

```bash
# Security scan settings
export MAX_SCAN_TIME_SECONDS=120
export PARALLEL_SCAN_WORKERS=4

# Security gate thresholds
export MAX_CRITICAL_VULNERABILITIES=0
export MAX_HIGH_VULNERABILITIES=5
export MIN_COMPLIANCE_SCORE=80
export MAX_SECRETS_DETECTED=0

# Deployment hooks
export HOOK_TIMEOUT=300
export HOOK_FAIL_BEHAVIOR=abort  # abort|warn|ignore
```

## Troubleshooting

### Scanner Issues

```bash
# Enable verbose logging
export VERBOSE=1
source lib/security/scanner.sh
scan_deployment "test"

# Check scanner logs
ls -la .agent/security/scans/
```

### Audit Logger Issues

```bash
# Test logger
python3 lib/security/audit-logger.py --action stats

# Check directories
ls -la .agent/security/audit/local/
ls -la .agent/security/audit/central/
```

### Compliance Issues

```bash
# Initialize compliance directories
source lib/security/compliance-checker.sh
ensure_compliance_directories

# Check policy files
ls -la .agent/security/compliance/policies/
```

## Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Security Scan | < 2 min | Full deployment scan |
| Audit Event Log | < 100ms | Single event logging |
| Compliance Check | < 1 min | Per framework |
| API Response | < 500ms | Dashboard endpoints |

## Security Gates

Pre-deployment gates enforce:
- Zero critical vulnerabilities
- Max 5 high vulnerabilities
- No hardcoded secrets
- 80%+ compliance score
- Secure network configuration

Gates can be configured via environment variables or disabled temporarily (not recommended for production).

## Support

For issues or questions:
1. Check documentation in `docs/operations/` and `docs/security/`
2. Review test suite in `scripts/testing/`
3. Enable verbose logging with `VERBOSE=1`
4. Check `.agent/security/` directories for logs and reports
