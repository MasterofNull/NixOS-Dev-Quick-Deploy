# Phase 60 Tool Lease Broker

Status: implementation validation in progress

## Problem

The first runtime narrowing slice capped the active local tool working set per turn, but long tasks still lacked a sanctioned way to swap tools mid-turn. Without a broker, the model either overuses the initial bundle or asks for a larger upfront registry.

## Fix

- Add a virtual `lease_tools` local tool exposed by switchboard.
- Keep `lease_tools` inside automatic non-conversational bundles so the model can request a different active bundle without loading every schema.
- Resolve valid intent or explicit-tool lease requests inside switchboard and rewrite the next-step tool schema payload.
- Return structured lease telemetry showing active, added, and evicted tools.
- Preserve the current active set on invalid lease requests.
- Expose virtual tool broker telemetry in switchboard `/health`.

## Validation

- `python3 scripts/testing/test-switchboard-tool-working-set-gc.py`
- `python3 -m py_compile ai-stack/switchboard/switchboard.py scripts/testing/test-switchboard-tool-working-set-gc.py`
- `nix-instantiate --parse nix/modules/services/switchboard.nix`
- `scripts/governance/run-focused-ci-checks.sh`
