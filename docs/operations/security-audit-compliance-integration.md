# Security, Audit, and Compliance Integration

**Status:** Active
**Owner:** DevOps Team
**Last Updated:** 2026-03-20

## Overview

This document describes the comprehensive security, audit, and compliance workflow integration for the NixOS-Dev-Quick-Deploy project. The implementation provides end-to-end security scanning, audit logging, and compliance checking throughout the deployment lifecycle.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Components](#core-components)
3. [Security Scanning](#security-scanning)
4. [Audit Logging](#audit-logging)
5. [Compliance Checking](#compliance-checking)
6. [Deployment Workflow Integration](#deployment-workflow-integration)
7. [Dashboard Usage](#dashboard-usage)
8. [Configuration](#configuration)
9. [Troubleshooting](#troubleshooting)
10. [Best Practices](#best-practices)

## Architecture Overview

### System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Deployment Pipeline                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │ Pre-Deploy   │      │  Deployment  │      │ Post-Deploy  │  │
│  │ Security     │─────>│  Execution   │─────>│ Verification │  │
│  │ Gate         │      │              │      │              │  │
│  └──────┬───────┘      └──────────────┘      └──────┬───────┘  │
│         │                                            │           │
│         │                                            │           │
└─────────┼────────────────────────────────────────────┼───────────┘
          │                                            │
          ▼                                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Security Layer                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Vulnerability│  │    Secret    │  │Configuration │          │
│  │   Scanner    │  │   Detector   │  │   Security   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Compliance  │  │     Audit    │  │    Network   │          │
│  │   Checker    │  │    Logger    │  │   Analyzer   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Pre-Deployment**: Security gates execute before deployment
2. **Audit Logging**: All events are logged with tamper-evident checksums
3. **Post-Deployment**: Verification and compliance checks run after deployment
4. **Continuous Monitoring**: Ongoing security monitoring and drift detection

## Core Components

### 1. Security Scanner (`lib/security/scanner.sh`)

**Purpose**: Comprehensive vulnerability scanning and security assessment

**Key Features**:
- Service vulnerability detection
- Configuration security assessment
- Secret detection in code and configs
- Network exposure analysis
- OWASP Top 10 checks
- NixOS hardening verification

**Usage**:
```bash
source lib/security/scanner.sh

# Full deployment scan
scan_deployment "deployment_123"

# Scan specific service
scan_service_vulnerabilities "redis"

# Detect secrets
detect_secrets "/path/to/code"

# Analyze network exposure
analyze_network_exposure "deployment_123"

# Verify NixOS hardening
verify_nixos_hardening "deployment_123"

# Generate report
generate_security_report "deployment_123" "report.json"
```

**Performance**:
- Target scan time: < 2 minutes for typical deployments
- Parallel scanning: Up to 4 workers
- Incremental scanning: Only changed components

### 2. Audit Logger (`lib/security/audit-logger.py`)

**Purpose**: Structured audit event logging with tamper-evident integrity

**Key Features**:
- Multiple event types (deployment, access, configuration, security)
- Dual persistence (local + centralized)
- Tamper-evident checksums with chain validation
- Query and filtering capabilities
- Retention policy enforcement
- <100ms logging latency

**Usage**:
```python
from audit_logger import AuditLogger

logger = AuditLogger()

# Log deployment event
logger.log_deployment_event(
    deployment_id="deploy_123",
    action="started",
    details={"user": "admin"}
)

# Log access event
logger.log_access_event(
    user="admin",
    action="login",
    result="success"
)

# Log security event
logger.log_security_event(
    event_action="vulnerability_detected",
    severity="high",
    actor="scanner",
    resource="service:redis",
    details={"cve": "CVE-2024-1234"}
)

# Query events
events = logger.query_events(
    event_type="deployment",
    severity="error",
    limit=100
)

# Verify integrity
integrity = logger.verify_chain_integrity()
```

**CLI Usage**:
```bash
# Log event
python3 lib/security/audit-logger.py \
  --action log \
  --event-type deployment \
  --event-action started \
  --actor system \
  --resource "deployment:123"

# Query events
python3 lib/security/audit-logger.py \
  --action query \
  --event-type security \
  --limit 50

# Verify chain
python3 lib/security/audit-logger.py \
  --action verify

# Get statistics
python3 lib/security/audit-logger.py \
  --action stats
```

### 3. Compliance Checker (`lib/security/compliance-checker.sh`)

**Purpose**: Policy-as-code validation for compliance frameworks

**Supported Frameworks**:
- SOC2 (2017)
- ISO 27001 (2013)
- CIS Benchmarks (Level 1 & 2)

**Key Features**:
- Automated compliance checking
- Configuration drift detection
- Access control verification
- Encryption requirements validation
- Compliance report generation (JSON & PDF)

**Usage**:
```bash
source lib/security/compliance-checker.sh

# Check SOC2 compliance
check_soc2_compliance "deployment_123"

# Check ISO 27001 compliance
check_iso27001_compliance "deployment_123"

# Check CIS benchmarks
check_cis_benchmarks "deployment_123" "L1"

# Detect configuration drift
detect_configuration_drift "deployment_123"

# Generate compliance report
generate_compliance_report "deployment_123" "SOC2" "report.json"
```

### 4. Security Workflow Validator (`lib/security/security-workflow-validator.sh`)

**Purpose**: End-to-end security workflow orchestration

**Key Features**:
- Pre-deployment security gates
- Post-deployment verification
- Continuous security monitoring
- Automated remediation triggering
- Integration with deployment pipeline

**Usage**:
```bash
source lib/security/security-workflow-validator.sh

# Run complete security workflow
run_security_workflow "deployment_123"

# Run pre-deployment gate only
run_pre_deployment_security_gate "deployment_123"

# Run post-deployment verification
run_post_deployment_security_verification "deployment_123"

# Start continuous monitoring
monitor_security_continuous "deployment_123" 300  # 5-minute interval

# Trigger remediation
trigger_automated_remediation "deployment_123" "drift"
```

### 5. Deployment Hooks (`lib/deploy/deployment-hooks.sh`)

**Purpose**: Extensible hook system for deployment lifecycle events

**Hook Types**:
- `pre_deployment`: Before deployment starts
- `post_deployment`: After deployment completes
- `pre_service_start`: Before service starts
- `post_service_start`: After service starts
- `pre_rollback`: Before rollback
- `post_rollback`: After rollback

**Usage**:
```bash
source lib/deploy/deployment-hooks.sh

# Register a hook
register_hook "pre_deployment" "security_scan" "/path/to/script.sh" 10

# Execute hooks
execute_hooks "pre_deployment" "deployment_123"

# List hooks
list_hooks "pre_deployment"

# Remove hook
remove_hook "pre_deployment" "security_scan"

# Register built-in security hooks
register_builtin_security_hooks
```

## Security Scanning

### Vulnerability Scanning

**Service Vulnerabilities**:
```bash
# Scan all services
scan_all_services

# Scan specific service
scan_service_vulnerabilities "redis"
```

**Dependency Vulnerabilities**:
- Python packages (requirements.txt)
- Container images (if applicable)
- System packages

**Severity Levels**:
- **Critical**: Immediate action required
- **High**: Urgent attention needed
- **Medium**: Should be addressed
- **Low**: Informational

### Secret Detection

**Detected Patterns**:
- API keys
- Passwords
- Tokens
- Private keys
- AWS credentials

**Allowlist Configuration**:
```json
{
  "secrets": {
    "patterns": ["example_.*", "test_.*"],
    "files": ["/path/to/test/file.sh"]
  }
}
```

### Configuration Security

**Checks Performed**:
- File permissions
- World-readable/writable files
- Insecure configurations (SSL disabled, etc.)
- Missing security headers

### Network Exposure Analysis

**Detected Issues**:
- Publicly exposed sensitive services
- Missing firewall rules
- Insecure network configurations

## Audit Logging

### Event Types

#### Deployment Events
```python
logger.log_deployment_event(
    deployment_id="deploy_123",
    action="started|completed|failed",
    actor="system|user_id",
    details={"key": "value"}
)
```

#### Access Events
```python
logger.log_access_event(
    user="admin",
    action="login|logout|access",
    result="success|failure|denied",
    resource="system|service:name"
)
```

#### Configuration Events
```python
logger.log_configuration_event(
    config_path="/etc/service.conf",
    action="created|modified|deleted",
    actor="admin",
    changes={"old": "value1", "new": "value2"}
)
```

#### Security Events
```python
logger.log_security_event(
    event_action="vulnerability_detected|scan_completed",
    severity="info|warning|error|critical",
    actor="scanner|system",
    resource="deployment:123",
    details={"findings": [...]}
)
```

### Tamper-Evident Logging

**Checksum Chain**:
- Each event includes SHA-256 checksum
- Checksum includes previous event's checksum
- Chain verification detects tampering

**Verification**:
```python
result = logger.verify_chain_integrity()
# Returns: {valid: bool, issues: [], total_events: int}
```

### Retention Policy

**Default**: 90 days

**Configuration**:
```python
logger = AuditLogger(retention_days=180)
```

**Enforcement**:
```python
result = logger.enforce_retention_policy()
# Returns: {removed: int, cutoff_date: str}
```

## Compliance Checking

### SOC2 Compliance

**Trust Service Criteria Covered**:
- CC6.1: Logical Access Controls
- CC6.6: Network Security
- CC7.2: System Monitoring
- CC8.1: Change Management

**Example**:
```bash
check_soc2_compliance "deployment_123"
```

**Output**:
```json
{
  "check_id": "check_123_soc2",
  "framework": "SOC2",
  "summary": {
    "total_controls": 4,
    "passed_controls": 3,
    "failed_controls": 1,
    "compliance_percentage": 75
  }
}
```

### ISO 27001 Compliance

**Controls Covered**:
- A.9.1.1: Access Control Policy
- A.9.2.1: User Registration
- A.10.1.1: Cryptographic Controls
- A.12.4.1: Event Logging
- A.18.1.1: Legal Compliance

### CIS Benchmarks

**Benchmark Categories**:
1. Filesystem Configuration
2. Mandatory Access Control
3. Network Configuration
4. Logging and Auditing
5. SSH Server Configuration
6. System Maintenance

**Levels**:
- **Level 1**: Essential basic security
- **Level 2**: Defense in depth

### Configuration Drift Detection

**Baseline Creation**:
```bash
create_configuration_baseline "deployment_123"
```

**Drift Detection**:
```bash
detect_configuration_drift "deployment_123"
```

**Result**:
```json
{
  "drift_detected": true,
  "drifts": [
    {
      "type": "service_configuration",
      "service": "redis",
      "expected": "value1",
      "actual": "value2"
    }
  ]
}
```

## Deployment Workflow Integration

### Pre-Deployment Security Gate

**Executed Before Deployment**:

1. Vulnerability scan
2. Secret detection
3. Configuration security scan
4. Compliance check
5. Network exposure analysis

**Gate Thresholds** (configurable):
```bash
MAX_CRITICAL_VULNERABILITIES=0
MAX_HIGH_VULNERABILITIES=5
MIN_COMPLIANCE_SCORE=80
MAX_SECRETS_DETECTED=0
```

**Integration**:
```bash
# In deployment script
if ! run_pre_deployment_security_gate "deployment_123"; then
    echo "Security gate failed - aborting deployment"
    exit 1
fi
```

### Post-Deployment Verification

**Executed After Deployment**:

1. Service security verification
2. NixOS hardening verification
3. Compliance status check
4. Configuration drift detection

### Continuous Monitoring

**Monitoring Interval**: 5 minutes (configurable)

**Monitored Items**:
- Network exposure changes
- Configuration drift
- Service security status

**Auto-Remediation**:
- Configuration drift → Restore from baseline
- Network exposure → Update firewall rules
- Vulnerabilities → Schedule updates

## Dashboard Usage

### Security API Endpoints

**Base URL**: `http://localhost:8889/api/security`

#### Get Security Scan Results
```http
GET /api/security/scan/{deployment_id}
```

#### Trigger Security Scan
```http
POST /api/security/scan/trigger?deployment_id=deploy_123
```

#### Get Vulnerabilities
```http
GET /api/security/vulnerabilities?severity=high&limit=100
```

#### Get Audit Events
```http
GET /api/security/audit/events?event_type=deployment&limit=100
```

#### Get Compliance Status
```http
GET /api/security/compliance/status
```

#### Get Compliance Report
```http
GET /api/security/compliance/report/SOC2
```

#### Get Security Summary
```http
GET /api/security/summary
```

### Security Dashboard Card

The dashboard provides real-time security metrics:

- Security score (0-100)
- Vulnerability breakdown by severity
- Compliance status per framework
- Recent audit events
- Quick actions (trigger scan, view reports)

## Configuration

### Environment Variables

```bash
# Security scan configuration
export SECURITY_SCAN_DIR="$REPO_ROOT/.agent/security/scans"
export SECURITY_REPORTS_DIR="$REPO_ROOT/.agent/security/reports"
export MAX_SCAN_TIME_SECONDS=120
export PARALLEL_SCAN_WORKERS=4

# Audit logging configuration
export AUDIT_LOCAL_DIR="$REPO_ROOT/.agent/security/audit/local"
export AUDIT_CENTRAL_DIR="$REPO_ROOT/.agent/security/audit/central"

# Compliance configuration
export COMPLIANCE_DIR="$REPO_ROOT/.agent/security/compliance"
export MIN_COMPLIANCE_SCORE=80

# Deployment hooks configuration
export HOOKS_DIR="$REPO_ROOT/.agent/deployment/hooks"
export HOOK_TIMEOUT=300
export HOOK_FAIL_BEHAVIOR=abort  # abort|warn|ignore
```

### Security Gate Thresholds

Edit configuration file or set environment variables:

```bash
export MAX_CRITICAL_VULNERABILITIES=0
export MAX_HIGH_VULNERABILITIES=5
export MAX_MEDIUM_VULNERABILITIES=20
export MIN_COMPLIANCE_SCORE=80
export MAX_SECRETS_DETECTED=0
```

### Compliance Frameworks

Enable/disable frameworks in:
```bash
$REPO_ROOT/.agent/security/compliance/policies/
```

## Troubleshooting

### Security Scan Fails

**Symptom**: Security scan times out or fails

**Solutions**:
1. Increase timeout: `export MAX_SCAN_TIME_SECONDS=300`
2. Reduce parallel workers: `export PARALLEL_SCAN_WORKERS=2`
3. Check disk space in `.agent/security/scans/`
4. Review scanner logs: `VERBOSE=1 scan_deployment "id"`

### Audit Logging Errors

**Symptom**: Audit events not being logged

**Solutions**:
1. Check directory permissions: `.agent/security/audit/`
2. Verify Python 3 is available: `python3 --version`
3. Test logger directly: `python3 lib/security/audit-logger.py --action stats`
4. Check disk space

### Compliance Check Fails

**Symptom**: Compliance check returns errors

**Solutions**:
1. Initialize policies: `source compliance-checker.sh && ensure_compliance_directories`
2. Check policy files: `ls .agent/security/compliance/policies/`
3. Review compliance logs with `VERBOSE=1`

### Pre-Deployment Gate Blocks Deployment

**Symptom**: Security gate prevents deployment

**Solutions**:
1. Review gate report: `cat .agent/security/workflows/gate_*_result.json`
2. Address issues found (vulnerabilities, secrets, etc.)
3. Temporarily adjust thresholds (not recommended for production)
4. Override gate (emergency only): `HOOK_FAIL_BEHAVIOR=warn`

## Best Practices

### 1. Security Scanning

- **Run scans regularly**: Schedule daily scans even without deployments
- **Review all findings**: Don't ignore low-severity issues
- **Maintain allowlists**: Document why secrets are allowlisted
- **Keep scanner updated**: Regularly update vulnerability databases

### 2. Audit Logging

- **Log all critical actions**: Deployments, access, configuration changes
- **Verify chain integrity**: Run weekly verification
- **Monitor retention**: Ensure compliance with data retention policies
- **Backup audit logs**: Audit logs are critical evidence

### 3. Compliance

- **Choose appropriate frameworks**: Match your industry requirements
- **Document exceptions**: Clearly document why controls are not met
- **Regular audits**: Run compliance checks weekly
- **Track improvements**: Monitor compliance score trends

### 4. Security Gates

- **Set realistic thresholds**: Balance security and development velocity
- **Provide feedback**: Ensure developers know why gates fail
- **Emergency procedures**: Document gate override procedures
- **Review gate failures**: Learn from blocked deployments

### 5. Continuous Monitoring

- **Set appropriate intervals**: Balance monitoring frequency and system load
- **Configure alerting**: Alert on critical security events
- **Review findings**: Don't let monitoring run unattended
- **Test remediation**: Regularly test auto-remediation

### 6. Integration

- **Use deployment hooks**: Integrate security into existing workflows
- **Automate reports**: Schedule compliance reports
- **Dashboard monitoring**: Check security dashboard regularly
- **Team training**: Ensure team understands security workflow

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [SOC 2 Trust Service Criteria](https://www.aicpa.org/interestareas/frc/assuranceadvisoryservices/aicpasoc2report)
- [ISO 27001 Standard](https://www.iso.org/isoiec-27001-information-security.html)
- [CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks/)
- [NixOS Security](https://nixos.org/manual/nixos/stable/index.html#sec-hardening)

## Changelog

- 2026-03-20: Initial implementation of Phase 4.3
- Security scanner, audit logger, and compliance checker created
- Deployment hooks system integrated
- Dashboard API routes added
- Comprehensive test suite implemented
