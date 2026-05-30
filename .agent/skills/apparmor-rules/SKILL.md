# AppArmor Rules Skill — NixOS-Dev-Quick-Deploy Harness
## Tags
apparmor, profile, ix, Ux, NoNewPrivileges, deny, rule, parse-error, EPERM, enforce, complain
## When to Use
Writing AppArmor rules for NixOS services; diagnosing EPERM/EACCES denials; profile reload after rebuild;
denial-to-rule workflow; NoNewPrivileges constraint; mode reference (r/w/a/k/ix/Ux).

## Purpose
Authoritative AppArmor rule authoring guide for this stack. Prevents the recurring parse
errors and EPERM failures that blocked multiple phases.

---

## 1. Valid Access Modes (complete reference)

```
r    read
w    write
a    append  ← MUTUALLY EXCLUSIVE with w (use one or the other)
x    execute (base — rarely used alone)
ix   inherit execution  ← USE THIS under NoNewPrivileges=true
Px   transition to named child profile (BLOCKED by NoNewPrivileges)
Ux   unconfined execution (BLOCKED by NoNewPrivileges — use ix instead)
Cx   transition to local child profile (BLOCKED by NoNewPrivileges)
k    file locking (fcntl) ← REQUIRED for SQLite WAL, JSONL with fcntl, Redis
m    memory map executable
l    link
```

**NEVER USE `c`** — it is not a valid AppArmor mode. It causes a silent parse failure that
breaks the ENTIRE profile, leaving the service unconfined or unloadable.

### Common combinations
```
r       read-only file
rw      read-write (no locking)
rk      read + file-lock (unusual — usually rwk)
rwk     read-write-lock (SQLite, JSONL with fcntl)
rix     read + inherit-execute (scripts called by service)
rwkix   full access to executable state files
```

---

## 2. NoNewPrivileges Constraint

NixOS services with `NoNewPrivileges = true` (the default security baseline) CANNOT use:
- `Ux` (unconfined execution)
- `Px` (profile transition)
- `Cx` (local profile transition)

These return **EPERM** at runtime (not EACCES — don't look for deny in audit log).

**Always use `ix` for subprocess execution** under `NoNewPrivileges = true`:
```
# WRONG — EPERM at runtime:
/bin/bash Ux,
/usr/bin/python3 Px -> python-profile,

# CORRECT:
/bin/bash ix,
/nix/store/**/bin/bash ix,
/nix/store/**/bin/python3 ix,
```

---

## 3. Glob Patterns

```
/path/to/file        exact file match
/path/to/dir/        directory (trailing slash)
/path/to/dir/**      all files recursively under dir
/path/to/dir/*       files directly in dir (not recursive)
/nix/store/**        all nix store paths
/nix/store/**/bin/*  all binaries in nix store

# Hardware monitoring (correct pattern):
/sys/devices/**/hwmon*/**  r,    # hwmon* not hwmon/ (hwmon0, hwmon1, etc.)

# Nix store binaries with hash prefix (use glob, not hardcode):
/nix/store/*/bin/ip ix,          # NOT /nix/store/abc123-iproute2.../bin/ip
```

---

## 4. Profile Reload Verification

```bash
# After nixos-rebuild:
journalctl -u apparmor.service -n 20 --no-pager    # Look for "Loaded profile X"
sudo aa-status | grep <profile-name>                # Confirm loaded + mode (enforce/complain)

# Syntax check before rebuild:
apparmor_parser -p /etc/apparmor.d/<profile>
# Exit 0 = valid. Exit non-0 = parse error with description.

# Monitor denials in real time:
journalctl -k -f | grep -i "apparmor.*DENIED"

# Parse a NixOS-generated profile path:
/nix/store/*-ai-<service>/bin/apparmor_parser -p <profile>
```

**AppArmor profiles managed by NixOS cannot be hot-reloaded with `apparmor_parser -r`.
They require `nixos-rebuild switch` to take effect.**

---

## 5. Common Permission Patterns for This Stack

### Python FastAPI service (coordinator, dashboard)
```
# Python interpreter and stdlib
/nix/store/**/python3* rix,
/nix/store/**/*.py r,
/nix/store/**/*.so mr,

# Process info (psutil)
/proc/** r,
capability sys_ptrace,
ptrace read peer=unconfined,

# Signal handling
signal (send, receive) peer=unconfined,

# Network
network inet tcp,
network inet6 tcp,
/etc/resolv.conf r,
/etc/ssl/certs/** r,
/etc/hosts r,
```

### Shell subprocess invocation (coreutils, ip, systemctl)
```
# Under NoNewPrivileges — must be ix:
/nix/store/**/bin/bash ix,
/nix/store/**/bin/sh ix,
/nix/store/**/bin/python3* ix,
/nix/store/**/bin/ip ix,
/nix/store/**/bin/curl ix,
/nix/store/**/bin/jq ix,
/run/current-system/sw/bin/* ix,

# systemctl (requires dbus + systemd socket)
/run/systemd/private/** rw,
/run/dbus/system_bus_socket rw,
```

### SQLite / JSONL with file locking
```
/var/lib/ai-stack/my-service.db rwk,
/var/lib/ai-stack/my-service.db-wal rwk,
/var/lib/ai-stack/my-service.db-shm rwk,
/var/lib/ai-stack/*.jsonl rwk,
/tmp/*.db rwk,
```

### sysfs hardware (hwmon, thermal)
```
/sys/devices/**/hwmon*/** r,
/sys/devices/virtual/thermal/** r,
/sys/class/thermal/** r,
/sys/class/hwmon/** r,
```

---

## 6. Debugging Denial → Rule Workflow

```bash
# 1. Find the denial:
journalctl -k --since "5 min ago" | grep -i "apparmor.*DENIED"
# Output: apparmor="DENIED" operation="open" profile="ai-foo" name="/path/to/file" ...
#         apparmor="DENIED" operation="exec" profile="ai-foo" name="/nix/store/abc.../bin/bash" ...

# 2. Map operation to rule:
# operation="open"    → file rule (r/w/rw/rwk)
# operation="exec"    → execute rule (ix for NoNewPrivileges)
# operation="connect" → network rule (network inet tcp,)
# operation="ptrace"  → capability sys_ptrace + ptrace rule
# operation="signal"  → signal rule

# 3. Add rule to NixOS profile in mcp-servers.nix, rebuild, verify.

# 4. Auto-remediation tool (if available):
python3 scripts/automation/apparmor-fix-agent.py
```

---

## 7. NixOS Profile Declaration

```nix
security.apparmor.policies."ai-my-service" = {
  enable = true;
  enforce = true;   # Use complain = true during development to log without blocking
  profile = ''
    profile ai-my-service {
      #include <abstractions/base>
      ...rules...
    }
  '';
};
```

Start with `enforce = false` (complain mode) during development, switch to `enforce = true`
once all denials are resolved.
