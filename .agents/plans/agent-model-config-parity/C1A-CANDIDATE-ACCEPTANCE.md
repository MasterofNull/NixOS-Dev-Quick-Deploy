# C1A Candidate Acceptance — Native Codex Role Declarations

**Status:** PENDING_INDEPENDENT_REVIEW / no integration authority
**Base HEAD:** `107f7e8ab2452b4d89ff737b28966e35bf4f9e24`

## Objective and root cause

Codex custom role layers existed as three TOML files but the trusted project
configuration did not declare `agents.<name>.description` and
`agents.<name>.config_file`, so native Codex could not expose those configured
roles. This candidate declares the roles and makes the focused validator reject
missing, escaped, or weakened declarations.

## Exact candidate

| Path | SHA-256 |
|---|---|
| `.codex/config.toml` | `ecbc63b045fb1bb921b955f061c7d54ed41ea5cbb9a8c1959be82b25ae4cfc8c` |
| `scripts/testing/test-codex-subagent-configuration.py` | `c05944c3edd8f58e9f9202672ae5d10697ac523500123f0ba70379ab46fd77b2` |

Frozen role layers:

| Path | SHA-256 |
|---|---|
| `.codex/agents/aq-implementer.toml` | `151a2745ffc08af5a80db212f9e5c12dcfb1a74efa66f0d94426fb195ef4c722` |
| `.codex/agents/aq-reviewer.toml` | `20e710c37b74622866e5a9c5c41ce1cc79818d743baa4259236b5ad5dc3b9fda` |
| `.codex/agents/aq-explorer.toml` | `4adf810cb0a4c989f0b7c8c5a7d1cd2f1ca36677054495e64b0f0d03a180b849` |

## Validation

- `python3 -m py_compile scripts/testing/test-codex-subagent-configuration.py`
  — PASS
- `python3 scripts/testing/test-codex-subagent-configuration.py` — PASS
- `codex features list` — config parsed; `hooks=true`; no deprecated-hook
  startup warning
- `git diff --check` over C1A and program documents — PASS
- staged inventory remains exactly
  `.agents/plans/aqos-refoundation-cycle0/C0.3-AUTHORIZATION-CONSUMPTION.md`

## Boundaries

No Nix, user-config, provider, wrapper, runtime, dashboard, Phase-0, staging,
commit, deployment, or live route change belongs to C1A. The manual removal of
the deprecated key from the effective user config is separately recorded
runtime recovery, not part of this candidate.

Independent review must verify official Codex declaration semantics, exact
relative paths, exact role model/effort/sandbox/nested-delegation constraints,
adversarial test coverage, and the two-file ceiling.

