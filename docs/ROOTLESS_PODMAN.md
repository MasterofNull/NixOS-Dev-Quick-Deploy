# Rootless Podman Storage

The quick deploy script now defaults to the `overlay` storage driver, which
provides the best performance on most filesystems using `fuse-overlayfs` for
rootless operation. Alternative drivers (`vfs`, `btrfs`, `zfs`) are also
supported and can be selected during Phase 1 or via the
`DEFAULT_PODMAN_STORAGE_DRIVER` environment variable.

Phase 5 pauses container services automatically before the system switch and
attempts automated storage cleanup if a driver mismatch is detected. You can
re-run the diagnostics any time via `./scripts/system-health-check.sh --detailed`.

## Current behaviour

- `/etc/containers/storage.conf` is regenerated automatically during
  `nixos-rebuild switch` with the selected driver (default: `overlay`).
  A timestamped backup is archived in `~/.cache/nixos-quick-deploy/backups/`.
- `~/.config/containers/storage.conf` is rendered by Home Manager so rootless
  Podman uses the same driver, with `fuse-overlayfs` providing overlay support
  for unprivileged containers.
- Phase 1 diagnostics print the detected driver and allow selection of
  `overlay`, `vfs`, `btrfs`, or `zfs`.

## Kernel user namespace prerequisites

- Upstream kernels (including the stock NixOS builds) expose
  `user.max_user_namespaces` instead of the Debian-specific
  `kernel.unprivileged_userns_clone` toggle. Any positive value (the default is
  usually `65536`) satisfies the diagnostics.
- Debian and Ubuntu kernels ship the `kernel.unprivileged_userns_clone`
  sysctl—set it to `1` via `sudo sysctl -w kernel.unprivileged_userns_clone=1`
  or declaratively through NixOS.
- When neither sysctl is present or they evaluate to `0`, the diagnostics halt
  with remediation instructions because rootless Podman cannot start without
  user namespaces.

## Switching storage drivers

If you need to switch between storage drivers (e.g., from `vfs` to `overlay`
or vice versa), you must clean the existing storage first:

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
no longer see overlay mount units during boot or `podman info` output. If the
health check still reports overlay usage, run `./scripts/system-health-check.sh --detailed`
and inspect the Podman section for remediation steps.

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
