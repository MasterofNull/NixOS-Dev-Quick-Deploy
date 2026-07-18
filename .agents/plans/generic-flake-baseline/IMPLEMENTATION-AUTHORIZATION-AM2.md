# Implementation Authorization AM2 — Source-Complete Package Baseline

Authorization ID: `auth-generic-flake-baseline-closure-am2-20260718`
Idempotency key: `generic-flake:source-visible-hosts:am2-package-baseline:20260718`
Parent: `auth-generic-flake-baseline-closure-am1-20260718`
Status: **PREPARED_ONLY — ACTIVE ONLY AFTER INDEPENDENT EXACT-SUBJECT PASS**
Owner basis: standing preauthorization for bounded refactor gating tasks.

AM1 completed, was independently accepted, and consumed. Its integration commit was blocked by the
package-count focused gate because `config/package-count-baseline.json` still records the six
incomplete outputs that the accepted source-visible flake intentionally no longer exports.

## Frozen accepted candidate and baseline

1. `flake.nix`
   `e92118fb6e369ac59d79df42290f9c7809a0e524995da5b94d06537f9389af0d`
2. `.github/workflows/test.yml`
   `f7692d30fade13adb9e936da3ac17d8775ae6d1de006a5b2c58b0d3bc14454ff`
3. `.agent/memory/issues-backlog.md`
   `7378977d2e2a2e11b001690959353e1624da92bea3a4e3f1fee15daf860f5f4c`
4. `config/package-count-baseline.json`
   `93866f03d045acd7da2fc5bc2dc8d31317edffe9e1cd81da85575d0e89e7af8f`

Files 1-3 are frozen and must not change under AM2.

## Exact baseline-only grant

One bounded implementer may edit only file 4 using the canonical package-count generator. The new
baseline must contain exactly the Git-backed exported targets:

- NixOS: `hyperd-ai-dev=367`, `hyperd-gaming=270`, `hyperd-minimal=170`;
- Home: `hyperd=67`, `hyperd-hyperd=67`;
- combined: `hyperd-ai-dev=434`, `hyperd-gaming=337`, `hyperd-minimal=237`;
- summary target counts 3 and 2, with values derived mechanically from those exact entries.

The implementer must prove the package-count gate passes, the five derivations still evaluate, the
baseline contains no incomplete `nixos-*`/`sbc-minimal-*` target, JSON/diff hygiene pass, and the full
focused/Tier-0 gates pass. Any package change, count drift beyond the measured values, or second-file
change requires AM3.

## Consumption and exclusions

The first completed exact four-hash report consumes AM2; interruption without completion does not.
No staging, commit, deployment, delegation, or self-review. Independent exact-subject acceptance is
mandatory.

No package list, Nix/module/lock, generated facts, workflow/flake/backlog change, deployment/runtime,
or fifth file is authorized.

`RECORD: prepared single-use mechanical package-baseline refresh lease.`
