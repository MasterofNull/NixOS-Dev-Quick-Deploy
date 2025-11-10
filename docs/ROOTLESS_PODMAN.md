# Rootless Podman Diagnostics and OverlayFS Recovery

The deployment flow now includes automated checks for rootless Podman so that
`nixos-rebuild switch` is no longer blocked by overlay mount failures such as
`overlay: mount: invalid argument` or stuck directories ending in `/merged`.
This document summarises what the new diagnostics cover and how to remediate the
common issues they surface.

## What the new validator does

* **Phase 4 pre-flight checks** call `run_rootless_podman_diagnostics` to ensure
  user namespaces, subordinate ID ranges, and Podman helpers are all in place.
* Kernel support for OverlayFS `metacopy` is detected automatically. When the
  feature is missing the configuration falls back to `nodev` mount options and
  logs an actionable warning instead of attempting an unsupported mount.
* System storage (`/var/lib/containers`) and user storage
  (`~/.local/share/containers`) are inspected for incompatible filesystems:
  - XFS volumes with `ftype=0` are flagged as blocking errors because OverlayFS
    cannot operate on them.
  - `tmpfs` mounts are rejected for persistent storage.
  - ZFS volumes that do not expose `acltype=posixacl` are highlighted with
    remediation guidance.
* Rootless storage trees are scanned for stale `overlay/.../merged` directories
  that usually accompany interrupted container clean-ups. The validator prints
  the first path it finds so that you can clean the mount manually or by using
  `podman system prune`. When mounted entries are detected the validator now
  attempts to unmount them automatically, remove the hashed overlay directory,
  and run `podman system reset --force` (with sudo for the system store) to
  rebuild the Podman storage metadata.

## Required fixes when the validator fails

| Failure | Why it matters | How to fix |
| --- | --- | --- |
| `kernel.unprivileged_userns_clone` ≠ 1 | User namespaces are disabled, preventing any rootless containers | The generated `configuration.nix` enables the sysctl, but ensure the value is not overridden elsewhere. |
| Missing `fuse-overlayfs` | Podman falls back to the kernel overlay driver, which fails for rootless setups on NixOS | Keep `virtualisation.podman.extraPackages = [ slirp4netns fuse-overlayfs ];` and rebuild. |
| `podman` group absent or user not a member | Rootless socket activation cannot drop privileges | Regenerate configs so `users.groups.podman` exists and your user stays in `extraGroups`. |
| No subordinate UID/GID ranges | User namespaces cannot map container IDs | Leave `autoSubUidGidRange = true;` enabled or add explicit `subUidRanges`/`subGidRanges`. |
| XFS `ftype=0` | OverlayFS cannot create upper layers, leading to `/merged` remnants | Reformat the filesystem with `mkfs.xfs -n ftype=1` and restore data from backup. |
| ZFS `acltype` not `posixacl` | Fuse OverlayFS needs POSIX ACL support | Run `zfs set acltype=posixacl <dataset>` on the dataset that backs your home. |

## Cleaning up `/merged` directories

Stale overlay trees typically live under one of these paths:

```
/var/lib/containers/storage/overlay/*/merged
~/.local/share/containers/storage/overlay/*/merged
```

You can safely remove a stale mount with Podman:

```
podman rm --force --all
podman system prune --volumes
```

If Podman refuses to clean the directory because the mount is still active, use
`findmnt` to identify the mount point and unmount it manually:

```
sudo findmnt --target /var/lib/containers/storage/overlay/<hash>/merged
sudo umount /var/lib/containers/storage/overlay/<hash>/merged
```

## Related files

* `lib/common.sh` now exports `run_rootless_podman_diagnostics` together with
  storage helper utilities.
* `phases/phase-04-pre-deployment-validation.sh` runs the validator so a failed
  pre-flight stops the deployment before `nixos-rebuild switch` is attempted.
* `templates/configuration.nix` and `templates/home.nix` generate storage
  configuration that respects the detected OverlayFS capabilities.
