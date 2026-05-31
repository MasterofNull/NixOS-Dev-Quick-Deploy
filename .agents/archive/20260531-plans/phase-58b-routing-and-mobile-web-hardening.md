# Phase 58B.9 — Routing and Mobile-Web Hardening

**Date:** 2026-05-19  
**Owner:** Codex

## Routing audit result

Added `scripts/testing/phase58b-routing-audit.py` to lock expected routing behavior for the six Phase 58B domains and two negative cases.

Result: **PASS**

Confirmed routing posture:

| Domain | Intent | Profile | Lifecycle posture |
|---|---|---|---|
| security-systems | `security_analysis` | `remote-reasoning` | promoted / opt-in |
| systems-software | `systems_software` | `local-tool-calling` | default |
| embedded-hardware | `embedded_hardware` | `remote-reasoning` | promoted / opt-in |
| mobile-web | `mobile_web` | `remote-reasoning` | promoted / opt-in |
| scientific-research | `scientific_research` | `remote-reasoning` | promoted / opt-in |
| gis-systems | `gis_systems` | `local-tool-calling` | promoted / opt-in |

## Routing fixes made

1. `security review ... OWASP ...` previously tied with generic `code_review`; fixed by moving explicit security review/OWASP weighting into `security_analysis`.
2. Generic `implementation` text previously matched `implement` via substring and could misroute planning prompts to `code_generation`; fixed by narrowing the signal to `implement `.
3. Generic software “regression” previously risked matching `scientific_research`; narrowed scientific signals to `linear regression` / `statistical regression`.

## Mobile-web Lighthouse decision

Decision: **fixture mode remains valid for promoted-state validation plumbing, but real Lighthouse is required before any future default transition.**

Rationale:

- `nodePackages.lighthouse` is not available in the current nixpkgs 25.11 posture used by this repo.
- Adding a non-declarative global npm install would violate the repo’s Nix-first toolchain standard.
- The MASA harness already supports real Lighthouse when `lighthouse` and `--url` are supplied.
- The deterministic fixture path is still useful for local/no-network validation of report shape, MASVS scanning, and failure gating.

Follow-up if defaulting mobile-web becomes important: create a declarative Lighthouse package path, likely via a pinned npm package derivation or a repo-local wrapper around a checked-in/generated npm lock. Do not rely on ad-hoc `npm install -g lighthouse` for default routing evidence.
