---
doc_type: reference
title: Herdr H1 Supply-Chain Report
status: active
date: 2026-08-08
---

> ACCEPTED 2026-08-15 by Claude Opus 4.8 (independent H1 acceptance owner; did not author H1). Source
> pinned + hashed, license owner-accepted, package builds, facade inert (runtime structurally rejected).
> See H1-ACCEPTANCE-20260815.md. This report is now the accepted supply-chain record for H1.

# Herdr H1 supply-chain report

## Frozen subject

- Upstream: `https://github.com/herdrdev/herdr`
- Release: `v0.7.5`
- Source revision: `ef4c23f5775bb8cfec05f05d0844226ff959a07a`
- Nix source hash: `sha256-3BA8eredGku+vsL2Af7sUf43QiArR5XTHNrI+X11vFM=`
- `LICENSE` SHA-256: `a7fa24f74382fb3e4d320a608533a7c2999dbc0f780f1f734c8b891b31f0d9bd`
- `Cargo.lock` SHA-256: `4d590b4abf9d6088704ae7ab9811c8bb766286ec75ca63364c7e23cb14be6ecf`

The package uses local `builtins.fetchTree` with the frozen NAR hash, then the
pinned source tree's own `nix/package.nix` and its source-relative vendored Zig
dependency expression. This retains the exact upstream Cargo/Zig closure
without copying generated dependency Nix into AQ-OS. It adds no upstream flake
input, `flake.lock` entry, release binary, mutable manifest, plugin,
integration, update, restore, or remote bootstrap path.

## License decision

On 2026-08-08 the owner accepted **AGPL-3.0-or-later** for the intended
internal deployment. The independent append-only owner-decision event is
`339c4e58fbfd4f268d6348e5b3e2da9b`; its canonical JSONL record hashes to
`e8086fd5d69835fbdf4232f23f5cf7302560f562fdbbba22f4a9a112dedeb5f8`.
This report binds that decision and is not legal advice. The package metadata
remains `AGPL-3.0-or-later`; it is not relabelled as permissive.

## H1 boundary

H1 config/facade installation is default-OFF. The raw `herdr` executable is
not linked into the shared user profile; only the closed `aq-herdr` facade is
exposed. It does not start a server, open a socket, create a pane, restore a
session, launch an agent, or contact a provider. Runtime remains structurally
rejected until a separately reviewed slice amends the Home Manager assertion.

## Validation status

Static/focused H1 validation binds the source, license, Cargo lock, Home
Manager defaults/assertion, canonical safe config, and non-executing facade.
An initial `nix build --offline --no-link` attempt produced no useful progress
for longer than the bounded monitoring interval and was terminated by the
orchestrator. It remains **UNPROVEN** and is not credited.

The required recovery build then ran the exact package expression with normal
Nix substitutes and no link or activation:

```text
nix build --impure --no-link --print-out-paths --expr \
  'let pkgs = import <nixpkgs> {}; in pkgs.callPackage ./nix/pkgs/herdr.nix {}'
exit 0
/nix/store/cjshi0cjx9p1m0plka95b9xpssyranzj-herdr-0.7.5
```

The output contains a root-owned mode-0555 `bin/herdr`; the bounded identity
probe returned exactly `herdr 0.7.5`. This proves the pinned package builds. It
does not install the raw binary into the user profile and did not start a
server, connect a socket, or activate a Home Manager generation.

No Herdr runtime, server, socket, pane, agent, plugin, integration, restore,
remote attach, updater, provider, deployment, or live traffic was exercised.
