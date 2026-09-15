# FT-2 independent review R0

Reviewer: Codex `/root/ft1_independent_acceptance`, non-author.
Disposition: REQUEST_REVISION, 2026-09-15.
Whole staged subject, unchanged before/after:
`39edf5f99e4a2dd8a94283aab2d1e74ea2faebe9d56d70133e601b8d4721c818`.

Sole blocker: explicit Rust/Go/Nix overrides reported READY build/test/lint
with available tools despite absent Cargo.toml/go.mod/flake.nix. This violates
the metadata-present readiness contract. Retain selected stack but report
UNCONFIGURED for stack-dependent commands when its marker is missing; test
with tool availability enabled. Secret scanning is independently available.

Passed: metadata-only six-stack/generic/mixed detection, no-subprocess tests,
missing tools, Python module UNCONFIGURED prerequisites, redacted scanner,
null-acceptance rejection, WARN wording, source/installed bundle self-test,
all 13 ShellCheck/Bash syntax checks and prior hook/PM invariants.

Nonblocking FT-3 hardening: bounded metadata reads and explicit symlink/non-UTF-8
handling. These do not broaden the bounded readiness correction. No reviewer
edits, staging, commits, activation or credit for unavailable lanes.
