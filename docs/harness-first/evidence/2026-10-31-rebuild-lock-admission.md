# Rebuild lock admission — 2026-10-31

Recorded 2026-10-31T20:00:42.685682+00:00. Owner-authorized isolated repair in `/tmp/rebuild-lock-20261031`; base `a50d83178cc644e97cbbf8fe4154105ccae650ed` (`origin/main`). Scope: existing `.agent/PROJECT-REBUILD-BREAKPOINT-PRD.md`, lock candidate, and this evidence. No commit, push, tier0, rebuild, or activation was performed.

## Exact candidate and preservation

- Candidate `flake.lock` SHA256: `20e8cf27a103bd22f8f80ad6bc5130f14074f69b429f5fa8ff6d30da9bca533d`.
- Lock-only `git diff --binary -- flake.lock` SHA256: `82927f9fa743f999278fbe39db61f5588c91cb6a6e18f92720909896d2e34234`.
- Owner main lock and `/tmp/rebuild-breakpoint-20261031/flake.lock.preserved` both retain SHA256 `f7c66441b633f31459ba215edfa9c51357fce88f63df0a3dad5c8cdf506890cf`; neither was written.
- Exactly three whole nodes (`nixified-ai`, `nixos-hardware`, `nixpkgs-unstable`) were restored from the base lock. Only `nixpkgs_5` differs from base: owner revision `6f06d204d8f2d8761d9da78778745974a3216381`, modified `2026-10-29T17:25:25Z`, eligible from `2026-10-31T17:25:25Z`. No graph edges, timestamps, policy, or dependency declarations were invented or changed.

## Deferred owner updates

The preserved full owner lock retains these newer pins. Their earliest 48-hour eligibility is below; elapsed age alone does not replace the remaining admission/build checks.

| Node | Restored revision | Deferred owner revision | Earliest eligibility (UTC) |
| --- | --- | --- | --- |
| nixified-ai | 46653bcb771564293be6902832ab074473643b8f | dedd2be9fe0db7bce66b00ad6e595c6b89afd5d2 | 2026-11-01 11:30:44 |
| nixos-hardware | b6754c901c21478fd8450d62101e712b2a4f0d75 | 04c6b94fa104bc23650983a4513aea196794d321 | 2026-11-01 10:18:29 |
| nixpkgs-unstable | 31ecbaca1bdefa45dffc409f0250bd8039ea0010 | 1c89083e451e891152365b799595cf7790a43325 | 2026-11-01 06:21:25 |

## Validation against the candidate lock

Commands ran through `lean-ctx -c --raw`, with bounded output and no paid inference.

- `scripts/governance/check-flake-age.sh`: exit 0, offline mode, minimum 48 hours, `RESULT status=pass checked=22 violations=0`. Restored nodes reported ages 83, 66, 101 hours; retained `nixpkgs_5` 50 hours.
- `git diff --check`: exit 0.
- `nix eval --raw .#nixosConfigurations.hyperd-ai-dev.config.system.build.toplevel.drvPath`: exit 0; `/nix/store/8dv2pys6vkgi7gs93g7qc26x4rv1arkn-nixos-system-hyperd-26.05.20261029.6f06d20.drv`.
- `nix eval --raw .#homeConfigurations.hyperd.activationPackage.drvPath`: exit 0; `/nix/store/vpza8bpp67l55xjkxncfgfxhqxm5zvi1-home-manager-generation.drv`.
- System/HM evaluation ran concurrently after the previous four-input candidate evaluation had ended. System evaluation emitted an ignored SQLite eval-cache busy notice and then completed successfully. Both emitted the expected dirty-tree warning. No warning suppression or cache workaround was used.
- Post-audit candidate hash remained identical. The previous four-input candidate system derivation supplied by the orchestrator (`/nix/store/qmdwxgzc3h2gzncf1w82ll6zwh4d8pcd-nixos-system-hyperd-26.05.20261029.6f06d20.drv`) is a different subject and is not used as this candidate's validation.

## Execution and limits

Minimal-code ladder rung 2: reuse the existing committed lock nodes; no new implementation or dependency. A cheapest-worker dispatch to `gpt-6-luna` was attempted by the orchestrator but rejected by the thread limit; this available lane handled the explicitly authorized mechanical substitution. Independent acceptance remains with the orchestrator/reviewer.

These results establish age admission and system/Home Manager evaluation for the identified lock. The closure checks below add system dry-build and actual Home Manager build evidence. They do not establish a successful actual system build, runtime QA, release acceptance, or activation. The owner's original update remains available unchanged for later admission. PULSE is local ignored process evidence and is excluded from staging.

Process friction: the first direct `git add` was blocked by the compact-output PreToolUse hook before execution; the requested `lean-ctx -c --raw` invocation succeeded. No approval or policy was bypassed.

## Closure validation (owner-requested follow-up)

- `nix build --dry-run .#nixosConfigurations.hyperd-ai-dev.config.system.build.toplevel`: exit 0; 65 derivations would build, seven cached paths would fetch (215.6 MiB download, 732.9 MiB unpacked). Planned system derivation `/nix/store/d6shp58n6aj04cfid4rmwydjflj8620m-nixos-system-hyperd-26.05.20261029.6f06d20.drv`. This is dependency planning, not proof those system derivations build successfully.
- `nix build --no-link --print-out-paths .#homeConfigurations.hyperd.activationPackage`: exit 0; nine derivations built and five cached paths fetched (208.8 MiB download, 715.8 MiB unpacked). Realized generation `/nix/store/9qbp9d1gflz72jfkc0c1xwd0nffsz6d8-home-manager-generation`, from previously evaluated derivation `vpza8bpp67l55xjkxncfgfxhqxm5zvi1-home-manager-generation.drv`. No activation was invoked.
- These closure commands used the staged plan/initial evidence/lock subject whose `git diff --cached --binary` SHA256 was `9c2c2fb3628822cf9cfebe9e96933c3e775461df820bb78b455cba08c13ae7c4`. The system derivation differs from the earlier pre-staging evaluation because staging plan/evidence changes the Git flake source. This final closure receipt is a subsequent documentation-only update; the candidate lock remains exactly `20e8cf27a103bd22f8f80ad6bc5130f14074f69b429f5fa8ff6d30da9bca533d`. No closure check is represented as testing a later documentation hash.
- The system dry build also printed one ignored eval-cache SQLite busy notice while concurrent Home Manager evaluation was active, then passed. No cache mutation/workaround was applied.
- `git write-tree` readback attempted through a Python subprocess was denied by the read-only shared `.git/worktrees/.../index.lock` boundary; exact receipt identification therefore uses the staged binary diff SHA256. The successful authorized `lean-ctx` staging path was used; no permissions or index location were changed.
