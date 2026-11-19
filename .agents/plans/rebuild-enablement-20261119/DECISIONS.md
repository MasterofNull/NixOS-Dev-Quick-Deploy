# Rebuild enablement decisions, 2026-11-19

Scope: make every change take effect on the next rebuild. Owner did not object to the Batch C defaults (enable aq-oncalld and auditd, keep microarchitecturalIsolation off).

## Gap A: invisible local toggles
The host's gitignored local deploy-options file (`deploy-options.local.nix` in the host dir) is untracked and imported through `builtins.pathExists` (flake.nix:273). A flake build from the git tree never sees it, so its toggles did not apply. Fix: plain feature booleans live in tracked `nix/hosts/hyperd/default.nix`; the local file keeps secrets wiring and per-machine overrides.

Findings:
- `agenticToolchain`: already true in a pure build (ai-dev.nix mkDefault true). The host line only makes it visible.
- `secrets.enable`, `sopsFile`, `ageKeyFile`: already true with the same paths in a pure build, from `p14s-amd-ai-workstation.nix:102-106` (mkDefault, derived from primaryUser/hostName). The local file's mkForce was redundant. Not moved. The sops file and age key exist on the host, and `sopsFile` is an external string path so no key material enters the build.
- `activationAutoRevert`: false in a pure build (ai-dev.nix mkDefault false). Now true in host config as a plain assignment, because two mkDefaults conflict.
- Consumption of the local file: default is pure (tracked config only). `nixos-rebuild --impure` or `aq-deploy-current` modes that pass --impure see the local file; it still wins via mkForce. Recommend the owner delete the three toggle blocks from the local file (leave the secrets block) so there is one source of truth.

## activationAutoRevert (ON)
- Risk: low. The sweep timer (60 s cadence, 1 min after boot) arms nothing. Nothing in nix, scripts or profiles auto-arms an activation (only the operator CLI `aq-activation-guard arm`). It cannot revert a healthy switch because no record exists to revert.
- Per-arm health timeout is a CLI argument (`sweep --health-timeout`, default 30 s; revert 60 s; unit TimeoutStartSec 5 min). When an operator arms a llama-dependent control, set `--window` at least 15 min so a 22 GB cold load is covered, and use a health check that tolerates a loading model.
- Cost: one oneshot per minute, negligible.
- Rollback: set false; armed records stop being swept.

## services.aiOncalld (ON)
- What it does: every 60 s reads the live journal through the triage engine, admits actionable incidents, claims them for a lane, and creates a local git worktree. Staged PRs are staged only. It contains no network, webhook, paging or push code (checked `scripts/ai/aq-oncalld` and `scripts/ai/lib/oncalld_engine.py`), so it stays local-only.
- Cost: MemoryMax 2G, CPUQuota 100% of one core, AppArmor profile in complain mode, secrets denied.
- Known limitation: the unit has ProtectHome=read-only with only the state dir writable. `git worktree add` writes `.git/worktrees` in the repo under /home, so worktree creation likely fails closed (WorktreeIsolationError, logged, incident skipped). Heartbeat, intake and triage still work. I did not widen the sandbox; widening ReadWritePaths to the repo `.git` is an owner decision. Verify after rebuild with `aq-oncalld --status`.
- Rollback: false.

## auditd (ON, narrowed)
- Enabled `mySystem.logging.audit.enable` with watchPaths limited to `/var/lib/aidb` and `/srv/patient-data`. The default list also watches postgres and redis data dirs with `-p rwxa`, which logs every DB file read; left out to avoid log churn. Exit statuses 1/255 are already tolerated so switch stays idempotent.
- Risk: the option docs warn of audit failure churn on some hardware/kernel combinations; this is a 7.3 kernel on a Renoir laptop. If journald shows audit backlog or desktop stutter, roll back.
- Cost: small CPU, auditd log growth in /var/log/audit.
- Rollback: false and rebuild; auditd stays loaded until reboot if rules were made immutable (they are not wired to `-e 2` here).

## Kept OFF
- `microarchitecturalIsolation`: forces nosmt and isolcpus 4-7 on an 8-core/16-thread APU already near 80 C and used for a 22 GB CPU-bound model. Large perf cost, low value on a single-user host. Revisit if untrusted agent code runs on this machine.
- Loki, promtail, remote syslog: need an owner-supplied remote host, storage and retention decision. `remoteSyslog` has no sane default host; exposeOnLan stays off.
- N3 network policy (networkPolicyObservability policy mode): asserted off until owner activation; can break egress/DNS.
