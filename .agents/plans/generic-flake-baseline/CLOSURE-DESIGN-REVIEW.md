# Independent Review — Generic Flake Baseline Closure

Review date: 2026-07-18
Reviewer: Codex sub-agent `/root/generic_flake_design_review`
Role: independent read-only design reviewer
Subject SHA-256: `9e460d8be33d98943a1e6a18067d3e737f945d246530c1e98e5b40fe3ea7a1be`
Verdict: **PASS**

## Evidence

- Only `nix/hosts/hyperd/facts.nix` is tracked. The tracked `nixos` and `sbc-minimal` host defaults
  have ignored, source-invisible facts in a Git-backed flake.
- The current Git-backed flake check fails with the documented facts/secrets/RAM/firmware assertions.
- All three required `hyperd-*` profiles evaluate successfully; `sbc-minimal-ai-dev` fails as
  documented.
- Local deployment uses `path:${REPO_ROOT}`, so filtering on pure source-visible `default.nix` plus
  `facts.nix` preserves locally generated facts without weakening host assertions.
- The exact three-file implementation inventory is sufficient. There is no `flake.lock` change, so
  supply-chain lock review is not applicable.

## Implementation guards

The implementation must use the same pure host filter for NixOS and Home Manager outputs, preserve
all `mkHost` facts/hardware assertions, fail CI on an empty export set, require all three `hyperd-*`
profiles, exclude the incomplete `nixos` and `sbc-minimal` profiles from Git-backed exports, and keep
negative assertion tests. The dirty issue backlog must be re-read and patched narrowly. Generated
facts, `.gitignore`, modules, deployment behavior, and `flake.lock` remain excluded.

`RECORD: independent PASS for the exact generic-flake closure design; implementation requires a separate authorization.`
