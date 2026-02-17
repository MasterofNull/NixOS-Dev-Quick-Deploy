# Boot + Filesystem Resilience Guardrails

Last updated: 2026-02-16

## Purpose

Define deterministic operator actions for boot/login failures caused by filesystem integrity issues and unsafe live-switch conditions.

## Signature to Action Matrix

1. Signature:
`systemd-fsck-root`, `Dependency failed for /sysroot`, `has unrepaired errors`, `error count since last fsck`
Action:
- Do not run live `switch`.
- Boot rescue ISO.
- Run offline repair: `e2fsck -f -y /dev/disk/by-uuid/<root-uuid>`.

2. Signature:
Black screen/blinking cursor during live `nixos-rebuild switch` from desktop session.
Action:
- Run deploy from TTY (`Ctrl+Alt+F3`) or use boot staging mode.
- Use `scripts/deploy-clean.sh` default safeguards (GUI sessions auto-fallback to `boot` mode).

3. Signature:
Target evaluates to `multi-user.target` on desktop host.
Action:
- Stop deploy.
- Fix profile/role mapping so desktop hosts set graphical target.

## Operational Commands

1. Immediate integrity scan (current + previous boot):
```bash
./scripts/fs-integrity-check.sh
```

2. Show rescue flow with host-specific UUID:
```bash
./scripts/recovery-offline-fsck-guide.sh
```

3. Declarative deploy path:
```bash
./scripts/deploy-clean.sh --host <host> --profile <ai-dev|gaming|minimal>
```

## Declarative Guardrails Implemented

1. `fs-integrity-monitor.service` + `.timer`
- Journal signature scan after boot and periodically.

2. `disk-health-monitor.service` + `.timer`
- SMART/NVMe health scan on root disk.

3. Deploy preflight gates in `scripts/deploy-clean.sh`
- Previous-boot fs integrity signatures block live switch by default.
- Graphical host cannot deploy headless targets unintentionally.
- GUI live-switch auto-fallbacks to `boot` mode unless explicitly overridden.

4. Bootloader resilience defaults
- `boot.loader.systemd-boot.configurationLimit = 20`
- `boot.loader.systemd-boot.graceful = true`

## Research References

1. `e2fsck(8)` manual (filesystem checks/repair semantics): https://www.man7.org/linux/man-pages/man8/e2fsck.8.html
2. `systemd-fsck@.service(8)` manual: https://www.freedesktop.org/software/systemd/man/latest/systemd-fsck%40.service.html
3. `systemd.timer(5)` manual (`Persistent=` behavior): https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html
4. NixOS option reference (`boot.loader.systemd-boot.*`): https://search.nixos.org/options
5. `smartctl(8)` manual (SMART health): https://manpages.debian.org/unstable/smartmontools/smartctl.8.en.html
