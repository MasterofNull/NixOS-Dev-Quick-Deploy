# Package refresh 2026-11-18

Owner-directed release refresh from `aq-pin-watch check`. Three local packages were bumped, one commit each, built serially with `nice -n 19 nix build` and smoke-tested. Two scanners and one MCP server are deliberately not bumped. Host load was 45-70 during builds, so each build ran alone.

## 1. lean-ctx 3.12.4 -> 3.12.6

Pinned in `nix/pkgs/lean-ctx.nix` (src hash and cargoHash refreshed). Build passed on the second attempt: the first run used a placeholder cargoHash to learn the real one, which is the normal procedure, not a failed build. Smoke: `lean-ctx --version` prints `lean-ctx 3.12.6 (source)`; `lean-ctx read <file>` returns the file.

Changelog findings (v3.12.5 and v3.12.6 releases plus the v3.12.4...v3.12.6 diff): no change to shell_allowlist or shell_security semantics. Relevant shell-policy changes are limited to #2236: on musl builds without NSS, the shell gate now finds the home directory via `getent passwd`, so the user's `config.toml` is read; our glibc build is unaffected. `lean-ctx doctor` now reports when the allowlist runs on defaults. The policy source is still resolved once per process, so a config edit still needs an MCP reconnect or restart; nothing in 3.12.5/3.12.6 adds config reloading. Other changes: config backups (`*.bak`) are now written without following symlinks; `ctx_multi_repo` root limit is configurable; `ctx_knowledge recall` gains limit/offset; `ctx_glob` bounds its walk; `ctx_read` task mode no longer runs for hours on large files (useful given the old CPU spikes); an opt-in shared parse cache is off by default. Nothing silently introduces a new allowlist.

## 2. opencode 1.19.5 -> 1.19.6

Pinned in `nix/pkgs/by-name/opencode/package.nix` (src hash and node_modules outputHash refreshed). Built against the bumped models-dev. Smoke: `opencode --version` prints `1.19.6`; `--help` renders. The release adds an OpenCode 2.0 upgrade prompt on desktop (not used here) and fixes oversized image requests. Plugins written for OpenCode 1 are unaffected by this patch.

## 3. models-dev a5458bdc -> d893237f

Pinned in `nix/pkgs/by-name/models-dev/package.nix`; version string is now `0-unstable-2026-11-18`. The node_modules outputHash is unchanged (lockfile unchanged), confirmed by the hash-mismatch probe. Built; `dist/_api.json` is valid JSON with 324 provider keys. opencode builds against it.

## 4. osv-scanner 2.2.4 -> 2.7.1: not bumped

There is no local package to bump. osv-scanner comes from nixpkgs (`pkgs.osv-scanner` in `nix/modules/roles/ai-stack.nix`). The `pinned_version` in `config/agent-capability-intake-candidates.json` is stale metadata (2.2.4); the installed binary is 2.3.3 and nixos-unstable has 2.7.0, not 2.7.1. Moving to the new versions needs a nixpkgs/flake refresh or an override package, which is outside a package-pin bump. Our invocation, `osv-scanner scan source .`, is still valid on the installed binary (`scan source --help` works). Recommendation: take it through the next flake refresh, then re-test and update the intake metadata.

## 5. trivy 0.66.0 -> 0.76.2: not bumped

Same situation: trivy comes from nixpkgs via `nix/data/profile-system-packages.nix`. Installed is 0.72.0 (metadata says 0.66.0); nixos-unstable has 0.76.2. Our invocation `trivy fs --scanners vuln,secret,misconfig --skip-db-update --exit-code 0 .` ran on 0.72.0 against a fixture requirements file with exit 0 and no flag errors (it only reported that 0.76.2 is available). Recommendation: take it through the next flake refresh.

## 6. github-mcp-server 0.20.2 -> 2.2.0: report only, hold

Pin metadata says 0.20.2, but the installed binary is 1.1.2, so the pin is already stale by a major. We use it in `scripts/ai/mcp-github-server` as `github-mcp-server stdio --read-only --toolsets context,repos,issues,pull_requests,actions,code_security`, with a classic-token scope check in the wrapper; the intake allowlist names `get_file_contents`, `search_code`, `issue_read`, `pull_request_read`, `list_workflow_runs`, `get_code_scanning_alert`.

Release notes 1.0.0 to 2.2.0: 2.0.0 adds typed tool inputs and outputs with output schemas (advertised only to MCP 2026-07-28 clients; compound tools changed schemas), 2.2.0 replaces server instructions with filtered MCP skills and adds agent automation tools, optional secret hiding in secret-scanning alert tools. No release note lists a removed flag. The v2.2.0 README still documents `--read-only` and `--toolsets`, and states read-only takes priority over `--tools`, so the read-only boundary we rely on should still hold. Risks: tool consolidation continues (`list_workflow_runs` is already `actions_list` in current builds), so the intake allowlist names may no longer match; new tools in 2.2.0 (agent automation) need classification as read or write before promotion.

Recommendation: hold. Bump only as its own slice that first reconciles the tool allowlist with the 2.x tool names, verifies `--read-only` hides all write tools in `tools/list`, and checks the wrapper's token handling.

## 7. Validation

See the commit trail and the gate output summarized in the handback: `check-harness-first-static-gates.sh` and `tier0-validation-gate.sh --pre-commit`.

## 8. Activation attestation

These are Nix package pins only: built, not deployed. Not integrated into a running system until the owner runs `aq-deploy-current` (rebuild is an owner act, not performed here). The running lean-ctx remains 3.12.4 until then, and its MCP server needs a reconnect afterward for config to be re-read. Observable via `lean-ctx --version`, `opencode --version`. Intervenable by reverting the three commits. Deferral: osv-scanner, trivy and github-mcp-server are intentionally held, dated 2026-11-18, pending the next flake refresh or a dedicated slice.
