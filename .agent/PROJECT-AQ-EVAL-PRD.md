---
title: AQ Eval Harness
doc_type: prd
id: aq-eval-harness
status: active
owner: codex
last_updated: 2026-06-29
---

# AQ Eval Harness PRD

## Problem

The capability backlog identifies LLM eval/red-team as the highest leverage next integration, but importing external eval frameworks would expand supply-chain and runtime authority before the harness has a local control surface.

## Goals

- Add a repo-local `aq-eval` wrapper for static eval/red-team suites.
- Keep first implementation dry-run and local-command focused.
- Validate eval suites as JSON before any model or external framework execution.
- Wire the surface into catalog and validation governance.

## Non-Goals

- Do not install Promptfoo, DeepEval, Ragas, Garak, or other third-party eval tools in this slice.
- Do not call external model APIs.
- Do not auto-promote prompt or model changes based on eval output.

## Acceptance

- `scripts/ai/aq-eval` supports `validate`, `list`, and `run`.
- `config/aq-eval-suites.json` records local static eval/red-team cases.
- Focused tests cover validation, listing, dry-run, and local command execution.
- System capability catalog exposes `aq-eval-harness`.
- Tier0 pre-commit gate passes before commit.
