# Evidence — factory kit K2 (template dir + clean-scan) — 2026-10-16

Plan: `.agents/plans/software-dev-factory-rollout/DESIGN.md` (v2.3 owner simplification note).

## Owner decision (2026-10-16)
Git repo + auth come from each local user's own sign-in/config at system init and deployment; the template carries no owner account info. Maintainer-signed tags, orphan release commits, signer anchor/rotation and signature verification are dropped (DESIGN sections 1.1-1.4, T4b/T6/T6b/T9, `aq-factory release`, "Owner key" decision marked SUPERSEDED). A first signed-release K2 implementation was built, reviewed, then discarded on this decision (archived, not staged).

## Changes
- `templates/factory-kit/`: kit template seeded from `templates/factory-gate-bundle/` (old bundle untouched).
- `scripts/governance/check-factory-kit-clean.py`: fails on owner identity strings (case-insensitive, byte-level, `--deny-string` extras), `/home/` and `/run/current-system` paths, deny filenames (secrets*, *sops*, .env/.env.*, *.local.nix, id_*, *.pem, *.key, *.p12, *.pfx, *.kdbx, *.age, credentials*, .netrc, .npmrc, *.pyc, .gitleaks*), symlinks, missing kit dir; runs gitleaks, fail-closed when absent (`--no-gitleaks` for tests only).
- `scripts/testing/test-factory-kit-k2.py`: real kit passes; 6 plants fail (owner string, uppercase owner string, `/home/x`, `secrets.nix`, symlink, `server.key`).
- DESIGN v2.3 note; tracker.json K2/K3 editorial text (no hand-typed status).

## Validation
- `python3 scripts/testing/test-factory-kit-k2.py` — `K2 OK: clean kit passes; 6 plants fail`.
- `python3 scripts/testing/test-factory-kit-k1.py` — PASS.
- `python3 scripts/governance/check-factory-kit-clean.py` — `factory-kit clean`, rc=0 (gitleaks present).
- `check-factory-kit-clean.py --no-gitleaks /nonexistent` — rc=2.

## Review
Independent reviewer (claude-sonnet, separate instance from implementers): PASS_WITH_FOLLOWUPS on subject ac66e0ca...; 4 scan false-negative followups RESOLVED (haiku implementer) and verified by orchestrator rerun -> PASS. Final staged code subject sha256 7cbe0afc6352be808bdb6edd66547fbade1e1abd4ad54a0a0e2e4bedda8575c8 (this evidence doc added after, docs only). Cross-lane confirmatory review queued.

## Activation (Rule 15)
- Integrated: kit template is the source for K3 `init`/`doctor` (existing installer); scan runnable standalone now.
- Turned ON: scan available now; CI/tier0 wiring of the scan = K4 (deferred, dated 2026-10-16).
- Validated: fixture test above against the real kit and planted temp copies.
- Observable: scan prints each violation with path; K4 adds CI surface (deferred 2026-10-16).
- Intervenable: `--deny-string` extension; template edits via PR.
- PM-tracked: `.agents/plans/software-dev-factory-rollout/tracker.json` item factory-kit-k2.
