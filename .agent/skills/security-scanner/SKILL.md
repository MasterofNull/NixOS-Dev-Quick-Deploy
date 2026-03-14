---
name: security-scanner
description: Security audit and vulnerability scanning workflow. Use when reviewing code for security issues, checking configurations, or validating hardening measures.
---

# Skill: security-scanner

## Description
Provides systematic security review patterns aligned with OWASP Top 10 and NixOS hardening best practices. Focuses on practical, actionable security checks.

## When to Use
- Reviewing code changes for security issues
- Auditing service configurations
- Checking for hardcoded secrets
- Validating systemd hardening
- Pre-deployment security checks

## Security Audit Protocol

### Phase 1: Quick Scan
Fast checks that catch common issues.

```bash
# Check for hardcoded secrets
grep -rn --include="*.py" --include="*.sh" --include="*.nix" \
  -E "(password|secret|api_key|token)\s*=\s*['\"][^'\"]+" .

# Check for exposed ports
ss -tlnp | grep -v "127.0.0.1"

# Check file permissions
find . -type f -perm /go+w -ls 2>/dev/null

# Check for insecure env vars
env | grep -iE "password|secret|token|key" | grep -v "_FILE="
```

### Phase 2: OWASP Top 10 Checklist

| Risk | Check | Command/Pattern |
|------|-------|-----------------|
| A01: Broken Access Control | Auth on endpoints | Check middleware, decorators |
| A02: Cryptographic Failures | Secrets management | Env vars, not hardcoded |
| A03: Injection | Input validation | Parameterized queries |
| A05: Security Misconfiguration | Default configs | Service hardening |
| A06: Vulnerable Components | Dependencies | `npm audit`, `pip-audit` |
| A09: Security Logging | Audit trails | No secrets in logs |

### Phase 3: Service Hardening Check

```bash
# Check systemd hardening
systemctl show <service>.service --property=PrivateTmp,NoNewPrivileges,ProtectSystem,ProtectHome

# Check AppArmor status
aa-status | grep <service>

# Check capabilities
getcap /usr/bin/<binary>
```

### Phase 4: NixOS-Specific Checks

```bash
# Check for hardcoded values in Nix
grep -rn --include="*.nix" -E "port = [0-9]+;" nix/

# Check secrets handling
grep -rn --include="*.nix" "sops\|agenix\|/run/secrets" nix/

# Validate no plain text secrets
find /etc/nixos -name "*.nix" -exec grep -l "password\|secret" {} \;
```

## Quick Commands

### Secret Scanning
```bash
# Git history for secrets
git log -p | grep -iE "password|secret|api_key|token" | head -20

# Pre-commit hook check
git diff --cached | grep -iE "(password|secret|token|key)\s*=\s*['\"]"

# File content scan
scripts/governance/check-secret-hygiene.sh 2>/dev/null || \
  grep -rn --include="*.{py,sh,json,yaml}" -E "sk-|ghp_|AIza" .
```

### Dependency Vulnerabilities
```bash
# Python
pip-audit 2>/dev/null || pip list --outdated

# Node.js
npm audit 2>/dev/null || true

# System packages
nix-shell -p vulnix --run "vulnix -S" 2>/dev/null || echo "vulnix not available"
```

### Network Security
```bash
# Open ports
ss -tlnp

# Firewall rules
sudo iptables -L -n 2>/dev/null || echo "Check firewall config"

# TLS configuration
curl -vI https://localhost:<port> 2>&1 | grep -E "SSL|TLS|certificate"
```

### Auth & Access
```bash
# Check API auth configuration
grep -rn --include="*.py" "X-API-Key\|Authorization\|Bearer" .

# Check file ownership
ls -la /run/secrets/ 2>/dev/null

# Check sudo configuration
sudo -l
```

## Security Hardening Checklist

### Service Configuration
- [ ] PrivateTmp=true
- [ ] NoNewPrivileges=true
- [ ] ProtectSystem=strict
- [ ] ProtectHome=true
- [ ] DynamicUser=true (where applicable)
- [ ] CapabilityBoundingSet= (restricted)
- [ ] SystemCallFilter=@system-service

### Secrets Management
- [ ] All secrets in /run/secrets or env vars
- [ ] No hardcoded credentials in code
- [ ] Secrets files have 0600 permissions
- [ ] API keys loaded from _FILE paths

### Network Security
- [ ] Services bind to 127.0.0.1 unless needed
- [ ] HTTPS/TLS for external endpoints
- [ ] Rate limiting configured
- [ ] CORS properly restricted

### Input Validation
- [ ] All user input sanitized
- [ ] Parameterized database queries
- [ ] Path traversal prevention
- [ ] Command injection prevention

## AI Stack Security Commands

```bash
# Run auth hardening checks
scripts/testing/check-api-auth-hardening.sh

# Check MCP security
scripts/testing/check-mcp-health.sh --optional

# Run focused parity (includes security)
scripts/testing/smoke-focused-parity.sh
```

## Token Efficiency Rules
1. Run quick scan first - catches 80% of issues.
2. Use automated scanners before manual review.
3. Focus on externally-exposed surfaces first.
4. Check secrets before code logic.
5. Document all findings with severity and fix.
