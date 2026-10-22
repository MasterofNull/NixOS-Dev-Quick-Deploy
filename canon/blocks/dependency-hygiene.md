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
