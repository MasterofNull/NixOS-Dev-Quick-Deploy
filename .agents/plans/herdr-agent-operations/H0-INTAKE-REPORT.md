---
doc_type: plan
id: herdr-h0-intake-20260808
title: Herdr H0 Capability Intake Report
status: draft
parent_prd: herdr-agent-operations
date: 2026-08-08
---

# Herdr H0 capability intake report

## Verdict

**PREPARED_ONLY — needs a separately reviewed, default-off mitigation slice; do not install or enable Herdr.** The intake target is upstream release `v0.7.5`, pinned by immutable source revision and exact source/Cargo dependency hashes in a future local Nix package. The pinned release is dual-licensed under AGPL-3.0-or-later or a separately obtained commercial license; its `LICENSE`, `Cargo.toml`, README, and Nix package agree on AGPL-3.0-or-later. It exposes a Nix flake package, default app, checks, and overlay, which are feasibility evidence only; AQ-OS H1 uses a local source-pinned package and does not add the upstream flake to `flake.lock`. H1 remains blocked until the owner accepts the AGPL obligations for local internal use or supplies a commercial-license record.

H0 changes no runtime capability. The candidate registry remains `proposed` with disabled external-repository install metadata, no tool permissions, and no network, shell, write, or secret permissions. It grants no download, no install, process start, no socket use, agent skill, plugin, integration, remote attach, update, manifest fetch, restore, service activation, provider change, or routing change.

## Intended role and non-authority boundary

Herdr is only a persistent PTY/presentation substrate. AQ-OS remains the lifecycle, routing, approval, cancellation, review, evidence, task-registry, worktree-lease, dashboard, and authority SSOT. Herdr's process/screen detection and `working`/`blocked`/`done` labels are advisory visual state, never task completion or authority facts.

If accepted later, the standard `aq-os` workspace has the deterministic seven-tab role layout: `control`, `reasoning`, `implementation`, `review`, `research`, `local`, `ops`. This is a presentation convention only; it does not create agents, start providers, assign leases, or change AQ-OS routing.

The repository has only cmux-style comments/matrix focus rendering in `scripts/ai/aq-tui-dashboard`; it has **no active cmux runtime integration or cutover claim**. H0 neither installs nor retires cmux.

## Upstream evidence and material risks

Upstream documents a local newline-delimited JSON socket API that can create/close panes and workspaces, start agents/processes, send input/keys, read terminal output, manage worktrees, subscribe to events, install integrations/plugins, reload configuration, and stop the server. Same-user access therefore cannot safely be treated as a method-level authorization boundary.

Plugins are arbitrary executable code, run as the user with environment and the full Herdr CLI; installation may clone/build code and plugins are global to that user. Integrations write agent hooks and report native session references. Background release and remote agent-manifest checks exist. Persistent session restore may resume supported agent sessions. `--remote` uses SSH, can create temporary SSH-control configuration, and may obtain a remote binary when absent. PTY scrollback, pane reads, process info, notifications, logs, and hook payloads can expose prompts, paths, command lines, tool output, secrets, or user activity.

These capabilities are incompatible with direct AQ-OS agent access. No plugin, integration, skill, raw socket, CLI passthrough, remote attach, restore, update, manifest refresh, or server-control path is admissible in H0.

## Required mitigation before any activation

1. Package only source-pinned `v0.7.5` through a local Nix expression; bind the commit, source hash, Cargo lock and dependency closure; produce an SBOM/license/dependency review. Do not add an upstream flake input or `flake.lock` entry. No curl, release binary, `herdr update`, or upstream manifest fetch.
2. Generate immutable default-off config: `[update] version_check=false`, `manifest_check=false`; `[session] resume_agents_on_restore=false`; `[remote] manage_ssh_config=false`; `[experimental] allow_nested=false`.
3. Keep Herdr as a user presentation process, not an AQ authority service. Confined agents must not receive `HERDR_SOCKET_PATH`, Herdr config/state directories, or the Herdr CLI.
4. If AQ-OS later reports into Herdr, use a host-owned mediation wrapper with bounded, redacted requests. Direct socket access is prohibited because upstream provides no per-method ACL. The only future candidate methods are `ping`, redacted metadata projection, `pane.report_agent`, `pane.report_agent_session`, `pane.release_agent`, bounded `notification.show`, and narrowly scoped server-owned waiting. Every process/input/read/layout/worktree/server/plugin/integration method remains denied.
5. Treat all terminal data as sensitive: no prompt/tool output/path/argv/session ID in dashboard labels, metrics, logs, or receipts. Prove sandbox path/socket isolation and unavailable/fail-closed behavior before a canary.

## Required future Service Coverage and rollback

Any enabled presentation slice must atomically add: package/pin/config/socket/proxy health to AQ-QA; dashboard and Agent Ops state for disabled/configured/effective/unavailable; a hermetic wrapper allowlist/denial test; and explicit no-terminal-content assertions. A harmless local presentation canary needs independent review and separate owner activation. Remote attach, integrations, plugins, session restore, updates, manifests, and provider/routing changes each need their own authority.

Rollback disables the Nix feature and removes proxy/socket bindings from confined sandboxes. It must not stop or alter canonical AQ-OS work, receipts, providers, leases, task records, or evidence.

## Sources reviewed

- `https://github.com/herdrdev/herdr` / upstream `v0.7.5` release; AGPL-3.0-or-later or commercial dual-license declaration.
- Pinned-source `LICENSE` SHA-256 `a7fa24f74382fb3e4d320a608533a7c2999dbc0f780f1f734c8b891b31f0d9bd` and `Cargo.lock` SHA-256 `4d590b4abf9d6088704ae7ab9811c8bb766286ec75ca63364c7e23cb14be6ecf`.
- Upstream flake outputs: package/default app/checks/overlay.
- Upstream Socket API, Plugins, Integrations, and Persistence/Remote documentation.
- `config/agent-capability-intake-candidates.json` and `.agent/PROJECT-HERDR-AGENT-OPERATIONS-PRD.md`.

RECORD: PREPARED_ONLY; independent security/SRE review is required before any implementation authorization.
