# AI Stack Port Conflict - Solutions Guide

## Problem Summary
You have **duplicate AI services** causing port conflicts:
- **System-level** (root): `ollama.service` + `qdrant.service` on ports 11434, 6333, 6334
- **User-level** (home-manager): `services.podman` trying to use the same ports

## Strategic Options

---

## ✅ Option 1: User-Level Only (RECOMMENDED)

### Why Choose This:
- **Security**: Rootless containers (no root privileges needed)
- **Isolation**: User-specific, doesn't affect other users
- **Portability**: Managed declaratively with home-manager
- **Data**: Stored in `~/.local/share/podman-ai-stack/`
- **Flexibility**: Easy to enable/disable per user

### Implementation:

```bash
# 1. Run the migration script
chmod +x migrate-to-user-level-ai-stack.sh
./migrate-to-user-level-ai-stack.sh

# 2. Verify services are running
systemctl --user status podman-local-ai-ollama.service
systemctl --user status podman-local-ai-qdrant.service

# 3. Test endpoints
curl http://127.0.0.1:11434/api/tags  # Ollama
curl http://127.0.0.1:6333/collections # Qdrant
```

### Configuration:
Your current [home.nix](file:///home/hyperd/.dotfiles/home-manager/home.nix#L43) already has:
```nix
localAiStackEnabled = true;
```
This is correct! Just disable the system services.

---

## Option 2: System-Level Only

### Why Choose This:
- **Shared**: All users on the system can access
- **Performance**: Slightly better for root-level permissions
- **Traditional**: Standard systemd service management
- **Data**: Centralized in `/var/lib/`

### Implementation:

```bash
# 1. Disable user-level AI stack in home-manager
# Edit ~/.dotfiles/home-manager/home.nix:
#   localAiStackEnabled = false;  # Change to false

# 2. Rebuild home-manager
cd ~/.dotfiles/home-manager
nix run github:nix-community/home-manager -- switch --flake .#hyperd

# 3. Keep system services running (already enabled)
sudo systemctl status ollama.service
sudo systemctl status qdrant.service
```

### Cons:
- ❌ Requires root for management
- ❌ Not declarative via home-manager
- ❌ Harder to version control user-specific configs

---

## Option 3: Different Ports (Both Services)

### Why Choose This:
- **Testing**: Run both for comparison
- **Development**: Test system vs user deployments
- **Migration**: Gradual transition period

### Implementation:

Edit [home.nix](file:///home/hyperd/.dotfiles/home-manager/home.nix#L49-L63):

```nix
  # Change ports to avoid conflicts
  ollamaPort = 11435;  # Was 11434
  openWebUiPort = 8082; # Was 8081
  qdrantHttpPort = 6335; # Was 6333
  qdrantGrpcPort = 6336; # Was 6334
  mindsdbApiPort = 47335; # Was 47334
  mindsdbGuiPort = 7736; # Was 7735
```

Then rebuild:
```bash
cd ~/.dotfiles/home-manager
nix run github:nix-community/home-manager -- switch --flake .#hyperd
```

### Cons:
- ❌ Confusing to manage two sets of services
- ❌ Double resource usage
- ❌ Different ports to remember

---

## Option 4: Conditional Based on Use Case

### Strategy:
Use system services when you want centralized AI, user services for personal projects.

Edit [home.nix](file:///home/hyperd/.dotfiles/home-manager/home.nix#L43):

```nix
  # Set this based on your current need
  localAiStackEnabled = false;  # Use system services
  # OR
  localAiStackEnabled = true;   # Use user services
```

Then adjust system services accordingly:
```bash
# If using user services:
sudo systemctl disable --now ollama.service qdrant.service

# If using system services:
sudo systemctl enable --now ollama.service qdrant.service
```

---

## Quick Decision Matrix

| Feature | User-Level | System-Level | Different Ports |
|---------|-----------|--------------|-----------------|
| **No root needed** | ✅ | ❌ | ✅ |
| **Declarative config** | ✅ | ❌ | ✅ |
| **Multi-user support** | Per-user | ✅ | ✅ |
| **Easy management** | ✅ | ⚠️ | ❌ |
| **Resource usage** | Efficient | Efficient | 2x usage |
| **Standard ports** | ✅ | ✅ | ❌ |

---

## Recommended Migration Path

### For Most Users (Development/Personal):
1. **Choose Option 1** (User-level only)
2. Run the migration script
3. Verify all services work
4. Remove system-level data if desired

### For Shared Systems:
1. **Choose Option 2** (System-level only)
2. Disable user-level in home-manager
3. Centralize configuration

### For Testing/Development:
1. **Choose Option 3** temporarily
2. Test both deployments
3. Migrate to Option 1 or 2 when decided

---

## Verification Commands

```bash
# Check what's using the ports
ss -tlnp | grep -E ':(6333|6334|11434|8081)'

# List all podman containers
podman ps -a

# Check systemd services
sudo systemctl list-units '*ollama*' '*qdrant*'
systemctl --user list-units 'podman-local-ai-*'

# Check logs
journalctl --user -u podman-local-ai-ollama.service -n 50
sudo journalctl -u ollama.service -n 50
```

---

## Current State Summary

**System Services (Root):**
- ✅ `ollama.service` - Running on port 11434
- ✅ `qdrant.service` - Running on ports 6333, 6334

**User Services (Home-Manager):**
- ❌ `podman-local-ai-ollama.service` - Failed (port conflict)
- ❌ `podman-local-ai-qdrant.service` - Failed (port conflict)
- ❌ `podman-local-ai-open-webui.service` - Failed (dependency)
- ❌ `podman-local-ai-mindsdb.service` - Failed (dependency)

**Other Containers:**
- Pod: `aidb` with containers: aidb-postgres, aidb-api, aidb-guardian (ports 5432, 8000)

---

## Next Steps

1. **Decide** which option fits your use case
2. **Backup** any important AI data (models, databases)
3. **Execute** the chosen solution
4. **Verify** services are running correctly
5. **Update** documentation/scripts if needed

For most development workflows, **Option 1 (User-Level Only)** is the best choice.
