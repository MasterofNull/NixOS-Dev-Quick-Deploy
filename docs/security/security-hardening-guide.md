# NixOS Security Hardening Guide

**Status:** Active
**Owner:** Security Team
**Last Updated:** 2026-03-20

## Overview

This guide provides comprehensive security hardening recommendations for NixOS-Dev-Quick-Deploy deployments. Following these guidelines will significantly improve your security posture and compliance with industry standards.

## Table of Contents

1. [NixOS Security Fundamentals](#nixos-security-fundamentals)
2. [System Hardening](#system-hardening)
3. [Network Security](#network-security)
4. [Service-Specific Hardening](#service-specific-hardening)
5. [Access Control](#access-control)
6. [Encryption](#encryption)
7. [Secret Management](#secret-management)
8. [Monitoring and Logging](#monitoring-and-logging)
9. [Incident Response](#incident-response)
10. [Security Checklist](#security-checklist)

## NixOS Security Fundamentals

### Declarative Security Configuration

NixOS's declarative approach provides security benefits:

**Advantages**:
- Configuration is version-controlled
- Changes are auditable
- Rollback capability
- Reproducible security posture

**Example NixOS Configuration**:
```nix
{
  # Enable automatic security updates
  system.autoUpgrade = {
    enable = true;
    allowReboot = false;
  };

  # Enable firewall
  networking.firewall.enable = true;

  # Kernel hardening
  boot.kernel.sysctl = {
    "kernel.dmesg_restrict" = 1;
    "kernel.kptr_restrict" = 2;
    "kernel.unprivileged_bpf_disabled" = 1;
    "kernel.unprivileged_userns_clone" = 0;
    "net.core.bpf_jit_harden" = 2;
  };
}
```

### System Updates

**Keep System Updated**:
```bash
# Update NixOS
sudo nixos-rebuild switch --upgrade

# Check for security advisories
nix-channel --update
```

## System Hardening

### Kernel Hardening

**Recommended Sysctls**:
```nix
boot.kernel.sysctl = {
  # Kernel hardening
  "kernel.dmesg_restrict" = 1;
  "kernel.kptr_restrict" = 2;
  "kernel.unprivileged_bpf_disabled" = 1;
  "kernel.yama.ptrace_scope" = 1;

  # Network hardening
  "net.ipv4.conf.all.rp_filter" = 1;
  "net.ipv4.conf.default.rp_filter" = 1;
  "net.ipv4.conf.all.accept_redirects" = 0;
  "net.ipv4.conf.default.accept_redirects" = 0;
  "net.ipv4.conf.all.secure_redirects" = 0;
  "net.ipv4.conf.default.secure_redirects" = 0;
  "net.ipv4.conf.all.send_redirects" = 0;
  "net.ipv4.conf.default.send_redirects" = 0;
  "net.ipv4.tcp_syncookies" = 1;
  "net.ipv4.tcp_rfc1337" = 1;
  "net.ipv4.icmp_echo_ignore_broadcasts" = 1;
  "net.ipv4.icmp_ignore_bogus_error_responses" = 1;
  "net.ipv6.conf.all.accept_redirects" = 0;
  "net.ipv6.conf.default.accept_redirects" = 0;

  # Filesystem hardening
  "fs.protected_hardlinks" = 1;
  "fs.protected_symlinks" = 1;
  "fs.suid_dumpable" = 0;
};
```

### AppArmor/SELinux

**Enable Mandatory Access Control**:
```nix
# AppArmor (recommended for NixOS)
security.apparmor = {
  enable = true;
  packages = with pkgs; [ apparmor-utils apparmor-profiles ];
};

# Or SELinux
security.selinux = {
  enable = true;
  type = "targeted";
};
```

### File System Hardening

**Mount Options**:
```nix
fileSystems = {
  "/tmp" = {
    device = "tmpfs";
    fsType = "tmpfs";
    options = [ "nosuid" "nodev" "noexec" "size=4G" ];
  };

  "/var/tmp" = {
    options = [ "nosuid" "nodev" ];
  };

  "/home" = {
    options = [ "nosuid" "nodev" ];
  };
};
```

### User Limits

**Resource Limits**:
```nix
security.pam.loginLimits = [
  {
    domain = "*";
    type = "hard";
    item = "nproc";
    value = "1000";
  }
  {
    domain = "*";
    type = "hard";
    item = "nofile";
    value = "65536";
  }
];
```

## Network Security

### Firewall Configuration

**Default Deny**:
```nix
networking.firewall = {
  enable = true;
  allowPing = false;  # Disable ping responses

  # Allowed TCP ports
  allowedTCPPorts = [ 22 80 443 ];

  # Allowed UDP ports
  allowedUDPPorts = [ ];

  # Per-interface rules
  interfaces = {
    eth0.allowedTCPPorts = [ 80 443 ];
  };

  # Custom rules
  extraCommands = ''
    # Rate limit SSH connections
    iptables -A INPUT -p tcp --dport 22 -m state --state NEW -m recent --set
    iptables -A INPUT -p tcp --dport 22 -m state --state NEW -m recent --update --seconds 60 --hitcount 4 -j DROP
  '';
};
```

### SSH Hardening

**Secure SSH Configuration**:
```nix
services.openssh = {
  enable = true;

  settings = {
    # Disable root login
    PermitRootLogin = "no";

    # Disable password authentication
    PasswordAuthentication = false;
    ChallengeResponseAuthentication = false;

    # Use only strong ciphers
    Ciphers = [
      "chacha20-poly1305@openssh.com"
      "aes256-gcm@openssh.com"
      "aes128-gcm@openssh.com"
    ];

    # Strong MACs
    Macs = [
      "hmac-sha2-512-etm@openssh.com"
      "hmac-sha2-256-etm@openssh.com"
    ];

    # Strong key exchange
    KexAlgorithms = [
      "curve25519-sha256"
      "curve25519-sha256@libssh.org"
      "diffie-hellman-group16-sha512"
      "diffie-hellman-group18-sha512"
    ];

    # Other security settings
    X11Forwarding = false;
    AllowAgentForwarding = false;
    AllowTcpForwarding = false;
    PermitUserEnvironment = false;
    ClientAliveInterval = 300;
    ClientAliveCountMax = 2;
    MaxAuthTries = 3;
    MaxSessions = 2;
  };

  # Only allow specific users
  allowUsers = [ "admin" "deploy" ];
};
```

### TLS/SSL Configuration

**Strong TLS Settings**:
```nix
services.nginx = {
  enable = true;

  # Global SSL settings
  sslProtocols = "TLSv1.2 TLSv1.3";
  sslCiphers = "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384";
  sslPreferServerCiphers = "on";

  # Additional headers
  appendHttpConfig = ''
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
  '';
};
```

## Service-Specific Hardening

### Redis Hardening

```nix
services.redis = {
  enable = true;

  # Bind to localhost only
  bind = "127.0.0.1";

  # Require authentication
  requirePass = "strong_password_here";

  # Disable dangerous commands
  settings = {
    rename-command = {
      FLUSHDB = "";
      FLUSHALL = "";
      CONFIG = "";
    };

    # Persistence settings
    save = "900 1";
    appendonly = "yes";
  };
};
```

**Manual Configuration** (if not using NixOS module):
```conf
# /etc/redis/redis.conf

# Network
bind 127.0.0.1
protected-mode yes
port 6379

# Authentication
requirepass YOUR_STRONG_PASSWORD

# Disable dangerous commands
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command CONFIG ""
rename-command SHUTDOWN ""
rename-command DEBUG ""

# Limits
maxclients 10000
maxmemory 2gb
maxmemory-policy allkeys-lru

# Persistence
save 900 1
save 300 10
save 60 10000
appendonly yes
```

### PostgreSQL Hardening

```nix
services.postgresql = {
  enable = true;

  # Authentication
  authentication = ''
    # TYPE  DATABASE  USER  ADDRESS      METHOD
    local   all       all                peer
    host    all       all   127.0.0.1/32 scram-sha-256
    host    all       all   ::1/128      scram-sha-256
  '';

  # Settings
  settings = {
    # Connection limits
    max_connections = 100;

    # Memory
    shared_buffers = "256MB";

    # Logging
    log_connections = true;
    log_disconnections = true;
    log_line_prefix = "%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h ";

    # SSL
    ssl = true;
    ssl_cert_file = "/path/to/server.crt";
    ssl_key_file = "/path/to/server.key";
  };
};
```

### AI Service Hardening

**LLaMA.cpp**:
```bash
# Run as non-root user
useradd -r -s /bin/false llama

# Restrict file permissions
chown llama:llama /path/to/models
chmod 750 /path/to/models

# Bind to localhost only
# In service configuration:
--host 127.0.0.1 --port 8080
```

**systemd Service Hardening**:
```nix
systemd.services.llama-cpp = {
  serviceConfig = {
    # User/Group
    User = "llama";
    Group = "llama";

    # Security
    NoNewPrivileges = true;
    PrivateTmp = true;
    ProtectSystem = "strict";
    ProtectHome = true;
    ReadWritePaths = [ "/var/lib/llama" ];

    # Network
    RestrictAddressFamilies = [ "AF_INET" "AF_INET6" ];

    # Capabilities
    CapabilityBoundingSet = "";
    AmbientCapabilities = "";

    # System calls
    SystemCallFilter = [ "@system-service" "~@privileged" ];
  };
};
```

## Access Control

### User Management

**Principle of Least Privilege**:
```nix
users.users = {
  admin = {
    isNormalUser = true;
    extraGroups = [ "wheel" ];  # sudo access
    openssh.authorizedKeys.keys = [
      "ssh-ed25519 AAAAC3..."
    ];
  };

  deploy = {
    isNormalUser = true;
    extraGroups = [ "docker" ];  # Only necessary groups
    openssh.authorizedKeys.keys = [
      "ssh-ed25519 AAAAC3..."
    ];
  };

  llama = {
    isSystemUser = true;
    group = "llama";
    home = "/var/lib/llama";
  };
};
```

### sudo Configuration

**Restrict sudo Access**:
```nix
security.sudo = {
  enable = true;
  wheelNeedsPassword = true;

  extraRules = [
    {
      users = [ "deploy" ];
      commands = [
        {
          command = "/run/current-system/sw/bin/systemctl restart llama-cpp";
          options = [ "NOPASSWD" ];
        }
      ];
    }
  ];
};
```

### File Permissions

**Secure Sensitive Files**:
```bash
# Configuration files
chmod 600 /etc/secrets/*
chown root:root /etc/secrets/*

# SSH keys
chmod 600 ~/.ssh/id_ed25519
chmod 644 ~/.ssh/id_ed25519.pub
chmod 700 ~/.ssh

# Service files
chmod 640 /etc/systemd/system/sensitive.service
chown root:root /etc/systemd/system/sensitive.service
```

## Encryption

### Encryption at Rest

**Disk Encryption (LUKS)**:
```nix
boot.initrd.luks.devices = {
  root = {
    device = "/dev/sda2";
    preLVM = true;
  };
};
```

**File-Level Encryption**:
```bash
# Encrypt sensitive files with gpg
gpg --symmetric --cipher-algo AES256 secret.txt

# Decrypt
gpg secret.txt.gpg
```

### Encryption in Transit

**Force TLS for All Services**:
```nix
services.nginx.virtualHosts."example.com" = {
  forceSSL = true;
  enableACME = true;

  locations."/" = {
    proxyPass = "http://127.0.0.1:8080";
    extraConfig = ''
      proxy_ssl_verify on;
      proxy_ssl_session_reuse on;
    '';
  };
};
```

### Certificate Management

**Let's Encrypt with ACME**:
```nix
security.acme = {
  acceptTerms = true;
  defaults.email = "admin@example.com";
};

services.nginx.virtualHosts."example.com" = {
  enableACME = true;
  forceSSL = true;
};
```

## Secret Management

### SOPS-nix Integration

**Setup SOPS**:
```nix
{
  imports = [ <sops-nix> ];

  sops = {
    defaultSopsFile = ./secrets.yaml;
    age.keyFile = "/var/lib/sops-nix/key.txt";

    secrets = {
      "redis/password" = {
        owner = "redis";
      };
      "postgres/password" = {
        owner = "postgres";
      };
    };
  };

  services.redis.requirePass = config.sops.secrets."redis/password";
}
```

**Create Secrets**:
```bash
# Generate age key
age-keygen -o ~/.config/sops/age/keys.txt

# Create secrets file
cat > secrets.yaml <<EOF
redis:
  password: ENC[AES256_GCM,data:...,tag:...,type:str]
postgres:
  password: ENC[AES256_GCM,data:...,tag:...,type:str]
EOF

# Edit secrets
sops secrets.yaml
```

### Environment Variables

**Avoid Hardcoding Secrets**:
```nix
systemd.services.myservice = {
  environment = {
    DATABASE_URL = "postgresql://user@localhost/db";
  };

  serviceConfig = {
    EnvironmentFile = config.sops.secrets."myservice/env".path;
  };
};
```

### Secret Rotation

**Regular Rotation Schedule**:
```bash
# Rotate every 90 days
# Document rotation procedure
# Test rotation in staging first
```

## Monitoring and Logging

### Audit Logging

**Enable auditd**:
```nix
security.audit = {
  enable = true;
  rules = [
    "-w /etc/passwd -p wa -k identity"
    "-w /etc/group -p wa -k identity"
    "-w /etc/shadow -p wa -k identity"
    "-w /etc/sudoers -p wa -k actions"
    "-a always,exit -F arch=b64 -S execve -k exec"
  ];
};
```

### System Logging

**Centralized Logging**:
```nix
services.journald = {
  extraConfig = ''
    Storage=persistent
    Compress=yes
    SystemMaxUse=1G
    ForwardToSyslog=yes
  '';
};

services.rsyslog = {
  enable = true;
  defaultConfig = ''
    *.* @@log-server:514
  '';
};
```

### Security Monitoring

**File Integrity Monitoring**:
```bash
# Install AIDE
nix-env -iA nixos.aide

# Initialize database
aide --init

# Check integrity
aide --check
```

## Incident Response

### Preparation

**Incident Response Plan**:
1. Identify security incident
2. Contain the threat
3. Eradicate the threat
4. Recover systems
5. Post-incident analysis

### Detection

**Monitoring Points**:
- Failed login attempts
- Privilege escalation
- Unusual network traffic
- File integrity changes
- Service crashes

**Alerting**:
```bash
# Monitor failed SSH attempts
journalctl -u sshd | grep "Failed password"

# Monitor sudo usage
journalctl | grep sudo
```

### Response Procedures

**Immediate Actions**:
```bash
# Isolate compromised system
sudo iptables -P INPUT DROP
sudo iptables -P OUTPUT DROP

# Preserve evidence
sudo journalctl > /secure/location/journal.log
sudo cp -r /var/log /secure/location/

# Kill suspicious processes
sudo kill -9 <PID>

# Disable compromised accounts
sudo passwd -l <username>
```

### Recovery

**System Recovery**:
```bash
# Rollback to previous configuration
sudo nixos-rebuild switch --rollback

# Restore from backup
# (Use your backup procedure)

# Verify system integrity
aide --check

# Review and apply security patches
sudo nixos-rebuild switch --upgrade
```

### Post-Incident

**Actions**:
1. Document the incident
2. Review what happened
3. Update security controls
4. Train team on lessons learned
5. Update incident response plan

## Security Checklist

### Initial Deployment

- [ ] Enable firewall with default deny
- [ ] Configure SSH hardening
- [ ] Disable root login
- [ ] Set up key-based authentication only
- [ ] Enable automatic security updates
- [ ] Configure kernel hardening
- [ ] Enable AppArmor/SELinux
- [ ] Set up disk encryption
- [ ] Configure secure mount options
- [ ] Set up audit logging
- [ ] Configure systemd service hardening
- [ ] Implement secret management (SOPS)
- [ ] Set up TLS/SSL certificates
- [ ] Configure security headers
- [ ] Enable fail2ban or similar

### Service Deployment

- [ ] Run services as non-root users
- [ ] Bind services to localhost when appropriate
- [ ] Implement authentication
- [ ] Enable encryption in transit
- [ ] Enable encryption at rest
- [ ] Configure resource limits
- [ ] Set up service-specific hardening
- [ ] Disable unnecessary features
- [ ] Configure logging
- [ ] Implement monitoring

### Ongoing Maintenance

- [ ] Apply security updates weekly
- [ ] Review logs daily
- [ ] Rotate secrets every 90 days
- [ ] Run vulnerability scans weekly
- [ ] Review access control monthly
- [ ] Test backups monthly
- [ ] Review firewall rules quarterly
- [ ] Update incident response plan annually
- [ ] Conduct security training quarterly
- [ ] Perform penetration testing annually

### Compliance

- [ ] Document security controls
- [ ] Maintain audit trail
- [ ] Regular compliance audits
- [ ] Update security policies
- [ ] Track compliance score
- [ ] Address compliance gaps
- [ ] Generate compliance reports

## References

- [NixOS Security](https://nixos.wiki/wiki/Security)
- [CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [OWASP Security Guidelines](https://owasp.org/)
- [SOPS Documentation](https://github.com/Mic92/sops-nix)

## Changelog

- 2026-03-20: Initial security hardening guide created
- Comprehensive hardening recommendations
- Service-specific security configurations
- Incident response procedures
- Security checklist for deployments
