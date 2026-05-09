# Agent Operational Perspective

Status: Active
Owner: AI Stack Maintainers
Last Updated: 2026-05-09

Purpose: provide a compact, evidence-first diagnostics bundle for local-agent
operational introspection prompts.

## Command

```bash
aq-operational-perspective --task "help me understand local agent operation and collaboration" --format json
```

Optional:

```bash
aq-operational-perspective --since=1h --format text
```

## What It Uses

1. `aq-qa 0 --json`
2. `aq-report --since=<window> --format=json`
3. optional `aq-feedback-loop --task "<prompt>" --format json`
4. optional `aq-context-manage summary --task "<prompt>" --json`
5. optional `aq-memory --json search "<prompt>" --project ai-stack --limit <n>`

## Output Contract

1. `observed_signals`
2. `inferred_constraints`
3. `evidence_sources`
4. `unknowns_or_next_checks`

The command is intentionally explicit about what is not currently measurable.
It should label unsupported metrics as unknown instead of fabricating them.
If the evidence bundle includes `context_assist_profiles: ["embedded-assist"]`,
use that lane as the compact search/context helper before broader synthesis.
The `remote_collaboration` block summarizes current remote success/fallback
posture and states the current memory-sync policy explicitly.

## Validation

```bash
python3 scripts/ai/aq-introspection-validate --file /tmp/local-agent-response.txt --format json
python3 scripts/testing/test-operational-perspective.py
python3 -m py_compile scripts/ai/aq-operational-perspective
scripts/governance/tier0-validation-gate.sh --pre-commit
```
