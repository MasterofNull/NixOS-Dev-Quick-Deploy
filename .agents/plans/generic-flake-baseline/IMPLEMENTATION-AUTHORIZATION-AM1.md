# Implementation Authorization AM1 — Generic Flake Review Corrections

Authorization ID: `auth-generic-flake-baseline-closure-am1-20260718`
Idempotency key: `generic-flake:source-visible-hosts:am1:20260718`
Parent: `auth-generic-flake-baseline-closure-20260718`
Status: **PREPARED_ONLY — ACTIVE ONLY AFTER INDEPENDENT EXACT-SUBJECT PASS**
Owner basis: standing preauthorization for bounded slices required to complete the refactor gates.

The parent grant was consumed by a completed candidate that received `REQUEST_REVISION`.

## Frozen candidate

1. `flake.nix`
   `e92118fb6e369ac59d79df42290f9c7809a0e524995da5b94d06537f9389af0d`
2. `.github/workflows/test.yml`
   `54dd63b8de79d2ba5b5098d2520775a769a6225dbb3cc65905a01b6e568f9404`
3. `.agent/memory/issues-backlog.md`
   `9cb29c9b0e6e532be4b2304756808b28907e9364ff16995e463e04624df451e8`

Any mismatch is a hard stop. `flake.nix` is frozen and must not change under AM1.

## Exact correction grant

One bounded implementer may edit only files 2 and 3 to:

1. bind every negative module assertion to the Git-backed flake installable rather than
   `builtins.getFlake (toString ./.)`, so ignored local overrides cannot change the tested source;
2. preserve and explicitly validate the existing `set -euo pipefail` fail-fast boundary for the
   profile/positive/negative evaluation step;
3. restore clean-runner input hydration with an online `nix flake show --no-write-lock-file .` before
   the offline no-build check and subsequent offline evaluations;
4. remove the prohibited `rm -rf` trap. Temporary negative-test evidence may remain in the ephemeral
   runner temp directory; no repository path may be deleted; and
5. keep the named backlog issue `DONE` only after the corrected workflow commands all pass, revising
   its evidence if necessary while byte-preserving every other backlog change.

The secrets, RAM, and firmware negatives must each fail with their exact expected message. All
Git-backed exports/positives, local `path:.` discovery, YAML/Nix parsing, and diff hygiene must be
rerun. If any production Nix or third-file correction is required, stop and request AM2.

## Consumption, acceptance, and exclusions

The first completed exact three-hash report consumes AM1. Interruption without a completed report
does not. No staging, commit, deployment, delegation, or self-review. Integration requires an
independent exact-subject PASS and Tier-0.

No `flake.nix`, `flake.lock`, generated facts, `.gitignore`, host modules/defaults, deployment/runtime,
unrelated issue, destructive cleanup, or third changed file is authorized.

`RECORD: prepared single-use workflow-and-evidence correction lease.`
