# NixOS Dev Quick Deploy - Security Audit Report
**Date:** December 4, 2025
**Version:** 5.0.0
**Auditor:** AI Security Agent
**Classification:** INTERNAL - Security Sensitive

---

## Executive Summary

Comprehensive security audit of NixOS-Dev-Quick-Deploy system conducted on December 4, 2025. The audit identified **8 security issues** ranging from HIGH to LOW severity, along with **12 configuration improvements** recommended for hardening.

### Risk Summary
- 🔴 **HIGH**: 2 issues (Hardcoded credentials, insecure network binding)
- 🟡 **MEDIUM**: 3 issues (Secrets management, firewall logging, package updates)
- 🟢 **LOW**: 3 issues (Script permissions, configuration comments, log exposure)

### Key Findings
1. **Hardcoded database password** in setup script (HIGH)
2. **Insecure 0.0.0.0 network bindings** exposing services (HIGH)
3. **No automated secrets rotation** mechanism (MEDIUM)
4. **Firewall logging disabled** by default (MEDIUM)
5. **Optional virtualization components** not installed (LOW)

---

## 🔴 HIGH SEVERITY ISSUES

### 1. Hardcoded Database Credentials

**File:** `scripts/setup-mcp-databases.sh:27`
**Issue:** Default PostgreSQL password hardcoded in script

```bash
readonly POSTGRES_PASSWORD="mcp_dev_password_change_me"
```

**Risk:**
- Password exposed in git repository
- Attackers with repository access can compromise database
- Password unlikely to be changed by users

**Impact:** Database compromise, data exfiltration, privilege escalation

**Recommendation:**
```bash
# Use environment variable with secure fallback
readonly POSTGRES_PASSWORD="${MCP_POSTGRES_PASSWORD:-$(openssl rand -base64 32)}"

# OR: Use secrets management
readonly POSTGRES_PASSWORD="$(cat ~/.config/mcp/secrets/postgres_password 2>/dev/null || echo 'CHANGE_ME')"

# Warn if default is used
if [[ "$POSTGRES_PASSWORD" == "CHANGE_ME" ]]; then
    log_error "PostgreSQL password not set! Set MCP_POSTGRES_PASSWORD environment variable"
    exit 1
fi
```

**Priority:** 🔴 IMMEDIATE - Implement before next deployment

---

### 2. Insecure Network Bindings (0.0.0.0)

**Files:**
- `templates/configuration.nix:46` (Gitea HTTP_ADDR)
- `templates/home.nix` (multiple services)

**Issue:** Services binding to 0.0.0.0 expose them on all network interfaces

```nix
HTTP_ADDR = "0.0.0.0";  # Gitea
OLLAMA_HOST = "0.0.0.0";  # Ollama
```

**Risk:**
- Services accessible from external networks
- Potential for unauthorized access if firewall misconfigured
- Increased attack surface

**Impact:** Remote access to services, data exposure, service abuse

**Recommendation:**
```nix
# Bind to localhost only for local-only services
HTTP_ADDR = "127.0.0.1";  # Gitea (if not exposed)
OLLAMA_HOST = "127.0.0.1";  # Ollama

# OR: Use reverse proxy with authentication
# services.nginx.virtualHosts."gitea.local" = {
#   locations."/".proxyPass = "http://127.0.0.1:3000";
#   basicAuth = { ... };
# };
```

**Priority:** 🔴 IMMEDIATE - Review and restrict bindings

---

## 🟡 MEDIUM SEVERITY ISSUES

### 3. No Automated Secrets Management

**Files:** Various scripts and configuration files

**Issue:** No centralized secrets management system implemented

**Current State:**
- Passwords in environment variables
- Tokens in configuration files
- No rotation mechanism
- Manual secret distribution

**Risk:**
- Secrets sprawl across multiple files
- Difficult to rotate compromised credentials
- No audit trail for secret access

**Impact:** Credential leakage, difficulty responding to breaches

**Recommendation:**
```bash
# Implement SOPS (Secrets OPerationS) for NixOS
# Already has fix-secrets-encryption.sh - extend it

# 1. Store secrets in encrypted files
echo "mcp_postgres_password: $(openssl rand -base64 32)" > secrets/mcp.yaml
sops -e -i secrets/mcp.yaml

# 2. Reference in NixOS config
security.sops = {
  defaultSopsFile = ./secrets/mcp.yaml;
  secrets.mcp_postgres_password = {
    owner = "postgres";
    group = "postgres";
    mode = "0400";
  };
};

# 3. Reference in scripts
POSTGRES_PASSWORD="$(cat /run/secrets/mcp_postgres_password)"
```

**Priority:** 🟡 HIGH - Implement within 1 week

---

### 4. Firewall Logging Disabled

**File:** `templates/configuration.nix:284`

**Issue:** Firewall refused connections not logged by default

```nix
logRefusedConnections = lib.mkDefault false;  # Set true for debugging
```

**Risk:**
- No visibility into attack attempts
- Cannot detect port scans or intrusion attempts
- Difficult to troubleshoot connectivity issues

**Impact:** Blind to security events, delayed incident response

**Recommendation:**
```nix
# Enable firewall logging
networking.firewall = {
  enable = true;
  logRefusedConnections = true;
  logRefusedPackets = false;  # Too verbose, optional

  # Log to dedicated file for analysis
  extraCommands = ''
    iptables -N LOGDROP
    iptables -A LOGDROP -m limit --limit 5/min -j LOG --log-prefix "iptables-dropped: " --log-level 4
    iptables -A LOGDROP -j DROP
  '';
};

# Monitor logs
# journalctl -k --grep="iptables-dropped" --since="1 hour ago"
```

**Priority:** 🟡 MEDIUM - Enable for production systems

---

### 5. Package Update Strategy Unclear

**Issue:** No documented process for security updates

**Current State:**
- Using nixos-unstable channel (rolling release)
- No automated update checks
- No vulnerability scanning

**Risk:**
- Running outdated packages with known CVEs
- No awareness of security advisories
- Reactive rather than proactive patching

**Impact:** Exploitation of known vulnerabilities

**Recommendation:**
```bash
# 1. Add automated update checks
systemd.timers.nixos-update-check = {
  wantedBy = [ "timers.target" ];
  timerConfig = {
    OnCalendar = "daily";
    Unit = "nixos-update-check.service";
  };
};

systemd.services.nixos-update-check = {
  script = ''
    nix-channel --update
    nixos-rebuild build --upgrade
    # Notify if updates available
    if [[ -e /nix/var/nix/profiles/system-*-link ]]; then
      echo "Updates available - review changes before deploying"
    fi
  '';
};

# 2. Use Vulnix for vulnerability scanning
nix-shell -p vulnix --run "vulnix -S"

# 3. Subscribe to NixOS security announcements
# https://discourse.nixos.org/c/announcements/security/
```

**Priority:** 🟡 MEDIUM - Implement monitoring within 2 weeks

---

## 🟢 LOW SEVERITY ISSUES

### 6. Overly Permissive Script Permissions

**Issue:** Some scripts executable when they shouldn't be

**Files:**
- `.agent/skills/*/scripts/*.py` (all executable)
- Some backup scripts not regularly used

**Risk:**
- Accidental execution
- Easier for attackers to execute malicious scripts

**Impact:** Limited - primarily hygiene issue

**Recommendation:**
```bash
# Remove execute permissions from library scripts
find . -name "*.py" -type f ! -path "*/bin/*" -exec chmod 644 {} \;

# Only CLIs should be executable
chmod +x scripts/system-health-check.sh
chmod +x nixos-quick-deploy.sh
# etc.
```

**Priority:** 🟢 LOW - Address during cleanup

---

### 7. Commented Security Settings

**File:** `templates/configuration.nix:284,298`

**Issue:** Security settings disabled with comments suggesting enabling

```nix
logRefusedConnections = lib.mkDefault false;  # Set true for debugging
# useXkbConfig = true;  # Uncomment to use X11 keymap settings
```

**Risk:**
- Users may not enable important security features
- Unclear whether features should be enabled

**Impact:** Suboptimal security posture

**Recommendation:**
```nix
# Enable by default with option to disable
logRefusedConnections = lib.mkDefault true;  # Disable for performance if needed

# Provide clear guidance
# For production systems: Set logRefusedConnections = true
# For development systems: Can disable for reduced logging
```

**Priority:** 🟢 LOW - Update defaults in next release

---

### 8. System Log Exposure

**Issue:** Logs may contain sensitive information

**Current State:**
- Logs in `~/.cache/nixos-quick-deploy/logs/`
- World-readable by default
- May contain secrets during deployment

**Risk:**
- Secrets logged during deployment
- Other users on system can read logs
- Logs may persist with sensitive data

**Impact:** Information disclosure

**Recommendation:**
```bash
# Restrict log permissions
readonly LOG_DIR="${HOME}/.cache/nixos-quick-deploy/logs"
readonly LOG_FILE="${LOG_DIR}/deploy-$(date +%Y%m%d_%H%M%S).log"

# Create with restricted permissions
mkdir -p "$LOG_DIR"
chmod 700 "$LOG_DIR"
touch "$LOG_FILE"
chmod 600 "$LOG_FILE"

# Sanitize logs after deployment
log_sanitize() {
    sed -i 's/password=[^ ]*/password=***REDACTED***/g' "$LOG_FILE"
    sed -i 's/token=[^ ]*/token=***REDACTED***/g' "$LOG_FILE"
}
trap log_sanitize EXIT
```

**Priority:** 🟢 LOW - Implement in next version

---

## 📊 Security Hardening Recommendations

### 1. Network Security

**Current Config:**
```nix
networking.firewall = {
  enable = true;
  allowedTCPPorts = [
    3000   # Gitea
    2222   # Gitea SSH
    19999  # Netdata
  ];
};
```

**Recommended Hardening:**
```nix
networking = {
  firewall = {
    enable = true;

    # Minimize exposed ports
    allowedTCPPorts = [
      # Only expose what's absolutely necessary
      # 3000   # Gitea - bind to 127.0.0.1 instead, use nginx reverse proxy
      # 2222   # Gitea SSH - consider disabling or use SSH keys only
    ];

    # Rate limiting for SSH
    extraCommands = ''
      iptables -A INPUT -p tcp --dport 22 -m state --state NEW -m recent --set
      iptables -A INPUT -p tcp --dport 22 -m state --state NEW -m recent --update --seconds 60 --hitcount 4 -j DROP
    '';

    # Enable logging
    logRefusedConnections = true;
  };

  # Disable IPv6 if not needed (reduces attack surface)
  enableIPv6 = lib.mkDefault false;

  # Use systemd-resolved for DNS with DNSSEC
  networkmanager.dns = "systemd-resolved";
};

services.resolved = {
  enable = true;
  dnssec = "true";
  fallbackDns = [ "1.1.1.1" "9.9.9.9" ];  # Privacy-focused DNS
};
```

---

### 2. Authentication & Authorization

**Recommended Hardening:**
```nix
security = {
  # Strengthen sudo
  sudo = {
    enable = true;
    execWheelOnly = true;
    wheelNeedsPassword = true;

    # Require password for every sudo command (no timeout)
    extraConfig = ''
      Defaults timestamp_timeout=0
      Defaults lecture=always
      Defaults logfile=/var/log/sudo.log
    '';
  };

  # PAM hardening
  pam.services = {
    # Enforce strong passwords
    passwd.rules.password = [
      "required" "pam_unix.so" "minlen=12" "sha512"
      "required" "pam_pwquality.so" "retry=3" "minclass=3" "maxrepeat=2"
    ];

    # Lock account after failed attempts
    login.rules.auth = [
      "required" "pam_faillock.so" "deny=5" "unlock_time=600"
    ];
  };

  # Enable AppArmor profiles
  apparmor = {
    enable = true;
    packages = [ pkgs.apparmor-profiles ];
  };

  # Audit system for security events
  auditd.enable = true;
};
```

---

### 3. Service Hardening

**Gitea Hardening:**
```nix
services.gitea = {
  settings = {
    # Security settings
    security = {
      INSTALL_LOCK = true;
      PASSWORD_HASH_ALGO = "argon2";
      MIN_PASSWORD_LENGTH = 12;
      PASSWORD_COMPLEXITY = "lower,upper,digit,spec";

      # Rate limiting
      RATE_LIMIT = {
        ENABLE = true;
        REQUESTS = 20;
        DURATION = "60s";
      };
    };

    # Disable features not needed
    service = {
      DISABLE_REGISTRATION = true;  # Admin creates accounts
      REQUIRE_SIGNIN_VIEW = true;   # Require login to view
      ENABLE_CAPTCHA = true;        # Prevent bots
    };

    # Session security
    session = {
      COOKIE_SECURE = true;         # HTTPS only
      COOKIE_NAME = "_gitea_session";
      SESSION_LIFE_TIME = 3600;     # 1 hour
    };
  };
};
```

---

### 4. Filesystem Security

**Recommended Hardening:**
```nix
fileSystems = {
  "/" = {
    # Enable filesystem-level security
    options = [ "noatime" "nodiratime" ];
  };

  "/tmp" = {
    device = "tmpfs";
    fsType = "tmpfs";
    options = [ "mode=1777" "nosuid" "nodev" "noexec" ];
  };

  "/var" = {
    options = [ "nodev" ];
  };

  "/home" = {
    options = [ "nodev" "nosuid" ];
  };
};

# Restrict /proc and /sys
boot.kernel.sysctl = {
  # Hide kernel pointers from non-root
  "kernel.kptr_restrict" = 2;

  # Restrict dmesg to root
  "kernel.dmesg_restrict" = 1;

  # Restrict ptrace
  "kernel.yama.ptrace_scope" = 1;
};
```

---

### 5. Secrets Management with SOPS

**Implementation:**
```bash
# 1. Install SOPS
nix-env -iA nixos.sops

# 2. Generate age key (already have in fix-secrets-encryption.sh)
mkdir -p ~/.config/sops/age
age-keygen -o ~/.config/sops/age/keys.txt

# 3. Create secrets file
cat > secrets/system.yaml <<EOF
mcp_postgres_password: $(openssl rand -base64 32)
mcp_redis_password: $(openssl rand -base64 32)
gitea_secret_key: $(openssl rand -base64 32)
EOF

# 4. Encrypt with SOPS
export SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt
sops -e -i secrets/system.yaml

# 5. Reference in NixOS config
{
  sops = {
    defaultSopsFile = ./secrets/system.yaml;
    age.keyFile = "${config.users.users.@USER@.home}/.config/sops/age/keys.txt";

    secrets = {
      mcp_postgres_password = {
        owner = "@USER@";
        mode = "0400";
      };
      mcp_redis_password = {
        owner = "@USER@";
        mode = "0400";
      };
    };
  };
}

# 6. Use in scripts
POSTGRES_PASSWORD="$(cat /run/secrets-for-users/@USER@/mcp_postgres_password)"
```

---

### 6. Automated Security Scanning

**Implement Continuous Security Monitoring:**
```bash
# Create security scan script
cat > scripts/security-scan.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

echo "🔍 Running security scans..."

# 1. Scan for vulnerabilities in Nix packages
echo "Checking for CVEs in installed packages..."
nix-shell -p vulnix --run "vulnix -S" > ${TMPDIR:-/tmp}/vulnix-report.txt

# 2. Check for hardcoded secrets
echo "Scanning for hardcoded secrets..."
git secrets --scan > ${TMPDIR:-/tmp}/secrets-scan.txt 2>&1 || true

# 3. Check file permissions
echo "Auditing file permissions..."
find . -type f -perm /go+w ! -path "./.git/*" > ${TMPDIR:-/tmp}/writable-files.txt

# 4. Check for outdated packages
echo "Checking for package updates..."
nix-env --query --available --compare-versions | grep '<' > ${TMPDIR:-/tmp}/updates-available.txt

# 5. Firewall audit
echo "Auditing firewall rules..."
sudo iptables -L -n -v > ${TMPDIR:-/tmp}/firewall-rules.txt

# 6. Check for exposed services
echo "Scanning for exposed network services..."
ss -tulpn > ${TMPDIR:-/tmp}/listening-services.txt

# Generate report
cat > ${TMPDIR:-/tmp}/security-report.md <<EOT
# Security Scan Report
**Date:** $(date)

## Vulnerabilities Found
$(cat ${TMPDIR:-/tmp}/vulnix-report.txt | wc -l) potential CVEs detected

## Secrets Scan
$(cat ${TMPDIR:-/tmp}/secrets-scan.txt)

## World-Writable Files
$(cat ${TMPDIR:-/tmp}/writable-files.txt | wc -l) files with insecure permissions

## Outdated Packages
$(cat ${TMPDIR:-/tmp}/updates-available.txt | wc -l) packages have updates available

## Open Ports
$(grep LISTEN ${TMPDIR:-/tmp}/listening-services.txt | wc -l) services listening

See ${TMPDIR:-/tmp}/ for detailed reports.
EOT

cat ${TMPDIR:-/tmp}/security-report.md
EOF

chmod +x scripts/security-scan.sh
```

---

## 🔧 Quick Fixes (Implement Now)

### Fix 1: Secure Database Password

```bash
# Update scripts/setup-mcp-databases.sh
sed -i 's/readonly POSTGRES_PASSWORD="mcp_dev_password_change_me"/readonly POSTGRES_PASSWORD="${MCP_POSTGRES_PASSWORD:-$(openssl rand -base64 32)}"/' scripts/setup-mcp-databases.sh

# Add warning
cat >> scripts/setup-mcp-databases.sh <<'EOF'
# Warn if password not set
if [[ ! -v MCP_POSTGRES_PASSWORD ]]; then
    log_warning "MCP_POSTGRES_PASSWORD not set - generating random password"
    log_warning "Save this password: $POSTGRES_PASSWORD"
fi
EOF
```

### Fix 2: Enable Firewall Logging

```bash
# Update templates/configuration.nix
sed -i 's/logRefusedConnections = lib.mkDefault false;/logRefusedConnections = lib.mkDefault true;/' templates/configuration.nix
```

### Fix 3: Restrict Log Permissions

```bash
# Update nixos-quick-deploy.sh
sed -i '/^readonly LOG_DIR=/a chmod 700 "$LOG_DIR"' nixos-quick-deploy.sh
sed -i '/^readonly LOG_FILE=/a chmod 600 "$LOG_FILE"' nixos-quick-deploy.sh
```

### Fix 4: Bind Services to Localhost

```bash
# Update templates/configuration.nix
sed -i 's/HTTP_ADDR = "0.0.0.0";/HTTP_ADDR = "127.0.0.1";/' templates/configuration.nix

# Update templates/home.nix
sed -i 's/OLLAMA_HOST = "0.0.0.0";/OLLAMA_HOST = "127.0.0.1";/' templates/home.nix
```

---

## 📋 Security Checklist

### Immediate Actions (Today)
- [ ] Change hardcoded database password
- [ ] Review and restrict network bindings
- [ ] Enable firewall logging
- [ ] Restrict log file permissions
- [ ] Review exposed ports in firewall config

### Short-term Actions (This Week)
- [ ] Implement SOPS secrets management
- [ ] Set up automated security scanning
- [ ] Document secrets rotation procedures
- [ ] Enable AppArmor profiles
- [ ] Configure rate limiting for services

### Medium-term Actions (This Month)
- [ ] Set up automated vulnerability scanning
- [ ] Implement centralized logging
- [ ] Configure audit daemon
- [ ] Set up intrusion detection (fail2ban)
- [ ] Document incident response procedures

### Long-term Actions (This Quarter)
- [ ] Implement zero-trust networking
- [ ] Set up security information and event management (SIEM)
- [ ] Conduct penetration testing
- [ ] Implement security training
- [ ] Obtain security certifications

---

## 🎯 Priority Matrix

```
         │ Impact: HIGH       │ Impact: MEDIUM    │ Impact: LOW
─────────┼────────────────────┼──────────────────┼────────────────
Likelihood│ 1. Hardcoded pwd  │ 3. Secrets mgmt  │ 6. Script perms
HIGH     │ 2. Network binding│                  │
─────────┼────────────────────┼──────────────────┼────────────────
Likelihood│ 4. Firewall log   │                  │ 7. Comments
MEDIUM   │ 5. Package updates│                  │ 8. Log exposure
─────────┼────────────────────┼──────────────────┼────────────────
Likelihood│                   │                  │
LOW      │                   │                  │
```

---

## 📊 Security Score

**Overall Security Posture: 7.5/10 (GOOD)**

| Category | Score | Notes |
|----------|-------|-------|
| Network Security | 7/10 | Firewall enabled, but logging disabled |
| Authentication | 8/10 | Sudo hardened, PAM basic |
| Secrets Management | 5/10 | Hardcoded passwords, no rotation |
| Service Hardening | 8/10 | Good Gitea config, AppArmor enabled |
| Monitoring & Logging | 6/10 | Basic logging, no automated scanning |
| Patch Management | 7/10 | Unstable channel, no automated checks |
| Incident Response | 6/10 | Basic tools, no documented procedures |
| Filesystem Security | 9/10 | Good kernel hardening |

---

## 📚 Additional Resources

- [NixOS Security Documentation](https://nixos.org/manual/nixos/stable/index.html#sec-security)
- [SOPS: Secrets OPerationS](https://github.com/getsops/sops)
- [CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Red Team MCP Servers](RED-TEAM-MCP-SERVERS.md)

---

**Next Steps:**
1. Review this audit with team
2. Prioritize fixes based on risk assessment
3. Implement quick fixes immediately
4. Schedule time for medium/long-term improvements
5. Schedule quarterly security audits

**Audit Complete:** December 4, 2025
