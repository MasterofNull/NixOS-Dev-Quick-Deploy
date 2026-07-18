# Implementation Authorization — Generic Flake Baseline Closure

Authorization ID: `auth-generic-flake-baseline-closure-20260718`
Idempotency key: `generic-flake:source-visible-hosts:20260718`
Status: **PREPARED_ONLY — ACTIVE ONLY AFTER INDEPENDENT EXACT-SUBJECT PASS**
Owner basis: standing preauthorization for bounded slices required to unlock and cleanly integrate the
system refactor.

Bound design SHA-256:
`9e460d8be33d98943a1e6a18067d3e737f945d246530c1e98e5b40fe3ea7a1be`.

Bound design-review SHA-256:
`8d7973ef69cec4627bd65c776b999f6902974a924b78db6905cdd9c590956c03`.

## Frozen baseline

1. `flake.nix`
   `00842dbc7e80b5ccd5bbc7b6c31916604a64a3704604564fda9fcdc78dd4b845`
2. `.github/workflows/test.yml`
   `dd4d682ed260d6b9ee1fa5b9094e8bdab75a01510c9b8259a85d8e785e5ee1d9`
3. `.agent/memory/issues-backlog.md`
   `f5822d7f47718f5c9e14a1496fccbf5e8f4294c2d115eb61e16f66540a1ece72`

Any predecessor mismatch is a hard stop. The issue backlog is already dirty with preserved findings;
the implementer must re-read it and narrowly update only the existing
`generic-nixos-ai-dev-flake-check-baseline` entry after validation.

## Exact grant

One bounded implementer may edit only the three files above to:

1. derive NixOS and Home Manager output hosts from one pure source-visible predicate requiring both
   `default.nix` and `facts.nix` in the same host directory;
2. preserve all existing `mkHost` facts, secret, RAM, firmware, and hardware assertions;
3. make CI enumerate actual exported NixOS/Home attributes, fail if the set is empty, require the
   three `hyperd-*` profiles, assert incomplete `nixos`/`sbc-minimal` profiles are not exported, and
   retain negative assertion coverage with expected messages; and
4. update only the named issue entry with measured closure evidence.

The implementation must prove Git-backed/offline flake enumeration and the three hyperd evaluations.
It must also prove local `path:${REPO_ROOT}` evaluation still sees generated facts without adding
those facts to Git.

## Consumption and acceptance

The first completed exact three-file candidate report consumes this grant. Interruption without a
completed candidate does not. The implementer may not stage, commit, deploy, delegate, or self-review.
Integration requires exact hashes, focused Nix/CI evidence, Tier-0, and independent exact-subject PASS
from another agent/session.

## Exclusions

No `flake.lock`, generated facts, `.gitignore`, host modules/defaults, deployment scripts, NixOS
activation, service restart, issue other than the named entry, or fourth file is authorized.

`RECORD: prepared single-use source-visible-host implementation lease.`
