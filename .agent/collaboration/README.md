# Collaboration State Policy

This directory contains local live coordination state.

Tracked portable knowledge:
- `.agent/WORKFLOW-CANON.md`
- `.agent/collaboration/RULES.md`
- `.agent/memory/issues-backlog.md`
- `.agents/prompts/`
- `.agents/plans/`
- durable docs under `docs/`

Local-only runtime state:
- `HANDOFF.md`
- `PENDING.json`
- `PULSE.log`
- `RESUME.json`
- `.agent/comms/command.json`
- `.agent/comms/output.json`
- `.agent/comms/output.txt`
- `.agents/attention/*.jsonl`
- `.agents/delegation/registry.jsonl`
- `.agents/delegation/outputs/`
- `.agents/telemetry/*.jsonl`

Agents may create and update the local runtime files during a session, but they
must promote durable lessons, decisions, and reusable knowledge into the tracked
locations above before committing. New deployments should start from templates
or fresh session state, not inherited in-flight locks or local telemetry.
