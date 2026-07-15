# M2 Bootstrap Authorization — Monitored Claude Fable Routing

**Decision:** `implementation_authorized = AUTHORIZED`
**Authorization ID:** `auth-m2-fable-routing-bootstrap-20260715`
**Issuer:** owner, explicit statement `Authorize the M2 Fable-routing bootstrap fix.`
**Purpose:** make the required flagship review route explicit and auditable before M2A authorization

## Exact inventory

1. `.agents/plans/agent-ops-traceability-r0m/FABLE-ROUTING-BOOTSTRAP-AUTHORIZATION.md`
2. `scripts/ai/delegate-to-claude`
3. `scripts/testing/test-delegate-claude-model-routing.py`

No fourth file is authorized.

## Grant

- Add `--model-tier` to the monitored Claude wrapper.
- Resolve only declared Anthropic tier names through `config/model-coordinator.json`; never hardcode
  `claude-fable-5` in the wrapper.
- Pass the resolved model through Claude CLI's native `--model` option.
- Record requested tier and resolved model in the monitored registry row.
- Preserve existing behavior when no tier is requested.
- Add hermetic tests with a fake Claude binary and temporary registry proving flagship resolution,
  exact CLI argv, registry identity, compatibility, and fail-closed unknown/malformed tiers.

## Non-goals and stop conditions

No M2 registry enforcement, lifecycle transition rewrite, concurrency fix, retry, provider fallback,
prompt change, model-coordinator edit, live Fable review, deployment, or fourth-file edit is authorized
by this bootstrap grant. The implementation requires independent Antigravity acceptance before commit
or use for the M2 Revision 2 review.

`RECORD: owner-authorized three-file bootstrap only; M2A/M2B remain unauthorized.`
