# Phase 58A.2 — Routing and Profile Inventory

## Objective

Produce an authoritative inventory of all active routing aliases, canonical profiles, provider realizations, and adapter surfaces. Identify drift between docs, config, and runtime. Apply safe P1/P2 fixes inline; defer behavior-changing fixes to follow-up slices.

## Inputs

- `config/route-aliases.json`
- `config/intent-routing-map.json`
- `ai-stack/mcp-servers/hybrid-coordinator/core/routing_contract.py`
- `nix/modules/services/switchboard.nix`
- `docs/agent-guides/46-SWITCHBOARD-PROFILES.md`
- `docs/architecture/front-door-routing.md`
- `docs/architecture/canonical-kernel-declaration.md` (upstream)
- `docs/architecture/role-matrix.md` (upstream)

## Outputs

- `docs/architecture/routing-profile-inventory.md` — full inventory + 7 drift findings
- `docs/architecture/front-door-routing.md` — routing path priority rule added (D-7 fix)
- `nix/modules/services/switchboard.nix` — dashboard port stale value fixed (D-6 fix)
- `.agents/plans/phase-58a-routing-profile-inventory.md` — this slice plan

## Deferred (follow-up cleanup slice)

- D-1: add `local` → route-aliases.json allowed_profiles (or retire `local` → `default`)
- D-2: rename `Reasoning` alias (local-tool-calling) to avoid confusion with remote-reasoning
- D-3: wire or deprecate `remote-default` alias
- D-4: mark EDGE phantom profiles as aspirational in routing_contract.py
- D-5: remove `local-chat` orphan profile from routing_contract.py

## Acceptance criteria

1. `docs/architecture/routing-profile-inventory.md` exists with full four-level inventory.
2. All drift findings are named with severity and recommendation.
3. D-6 (dashboard port) and D-7 (routing path priority rule) are applied inline.
4. No instruction surface or config is changed in a behavior-affecting way during this slice.

## Validation

- `nix-instantiate --parse nix/modules/services/switchboard.nix` — PASS
- `grep "8889" nix/modules/services/switchboard.nix` — dashboard port correct
- Manual consistency check: inventory profiles match routing_contract.py PROFILE_REGISTRY

## Status

COMPLETE — 2026-05-18

### Evidence
- `docs/architecture/routing-profile-inventory.md` created: 17 profiles catalogued across 4 tiers, 7 drift findings (D-1 through D-7).
- D-6 fixed: `switchboard.nix` profile-card port updated `8006 → 8889` (×2 occurrences).
- D-7 fixed: `docs/architecture/front-door-routing.md` updated with explicit routing path priority rule.
- `nix-instantiate --parse` passed on switchboard.nix.

## Rollback

Delete `docs/architecture/routing-profile-inventory.md`, revert `front-door-routing.md` routing priority section, and revert `switchboard.nix` port values.
