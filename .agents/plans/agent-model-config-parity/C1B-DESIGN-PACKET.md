# C1B Design Packet — Effective Agent Configuration Doctor

**Status:** DESIGN / no implementation or live mutation authority

## Objective

Add a provider-neutral, read-only configuration doctor that compares declared
agent deployment sources with effective client-visible state and returns one
closed, redacted health record. It detects the class of drift that reintroduced
`features.codex_hooks` and the missing Codex custom-role declarations.

## Proposed ceiling

1. New `config/schemas/agent-config-health.schema.json`
2. New `scripts/ai/aq-agent-config-doctor`
3. New `scripts/testing/test-agent-config-doctor.py`

No existing runtime, wrapper, Nix, dashboard, Phase-0, provider, or deployment
surface changes in C1B.

## Contract

The doctor accepts explicit input paths for hermetic tests and defaults to the
current repository/user paths for operator use. It must:

- parse user/project Codex TOML, named role layers, model coordinator JSON, and
  the declarative projection source without executing them;
- calculate SHA-256 fingerprints for every source and the normalized effective
  projection;
- enforce `features.hooks=true`, reject deprecated/unknown governed keys, require
  explicit project trust, require every named role declaration and relative
  in-repository `config_file`, and validate exact role model/effort/sandbox/
  nested-delegation constraints;
- report coordinator/provider/model conflicts without changing routes;
- emit only closed-schema JSON with bounded findings and redacted paths/values;
- separate `declared`, `effective`, `drift`, and `unavailable` states;
- never print secrets, prompt contents, auth material, raw environment, or
  high-cardinality task/session identifiers.

## Native doctor relationship

Codex 0.145 provides `codex doctor --json`, including redacted `config.load`,
feature, model, MCP, sandbox, update, and runtime provenance evidence. C1B stays
pure and hermetic; it does not invoke that network-capable command. C1C may
consume a separately captured, bounded `config.load` projection from the native
doctor as live evidence and must disclose the native version and probe scope.

## Required fixtures

- clean declared/effective parity;
- deprecated hook alias in user and project layers;
- missing hooks;
- absent/untrusted project;
- missing role, absolute/path-traversal role file, wrong model/effort/sandbox,
  writable reviewer, nested delegation enabled, instruction weakening;
- stale model coordinator and provider/model fallback mismatch;
- malformed TOML/JSON/schema, unreadable source, symlink/path escape;
- secret-shaped values proving redaction and bounded output;
- deterministic fingerprints independent of input ordering.

## Stops

Any need to mutate user config, call `codex`, contact a provider, add a service,
touch Phase-0/dashboard/Nix, stage, commit, or deploy requires a later slice.

## Acceptance

Both clean and adversarial fixtures pass; schema is closed; output is
deterministic and secret-safe; tests prove no subprocess/network/write behavior;
an independent reviewer issues an exact-subject verdict.

