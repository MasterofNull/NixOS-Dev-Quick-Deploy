---
doc_type: plan
id: flat-collaboration-enablement
title: Flat Collaboration Enablement
status: active
owner: codex
last_updated: 2026-06-29
parent_prd: flat-collaboration-enablement-prd
---

# Flat Collaboration Enablement

## Goal

Enable flat model-team collaboration without weakening the existing proposal, cross-review, consensus, and reviewer-separation gates.

## Slice

- [x] Flip repo collaboration feature flags to gate-backed enabled mode.
- [x] Upgrade `aq-flat-prd-gate` so disabled rollout flags fail.
- [x] Block same-author cross-review artifacts in topic packages.
- [x] Add tooling-manifest auto-selection for `flat_prd_gate`.
- [x] Validate focused checks and aq-qa phase 0.
- [x] Validate tier0.
- [x] Commit scoped changes.

## Activation

Repo config is enabled immediately for config readers. Deployed service copies may require the normal rebuild cadence if a running service reads these YAML files from the Nix store.
