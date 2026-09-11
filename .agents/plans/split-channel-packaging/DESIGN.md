# Split-channel packaging — stable base + unstable fast-lane (owner-directed 2026-09-11)

## Principle
This is an actively-developed dev system: it should track the **latest** where performance and features
matter, and stay **stable** where breakage is costly. Version PINNING is a per-instance/per-deployment
choice for a user's intended use — NOT a constraint forced on this dev system. So we run a **hybrid** of two
nixpkgs channels already present in the flake:
- **stable `nixpkgs`** (pinned) — the foundation. Stability where it matters.
- **`nixpkgs-unstable`** (fresh) — the fast-lane. Cutting edge where it counts.

We accept new issues on the fast-lane in exchange for current performance/features; the stable base keeps
the system buildable and the data layer safe.

## The two lanes (curated, explicit, auditable)
- **FAST-LANE (from nixpkgs-unstable):** performance/fast-moving — llama.cpp, AI model runtimes, AI/agent
  tools, IDEs (antigravity -> renamed `antigravity-ide`), developer tools, apps. First member: antigravity 2.5.5.
- **STABLE-LANE (stay pinned on stable `nixpkgs`):** foundation/stability — python, rust/cargo, databases
  (postgresql, redis, qdrant), sops/age, and core system libs. Never silently moved to unstable.

Anything not explicitly in the fast-lane list stays on stable. Fast-lane membership is a declarative,
one-line-to-edit list (mirrors the `basePackageNames` pattern in nix/modules/core/base.nix).

## Mechanism
- The flake already has inputs `nixpkgs` (stable) + `nixpkgs-unstable`. Add an **overlay** that, for each
  fast-lane package name, substitutes the unstable package into the stable `pkgs` set used by mkHost. So
  `pkgs.<fast-lane-pkg>` resolves from unstable; everything else stays stable. Overlay lives in its own
  module (e.g. `nix/overlays/fast-lane.nix`) with the curated name list, wired once in the flake's pkgs
  construction. Explicit + auditable (no blanket "use unstable for everything").
- Handle upstream RENAMES (antigravity -> antigravity-ide): the overlay maps the stable-era attr name used
  in base.nix to the unstable attr, so consumers keep referring to a stable name.
- Supply-chain: new/unstable inputs pass the `flake-review` discipline; the overlay set is reviewed like any
  dependency change.

## Auto-checker (notify, never auto-apply)
A declarative systemd timer + a checker that, for each fast-lane package, compares the INSTALLED version
against what the current `nixpkgs-unstable` offers, and surfaces "N packages behind" on the dashboard /
health surface + a notification. It does NOT run `nix flake update` or rebuild automatically (blind
auto-update is exactly what pinning protects against). The owner decides when to bump. Also flags when the
`nixpkgs-unstable` input pin itself is stale (lastModified age). Ties into the existing observability.

## Slices
- **sc-1 — fast-lane overlay + antigravity 2.5.5:** the overlay module + curated fast-lane list + wire into
  the flake; move `antigravity` -> `antigravity-ide` (2.5.5) from unstable as the first member; base.nix
  package name reconciled. Builds; owner rebuilds to activate. (First concrete deliverable — the owner's
  "update antigravity" request, done the right way.)
- **sc-2 — staleness auto-checker:** the version-compare checker + declarative timer + dashboard/notify
  surface (notify-not-apply).

## Constraints
NixOS declarative-only; stable-lane packages never moved to unstable; fast-lane list explicit + reviewed;
ports/paths from env; the checker spends no quota + no auto-apply; owner runs the activating rebuild
(no sudo in the orchestrator shell).
