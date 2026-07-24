# Capability Intake Review: playwright-mcp

Reference skills: `capability-intake`, `security-scanner`, `webapp-testing`

## Audit Verdict: REQUEST_REVISION

### Evidence:
1. Exposes high-risk operations (browser control, screenshot capture, DOM navigation).
2. Uses `npx` dynamic installer which fetches mutable remote packages during initialization.
3. Declares broad network egress, presenting high risk of unauthorized outbound data leakage.

### Proposed Test Cases:
1. Mock browser navigation to a local dashboard target that redirects to an unauthorized external server, verifying that connection is refused.

### Follow-up Patch Scope:
1. Enforce private sandbox execution (e.g., using `systemd-run` or AppArmor profiles) to confine browser egress to loopback interface and local dashboard ports (e.g. port `8889` only).
2. Implement dynamic version check on the downloaded Playwright npm package.

## Resolution (2026-07-23) — NOT RESOLVED, verdict unchanged (REQUEST_REVISION)

An Antigravity-authored candidate diff for the sibling `mcp-admission-controller` finding neither claimed nor
attempted to resolve this finding, and this revision does not either — both were confirmed out of scope by
independent review
(`.agents/plans/capability-intake-security/ANTIGRAVITY-CANDIDATE-REVIEW.md`, "Completeness" table: "NOT
ADDRESSED" for both mitigations).

Neither the private-sandbox confinement (`systemd-run`/AppArmor loopback-only egress) nor the dynamic
Playwright npm version check has been implemented. `playwright-mcp` is **not** thereby "safe by omission" —
its registry entry already routes to `needs-review`/`accepted-with-mitigations` via the existing
`dynamic-installer:npx` risk flag, independent of this finding — but the specific mitigations this finding
requested remain unbuilt. **This finding is explicitly deferred as a separate follow-up slice, not marked
PASS or RESOLVED.** Do not treat the schema-validator or curl-hardening work landed elsewhere in this cycle as
covering this finding; it does not.

## Resolution (2026-07-23, follow-up slice) — item 2 RESOLVED; item 1 IMPLEMENTED, ACTIVATION PENDING REBUILD

**Item 2 (dynamic version check) — RESOLVED, active now, no rebuild needed.**
`scripts/ai/mcp-playwright-sandboxed` re-resolves `@playwright/mcp@0.0.76`'s `version` and `dist.integrity`
against the live npm registry on every launch and refuses to run (fail closed) on lookup failure, version
drift, or integrity-hash mismatch — this is the concrete defense against "npx dynamic installer which fetches
mutable remote packages": even a same-version-string republish under the pinned tag changes `dist.integrity`
and is caught. Verified live: correct pin → launches (confirmed via `--version` → `Version 0.0.76`); wrong
pinned spec passed in → refuses with a clear stderr message and exit 1. All four launch sites now invoke this
wrapper instead of raw `npx`: `.claude/settings.json`, `.gemini/settings.json`,
`ai-stack/continue/config.json`, and `config/agent-capability-intake-candidates.json`'s `install.command`.

**Item 1 (private sandbox / loopback-only egress) — IMPLEMENTED, NOT YET ACTIVE on this host.**
The wrapper launches playwright-mcp inside a `systemd-run` scope with `IPAddressDeny=any` /
`IPAddressAllow=127.0.0.1/8,::1/128` — the same directive already used for the persistent MCP daemons
(`nix/modules/roles/ai-stack.nix`, `nix/modules/services/mcp-servers.nix`,
`nix/modules/services/llama-router.nix`). **Live-tested and found NOT enforcing under an unprivileged
(`--user`) scope on this host**: a `curl` to an external IP from inside such a scope succeeded (HTTP 301)
despite the unit correctly showing `IPAddressAllow=127.0.0.0/8` / `IPAddressDeny=0.0.0.0/0 ::/0` in
`systemctl --user show` — `kernel.unprivileged_bpf_disabled=2` on this host blocks the cgroup BPF egress
filter from attaching for non-`CAP_BPF` callers, so the properties are recorded but inert. A root-context
`systemd-run` is not gated by that sysctl. A narrowly-scoped `NOPASSWD` sudo rule for exactly this
`systemd-run` invocation (fixed IP properties + `*/bin/npx -y @playwright/mcp@0.0.76 *`, nothing broader) is
now declared in `nix/modules/services/mcp-servers.nix` ("Playwright MCP sandbox" block) — **this requires
`nixos-rebuild switch` to activate; it has not been rebuilt as part of this slice** (out of scope for a
non-operator implementer, and granting a new root-exec sudo rule is a judgment call the operator should see
land, not one to silently activate). Until that rebuild, the wrapper detects the missing sudo grant, prints an
explicit stderr warning, and falls back to the unprivileged (non-enforcing) scope rather than silently
claiming confinement that isn't happening. App-level confinement (`--host 127.0.0.1`, `--allowed-origins`
localhost-only, `--isolated`) is unaffected and still applies in both cases.

**Verdict: still not fully RESOLVED — item 2 is closed; item 1 is a committed, correct declaration pending
operator `nixos-rebuild switch` before it is genuinely enforcing.** Do not mark this PASS until the rebuild
has landed and `sudo -n true` / a live egress test confirms enforcement on the target host.

_PULSE: [2026-07-23] [claude-subagent-playwright-mcp-mitigations] [security]: scripts/ai/mcp-playwright-sandboxed, nix/modules/services/mcp-servers.nix, .claude/settings.json, .gemini/settings.json, ai-stack/continue/config.json, config/agent-capability-intake-candidates.json, tasks_inbox/capability-intake-playwright-mcp.md — implemented dynamic npm version+integrity check (active, verified) and systemd-run loopback sandbox wrapper for playwright-mcp (declared + wired, root-enforcement pending nixos-rebuild switch; unprivileged fallback verified non-enforcing on this host, fails loud not silent)._
