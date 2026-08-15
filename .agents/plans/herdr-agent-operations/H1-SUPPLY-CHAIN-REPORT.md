---
doc_type: reference
title: Herdr H1 Supply-Chain Report
status: draft
date: 2026-08-15
---

> CORRECTION PENDING — `ea96bcbfc05fca32d164137fd2cef261f5c68acc` is the physical H1 implementation
> commit, not accepted H1. Its claimed acceptance was recorded before the required independent binding
> review and is superseded by the additive correction process in
> `.agent/PROJECT-HERDR-H1-CORRECTION-PRD.md`. Acceptance is only the atomic correction commit containing
> this exact evidence plus the final hash-bound `PASS` receipt at
> `.agents/plans/herdr-agent-operations/H1-CORRECTION-INDEPENDENT-REVIEW-20260815.md`; no `PASS`,
> accepted-H1 hash, or runtime authority is claimed before that condition.

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
The real opt-in Home Manager evaluation proof is supplied by
`python3 scripts/testing/test-herdr-h1-contract.py --nix-eval`; it exited `0` and printed
`herdr-h1-contract: PASS`. This real Home Manager/Nix evaluation proves both options default `false`,
`runtimeEnable = true` is rejected, and enabled configuration exposes exactly the `aq-herdr` facade (not raw
Herdr) plus the frozen config, without activation.

### Correction evidence ledger

| evidence | status | binding data |
|---|---|---|
| Physical implementation | recorded, conditionally accept-ready | commit `ea96bcbfc05fca32d164137fd2cef261f5c68acc`; acceptance is only the atomic correction commit containing this exact evidence and the final hash-bound `PASS` receipt at the authorized review path; no PASS is claimed before that condition |
| Real HM/Nix evaluation | terminal evidence | command `python3 scripts/testing/test-herdr-h1-contract.py --nix-eval`; exit `0`; output `herdr-h1-contract: PASS`; defaults false, runtime rejection, enabled facade/no raw Herdr, exact config |
| No-link package build | terminal evidence | command/output receipt below; exit `0`; target `/nix/store/cjshi0cjx9p1m0plka95b9xpssyranzj-herdr-0.7.5`; bounded version `herdr 0.7.5` |
| SPDX SBOM | terminal deterministic evidence | `.agents/plans/herdr-agent-operations/evidence/H1-SBOM.spdx.json`; SHA-256 `cfa9a5904c50fdc01ed839bd5f3f827dc6c57ec36e4191e61879900938da715c`; SPDX `2.3`; Syft `1.44.0`; pinned source target below |
| Independent correction review | conditionally required | the final hash-bound `PASS` receipt must be recorded at `.agents/plans/herdr-agent-operations/H1-CORRECTION-INDEPENDENT-REVIEW-20260815.md`; exact reviewed-subject hash and reviewer identity bind that receipt; no PASS is claimed before it exists |

An initial `nix build --offline --no-link` attempt produced no useful progress
for longer than the bounded monitoring interval and was terminated by the
orchestrator. It remains **UNPROVEN** and is not credited.

The correction's fresh no-link build ran the exact package expression with normal Nix substitutes and no link
or activation:

```text
nix build --impure --no-link --print-out-paths --expr \
  'let pkgs = import <nixpkgs> {}; in pkgs.callPackage ./nix/pkgs/herdr.nix {}'
exit 0
/nix/store/cjshi0cjx9p1m0plka95b9xpssyranzj-herdr-0.7.5
```

The output contains a root-owned mode-0555 `bin/herdr`; the bounded identity
probe returned exactly `herdr 0.7.5`. It
does not install the raw binary into the user profile and did not start a
server, connect a socket, or activate a Home Manager generation.

## SPDX SBOM receipt

The mechanically generated SPDX `2.3` document is
`.agents/plans/herdr-agent-operations/evidence/H1-SBOM.spdx.json`, SHA-256
`cfa9a5904c50fdc01ed839bd5f3f827dc6c57ec36e4191e61879900938da715c`.
Syft `1.44.0` scanned the pinned source target
`/nix/store/wh5a5fzsd5a1x6wpjln25j54s17as2df-source` and emitted normalized package name/namespace
metadata, `347` packages, and `1220` relationships. This SBOM binds the pinned Cargo/vendor source inventory;
the Nix output build above is separate build-identity evidence and is not substituted for the source inventory.

Syft scanned that same pinned source twice and the exact reproducible normalization pipeline specified in
`.agents/plans/herdr-agent-operations/H1-CORRECTION-DESIGN-20260815.md` produced byte-identical SPDX JSON
(`cmp` PASS). The pipeline fixes the created timestamp, document root identity, and namespace, then sorts all
arrays before hashing; the deterministic digest above supersedes the earlier nondeterministic receipt.

No Herdr runtime, server, socket, pane, agent, plugin, integration, restore,
remote attach, updater, provider, deployment, or live traffic was exercised.
