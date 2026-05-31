# MAEAH Security Contract Gates
> Date: 2026-05-21
> Status: Normative supplement to MAEAH v0.3 parity amendments
> Source: External parity catalog + architecture/security/memory/edge agent reviews

## Rule 1 — Loopback is not authorization

Read-only health/status endpoints may be unauthenticated. Mutating admin, lifecycle, scheduler, MCP, A2A delegation, memory sharing, model promotion, and rollback operations require explicit authorization even on loopback.

Acceptance criteria:

- Unauthenticated loopback mutation returns `401` or `403`.
- Dashboard/internal callers use API key, Unix socket peer credentials, signed local service token, or equivalent non-forgeable local mechanism.
- Header-only privilege such as `X-Dashboard-Internal: 1` is invalid unless paired with local proof/auth.

## Rule 2 — Agent identity has a lifecycle

Signed Agent Cards are necessary but not sufficient.

Acceptance criteria:

- Agent Cards are canonicalized before signing.
- Signature covers identity, capabilities, endpoints, auth methods, issued-at, expiry, public-key fingerprint, and schema version.
- Remote cards require expiry, known trust root, replay rejection, rotation path, revocation path, and quarantine reason codes.
- Capability claims remain advisory until matched against local policy overlays.

## Rule 3 — Delegation is scoped and non-escalating

A2A task delegation must carry a bounded delegation envelope.

Required envelope fields:

- issuer agent;
- subject agent;
- allowed capabilities;
- allowed MCP servers/tools;
- resource roots;
- max duration;
- max budget;
- network egress policy;
- trace ID / parent task ID.

Acceptance criteria:

- Tool calls prove both agent identity and task-scoped authorization.
- Privilege cannot increase across delegation chains.
- Priority inheritance is separate from privilege inheritance.
- Denials emit `delegation_denied` with reason code.

## Rule 4 — Every tool has a sandbox profile

Unknown tools default to deny.

Minimum profile matrix:

| Profile | Use | Network | Filesystem | Devices |
|---|---|---:|---:|---:|
| `read_only_workspace` | grep/list/read | denied | declared roots read-only | denied |
| `workspace_rw_patch` | code edits | denied default | declared repo paths rw, secrets denied | denied |
| `network_fetch` | web/API fetch | allowlisted | temp/artifact dirs only | denied |
| `browser_test` | Playwright/UI tests | localhost/allowlist | temp browser profile | denied |
| `model_runtime` | inference service | loopback/declared backend | model dirs read-only except cache | declared GPU/iGPU only |

Acceptance criteria:

- MCP tool declarations include sandbox profile, roots, timeout, output cap, artifact retention, secret policy, and network policy.
- Path traversal outside declared roots fails closed.
- Sandbox violations emit structured audit events.

## Rule 5 — MCP output is tainted by default

Acceptance criteria:

- Remote MCP requires resource indicators and auth policy.
- `tools/list`, `tools/call`, resource reads, prompts, and sampling requests are audited.
- Server-initiated sampling is disabled unless explicitly policy-granted.
- Tool outputs are stored as tainted artifacts and are not blindly inserted into prompts or trusted memory.
- Prompt-injection canaries in tool output do not trigger privileged follow-up calls.

## Rule 6 — Model catalog is a supply-chain boundary

Acceptance criteria:

- Runtime catalog entries include source, sha256, size, license, quant format, architecture, and trust level.
- Remote catalog updates are signed or operator-approved.
- Downloads use allowlisted hosts.
- Promotion requires verified hash and compatible metadata.
- Auto-promotion from remote catalogs is forbidden by default.
- Artifact paths cannot escape the model root.
- MTP sibling compatibility checks model ID/version/hash, not only display name.

## Rule 7 — Memory has provenance and poisoning controls

Acceptance criteria:

- Cross-agent memory reads require explicit grant or project policy.
- Shared facts include source agent, timestamp, confidence, evidence refs, and signature/hash when available.
- Tool-derived memory is tainted until summarized/validated.
- Remote-agent memory writes quarantine by default.
- Compaction preserves provenance.
- Malicious memory cannot override system/developer policy or tool authorization.

## Rule 8 — Audit is privacy-safe and tamper-aware

Acceptance criteria:

- Audit events include actor, action, resource, decision, policy ID, trace ID, and reason code.
- Secrets/API keys are redacted before logs/traces.
- Prompt/completion capture is off by default or explicitly policy-controlled.
- Admin mutations, model promotions, peer trust changes, MCP calls, sandbox denials, and policy overrides are audit-required.
- Audit is persisted, append-only where practical, and suitable for replay/integrity checks.

## Rule 9 — Security-sensitive slices require independent review

Security-sensitive changes include auth, A2A trust, MCP permissions, sandboxing, model promotion, secrets, memory sharing, and remote mesh exposure.

Acceptance criteria:

- No agent self-acceptance for security-sensitive slices.
- Gemini-authored implementation requires Claude or Codex review before integration/commit.
- Plans include a short threat model before non-loopback mesh or remote MCP is enabled.
- Open findings are classified as blocking, accepted risk, or deferred with owner/date.

---

## Phase 1 Static Regression Gate — Codex 2026-05-21

This section adds a repository-local regression check without narrowing or replacing the normative rules above.

`tools/sandbox`, runtime authorization middleware, nsjail/WASM execution, and signed delegation token verification remain later Phase 62+ implementation slices. Until those land, the Phase 1 static gate pins the currently enforceable surfaces so they cannot silently drift while implementation proceeds.

Static gate command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/testing/test-security-contract-gates.py
```

The test validates:

1. `config/runtime-safety-policy.json` keeps `plan-readonly`, `execute-mutating`, and `strict` fail-closed enough for current workflow sessions.
2. `config/runtime-isolation-profiles.json` keeps read-only execution non-mutating/non-networked and constrains mutating execution to the declared mutable agent workspace with loopback-only network.
3. `docs/architecture/gemini-review-gate.md` keeps the required review package, verdict protocol, and no-self-acceptance language for Gemini/Qwen integration.
4. `.agents/plans/multi-agent-edge-harness/PARITY-INTEGRATION-PLAN.md` keeps PA-2, PA-3, and PA-4 mapped into Phase 1 security/governance controls.

Expected result:

```text
PASS: security contract gates are pinned
```
