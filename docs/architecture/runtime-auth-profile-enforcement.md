# Runtime Auth/Profile Enforcement

Status: Active baseline
Owner: AI harness maintainers
Last updated: 2026-05-21

## Purpose

Hybrid-coordinator requests now resolve an explicit runtime auth context before
handler dispatch. The context makes the request's trust boundary and effective
execution profile visible to handlers, tests, and operator surfaces.

This is the first runtime slice for the parity-plan S2 MCP auth/profile track. It
does not introduce a new credential store; it reuses the existing
`HYBRID_COORDINATOR_API_KEY` / `HYBRID_API_KEY_FILE` wiring and the established
loopback-agent exception list.

## Request modes

| Mode | When used | Default profile | Allowed profiles |
|---|---|---|---|
| `public` | Public health/discovery endpoints | `readonly-strict` | `readonly-strict` |
| `loopback-agent` | Localhost request to an approved agent endpoint prefix | `execute-guarded` | `readonly-strict`, `execute-guarded` |
| `api-key` | Valid `X-API-Key` or bearer token | `execute-guarded` | `readonly-strict`, `execute-guarded`, `worktree-guarded` |
| `no-api-key-configured` | Compatibility mode when no API key is configured | `execute-guarded` | `readonly-strict`, `execute-guarded` |

Clients may request a narrower/alternate profile with
`X-Harness-Auth-Profile`. The middleware rejects profiles that are not allowed
for the resolved auth mode.

## Runtime contract

The middleware writes this request state before handler execution:

```python
request["auth_context"] = {
    "mode": "api-key",
    "profile": "execute-guarded",
    "authenticated": True,
    "reason": "api_key_valid",
}
```

Successful responses also include:

- `X-Harness-Auth-Mode`
- `X-Harness-Auth-Profile`

Invalid credentials return `401`. Invalid profile requests return `403`.

## Operator visibility

The Command Center harness overview exposes the policy under:

```text
/api/harness/overview -> policies.runtime_auth_profiles
```

## Validation

- `scripts/testing/test-hybrid-auth-profile-policy.py`
- `scripts/governance/tier0-validation-gate.sh --pre-commit`
