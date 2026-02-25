# Hospital + Classified Security Baseline

**Created:** 2026-02-24  
**Status:** ACTIVE BASELINE (Phase 36)

## 1) Threat Model Baseline

### Trust Zones
- Zone A: User and operator endpoints
- Zone B: Control plane (deployment, orchestration, CI/CD)
- Zone C: AI runtime plane (model serving, MCP services, routing)
- Zone D: Data plane (PHI/classified stores, vector indexes, backups)
- Zone E: Observability and audit plane

### Data Classes
- `PUBLIC`
- `INTERNAL`
- `PHI`
- `CLASSIFIED`

### Adversary Classes
- External attacker with network foothold
- Malicious or negligent insider with valid credentials
- Supply-chain adversary through dependency or container compromise
- Model/tool abuse actor via prompt injection or retrieval poisoning

### Critical Abuse Paths (Initial)
- Cross-zone retrieval leaks `PHI`/`CLASSIFIED` context into lower-trust outputs
- Compromised workload identity enables lateral movement into data plane
- Non-immutable logs block forensic reconstruction after incident
- Misconfigured telemetry persists sensitive free-text payloads
- Backup and vector index retention bypass deletion obligations

## 2) Control Matrix (Initial)

| Control Family | Required Control | Evidence Artifact | Status | Owner |
|---|---|---|---|---|
| Identity | Service-scoped workload identity and least-privilege RBAC | Service accounts + RBAC manifests + access tests | Partial | Platform |
| Secrets | Encrypted at rest + automated rotation | SOPS config + rotation runbook + rotation logs | Partial | Platform |
| Network | Default-deny + explicit ingress/egress allow list | NetworkPolicy manifests + enforcement tests | Partial | Platform |
| Encryption | TLS for all inter-service traffic handling sensitive data | Service TLS config + cert inventory + client validation | Partial | Platform |
| Auditability | Immutable logs with actor attribution and synchronized clocks | Log pipeline config + tamper checks + time sync proof | Missing | Security |
| Data lifecycle | Retention/deletion controls across DB, vector DB, logs, backups | Retention policies + deletion verification evidence | Missing | Data/Platform |
| AI safety | Prompt/output redaction + zone-aware retrieval controls | Policy config + redaction tests + retrieval isolation tests | Missing | AI Platform |
| Incident readiness | Tested IR runbooks with RTO/RPO evidence | Drill reports + rollback proof + postmortems | Missing | SRE/Security |

## 3) Release Gate (Fail-Closed)

A release candidate is blocked if any item below fails:
- Threat model is not updated for architecture/config changes
- Control matrix has any CRITICAL control with `Missing` status and no approved exception
- Security audit fails (`scripts/security-audit.sh`)
- Host networking or hostPort exposure exists without explicit approved exception
- Rolling image tags (`latest`/`main`/untagged) exist in active manifests
- NetworkPolicy default-deny baseline is absent
- TLS posture for sensitive inter-service traffic is not validated
- Telemetry writes plaintext sensitive free-text payloads
- Incident response and rollback evidence is older than allowed drill window

## 4) 30/60/90-Day Execution Cadence

### 0-30 Days (Containment)
- Enforce release gate in CI as blocking
- Remove unapproved host networking exposure
- Complete identity and secrets scoping for highest-risk services
- Publish first full evidence bundle

### 31-60 Days (Control Closure)
- Close all `Missing` controls in auditability, data lifecycle, and AI safety
- Validate cross-zone data controls and deletion guarantees
- Run red-team style abuse-path exercises and remediate findings

### 61-90 Days (Operational Assurance)
- Run recurring IR and recovery drills with measured RTO/RPO
- Approve controlled exceptions with expiry and owner
- Transition to continuous compliance review per release
