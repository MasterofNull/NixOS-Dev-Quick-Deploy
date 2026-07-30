# Codex Sub-agent Configuration C0 Plan

## Slice C0 — native configuration baseline

Add one project config, three narrow custom agent files, and one focused
validator. Keep the existing Home Manager repair and projection test in the
same corrective change because they own the effective deprecated-key/root-trust
regression.

### Exact implementation inventory

1. `.codex/config.toml`
2. `.codex/agents/aq-implementer.toml`
3. `.codex/agents/aq-reviewer.toml`
4. `.codex/agents/aq-explorer.toml`
5. `scripts/testing/test-codex-subagent-configuration.py`
6. `nix/home/base.nix`
7. `scripts/testing/test-agent-mcp-client-projection.py`

### Validation

```text
python3 scripts/testing/test-agent-mcp-client-projection.py
python3 scripts/testing/test-codex-subagent-configuration.py
codex features list
```

### Stops

Stop on an unsupported model/effort key, a project layer that widens the parent
sandbox, a fourth custom agent, concurrency above three, any external-lane
model mutation, dashboard lifecycle writer, provider call, deployment, staging,
or commit.

## Follow-on C1 — monitored parity

Prepare only after C0 acceptance. Extend the broker/Agent Ops projection so
native Codex threads and external lanes share typed low-cardinality lifecycle
health in `aq-qa` and the command-center dashboard. Do not scrape prompts,
outputs, argv, environment, or task bodies.

