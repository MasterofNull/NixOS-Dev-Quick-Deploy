---
doc_type: prd
id: system-capability-catalog
title: System Capability Catalog
status: active
owner: codex
last_updated: 2026-06-29
---

# System Capability Catalog PRD

## Objective
Create one machine-readable source of truth for harness tools, plugins, MCP servers,
modules, datasets, workflows, skills, and feature surfaces so agents can discover,
compare, validate, and improve capabilities without relying on stale scattered notes.

## Problem
Capabilities currently live across intake candidates, capability-gap metadata, workflow
blueprints, skills, docs, service endpoints, and local runtime manifests. Agents can use
some of these surfaces, but there is no compact catalog that answers:

- what exists
- where it is implemented
- who can use it
- how mature it is
- which security gate controls it
- which parity checks should compare it with external mature AI repos
- which datasets or stores back it

This makes gap discovery and external feature ingestion harder to automate safely.

## Requirements
- Add a JSON SSOT catalog under `config/`.
- Track capability category, state, maturity, owner, users, source references, validation,
  security/admission posture, data stores, and parity targets.
- Provide a human reference sheet generated from the JSON catalog under `docs/operations/reference/`.
- Add validation that catches duplicate ids, missing required fields, broken repo
  references, stale docs, and external capabilities missing intake/security metadata.
- Keep external ingestion deny-by-default through `capability-intake`.
- Delegate long-running parity discovery to the local agent as advisory work.

## Acceptance Criteria
- `python3 scripts/ai/aq-capability-catalog validate` passes.
- `python3 scripts/ai/aq-capability-catalog check-doc` passes.
- A focused regression test covers the catalog validator and generated reference sheet.
- Tier0 passes before commit.
