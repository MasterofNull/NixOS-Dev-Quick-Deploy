---
name: nixos-system
description: "NixOS System Skill — NixOS-Dev-Quick-Deploy Harness"
---

# NixOS System Skill — NixOS-Dev-Quick-Deploy Harness
## Tags
nix, nixos, flake, rebuild, module, options.nix, systemd, AppArmor, python-env, secrets, port
## When to Use
Adding/changing a Nix module or service option; triggering nixos-rebuild; wiring ports from options.nix;
Python env in Nix; secrets via deploy-options.local.nix; AppArmor NixOS integration.

## Purpose
Authoritative guide for NixOS module authoring, service declaration, AppArmor integration,
flake-based rebuilds, and option wiring in this stack. Prevents recurring agent mistakes.

---

## 1. Rebuild Workflow

```bash
# Always use the correct flake target:
sudo nixos-rebuild switch --flake .#hyperd-ai-dev

# NOT .#hyperd (does not exist)
# NOT nixos-rebuild without --flake
```

**After any change to:**
- `nix/modules/services/mcp-servers.nix` → rebuild required
- `nix/modules/roles/ai-stack.nix` → rebuild required
- `nix/modules/core/options.nix` → rebuild required
- AppArmor profiles in `nix/modules/services/mcp-servers.nix` → rebuild required (not hot-reload)

Claude Code cannot run `sudo nixos-rebuild` directly (setuid missing in shell). Flag to user when rebuild needed. Add `PENDING-REBUILD` entry to HANDOFF.md.

---

## 2. Port / Option Source of Truth

All service ports are declared in `nix/modules/core/options.nix`.

```nix
# Read ports like:
cfg.ports.llamaCpp          # llama.cpp inference (8080)
cfg.ports.llamaEmbed        # llama embedding (8081)
cfg.ports.aidb              # AIDB vector store (8082) → check options.nix for current
cfg.ports.hybridCoordinator # hybrid-coordinator (8003)
cfg.ports.switchboard       # switchboard (8085)
cfg.ports.cliBridge         # cli-bridge (8089)
cfg.ports.dashboard         # dashboard (8889)
```

**Never hardcode port numbers in Python or shell.** Always inject via env vars from the NixOS
service config. In Python: `int(os.environ.get("HYBRID_URL", "").split(":")[-1])`.

---

## 3. Module Authoring Patterns

### Service declaration (mcp-servers.nix pattern)

**ALWAYS use `commonServiceConfig // { ... }` as the base.** Never write a bare `serviceConfig { }`.
`commonServiceConfig` provides the full hardening baseline declared in mcp-servers.nix:
- `ProtectHome = "read-only"` — REQUIRED: allows the service user to enter /home/hyperd/ (repo lives there)
- `WorkingDirectory = dataDir` — `/var/lib/ai-stack`, owned by the service user
- `ReadOnlyPaths = [repoSource]` — read access to the Nix store copy of the repo
- `ReadWritePaths = serviceWritablePaths` — write access to /var/lib/ai-stack/**
- `NoNewPrivileges`, `PrivateTmp`, `SystemCallFilter`, `RestrictAddressFamilies` — full hardening

```nix
systemd.services."ai-my-service" = lib.mkIf roleEnabled {
  description = "My service description";
  wantedBy = [ "ai-stack.target" ];
  after = hybridDeps;  # or appropriate deps list
  wants = [ "network-online.target" ];

  serviceConfig =
    commonServiceConfig          # <-- MANDATORY base: inherits all hardening
    // {
      User = hybridUser;         # or appropriate service user var (hybridUser, aidbUser, etc.)
      ExecStart = "${python3Env}/bin/python3 path/to/service.py";
      Restart = "always";        # or "on-failure" or "no" for oneshot
      RestartSec = "5s";
      AppArmorProfile = "ai-my-service";  # if profile exists; see §4
      Environment = [
        "PORT=${toString ports.myService}"
        # Never hardcode — always use ports.* vars from options.nix
      ];
    };
};

# For oneshot services (timers, one-time tasks):
systemd.services."ai-my-oneshot" = {
  serviceConfig =
    commonServiceConfig
    // {
      Type = "oneshot";
      User = hybridUser;
      Restart = "no";            # Oneshot: timer handles re-invocation, not systemd restart
      ExecStart = "${mcp.repoPath}/scripts/ai/my-script";
      TimeoutStartSec = "120s";
      Environment = [ "REPO_ROOT=${mcp.repoPath}" ];
    };
};
```

**Why `ProtectHome = "read-only"` is non-negotiable here**: service users (ai-hybrid, ai-aidb, etc.)
are not in the `hyperd` group. `/home/hyperd` is `700`. Without ProtectHome, `WorkingDirectory`
under the repo path fails with `CHDIR: Permission denied` (status=200).

**Working directory rule**: Use `WorkingDirectory = dataDir` (from commonServiceConfig) unless the
service specifically needs to be in the repo root. Pass the repo path as `REPO_ROOT` env var instead.

### Using lib.mkIf for conditional activation
```nix
# Standard pattern for AI stack services:
let roleEnabled = config.aiHarness.roles.aiDev.enable; in
{
  systemd.services."ai-foo" = lib.mkIf roleEnabled { ... };
  environment.etc."profile.d/foo.sh" = lib.mkIf roleEnabled { ... };
}
```

### Profile-driven feature flags
Features are enabled via `nix/modules/profiles/ai-dev.nix`, not inline conditionals.
Don't add `enable = true/false` options to individual services unless they have a clear
toggle use case. Use `roleEnabled` pattern above.

---

## 4. AppArmor Integration

AppArmor profiles live in `nix/modules/services/mcp-servers.nix` under
`security.apparmor.policies."<profile-name>".profile`.

### Valid AppArmor modes (common mistakes)
```
r    = read
w    = write (do NOT combine with a — they are mutually exclusive)
a    = append (mutually exclusive with w)
k    = file locking (required for fcntl locks — SQLite WAL, registry.jsonl)
x    = execute (base)
ix   = inherit execution (REQUIRED under NoNewPrivileges=true — Ux/Px are BLOCKED)
Px   = transition to named profile (blocked by NoNewPrivileges)
Ux   = unconfined execution (blocked by NoNewPrivileges)
rw   = read+write (OK)
rwk  = read+write+lock (typical for SQLite/JSONL files)
```

**`c` is INVALID** — AppArmor parse failure, silently breaks the entire profile.
**`a` + `w` together** = parse error (mutually exclusive).
**`NoNewPrivileges=true` + `Ux`/`Px`** = EPERM at runtime (not EACCES). Use `ix`.

### Typical service profile skeleton
```
profile ai-my-service {
  #include <abstractions/base>
  #include <abstractions/python>
  #include <abstractions/nameservice>

  # Repo access
  /home/hyperd/Documents/NixOS-Dev-Quick-Deploy/** r,
  /home/hyperd/Documents/NixOS-Dev-Quick-Deploy/scripts/ai/* rix,

  # Nix store (all Python deps live here)
  /nix/store/** r,
  /nix/store/**/bin/* rix,

  # Runtime state
  /var/lib/ai-stack/** rwk,
  /tmp/** rwk,

  # Proc/sys (for psutil)
  /proc/** r,
  /sys/devices/** r,

  # Network (if service makes HTTP calls)
  network inet tcp,
  network inet6 tcp,
}
```

### After profile change
```bash
# Verify syntax BEFORE rebuilding:
apparmor_parser -p /etc/apparmor.d/<profile>

# After nixos-rebuild, verify profile loaded:
journalctl -u apparmor.service -n 20 --no-pager
sudo aa-status | grep my-service

# Monitor denials:
journalctl -k | grep -i "apparmor.*DENIED"
```

---

## 5. Python Environment in Nix Services

Services run under a specific Python environment derivation, not the system Python.
The environment is defined in `nix/modules/roles/ai-stack.nix` as `python3Env`.

```nix
# Correct — use the derivation Python:
ExecStart = "${python3Env}/bin/python3 ${cfg.repoPath}/service.py";

# WRONG — uses system Python without venv deps:
ExecStart = "python3 service.py";
```

To check which Python a running service uses:
```bash
cat /proc/$(pgrep -f service.py)/cmdline | tr '\0' ' '
```

---

## 6. Secrets Wiring

Secrets are injected via `sops-nix` into `/run/secrets/<name>`. Never hardcode secrets
in Nix expressions or Python. Never commit `deploy-options.local.nix` (gitignored).

```python
# Python pattern:
api_key_file = os.environ.get("MY_API_KEY_FILE", "")
if api_key_file and os.path.exists(api_key_file):
    with open(api_key_file) as f:
        api_key = f.read().strip()
```

---

## 7. Common Rebuild Failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| `error: attribute 'X' missing` | Option typo or missing `options.nix` declaration | Check `nix/modules/core/options.nix` |
| `infinite recursion` | Circular `config` → `options` reference | Use `lib.mkDefault` or split into separate module |
| Service won't start after rebuild | AppArmor profile parse error | `journalctl -u apparmor.service`; `apparmor_parser -p /etc/apparmor.d/<profile>` |
| EADDRINUSE on service start | Previous instance still running | `ss -tlnp \| grep <port>`, kill orphan |
| `Failed to open /run/secrets/X` | Secret not declared in `secrets.nix` | Add to `sops.secrets` in host configuration |
