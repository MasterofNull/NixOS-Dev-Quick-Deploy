# Activation signer provisioning (slice 2): Nix module, store-installed signer, tests

## Objective

Slice 2 of the activation signing MVP (design: `.agents/plans/system-integrity-recovery/ACTIVATION-PIPELINE.md` rev7; slice 1: `docs/harness-first/evidence/2026-10-30-activation-signing-core.md`). Provision the owner-side pieces the slice-1 verifier reads, and ship the signer: `nix/modules/services/activation-signing.nix`, `scripts/ai/lib/activation_signer.py`, tests. Nothing is activated by this slice: with no pinned public key nothing verifies.

## Workflow/Session IDs

- Branch `feat/activation-signer-provisioning` (worktree `.agents/delegation/worktrees/activation-signer`), from origin/main containing #671.
- Implementer: Claude Sonnet 5.5 sub-agent; uncommitted, left for orchestrator review (new files marked intent-to-add so flake evaluation sees them).

## Delegation Decision

Bounded single-slice implementation on the Claude balanced tier (Rule 17). Independent review is the orchestrator's to route; the implementer does not review its own work.

## Commands Executed

- `python3 scripts/testing/test-activation-signer.py`, `python3 scripts/testing/test-activation-chain.py`
- `nix-instantiate --parse` on the three changed/new `.nix` files
- `nix eval` of `environment.etc."aq-activation/{signers.json,deployment-id,eligible.json}".text`, `security.sudo.configFile`, the keygen unit `ExecStart`
- `nix build` of the `aq-activation-sign` package; smoke runs of the built wrapper (bad usage, no TTY, planted `PYTHONPATH` module)
- `python3 scripts/testing/test-hyperd-unattended-sudo-wildcards.py`
- `bash scripts/governance/tier0.d/check-ci-test-coverage.sh`, `./scripts/governance/run-ci-checks.sh --all --only activation-signer-test`

## Validation Evidence

- 16 signer tests pass: key mode 0400 and idempotent bootstrap; `--init-chain` verifies with slice 1 `load_chain` and refuses over a head or any segment; no TTY / unconfirmed / unpinned key refused with nothing written; end-to-end grant -> `activation_verified` True (and False for another closure); revoke then wave cannot clear, then individual regrant activates; request id (`../`, short, uppercase, overlong), op mismatch, ineligible item, subject mismatch, bad plan, wrong review digest, wrong closure, `MISSING:` attestation, manifest entry without units all refused; validation/review content binding; unit path rules (`/home`, unlisted checkout path, mutable Environment/EnvironmentFile/ReadOnlyPaths, empty and ExecStart-less output refused; manifest-declared paths accepted); symlink request/attestation not followed, private file refused; file swapped after display does not change signed bytes (signature and evidence copy hold the displayed snapshot); terminal escapes stripped from the display; crash between segment and head blocks all ACTIVATED, then the next signer run completes the head with no duplicate seq; `--recover` rebuilds a missing head and refuses a tampered segment.
- Slice 1 suite still passes (26 tests). `check-ci-test-coverage.sh`: PASS (760 tests, 616 declared). `activation-signer-test` registered in `config/ci-checks.json`, run in the CI `syntax` job next to `activation-chain-test`.
- Evaluated outputs (host `hyperd-ai-dev`): `signers.json` = `{"keys":[]}` (fail closed); `deployment-id` = `732ee68f390263049bdf66a3a61e6ae1` (derived from hostName + salt); `eligible.json` = `[]`.
- Evaluated sudoers lines (password required, no NOPASSWD, `timestamp_timeout=0` global):
  `hyperd ALL=(ALL:ALL) <store>-aq-activation-sign/bin/aq-activation-sign --init-chain, ... --recover, ... grant *, ... revoke *, ... wave-grant *` and `Defaults!<store>-aq-activation-sign/bin/aq-activation-sign env_reset`. `scripts/testing/test-hyperd-unattended-sudo-wildcards.py`: all PASS (68 NOPASSWD rules, all on the existing allowlist; allowlist untouched).
- Built `aq-activation-sign` runs under `env -i` and `python -I`: bad usage exit 2; no TTY refused (exit 1); a planted `activation_chain.py` on `PYTHONPATH` is ignored.
- Not exercised here (needs root and a rebuild): the oneshot writing `/var/lib/aq-activation/signing.key`, the real `sudo` prompt, and a live round trip.

## Rollback Plan

Set `mySystem.activation.signing.enable = false` (or revert the commit) and rebuild; the key and chain under `/var/lib/aq-activation` stay on disk (root-owned) and are not touched. Reverting does not restore any unsigned ACTIVATED path (slice 1 owns that). If a signing key is suspected leaked: move `signing.key` aside as root, let the oneshot generate a new one, pin the new public key and rebuild; keep the old key in `signerPublicKeys` only if old grants should stay valid (owner decision).

### Owner activation steps (after merge and rebuild)

All sudo steps are owner acts (fresh password each time).

1. Rebuild (`nrs` as usual). Confirm the key exists and is root-only: `sudo ls -l /var/lib/aq-activation/signing.key` should show `-r-------- root root`; `ls -ld /var/lib/aq-activation /var/lib/aq-activation/log` shows `root root drwxr-xr-x`.
2. Read the public key (world-readable): `cat /var/lib/aq-activation/signing.pub` (64 hex characters). Never copy `signing.key`.
3. Pin it in a PR: set `mySystem.activation.signing.signerPublicKeys = [ "<that hex>" ];` in the host or profile config (and, if the hostname may change, an explicit `mySystem.activation.signing.deploymentId`). Merge, rebuild. Verify: `cat /etc/aq-activation/signers.json` contains the key and `cat /etc/aq-activation/deployment-id` is the intended id.
4. Create the chain: `sudo aq-activation-sign --init-chain` from an interactive terminal; check the displayed deployment id and key, type the `sign <token>` it prints. The command refuses if any history exists; `ls /var/lib/aq-activation/log` should then show `0.json` and `cat /var/lib/aq-activation/head` the seq/hash.
5. Choose ONE eligible item (later): add it to `mySystem.activation.eligibleItems` (`{ plan; item; units; paths; state_paths; }`), rebuild, run the (future) `aq-activation-request`, then `sudo aq-activation-sign grant <request.json>`, read the displayed manifest entry, state paths and evidence, type the token. Confirm the board shows ACTIVATED (the projector must see the same closure; any later rebuild makes the grant `grant-stale`).
6. If something goes wrong: a head/segment mismatch blocks all ACTIVATED; run `sudo aq-activation-sign --recover`.

## Residual Risk

- Request file format is defined here (the `aq-activation-request` tool is a later slice): `{request_id, op, plan, item_id, subject, attestation_path, validation_path, review_path, review_digest, enable_evidence, detection_snapshot[, system_closure]}`; wave = `{request_id, op, wave_id, items:[...]}`; revoke = `{request_id, op, plan, item_id, subject}`. Attachments must be absolute, world-readable regular files (so the root-owned evidence copy discloses nothing new).
- The sudo rule allows `grant *`, `revoke *`, `wave-grant *` with free arguments (design said exactly one argument); the signer validates the argument count itself and a fresh password is still required.
- Unit check is static: the item's `ExecStart*` `path=`/`argv[]=`, `Environment`, `EnvironmentFile`, `ReadOnlyPaths`, `ReadWritePaths`, `WorkingDirectory` must reference only `/nix/store/...` or manifest paths and never `/home`. Strict by design: `/run/wrappers`, `/run/current-system` and URL arguments are refused. A store binary can still read undeclared mutable state (honest limit from the design).
- `deployment-id` derives from `networking.hostName`; renaming the host invalidates the chain. Pin an explicit `deploymentId` before `--init-chain` if the hostname may change.
- Verifier side not done: the verifier still reads `/etc/aq-activation/signers.json` from the checkout projector rather than the store-installed verifier; `unverified-checkout` marking and evidence-copy baseline recompute remain slice 3. The signer writes the evidence copy (`/var/lib/aq-activation/evidence/<seq>/` with `envelope-digests.json`) but nothing rehashes it yet.
- Not implemented (deferred): attestation six-dimension parser and dated-deferral check (the signer only refuses `MISSING:`; `aq-activation-request` owns the format); strace/inotify no-checkout-writes test (the signer has no checkout path, but this is untested under root); concurrent-signer race test (exclusive `flock` is used but only exercised single-process); effective-authority audit script for the live system.
- The keygen oneshot has a `CAP_DAC_OVERRIDE`-class bounding set and runs as root on every boot but only creates the key if absent.

## Hint Feedback

No aq-hints were queried; the design SSOT and slice 1 evidence were read directly.
