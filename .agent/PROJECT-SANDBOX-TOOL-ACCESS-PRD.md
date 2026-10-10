# Sandbox tool access for the next rebuild

Date: 2026-10-09. Scope: Home Manager Codex config reconciliation and regression coverage. Activation is deferred to the owner's next rebuild; no sudo or deployment; scoped commits follow validation.

Objective: installed command-line tools can run with workspace writes and network access while filesystem containment and explicit user escalation approval remain. Reuse the existing yq merge (minimal-code rung 2); introduce no dependency or wrapper.

Implementation: set approval_policy=on-request and approvals_reviewer=user. When neither default_permissions nor a permissions table exists, declare sandbox_mode=workspace-write, network_access=true, writable_roots=[configured repoPath], and permit the native /tmp and TMPDIR roots. Do not add unproven home cache grants. Preserve modern permission profiles without injecting conflicting legacy sandbox settings. Keep existing scoped MCP approvals; no blanket external-effect authorization.

Acceptance: execute the actual generated yq transform with clean/existing/modern-profile fixtures; verify unrelated settings and profiles survive, unsafe legacy roots are replaced, and repeated projection is idempotent. Check installed Codex 0.162.0 strict parsing with a disposable CODEX_HOME, and Nix syntax. Sources: https://learn.chatgpt.com/docs/config-file/config-reference and https://learn.chatgpt.com/docs/permissions; installed codex --help and codex mcp list --help.

Limits: normal PATH tools remain subject to host permissions, managed policy, and command rules. Codex protected .git/.agents/.codex paths may need approval. Existing sessions and managed clients do not inherit this declaration automatically. Named permission profiles are preserved and may retain stricter network/root policy. Writable home caches remain excluded pending concrete need.

## Local nsjail tool slice

Approved configuration scope, 2026-10-09: reuse Nix packages to declare NSJAIL_TOOL_PATH and NSJAIL_REPO_PATH for local shell tools. Mount configured repository read-only; use each invocation's isolated temporary filesystem for HOME/cache. Preserve network isolation, required-sandbox failure handling, injection guards and host socket separation. No user-home/npm mounts, sudo, privilege changes or activation. Acceptance: existing local-shell regression tests plus argv/path boundary tests, Nix parse, and real nsjail executable probes where permitted. Tool presence does not attest every wrapper's dependencies or host-service permissions.

Runtime finding, 2026-10-09: nsjail 3.6 interprets --tmpfs /tmp:size=16m as a literal destination; root probe failed chdir(/tmp) with ENOENT. Producer now uses documented --mount none:/tmp:tmpfs:size=16777216. RESOLVED: regression asserts mount destination and limit; installed nsjail 3.6 probe passed with corrected argv (exit 0), as recorded in ACTIVATION-AUDIT.md. Service environment activation remains deferred to the next rebuild.

Runtime finding, 2026-10-09: Git exited 128 because /dev/null was absent from the jail. Bind only /dev/null read/write for conventional tool redirection; no broader /dev visibility. RESOLVED: regression asserts the single-device mount; installed nsjail probe executed Git 2.54.0, temporary writes and the read-only repository boundary successfully (exit 0), as recorded in ACTIVATION-AUDIT.md. Service environment activation remains deferred to the next rebuild.

## Critical Findings — Consolidated Severity Matrix
### P1 — Runtime correctness
| # | Finding | Agent Source | File:Line | Impact |
|---|---|---|---|---|
| P1-1 | nsjail 3.6 needs explicit tmpfs mount options; colon suffix was a literal destination | Codex runtime probe | ai-stack/local-agents/builtin_tools/shell_tools.py | Jail failed before execution; fixed producer and argv regression |
| P1-2 | Minimal jail lacked /dev/null | Codex runtime probe | ai-stack/local-agents/builtin_tools/shell_tools.py | Git failed; single-device bind and regression added |
### P2 — Existing limitations
| # | Finding | Agent Source | File:Line | Impact |
|---|---|---|---|---|
| P2-1 | Optional nsjail mode retains preexisting host fallback on execution errors | Independent sandbox reviewer | ai-stack/local-agents/builtin_tools/shell_tools.py | This slice does not guarantee confinement of every local invocation; required mode remains fail closed |
| P2-2 | Incomplete named permission profiles cannot parse | Codex strict-parser fixtures | nix/home/base.nix | Preserve invalid owner config and assert rejection rather than choosing a permission profile |
