# Factory shared toolchain — live, unlimited, governed-to-grow

status: proposed · owner: hyperd · authorized 2026-09-19

## Problem
Deployed projects (e.g. the native-plant project) lack the dev tools the agentic
team depends on (playwright, browser-testing, language toolchains). We must NOT
vendor a heavy package payload into every project, and we must NOT gate or restart
a running agent to let it reach a tool. Tools are a SHARED capability of the
versioned factory engine ("connect to the shared engine for ... tools"), reached by
reference, never copied per project.

## Principle (owner-corrected 2026-09-19)
1. A running agent reaches ANY tool LIVE, mid-session, with NO restart and NO
   manifest permission-check. The manifest never limits a running agent.
2. Nix store dedup means "available fleet-wide" costs ~0 extra disk — a shared
   store path referenced by N projects is one path, not N copies. The lean concern
   is about not copying host-specific state, not about tool availability.
3. Adding a NEW package to the SHARED toolchain (durable, pinned, fleet-wide) is a
   shared-blast-radius change and is governed; using an already-available tool
   on-demand is not governed at all.

## Two speeds
### Live / on-demand (immediate, ungoverned, ephemeral)
- A thin `aq-tool <pkg> [args...]` wrapper resolves a tool from the shared Nix
  store / the pinned nixpkgs the factory tracks and runs it in the CURRENT session
  (`nix run`/`nix shell` under the hood) — no restart, no PATH mutation required,
  no manifest gate. Any running agent, any tool, any time.
- The baseline agentic toolchain (the tools every agent needs regardless of domain:
  browser-testing/playwright, the aq-* CLIs, search/edit/context tools) is on every
  agent shell's PATH by default via a shared Nix profile — so the common case needs
  no wrapper at all.
- A pivoting/evolving project needs zero re-provisioning: its agent just uses more
  tools; access was never limited.

### Durable / pinned / fleet-wide (governed contribute-back)
- To make a new tool a PERMANENT, version-pinned, reproducible part of the shared
  toolchain that every project inherits, a project agent opens a
  toolchain-contribution against the one SSOT shared toolchain flake/overlay.
- It is vetted at the shared-change (FT-6 higher) tier via `capability-intake`
  (security-gated external-package intake) + `flake-review` (supply-chain review),
  then pinned. All projects gain it by reference on next resolve; reproducible; no
  drift. A project may pin an older toolchain rev for stability while others advance.

## The capability manifest is a RECORD, not a gate
- It DECLARES what a project relies on (durable tool set) for reproducibility,
  pinning, and readiness reporting — a running agent can append to it live.
- Readiness preflight (FT-5) WARNs (typed) if a declared tool is absent from the
  shared toolchain; it NEVER restricts what a running agent can reach on-demand.

## Components / slices
- ST-1: shared toolchain flake/overlay (baseline + opt-in profiles), one SSOT;
  baseline profile on agent-shell PATH via a shared Nix profile.
  **Implemented 2026-09-19** (branch `delegate/shared-toolchain`,
  DEFAULT-OFF, not yet activated): SSOT +
  module = `nix/modules/roles/agentic-toolchain.nix`
  (`mySystem.roles.agenticToolchain.{enable,profiles}`), imported by
  `nix/modules/roles/default.nix`, surfaced (available-but-disabled) from
  `nix/modules/profiles/ai-dev.nix`. Baseline = Playwright driver +
  pre-fetched browsers (the owner-reported native-plant gap); one opt-in
  profile (`rust`: clippy/rustfmt/rust-analyzer) proves the opt-in
  mechanism. **Activation is a separate owner act**: set
  `mySystem.roles.agenticToolchain.enable = true` (host override or
  `deploy-options.local.nix`) and run `nixos-rebuild switch` — nothing
  changes until then. ST-3/ST-4 (this doc's remaining slices) remain
  unimplemented; ST-2 is independently implemented at `4017e5d9`.
- ST-2: `aq-tool` live on-demand runtime reach (nix run/shell wrapper), no restart,
  no gate; implemented independently in `4017e5d9`. It remains outside ST-1's
  default-off Nix module and does not activate this baseline.
- ST-3: capability manifest as declaration/record (append-live), + readiness WARN
  on declared-but-missing; manifest never gates runtime access.
- ST-4: governed contribute-back flow — toolchain-contribution -> capability-intake
  + flake-review at FT-6 tier -> pin to the shared flake -> fleet-wide by reference.

## Constraints
- NixOS-first, flake-based; reference-share via the Nix store, never vendor-copy.
- Live access must not require a rebuild/restart (nix run/shell from the store).
- Durable additions are reproducible + pinned + supply-chain-vetted (governed).
- No host-specific credentials/ports/hardware/mutable-state copied (declare-unavailable).
- Rule 16 parity: the tool-access discipline written into all agent instruction files.
