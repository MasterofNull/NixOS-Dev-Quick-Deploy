# Phase 60 aq-chat Local Tool Profile Alias

Status: implementation validation in progress

## Problem

The default `aq-chat` path correctly routes local conversations through switchboard local tool selection, but `aq-chat --profile local-tool-calling` was treated as a nonlocal profile and sent to the hybrid orchestration path. That produced a 400 even though the same request worked through switchboard.

## Fix

- Treat `local-tool-calling` as a local switchboard-backed profile inside `aq-chat`.
- Keep the switchboard request header as `X-AI-Profile: local-tool-calling`.
- Add a focused regression check so the alias cannot drift back to the hybrid path.

## Validation

- `python3 scripts/testing/test-aq-chat-local-tool-profile.py`
- `scripts/governance/run-focused-ci-checks.sh`
- `scripts/governance/tier0-validation-gate.sh --pre-commit`
- Live smoke: `printf 'how are you today?\n/exit\n' | scripts/ai/aq-chat --profile local-tool-calling`
