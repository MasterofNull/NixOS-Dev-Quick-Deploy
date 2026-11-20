# Gate-Triggered Dependency Hygiene Ladder (Canonical — all agents)

<!-- SSOT: .agents/plans/sota-rounding/DESIGN.md W7 (owner directives 2026-10-14) -->

### Trigger
ONLY a failing security gate (pip-audit, npm audit, grype, dependency-cve), strictly scoped to the implicated package. No unsolicited broad dependency audits or sweeping lockfile rewrites.

### Decision Ladder
1. **Fixed Release Available**: Raise the package version floor immediately to the fixed release.
2. **Active Upstream, Fix Unreleased**: Mitigate our code usage + add a time-boxed exception in `config/security-exceptions.json` (<=90 days; expiry strictly blocks the gate).
3. **Abandoned / Stale Upstream** (no release/commits >18 months, archived repo, OpenSSF Scorecard `Maintained` low, or unresolved maintenance issue):
   - Migrate to an **actively maintained replacement** with equivalent parity (maintained fork, standard alternative, or standard library for minimal footprints).
   - Bridge with mitigation + time-boxed exception until migration lands.
4. **Upstream Contribution**: Upstream PRs/help for active open-source projects must be owner-authored and adhere to a propose-not-push policy.

### Release-Note Review on Every Version Change (owner directive 2026-11-19)
This applies to every pin bump (`nix/pins/*.json`), flake input refresh (`aq-update`, `flake.lock`), and package or model swap, not only to security-gate work. Do it before the change lands and before any rebuild or reboot.
1. **List what moved**: get the old -> new version of each package that the change touches and that we configure or run as a service (closure diff, e.g. `nvd diff` or `nix store diff-closures` on the old and new system, plus the pin/lock diff).
2. **Read upstream release notes / changelog / breaking-change list** for the whole range, not just the newest release. Look for removed or renamed CLI flags and options, changed defaults, config or schema changes, data or on-disk format migrations, dropped hardware or driver paths, and new auto-tuning behaviour.
3. **Adapt our system in the same PR**: update Nix modules, unit flags, configs, and scripts for each relevant change, then build the affected units and grep the result for the new flags. A rebuild must not be the first point where a removed flag or changed default shows up.
4. **Validate with the real live config**: use the production model, flags, and hardware path, not a smaller stand-in. A side instance is fine.
5. **Record it**: the PR body gets an "Upstream changes reviewed" list (package, version range, relevant changes, our adaptation, or "none relevant"). If notes are missing or too vague, say so and widen the live validation.

Example: llama.cpp b9222 -> b12503 (#806) replaced `--mmap`/`--mlock` with `--load-mode` and changed the default to `auto`. That default dropped mmap on the Renoir iGPU. The bump was validated only on the small embedder, so the 35B service failed after the rebuild with "Vulkan device lost", and `--mlock` became an invalid argument. Evidence: `docs/harness-first/evidence/2026-11-19-llama-cpp-b12503-load-mode-mmap.md`.
