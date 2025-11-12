# Rootless Podman Storage

Overlay-based Podman storage is no longer part of the deployment workflow. The
quick deploy script locks the driver to `vfs`, `btrfs`, or `zfs` during Phase 1,
and the diagnostics phase refuses to continue if an older overlay override is
still active. This keeps `nixos-rebuild` and `systemd` from mounting
`/var/lib/containers/storage/overlay` entries during boot. Phase 5 now pauses
container services automatically, attempts the cleanup steps below, and only
falls back to manual intervention when the automated run cannot proceed.

## Current behaviour

- `/etc/containers/storage.conf` is regenerated automatically so the system
  scope uses the filesystem-appropriate driver (typically `vfs` when no native
  driver is available).
- `~/.config/containers/storage.conf` is rendered by Home Manager so rootless
  Podman inherits the same decision, but silently falls back to `vfs` if the
  home directory cannot host the requested driver.
- Phase 1 diagnostics print the detected driver and block if an overlay driver
  is forced through overrides.

## Cleaning legacy overlay directories

If an older configuration left overlay layers behind, reset the stores once and
rebuild with the new templates applied:

```bash
# Rootless store (per user)
podman system reset --force
rm -rf ~/.local/share/containers/storage ~/.local/share/containers/cache

# System store (requires sudo)
sudo podman system reset --force
sudo rm -rf /var/lib/containers/storage
```

Re-run `./nixos-quick-deploy.sh --resume` afterwards so the regenerated
configuration keeps the supported driver. Once the rebuild completes you should
no longer see overlay mount units during boot or `podman info` output.

### Reset refuses to touch `/etc/containers/storage.conf`

`podman system reset --force` prints the warning shown below whenever a
manually edited `/etc/containers/storage.conf` exists:

```
A "/etc/containers/storage.conf" config file exists.
Remove this file if you did not modify the configuration.
```

The quick deploy workflow manages this file automatically, so it is safe to
move it out of the way and let Phase&nbsp;1 regenerate the driver settings:

```bash
if [ -f /etc/containers/storage.conf ]; then
    backup="/etc/containers/storage.conf.pre-reset.$(date +%Y%m%d-%H%M%S)"
    sudo mv /etc/containers/storage.conf "$backup"
fi
sudo podman system reset --force
```

After the reset completes re-run `./nixos-quick-deploy.sh --resume` so the
template logic writes a fresh `storage.conf`.

### `/var/lib/containers/storage/overlay` cannot be removed (`Device or resource busy`)

The `rm -rf /var/lib/containers/storage` step fails when overlay mountpoints are
still active. Unmount them before retrying the cleanup:

1. Stop Podman services and any quadlet units that may be holding references:

   ```bash
   for svc in podman podman.socket podman-auto-update.service; do
       sudo systemctl stop "$svc" 2>/dev/null || true
   done
   sudo systemctl list-units 'podman-*.service'
   ```

   Stop any remaining `podman-quadlet@<name>.service` instances reported by the
   final command.

2. Use `findmnt` to locate stale overlay mounts and detach them:

   ```bash
   sudo findmnt -rn -t overlay -o TARGET |
   while IFS= read -r target; do
       case "$target" in
           /var/lib/containers/storage/overlay/*/merged)
               sudo umount -lf "$target"
               ;;
       esac
   done
   ```

   Re-run the `findmnt` command until it no longer prints any
   `/var/lib/containers/storage/overlay/.../merged` paths.

3. Remove the storage directory once all mounts have been detached:

   ```bash
   sudo rm -rf /var/lib/containers/storage
   ```

With the directory removed, repeat `./nixos-quick-deploy.sh --resume` so the
generated NixOS configuration keeps the supported storage driver.
