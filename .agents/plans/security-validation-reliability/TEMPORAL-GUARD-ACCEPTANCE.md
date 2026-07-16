# Temporal Supply-Chain Guard — Independent Acceptance

Status: **PASS**
Reviewed: 2026-07-16
Implementer: Lorentz (bounded Codex sub-agent)
Independent reviewer: Huygens (separate Codex sub-agent)

## Frozen candidate

- `scripts/governance/check-flake-age.sh`
  - SHA-256: `33b80e32296bf6c202a1081989419824811be11940c08e348c23401017c61f68`
- `scripts/testing/test-check-flake-age.sh`
  - SHA-256: `599e040ee10d2272834e3626089b250020c35040d826322c35081a1aebe07b3d`

## Why the repair was required

The previous guard could not execute because Python-style triple quotes were invalid Bash. It also
used online-capable metadata resolution, unvalidated word splitting, hour-truncated comparison, and
untrusted Bash arithmetic. That left the mandatory 48-hour supply-chain policy unavailable exactly
while a five-input lock refresh was awaiting adjudication.

## Accepted behavior

- Invokes exactly `nix flake metadata --offline --json .`; it never fetches or refreshes inputs.
- Enforces the 48-hour boundary in seconds and classifies timestamps in jq under the exact-integer
  ceiling; untrusted timestamps never enter Bash arithmetic.
- Requires a valid, nonempty, rooted lock graph. Root alone may omit `locked`; every non-root node
  requires a non-null object and must be timestamp-bearing or an explicit path lock.
- Rejects malformed/blank metadata, unsafe names, negative/fractional/string/boolean/missing/overflow
  timestamps, future timestamps, unavailable dependencies, and hidden missing/null non-root locks.
- Sorts input names before emitting stable key/value evidence.
- Preserves a valid path-only graph as a deliberate `checked=0` pass.

Independent review found and caused correction of three successive fail-open defects: signed numeric
overflow, empty/invalid graph vacuous success, and hidden non-root nodes without lock evidence.

## Evidence

- Focused adversarial test: PASS.
- `bash -n` and ShellCheck on both files: PASS.
- Phase 5 production-hardening integration: 2/2 PASS.
- Scoped diff check: PASS.
- Real host offline audit: 22 timestamped inputs checked, zero violations; youngest observed input was
  nixified-ai at 54 hours.

This acceptance repairs the guard only. It does not accept or commit the held `flake.lock` and Home
Manager changes, authorize a NixOS deployment, or waive the remaining absolute Zsh `dotDir` repair
and atomic Nix-candidate validation.

VERDICT: PASS
