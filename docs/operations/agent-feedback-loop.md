# Agent Feedback Loop

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-05-09

Purpose: turn agent or operator feedback into a bounded harness workflow that is
small enough to run during normal repo work.

## Command

```bash
aq-feedback-loop --task "act on local agent feedback for context injection, health gating, remote task schema, and evidence-first introspection"
```

Optional:

```bash
aq-feedback-loop \
  --task "act on local agent feedback for context injection, health gating, remote task schema, and evidence-first introspection" \
  --feedback-file /tmp/local-agent-feedback.txt \
  --format json
```

## What It Produces

1. recommended scope from `aq-context-bootstrap`
2. PRD and plan artifact paths
3. explicit preflight commands
4. starter commands
4. workstreams
5. validation commands
6. commit suggestions

## Default Loop

1. Run `aq-feedback-loop --task "<task>"`
2. Run the emitted preflight commands first, especially `aq-qa 0 --json`
3. Create or update the recommended PRD and plan files
4. Run the memory checkpoint command it suggests
5. Implement one reversible slice
6. Run the validation commands
7. Stage only the slice files and commit

## Relationship To Existing Tools

`aq-context-bootstrap`
- classifies the task and recommends the first context path

`aq-hints`
- provides ranked workflow guidance before implementation

`aq-context-manage`
- checkpoints decisions and next steps into harness memory

`aq-qa`
- provides the explicit health gate before runtime-heavy work

`aq-report`
- gives recent routing, memory, and reliability posture

If `aq-context-bootstrap` classifies the task as `context-offload`, the feedback
loop promotes its continuation startup packet into `preflight_commands` so
memory recall and compact context checks happen before deeper planning.

## Validation

```bash
python3 scripts/ai/aq-feedback-loop --task "act on local agent feedback for context injection, health gating, remote task schema, and evidence-first introspection" --format json
bash scripts/testing/check-feedback-loop.sh
```
