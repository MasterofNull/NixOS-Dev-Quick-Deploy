---
doc_type: design-review
id: herdr-h1-acceptance-20260815
title: Herdr H1 — independent acceptance
status: complete
parent_prd: herdr-agent-operations
reviewer: "Claude Opus 4.8 (independent H1 acceptance owner; did not author H1)"
verdict: "ACCEPT"
date: 2026-08-15
---

# Herdr H1 — independent acceptance

Owner-directed 2026-08-15. Independent acceptance of the Herdr H1 package/facade slice (I did not author
it, satisfying "neither agent accepts its own implementation"). **H1 is inspection-only and inert — this
acceptance authorizes NO Herdr runtime, server, socket, pane, session, agent, plugin, or remote.**

## Accepted deliverables
- `nix/pkgs/herdr.nix` — pinned package: `builtins.fetchTree` rev `ef4c23f5775bb8cfec05f05d0844226ff959a07a`,
  narHash `sha256-3BA8eredGku+vsL2Af7sUf43QiArR5XTHNrI+X11vFM=`, LICENSE + Cargo.lock hashed; builds
  upstream `nix/package.nix`.
- `nix/home/herdr.nix` — Home-Manager facade; `assertion = !cfg.runtimeEnable` structurally rejects
  runtime (a build failure, not a policy note). Raw `herdr` NOT linked into the profile.
- `scripts/ai/aq-herdr` — closed facade; "Never invokes Herdr or contacts its socket"; `attach` returns
  `not-activated`.
- `scripts/testing/test-herdr-h1-contract.py` — contract test (PASS).
- `flake.nix` — adds `./nix/home/herdr.nix` to the HM layering (single-line diff, no other change).
- `.agents/plans/herdr-agent-operations/H1-SUPPLY-CHAIN-REPORT.md` (now `active`) + `docs/operations/
  herdr-agent-operations.md`.

## Verification (verify-before-accept)
- **Supply-chain integrity:** source pinned to an exact rev + NAR hash; LICENSE + Cargo.lock SHA-256
  recorded; NO upstream flake input / flake.lock entry / release binary / mutable manifest / plugin /
  updater / remote bootstrap. Freshness-checked: `nix/pkgs/herdr.nix` pins match the report exactly.
- **License:** AGPL-3.0-or-later, owner-accepted via append-only event `339c4e58fbfd4f268d6348e5b3e2da9b`
  (cited by the report; not relabelled permissive).
- **Inertness:** structural (`!runtimeEnable` assertion) + facade-only exposure; report attests no runtime
  was exercised.
- **Builds:** report records `nix build … exit 0 → herdr-0.7.5`, identity probe `herdr 0.7.5`.
- **Test:** `test-herdr-h1-contract.py` PASS. tier0 green at commit time.

## Verdict: ACCEPT
H1 is accepted at THIS commit. The commit hash is the frozen H1 prerequisite for H2A (resolves H2A's
`H1-accepted-hash: TBD`). Any change to the accepted files requires re-review.

## Not authorized here
Herdr runtime (H3 territory), the H2 operator-context/presentation projections and their implementation,
and any activation beyond installing the inert inspection facade.
