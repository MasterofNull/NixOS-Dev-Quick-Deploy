# AQ Eval Harness Plan

Status: In progress
Owner: codex
Date: 2026-06-29

## Checklist

- [x] Check local-agent health and artifact visibility.
- [x] Fix agent-mode delegation output blind spot.
- [x] Add repo-local eval suite config.
- [x] Add `aq-eval` wrapper.
- [x] Add focused tests.
- [x] Wire catalog and validation registry.
- [x] Validate focused checks and tier0.
- [x] Commit slice.

## Boundaries

- No external eval framework import in this slice.
- Local command execution is limited to command arrays declared in `config/aq-eval-suites.json`.
- Model-scored evals and red-team probes require later capability-intake and PRD slices.
