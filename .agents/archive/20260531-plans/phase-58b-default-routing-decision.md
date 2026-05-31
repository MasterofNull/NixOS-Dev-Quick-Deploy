# Phase 58B Default Routing Decision

**Date:** 2026-05-19  
**Owner:** Codex  
**Decision:** Keep one narrow default (`systems-software`); do not bulk-default the other Phase 58B domains.

## Context

All six Phase 58A/58B capability domains reached `promoted` after PRD acceptance, AIDB namespace seeding, representative workflow evidence, Gemini review-gate PASS, and candidate/post-rebuild soak evidence.

A later L7 routing fix (`041dbaf6`) intentionally advanced `systems-software` to `default` because the repo's primary ongoing workload is NixOS/Nix/shell/Python systems work and the domain uses local-tool-calling without remote dependency.

## Current decision

| Domain | Lifecycle state | Default posture |
|---|---:|---|
| security-systems | promoted | Opt-in / explicit security intent routing only |
| systems-software | default | Default for primary repo systems work |
| embedded-hardware | promoted | Opt-in / explicit embedded intent routing only |
| mobile-web | promoted | Opt-in / explicit mobile-web intent routing only; real Lighthouse remains enhancement |
| scientific-research | promoted | Opt-in / explicit scientific intent routing only |
| gis-systems | promoted | Opt-in / explicit GIS intent routing only |

## Rationale

The `default` lifecycle state means new work can automatically use that capability. Systems-software is the only Phase 58B domain that maps directly to the repo's normal daily workload and strongest live-use path. The other five domains are broad specialized capability areas; bulk-defaulting them would create routing ambiguity and over-route general work into domain-specific lanes.

Future defaulting should happen only after a per-domain routing/default slice answers:

1. Which existing route/profile/kernel object is being replaced?
2. What traffic should automatically enter the domain?
3. What rollback restores previous routing?
4. What live-use evidence exists beyond fixture/soak validation?

## Next recommended slices

1. Fix collaboration status access (`aq-collaborate list` Postgres auth) and stale delegation registry entries.
2. Mobile-web hardening: provide real Lighthouse CLI path or document fixture mode as permanent validation-only behavior.
3. Routing audit: verify the intent classifier maps only explicit domain intents into the five promoted-but-not-default domains.
4. Per-domain default evaluation only when real workload evidence supports it.
