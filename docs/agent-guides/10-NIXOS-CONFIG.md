# NixOS Configuration Management

**Purpose**: Modify system and AI stack configurations safely using declarative Nix modules.

---

## Quick Reference

**Source of truth**: `nix/modules/` directory

- **Core Options (Ports/Tiers)**: `nix/modules/core/options.nix`
- **AI Stack Services**: `nix/modules/services/`
- **User Home Config**: `nix/home/`

**Deployment Tool**: `./deploy` (wrapper for `nixos-rebuild`)

---

## Workflow

### 1. Identify the Target Module

- To change **ports or hardware settings**, edit `nix/modules/core/options.nix`.
- To tune **AI models**, edit `nix/modules/services/llama-cpp.nix`.
- To modify **User environment**, edit `nix/home/default.nix`.

### 2. Apply Changes

```bash
# Rebuild and switch (standard)
sudo nixos-rebuild switch --flake .

# Build only (dry-run)
nixos-rebuild build --flake .
```

### 3. Verify Changes

```bash
# Check generation
nixos-rebuild list-generations

# Verify specific option value
aq-qa 0                                      # Confirm services are healthy
```

---

## Common Tasks

### Change a Service Port

Edit `nix/modules/core/options.nix` in the `ports` submodule:
```nix
ports = {
  mcpHybrid = lib.mkOption {
    default = 8003; # Change this value
  };
};
```

### Switch AI Model

Edit `nix/modules/services/llama-cpp.nix` or the host's `default.nix`:
```nix
mySystem.aiStack.llamaCpp.activeModel = "gemma4-e4b";
```

### Enable a New Service

Edit the relevant role or `nix/hosts/<hostname>/default.nix`:
```nix
mySystem.aiStack.embeddingServer.enable = true;
```

---

## Best Practices

1. **Declarative First**: Never use `systemctl` to permanently change service state; use Nix modules.
2. **Single Source of Truth**: Always use `nix/modules/core/options.nix` for ports to avoid drift.
3. **Traceability**: Commit changes to git before applying so you have a clear audit trail.
4. **Validation**: Run `aq-qa 0` after every rebuild to ensure the stack is still functional.

---

## Next Steps

- [Debugging Guide](12-DEBUGGING.md)
- [Service Status](02-SERVICE-STATUS.md)
- [System Overview](00-SYSTEM-OVERVIEW.md)
