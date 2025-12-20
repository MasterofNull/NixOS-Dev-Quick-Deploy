# NixOS Configuration Management

**Purpose**: Modify system and home-manager configurations safely

---

## Quick Reference

**Source of truth**: `templates/` directory in nixos-quick-deploy repo

- **System config**: `templates/configuration.nix`
- **Home config**: `templates/home.nix`

**Deployment script**: `./nixos-quick-deploy.sh`

---

## Workflow

### 1. Modify Templates

```bash
# Edit system config
vim templates/configuration.nix

# Edit home config
vim templates/home.nix
```

### 2. Deploy Changes

```bash
# Deploy both (recommended)
./nixos-quick-deploy.sh

# Deploy only system
./nixos-quick-deploy.sh --system-only

# Deploy only home
./nixos-quick-deploy.sh --home-only
```

### 3. Verify Changes

```bash
# Check current generation
nixos-rebuild list-generations

# Check home-manager generation
home-manager generations
```

### 4. Rollback if Needed

```bash
# Automatic rollback
./nixos-quick-deploy.sh --rollback

# Manual rollback
sudo nixos-rebuild switch --rollback
home-manager switch --rollback
```

---

## Common Tasks

### Add System Package

```nix
# templates/configuration.nix
environment.systemPackages = with pkgs; [
  # ... existing packages
  docker
  git
  vim
];
```

### Enable Service

```nix
# templates/configuration.nix
services.docker.enable = true;
services.postgresql.enable = true;
```

### Add User Package

```nix
# templates/home.nix
home.packages = with pkgs; [
  # ... existing packages
  firefox
  vscode
];
```

### Configure Service

```nix
# templates/configuration.nix
services.postgresql = {
  enable = true;
  package = pkgs.postgresql_16;
  dataDir = "/var/lib/postgresql/16";
};
```

---

## Best Practices

1. **Always edit templates first** - They are source of truth
2. **Test in VM if unsure** - Use `nixos-rebuild build-vm`
3. **Commit before deploy** - Git history allows easy rollback
4. **Deploy with backup** - Script automatically creates backups
5. **Verify after deploy** - Check services started correctly

---

## Troubleshooting

### Build Fails

```bash
# Check syntax
nix-instantiate --parse templates/configuration.nix

# View detailed errors
./nixos-quick-deploy.sh 2>&1 | tee deployment.log
```

### Service Not Starting

```bash
# Check service status
systemctl status SERVICE_NAME

# View logs
journalctl -u SERVICE_NAME -n 50
```

---

## Next Steps

- [Container Management](11-CONTAINER-MGMT.md)
- [Debugging Guide](12-DEBUGGING.md)
- [Service Status](02-SERVICE-STATUS.md)
