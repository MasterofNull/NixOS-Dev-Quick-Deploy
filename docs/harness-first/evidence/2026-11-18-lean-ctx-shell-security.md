# Harness-First Task Evidence

Date: 2026-11-18
Task ID: HF-20261118-lean-ctx-shell-security

## Objective
- Requested: owner directive 2026-11-18 to unblock all agent tools. Since #778 bumped lean-ctx to 3.12.4, its default shell allowlist blocks harness tools (aq-pin-watch, aq-update --dry-run, systemctl status, nixos-version) for every lane. The owner chose `shell_security = "warn"` (log and compress, never block).
- Delivered: option `mySystem.leanCtx.shellSecurity` (null | "enforce" | "warn" | "off", default null = unmanaged) in `nix/modules/core/options.nix`; set to "warn" in the ai-dev profile; activation script `leanCtxShellSecurity` (in `nix/modules/roles/ai-stack.nix`, which installs lean-ctx) that edits `~/.lean-ctx/config.toml` through `scripts/deploy/lean-ctx-set-shell-security.py`.
- Schema check: the lean-ctx 3.12.4 binary contains the key `shell_security`, its CLI hint `lean-ctx config set shell_security warn|off`, the block message `set shell_security = "warn" in your config.toml`, and the warn-only message `shell_security=enforce would block this command; it ran`. Valid values: enforce (default), warn, off. Top-level key.
- Editor semantics: replaces the top-level line if present, otherwise inserts before the first `[table]` header; other lines byte-identical; file created 0600 when absent; idempotent; `shell_allowlist` untouched.

## Workflow/Session IDs
- Workflow ID: n/a (bounded slice from orchestrator)
- Session ID: Simurg@claude/sonnet, orchestrator Simurg@claude/opus-5.5#da0ef470

## Delegation Decision
- Delegated by the orchestrator to a Claude sonnet implementer (Rule 17). Review is by a different lane (no self-review).

## Commands Executed
```bash
python3 scripts/testing/test-lean-ctx-shell-security.py
nice -n 19 nix eval .#nixosConfigurations.hyperd-ai-dev.config.mySystem.leanCtx.shellSecurity
nice -n 19 nix eval --raw .#nixosConfigurations.hyperd-ai-dev.config.system.activationScripts.leanCtxShellSecurity.text
bash scripts/testing/check-harness-first-static-gates.sh
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Validation Evidence
- Unit test (temp files): insert before first table, replace existing value, idempotent re-run, absent file created 0600, empty and no-trailing-newline files, mode preserved, invalid value rejected, all other content unchanged. Registered in `config/ci-checks.json` as `lean-ctx-shell-security`.
- `nix eval` shows the option resolves to "warn" for hyperd-ai-dev and the activation text renders (see commit/handoff output).
- Activation attestation: integrated (option + activation script in the ai-stack module); turned ON for ai-dev via `lib.mkDefault "warn"`; validated by the unit test and nix eval, live effect needs the owner's next `nixos-rebuild switch` (not run here); observable by `grep shell_security ~/.lean-ctx/config.toml` and lean-ctx's warn-only log line; intervenable by setting `mySystem.leanCtx.shellSecurity` to "enforce" or null; PM-tracked via this evidence file.

## Rollback Plan
- Set `mySystem.leanCtx.shellSecurity = null;` (unmanaged) or "enforce", rebuild; or `lean-ctx config set shell_security enforce` for an immediate runtime change (re-asserted by the next activation only while the option is non-null). Revert the commit to remove the script entirely.

## Residual Risk
- "warn" removes lean-ctx's blocking layer: commands outside its allowlist now run and are only logged. Claude Code permissions and the auto-mode classifier still gate commands, so the blocking layer is not gone overall, but lean-ctx is no longer a second independent gate.
- The activation script runs as root and writes into the user's home; it only touches `~/.lean-ctx/config.toml` and chowns the directory and file to the primary user. Failures are non-fatal (`|| true`).
- The key is edited line-wise, not with a TOML parser; an unusual file (multi-line strings containing a `[` at line start before any table) could mislead the table detection. Not expected for lean-ctx-written configs.

## Hint Feedback
- Hint IDs used: none (direct slice instructions).

## Source semantics (lean-ctx 3.12.4, rust/ in the v3.12.4 source)
- `shell_security` enforce|warn|off: `src/core/shell_allowlist/mode.rs:8-14` (enforce blocks; warn runs the same checks but only logs; off skips gating entirely, compression stays on). Aliases at `mode.rs:44-50`. Unknown value falls back to enforce (`mode.rs:76`).
- Chokepoint: `crates/lean-ctx-shell-policy/src/enforcement.rs:24-60` (`check_shell_allowlist`: Off -> Ok, Warn -> log and Ok, Enforce -> block).
- `shell_allowlist = []`: empty means blocklist-only, all programs pass (`enforcement.rs:154-157`; extras only apply when the base list is non-empty, `config.rs:25`); dangerous-pattern blocks still apply in enforce. It is not block-all. Unneeded here since warn/off already unblock programs.
- Config is not cached across calls: release builds read the passwd-home config.toml on each call, keyed by content hash (`src/core/config/shell_policy.rs:63-65`, `pinned_config` 198-247). Env overrides are ignored in release (`mode.rs:64-65`).
- Hook path under warn: `needs_enforcement_wrap` (`crates/lean-ctx-hooks/src/hook_handlers/file_rewrite.rs:315-327`) still wraps unlisted commands in `lean-ctx -c --raw`, which passes under warn via `check_shell_allowlist`; the CLI gate enforces only when that check returns Err (`src/shell/exec/execution.rs:363-372`).
- Live check after the owner set warn: `lean-ctx doctor` reports "Shell allowlist warn-only"; `systemctl --failed`, `nixos-version`, a nested `bash -c` and a python3 heredoc all ran through the Bash tool. Earlier blocks predate the edit.
