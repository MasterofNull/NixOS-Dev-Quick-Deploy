# Evidence — factory kit K3 (aq-factory init + doctor lifecycle) — 2026-10-17

Plan: `.agents/plans/software-dev-factory-rollout/DESIGN.md` (v2.3 owner simplification note).

## Objective
Wire `aq-factory init` and `aq-factory doctor` via the existing installer (`scripts/ai/lib/factory_gate_install.py`) sourcing `templates/factory-kit/`, with local user identity enforcement (no maintainer-signed tags/orphan release).

## Changes
- `scripts/ai/aq-factory`: preserves `skill` subcommand while adding `init` and `doctor`.
  - `init`: validates git repository, checks cleanliness, enforces local git user identity (`user.name`, `user.email`, and `owner_handle` validated against B2 regex), generates preview, installs from `templates/factory-kit`, generates `.factory/kit.lock` + `.factory/kit.toml` (without absolute paths or raw name/email; safe TOML escaping via json.dumps), and configures `core.hooksPath`.
  - `doctor`: read-only verification of platform (WSL/POSIX), lock/receipt integrity, active executable hooks, host path leakage scan across `.githooks` and `.factory`, required tools on PATH, and absence of foreign hook managers.
  - CLI backwards compatibility: legacy positional invocation `aq-factory <name> "<purpose>" [--root <dir>] [--dry-run]` transparently routes to `skill`.
  - Fail-closed REPO_ROOT resolution without any fallback to owner/host-specific paths.
- `scripts/testing/test-factory-kit-k3.py`: validates skill preservation, legacy CLI positional compatibility, identity enforcement fail-closed behavior, owner handle validation, TOML validity with quoted/special strings, leak-free `.factory/kit.toml`, preview/init/doctor lifecycle, and idempotency.

## Validation
- `python3 scripts/testing/test-factory-kit-k3.py` — PASS
- `python3 scripts/testing/test-factory-kit-k2.py` — PASS (`K2 OK: clean kit passes; 6 plants fail`)
- `python3 scripts/testing/test-factory-kit-k1.py` — PASS
- `python3 scripts/governance/check-factory-kit-clean.py` — PASS (`factory-kit clean`)
- `bash /home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/delegation/outputs/k3probe.sh "$PWD"` — PASS

## Review Record
Author-lane: antigravity
Review-Disposition: PASS (incorporating Claude review findings 1-7)
Reviewed-by: claude

## Activation (Rule 15)
- Integrated: `aq-factory init` and `aq-factory doctor` are live CLI subcommands in the running harness.
- Turned ON: runnable directly via `scripts/ai/aq-factory`.
- Validated: automated lifecycle tests pass with isolated git config fixtures and probe scripts.
- Observable: `aq-factory doctor` prints structured OK/WARN/FAIL status and json output.
- Intervenable: configuration editable via `.factory/kit.toml` and CLI flags.
- PM-tracked: `.agents/plans/software-dev-factory-rollout/tracker.json` item `k3`.
