# AI Repo Discovery and Parity PRD

Status: Active
Owner: codex
Date: 2026-06-29

## Problem

Agents need a single, security-gated queue of mature external AI system repositories to compare against the local harness. Today, research findings can remain in chat or ad hoc notes, which prevents repeatable parity checks, local-agent delegation, and deny-by-default intake.

## Goals

- Catalog high-value AI repos, MCP servers, skills, and tools as candidates only.
- Route every candidate through parity checks and capability-intake security gates before implementation.
- Make the catalog machine-readable for local agents and recursive self-improvement loops.
- Delegate gap mapping to the locally hosted agent without granting install, write, or network authority.

## Non-Goals

- Do not install or enable new external tools from this slice.
- Do not grant new GitHub token scopes or external service credentials.
- Do not bypass `capability-intake`.

## Acceptance

- `config/suggested-ai-repo-candidates.json` exists and validates.
- System capability catalog points to the suggested repo catalog.
- Validation registry contains a focused candidate catalog check.
- Local agent receives a bounded mapping task for parity analysis.
- Tier0 pre-commit gate passes before commit.
