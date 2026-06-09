# Agent Artifact Distribution Policy

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-06-09

## Intent

Agent outputs fall into two classes:

1. Portable collective knowledge that should ship to new deployments.
2. Local runtime state that reflects one machine, one operator, or one active work session.

The repository should distribute the first class and ignore the second. This
keeps new nodes useful without inheriting stale locks, local telemetry, or
operator-specific routing history.

## Distributed Artifacts

Track these when they pass normal review and security checks:

- `.agent/WORKFLOW-CANON.md`
- `.agent/collaboration/RULES.md`
- `.agent/memory/issues-backlog.md`
- `.agents/prompts/`
- `.agents/plans/`
- `.agents/improvement/candidates.json`
- `docs/`
- validated tests, config, and source code

Before commit, durable artifacts must be checked for secrets, host-specific
paths, and stale claims. Runtime evidence should be summarized rather than
copied wholesale.

## Local-Only Artifacts

Do not track these live runtime files:

- `.agent/collaboration/HANDOFF.md`
- `.agent/collaboration/PENDING.json`
- `.agent/collaboration/PULSE.log`
- `.agent/collaboration/RESUME.json`
- `.agent/comms/command.json`
- `.agent/comms/output.json`
- `.agent/comms/output.txt`
- `.agents/attention/ATTENTION.json`
- `.agents/attention/ATTENTION_ARCHIVE.jsonl`
- `.agents/delegation/registry.jsonl`
- `.agents/delegation/outputs/`
- `.agents/scratchpad/`
- `.agents/telemetry/*.jsonl`
- `nix/hosts/*/facts.nix`

These files can contain stale in-flight work, local event streams, or
host-specific facts. They remain useful locally, but new deployments should
generate their own copies.

## Promotion Rule

If a local runtime artifact contains reusable knowledge, promote it before
commit:

- bug or limitation -> `.agent/memory/issues-backlog.md`
- procedure or runbook -> `docs/operations/`
- model/team prompt -> `.agents/prompts/`
- PRD or plan -> `.agents/plans/`
- regression -> `scripts/testing/` plus `config/validation-check-registry.json`

Raw runtime artifacts are evidence, not canonical instructions.
